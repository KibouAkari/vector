#!/usr/bin/env python3
"""Read registered model metadata and hash only two known GGUF blobs; no inference."""
from datetime import datetime,timezone
import fcntl,hashlib,json,os
from pathlib import Path
import re,secrets,subprocess
ROOT=Path('/root/vector-workspace')
SERVICE='vector-local-inference'
MODELS={
 'vector-qwen3:1.7b-q8':dict(digest='97f1ed78571eac64f6b5b7413d9bc5f50fc95ab13ad4403cd813aebb9ba3a5b0',
  blob='061b54daade076b5d3362dac252678d17da8c68f07560be70818cace6590cb1a',size=1834426016,
  template='57f1fd00f0013a2be96aa79b857391f27e23df5b5f847072b524c897e24d0361'),
 'vector-hermes3:8b-q4km':dict(digest='ddd98889feddbec419ccb27c2839214c100ce4ebae74f16b12fe17f5c6572a20',
  blob='d4403ce5a6e930f4c2509456388c20d633a15ff08dd52ef3b142ff1810ec3553',size=4920733824,
  template='e3b2721cec511e3a627ae0993753abbf5c72cdf4cfcdbc8f5c33ce15c4c4e04b')}
NAMES=('vector-app','vector-worker','vector-runner','vector-postgres','vector-redis','vector-privacy-ner',SERVICE,'fegcraft-updated','vector-fegcraft-assistant')
METADATA_JS=r'''
import crypto from 'node:crypto';
const allowed=__MODELS__;
const hash=s=>crypto.createHash('sha256').update(s).digest('hex');
async function api(path,body){
 const r=await fetch('http://vector-local-inference:11434'+path,{method:body?'POST':'GET',redirect:'error',signal:AbortSignal.timeout(8000),
  ...(body?{headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}:{})});
 if(!r.ok)throw Error('native-http');
 const reader=r.body.getReader(),chunks=[];let size=0;
 try{while(true){const {done,value}=await reader.read();if(done)break;size+=value.length;if(size>262144)throw Error('native-response-limit');chunks.push(Buffer.from(value));}}
 finally{await reader.cancel().catch(()=>{});}
 return JSON.parse(Buffer.concat(chunks).toString('utf8'));
}
const version=await api('/api/version'),tags=await api('/api/tags');
if(typeof version.version!=='string'||!/^\d+(?:\.\d+){1,3}(?:[-+][a-zA-Z0-9.-]+)?$/.test(version.version)||!Array.isArray(tags.models)||tags.models.length>200)throw Error('native-shape');
const results=[];
for(const [name,expected] of Object.entries(allowed)){
 const rows=tags.models.filter(m=>m.name===name);
 if(rows.length!==1||rows[0].digest!==expected.digest){results.push({model:name,registration_matches:false});continue;}
 const show=await api('/api/show',{model:name,verbose:false});
 if(typeof show.template!=='string'||typeof (show.system??'')!=='string'||typeof show.modelfile!=='string')throw Error('model-shape');
 const template_hash=hash(show.template),system=show.system??'';
 const source=show.modelfile.match(/^FROM\s+\/root\/\.ollama\/models\/blobs\/sha256-([a-f0-9]{64})\s*$/m);
 const info={};for(const [key,value] of Object.entries(show.model_info??{})){
  if(/^(?:general\.(?:architecture|file_type)|tokenizer\.ggml\.(?:model|pre|bos_token_id|eos_token_id|padding_token_id|add_bos_token|add_eos_token)|[a-z0-9_]+\.(?:context_length|embedding_length|block_count|attention\.head_count(?:_kv)?))$/.test(key)
   && (typeof value==='boolean'||typeof value==='number'&&Number.isFinite(value)||typeof value==='string'&&value.length<120))info[key]=value;
 }
 const parameters=(typeof show.parameters==='string'?show.parameters:'').split('\n').filter(line=>/^\s*(?:num_ctx|num_thread|num_predict|temperature|top_p|top_k|min_p|repeat_penalty|repeat_last_n|stop)\s+/.test(line)).slice(0,32).map(line=>line.slice(0,300));
 results.push({model:name,registration_matches:true,registered_blob:source?.[1]??null,template_sha256:template_hash,
  public_template:template_hash===expected.template&&system.length===0&&show.template.length<=16384?show.template:null,
  template_withheld:template_hash!==expected.template||system.length!==0||show.template.length>16384,
  system_characters:system.length,system_sha256:hash(system),parameters,model_info:info});
}
console.log(JSON.stringify({runtime_version:version.version,models:results}));
'''


