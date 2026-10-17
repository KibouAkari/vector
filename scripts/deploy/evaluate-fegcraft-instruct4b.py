#!/usr/bin/env python3
"""Add one checksum-pinned unused local candidate and test the full adapter."""
from contextlib import contextmanager,redirect_stdout
from datetime import datetime,timezone
import ast,fcntl,hashlib,importlib.util,json,os,re,secrets,select,shutil,subprocess,tempfile,urllib.request
from pathlib import Path

ROOT=Path('/root/vector-workspace')
REPO=ROOT/'github/vector'
IMPORTS=ROOT/'local-inference'
SERVICE='vector-local-inference'
RUNTIME='sha256:06d4cf34b8d726cc901d3cc663e36ac568b0012acf68ff2d6273fcf793e399d1'
BASELINE='vector-qwen3:1.7b-q8'
BASE_DIGEST='97f1ed78571eac64f6b5b7413d9bc5f50fc95ab13ad4403cd813aebb9ba3a5b0'
CANDIDATE=dict(name='vector-qwen3-instruct2507:4b-q4km',
 repo='unsloth/Qwen3-4B-Instruct-2507-GGUF',revision='a06e946bb6b655725eafa393f4a9745d460374c9',
 file='Qwen3-4B-Instruct-2507-Q4_K_M.gguf',size=2497281120,
 sha256='3605803b982cb64aead44f6c1b2ae36e3acdb41d8e46c8a94c6533bc4c67e597')
MARKER=IMPORTS/'vector-qwen3-instruct2507-4b-q4km.import.json'
MODELFILE=IMPORTS/'vector-qwen3-instruct2507-4b-q4km.Modelfile'
MODEL_TEXT='FROM /imports/'+CANDIDATE['file']+'\nPARAMETER num_ctx 2048\nPARAMETER num_thread 2\nPARAMETER num_predict 96\nPARAMETER temperature 0.7\nPARAMETER top_p 0.8\nPARAMETER top_k 20\nPARAMETER min_p 0\n'

# Creation imports metadata/weights but never loads/generates. Still share the
# real local CPU admission slot; no DSN or credentials leave the existing app.
IMPORT_SLOT=r'''
import pg from 'pg';import readline from 'node:readline';
const db=new pg.Client({connectionString:process.env.DATABASE_URL,connectionTimeoutMillis:5000});
let locked=false;
const ps=async()=>{const r=await fetch('http://vector-local-inference:11434/api/ps',{redirect:'error',signal:AbortSignal.timeout(10000)});if(!r.ok)throw Error('native');const v=await r.json();if(!Array.isArray(v.models)||v.models.length)throw Error('weights-busy');};
const input=readline.createInterface({input:process.stdin});
const released=new Promise(resolve=>{input.once('line',resolve);input.once('close',resolve);});
try{
 await db.connect();await db.query('BEGIN READ ONLY');await db.query("SET LOCAL statement_timeout = '5s'");
 if((await db.query("SELECT COUNT(*)::int AS n FROM agent_jobs WHERE status IN ('queued','running')")).rows[0].n!==0)throw Error('busy');
 locked=(await db.query('SELECT pg_try_advisory_lock($1::bigint) AS locked',['6194261933202610'])).rows[0].locked;
 if(!locked)throw Error('busy');await ps();console.log(JSON.stringify({ready:true}));
 await Promise.race([released,new Promise((_,reject)=>{const t=setTimeout(()=>reject(Error('deadline')),600000);t.unref();})]);
}catch{console.error('CANDIDATE_IMPORT_ADMISSION_FAILED');process.exitCode=1;}
finally{
 try{if(locked)await ps();}catch{process.exitCode=1;}
 finally{if(locked)await db.query('SELECT pg_advisory_unlock($1::bigint)',['6194261933202610']).catch(()=>{process.exitCode=1;});await db.end();input.close();}
}
'''


def command(*args,timeout=30):
    value=subprocess.run(args,capture_output=True,timeout=timeout)
    if value.returncode:raise RuntimeError('Candidate command failed: '+args[0]+'. Existing files/models retained.')
    return value.stdout


def exclusive(path,content):
    if path.is_symlink():raise RuntimeError('Unexpected candidate symlink; no overwrite.')
    if path.exists():
        if not path.is_file() or path.read_bytes()!=content:raise RuntimeError('Different candidate evidence exists; no overwrite.')
        return
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'wb') as out:out.write(content)