def run(*args,timeout=25):
    r=subprocess.run(args,capture_output=True,text=True,timeout=timeout)
    if r.returncode:raise RuntimeError('Read-only audit command failed: '+args[0])
    return r.stdout


def fingerprint():
    values=json.loads(run('docker','inspect',*NAMES))
    result={v['Name']:dict(id=v['Id'],image=v['Image'],started=v['State']['StartedAt'],running=v['State']['Running'],networks=sorted(v['NetworkSettings']['Networks'])) for v in values}
    if set(result)!={'/'+name for name in NAMES} or not all(v['running'] for v in result.values()):raise RuntimeError('Production is not ready.')
    for path in ('/opt/vector/docker-compose.yml','/opt/fegcraft-updated/docker-compose.yml','/root/vector-workspace/releases/vector-fegcraft-install-20261017T125904Z-4fdeaf/compose.json'):
        result[path]=hashlib.sha256(Path(path).read_bytes()).hexdigest()
    return result


def verify_blob(model,metadata,command=run):
    if model not in MODELS:raise ValueError('Unapproved model.')
    expected=MODELS[model]
    if metadata.get('registration_matches') is not True or metadata.get('registered_blob')!=expected['blob']:
        return dict(verified=False,reason='REGISTRATION_OR_SOURCE_DIFFERS')
    path='/root/.ollama/models/blobs/sha256-'+expected['blob']
    # Fixed known path, no shell/glob, no import-directory or filesystem scan.
    command('docker','exec',SERVICE,'test','!','-L',path)
    command('docker','exec',SERVICE,'test','-f',path)
    size=command('docker','exec',SERVICE,'stat','-c','%s',path).strip()
    if size!=str(expected['size']):return dict(verified=False,reason='WEIGHT_SIZE_MISMATCH')
    # Kill the reader inside its existing container if the bounded read expires.
    output=command('docker','exec',SERVICE,'timeout','--signal=TERM','--kill-after=5s','90s','sha256sum',path,timeout=110)
    match=re.fullmatch(r'([a-f0-9]{64})\s+\*?'+re.escape(path)+r'\s*',output)
    actual=match[1] if match else None
    return dict(verified=actual==expected['blob'],size_bytes=int(size),sha256=actual,reason=None if actual==expected['blob'] else 'WEIGHT_SHA256_MISMATCH')


def audit(command=run,state=fingerprint,progress=print):
    before=state()
    data=json.loads(command('docker','exec','-i','vector-app','node','--input-type=module','-e',METADATA_JS.replace('__MODELS__',json.dumps(MODELS)),timeout=40))
    if not isinstance(data,dict) or not isinstance(data.get('models'),list) or {m.get('model') for m in data['models']}!=set(MODELS) or len(data['models'])!=len(MODELS):raise RuntimeError('Unexpected metadata scope.')
    for model in data['models']:
        progress('Prüfe registrierte Gewichtsdatei: '+model['model'],flush=True)
        try:model['weight_integrity']=verify_blob(model['model'],model,command)
        except (RuntimeError,subprocess.TimeoutExpired):model['weight_integrity']=dict(verified=False,reason='WEIGHT_READ_NOT_VERIFIED')
        progress('Dateiprüfung abgeschlossen: '+str(model['weight_integrity']['verified']),flush=True)
    data.update(production_unchanged=state()==before,runtime_image=before['/'+SERVICE]['image'],model_calls=0,cloud_calls=0,api_cost_chf=0,messages_sent=0,
        production_activated=False,eligible_for_activation=False,quality_passed=False)
    data['integrity_verified']=all(m['weight_integrity']['verified'] for m in data['models'])
    data['passed']=data['integrity_verified'] and data['production_unchanged']
    return data


def main():
    os.umask(0o077)
    if os.geteuid()!=0:raise RuntimeError('Run as root through the owner runner.')
    with (ROOT/'.chat-release.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        folder=ROOT/'releases'/('vector-model-artifact-audit-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+secrets.token_hex(3));folder.mkdir(mode=0o700)
        print('Nur Metadaten und zwei bekannte Gewichtsdateien lesen. Keine Modellanfrage, Änderung oder Neustart.',flush=True)
        print('Belege:',folder,flush=True)
        result=audit();(folder/'result.json').write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(result,indent=2));print('Report:',folder/'result.json')
        if not result['passed']:raise RuntimeError('Audit incomplete or drift found; preserve models and inspect the report.')
        print('Dateiintegrität geprüft. Modellqualität bleibt unqualifiziert; keine Aktivierung.')


if __name__=='__main__':
    try:main()
    except Exception as exc:
        print('ERROR:',str(exc) if isinstance(exc,RuntimeError) else type(exc).__name__)
        raise SystemExit(1)