def verified(path,runner=command):
    if path.is_symlink() or not path.is_file():return False
    meta=path.stat()
    if meta.st_size!=CANDIDATE['size'] or meta.st_uid!=os.geteuid() or meta.st_mode&0o022:return False
    value=runner('timeout','--signal=TERM','--kill-after=5s','90s','sha256sum',str(path),timeout=110)
    return value.decode().split()[0]==CANDIDATE['sha256']


def artifact(directory):
    target=IMPORTS/CANDIDATE['file']
    if target.exists() or target.is_symlink():
        if not verified(target):raise RuntimeError('Existing candidate weight file is unverified; preserve and inspect it.')
        return target
    fd,name=tempfile.mkstemp(prefix='.qwen3-instruct2507-',suffix='.partial',dir=IMPORTS);os.close(fd)
    partial=Path(name)
    url='https://huggingface.co/'+CANDIDATE['repo']+'/resolve/'+CANDIDATE['revision']+'/'+CANDIDATE['file']
    print('Lade einmalig 2.50 GB Kandidatengewichte. Minecraft bleibt online.',flush=True)
    (directory/'download.json').write_text(json.dumps(dict(artifact=CANDIDATE,partial=str(partial)))+'\n')
    # Only GGUF bytes, no executable model repository code or shell installer.
    subprocess.run(['curl','--disable','--fail','--show-error','--location','--progress-bar','--noproxy','*',
        '--proto','=https','--proto-redir','=https','--connect-timeout','20','--max-time','900',
        '--max-filesize',str(CANDIDATE['size']),'--speed-time','60','--speed-limit','16384',
        '--output',str(partial),url],check=True,timeout=920)
    if not verified(partial):raise RuntimeError('Candidate download size/checksum mismatch; partial file retained.')
    # Hard link is atomic and refuses a newly appearing destination; never replace.
    os.link(partial,target);partial.unlink()
    return target


@contextmanager
def import_slot(directory):
    process=subprocess.Popen(['docker','exec','-i','vector-app','node','--input-type=module','-e',IMPORT_SLOT],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    try:
        if not select.select([process.stdout],[],[],45)[0] or json.loads(process.stdout.readline() or b'{}')!={'ready':True}:
            raise RuntimeError('Local import slot busy/unavailable; no import.')
        yield
    finally:
        _,stderr=process.communicate(input=b'release\n',timeout=30)
        (directory/'import-coordinator-stderr.log').write_bytes(stderr[-8192:])
        if process.returncode:raise RuntimeError('Candidate import slot release/idle state unverified.')


def manifest(api):
    rows=api('/api/tags').get('models')
    if not isinstance(rows,list) or len(rows)>200:raise RuntimeError('Invalid local model manifest.')
    result={}
    for row in rows:
        name=row.get('name');digest=row.get('digest')
        if not isinstance(name,str) or len(name)>160 or name in result or not isinstance(digest,str) or not re.fullmatch('[a-f0-9]{64}',digest):raise RuntimeError('Invalid model identity.')
        result[name]=digest
    if result.get(BASELINE)!=BASE_DIGEST:raise RuntimeError('Previously audited baseline registration changed.')
    return result


def register(api,before,directory,runner=command):
    candidate=CANDIDATE['name']
    if candidate in before:
        if MARKER.is_symlink() or not MARKER.is_file() or MARKER.stat().st_size>16384:raise RuntimeError('Candidate exists without verified import marker; no replacement.')
        saved=json.loads(MARKER.read_bytes())
        if saved.get('artifact')!=CANDIDATE or saved.get('model_digest')!=before[candidate]:raise RuntimeError('Candidate import marker differs; no replacement.')
    else:
        if MARKER.exists() or MARKER.is_symlink():raise RuntimeError('Orphan candidate marker; no replacement.')
        exclusive(MODELFILE,MODEL_TEXT.encode())
        print('Importiere den geprüften Kandidaten unter eigenem Namen, ohne Inferenz.',flush=True)
        runner('docker','exec',SERVICE,'ollama','create',candidate,'-f','/imports/'+MODELFILE.name,timeout=180)
    after=manifest(api)
    if {k:v for k,v in after.items() if k!=candidate}!={k:v for k,v in before.items() if k!=candidate} or candidate not in after:
        raise RuntimeError('Unexpected model registry change; retain all models and inspect.')
    show=api('/api/show',{'model':candidate});info=show.get('model_info',{})
    blob='/root/.ollama/models/blobs/sha256-'+CANDIDATE['sha256']
    if (not isinstance(info,dict) or info.get('general.architecture')!='qwen3'
        or info.get('qwen3.block_count')!=36 or show.get('system','')!=''
        or not isinstance(show.get('template'),str) or not show['template']
        or not isinstance(show.get('modelfile'),str)
        or not re.search(r'^FROM '+re.escape(blob)+r'\s*$',show['modelfile'],re.M)):
        raise RuntimeError('Imported candidate metadata does not match the reviewed artifact.')
    # Verify the actual runtime blob too; don't trust registry metadata alone.
    runner('docker','exec',SERVICE,'test','!','-L',blob)
    runner('docker','exec',SERVICE,'test','-f',blob)
    if int(runner('docker','exec',SERVICE,'stat','-c','%s',blob).strip())!=CANDIDATE['size']:raise RuntimeError('Runtime candidate blob size differs.')
    if runner('docker','exec',SERVICE,'timeout','--signal=TERM','--kill-after=5s','90s','sha256sum',blob,timeout=110).decode().split()[0]!=CANDIDATE['sha256']:
        raise RuntimeError('Runtime candidate checksum differs; no inference.')
    marker=dict(artifact=CANDIDATE,model_digest=after[candidate])
    exclusive(MARKER,(json.dumps(marker,sort_keys=True)+'\n').encode())
    return dict(model_digest=after[candidate],template_sha256=hashlib.sha256(show['template'].encode()).hexdigest(),existing_models_unchanged=True,registered=True)


def candidate_sources(base,digest):
    if not re.fullmatch('[a-f0-9]{64}',digest):raise RuntimeError('Invalid candidate digest.')
    old="const model='"+BASELINE+"';"
    if base.COORDINATOR.count(old)!=1 or base.COORDINATOR.count(BASE_DIGEST)!=1:raise RuntimeError('Coordinator changed; no weakened admission.')
    coordinator=base.COORDINATOR.replace(old,'const model='+json.dumps(CANDIDATE['name'])+';').replace(BASE_DIGEST,digest)
    old_init="ObservedKnowledge('outer-shared-lock',usage="
    if base.HARNESS.count(old_init)!=1 or base.HARNESS.count("'model':'"+BASELINE+"'")!=1:raise RuntimeError('Full adapter harness changed.')
    harness=base.HARNESS.replace(old_init,"ObservedKnowledge('outer-shared-lock',model="+repr(CANDIDATE['name'])+",usage=")
    harness=harness.replace("'model':'"+BASELINE+"'","'model':"+repr(CANDIDATE['name']))
    return coordinator,harness


def main():
    os.umask(0o077);revision=os.environ.get('VECTOR_FEGCRAFT_REV','')
    if os.geteuid()!=0 or not re.fullmatch('[a-f0-9]{40}',revision):raise RuntimeError('Root and exact VECTOR_FEGCRAFT_REV required.')
    command('git','-C',str(REPO),'merge-base','--is-ancestor',revision,'origin/main')
    with (ROOT/'.chat-release.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        directory=ROOT/'releases'/('vector-fegcraft-instruct4b-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+secrets.token_hex(3));directory.mkdir(mode=0o700)
        print('Kandidatenbelege:',directory,flush=True)
        support=directory/'evaluation-support.py'
        content=command('git','-C',str(REPO),'show',revision+':scripts/deploy/evaluate-fegcraft-general-help.py',timeout=15)
        ast.parse(content);support.write_bytes(content)
        spec=importlib.util.spec_from_file_location('instruct4b_support',support);base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base)
        before=base.fingerprint()
        if before['/vector-app']['image'] not in base.APP_IMAGES:raise RuntimeError('Observed app image changed; no candidate import.')
        service=json.loads(command('docker','inspect',SERVICE))[0]
        if (service['Image']!=RUNTIME or not service['State']['Running'] or service['HostConfig']['PortBindings']
            or list(service['NetworkSettings']['Networks'])!=[SERVICE] or service['HostConfig']['NanoCpus']!=2000000000
            or service['HostConfig']['Memory']!=12*1024**3 or service['HostConfig']['MemorySwap']!=12*1024**3
            or service['HostConfig']['ReadonlyRootfs'] is not True
            or 'OLLAMA_NO_CLOUD=1' not in service['Config']['Env']):raise RuntimeError('Private native runtime differs; no download/import.')
        mounts=service['Mounts']
        if IMPORTS.is_symlink() or not IMPORTS.is_dir() or not any(m.get('Destination')=='/imports' and m.get('Source')==str(IMPORTS) and m.get('RW') is False for m in mounts):raise RuntimeError('Reviewed private import mount unavailable.')
        if IMPORTS.stat().st_uid!=os.geteuid() or IMPORTS.stat().st_mode&0o022:raise RuntimeError('Private import directory ownership/permissions changed.')
        volumes=[m for m in mounts if m.get('Destination')=='/root/.ollama' and m.get('Type')=='volume' and m.get('RW') is True]
        if len(volumes)!=1:raise RuntimeError('Unexpected native model store.')
        if not json.loads(command('docker','network','inspect',SERVICE))[0]['Internal']:raise RuntimeError('Native network is not internal.')
        for path in (IMPORTS,Path(volumes[0]['Source'])):
            if shutil.disk_usage(path).free<10*1024**3:raise RuntimeError('Keep at least 10 GiB free disk headroom before candidate import.')
        memory=dict(line.split(':',1) for line in Path('/proc/meminfo').read_text().splitlines())
        if int(memory['MemAvailable'].strip().split()[0])<8*1024**2:raise RuntimeError('At least 8 GiB currently available RAM required.')
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self,*args):return None
        http=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
        endpoint='http://'+service['NetworkSettings']['Networks'][SERVICE]['IPAddress']+':11434'
        def api(path,payload=None):
            req=urllib.request.Request(endpoint+path,json.dumps(payload).encode() if payload is not None else None,{'Content-Type':'application/json'})
            with http.open(req,timeout=15) as response:raw=response.read(1048577)
            if len(raw)>1048576:raise RuntimeError('Native metadata response limit.')
            value=json.loads(raw)
            if not isinstance(value,dict):raise RuntimeError('Invalid native metadata.')
            return value
        if api('/api/version').get('version')!='0.40.4':raise RuntimeError('Reviewed runtime version changed.')
        original_models=manifest(api)
        artifact(directory)
        with import_slot(directory):registration=register(api,original_models,directory)
        (directory/'registration.json').write_text(json.dumps(registration,indent=2)+'\n')
        coordinator,harness=candidate_sources(base,registration['model_digest'])
        base.COORDINATOR=coordinator;base.HARNESS=harness
        os.environ['VECTOR_FEGCRAFT_GENERAL_DIAGNOSTIC']='0'
        print('Prüfe die vollständige lokale Antwortkette inklusive Schutz, Kontext, Fakten und Laufzeiten. Keine Spielnachricht.',flush=True)
        with (directory/'qualification.log').open('x') as log,redirect_stdout(log):result=base.evaluate(report_only=True)
        expected_models={**original_models,CANDIDATE['name']:registration['model_digest']}
        existing_models_unchanged=manifest(api)==expected_models
        result.update(candidate_artifact=CANDIDATE,registration=registration,
            production_unchanged=bool(result['production_unchanged'] and base.fingerprint()==before),
            existing_models_unchanged=existing_models_unchanged,evaluation_completed=True,
            candidate_registered_only=True,production_activated=False,eligible_for_activation=False)
        result['passed']=bool(result['quality_passed'] and existing_models_unchanged and result['production_unchanged'] and result['cleanup_verified'] and result['weights_unloaded'])
        (directory/'result.json').write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(result,indent=2));print('Report:',directory/'result.json')
        if not result['passed']:raise RuntimeError('Candidate quality gate failed. Candidate retained unloaded; general help remains OFF. No existing model was replaced.')
        print('Begrenzte Kandidatenprüfung bestanden. Antworten manuell prüfen; keine Aktivierung und keine Garantie für alle Mods. Rollen-, Treiber- und Dienstqualifikation bleiben erforderlich.')


if __name__=='__main__':
    try:main()
    except Exception as exc:
        print('ERROR:',str(exc) if isinstance(exc,RuntimeError) else type(exc).__name__)
        raise SystemExit(1)
