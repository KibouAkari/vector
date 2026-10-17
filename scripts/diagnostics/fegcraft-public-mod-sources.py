#!/usr/bin/env python3
"""Read installed public Fabric metadata for documentation review, never fetch it."""
from datetime import datetime,timezone
import fcntl,hashlib,json,os,re,secrets,stat,subprocess,zipfile
from pathlib import Path
from urllib.parse import urlsplit

ROOT=Path('/root/vector-workspace')
REPO=ROOT/'github/vector'
MODS=Path('/opt/fegcraft-updated/data/mods')
INVENTORY=ROOT/'releases/vector-fegcraft-install-20261017T125904Z-4fdeaf/mods.json'
NAMES=('fegcraft-updated','vector-app','vector-worker','vector-runner','vector-postgres','vector-redis','vector-local-inference','vector-privacy-ner','vector-fegcraft-assistant')
PROFILES=(Path('/opt/fegcraft-updated/docker-compose.yml'),Path('/opt/vector/docker-compose.yml'),
 ROOT/'releases/vector-fegcraft-install-20261017T125904Z-4fdeaf/compose.json')
ID=re.compile(r'[a-z0-9_.-]{1,64}')


def command(*args):
    r=subprocess.run(args,capture_output=True,timeout=20)
    if r.returncode:raise RuntimeError('Public metadata check failed; private command output withheld.')
    return r.stdout


def no_links(path):
    if any(p.is_symlink() for p in (path,*path.parents)):raise RuntimeError('Unexpected metadata path symlink.')


def public_url(value):
    """Repository/project roots only; never print arbitrary contact URLs/tokens."""
    if not isinstance(value,str) or len(value)>512 or any(ord(c)<33 or ord(c)>126 for c in value) or '\\' in value:return None
    try:u=urlsplit(value)
    except ValueError:return None
    if u.scheme!='https' or u.username or u.password or u.query or u.fragment or u.netloc!=u.hostname:return None
    parts=[p for p in u.path.split('/') if p]
    if any(not re.fullmatch(r'[A-Za-z0-9_.-]{1,100}',p) or p in ('.','..') for p in parts):return None
    host=u.hostname
    if host in ('github.com','gitlab.com') and len(parts)>=2:
        repo=parts[1].removesuffix('.git')
        if not repo or repo in ('.','..'):return None
        return 'https://'+host+'/'+parts[0]+'/'+repo
    if host=='modrinth.com' and len(parts)>=2 and parts[0]=='mod':
        return 'https://modrinth.com/mod/'+parts[1]
    if host in ('curseforge.com','www.curseforge.com') and len(parts)>=3 and parts[:2]==['minecraft','mc-mods']:
        return 'https://www.curseforge.com/minecraft/mc-mods/'+parts[2]
    return None


def public_record(value,expected):
    if not isinstance(value,dict) or not isinstance(value.get('id'),str) or not ID.fullmatch(value['id']) or value['id'] not in expected:return None
    version=value.get('version')
    if not isinstance(version,str) or not re.fullmatch(r'[A-Za-z0-9.+_-]{1,64}',version):version=None
    contact=value.get('contact',{})
    sources=[]
    if isinstance(contact,dict):
        for key in ('sources','homepage'):
            url=public_url(contact.get(key))
            if url:sources.append(url)
    licenses=value.get('license',[])
    if isinstance(licenses,str):licenses=[licenses]
    if not isinstance(licenses,list):licenses=[]
    licenses=sorted({v for v in licenses if isinstance(v,str) and re.fullmatch(r'[A-Za-z0-9.+_-]{1,40}',v)})[:8]
    return dict(id=value['id'],version=version,license_ids=licenses,source_candidates=sorted(set(sources)))


def metadata(path):
    no_links(path)
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    with os.fdopen(fd,'rb') as stream:
        info=os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size>100_000_000:raise ValueError('JAR_BOUND')
        with zipfile.ZipFile(stream) as archive:
            member=archive.getinfo('fabric.mod.json')
            if member.file_size>65536 or member.flag_bits&1:raise ValueError('METADATA_BOUND')
            # Only one fixed entry; never traverse nested JARs/assets/recipes.
            with archive.open(member) as entry:data=entry.read(65537)
            if len(data)>65536:raise ValueError('METADATA_BOUND')
            return json.loads(data)


def collect(directory,expected,reader=metadata):
    no_links(directory)
    if not directory.is_dir():raise RuntimeError('Installed mod directory unavailable.')
    paths=sorted(directory.glob('*.jar'))
    if len(paths)>200:raise RuntimeError('Unexpected installed JAR count; no recursive scan.')
    rows={};skipped=0;unmatched=0
    for path in paths:
        try:value=reader(path)
        except (OSError,ValueError,KeyError,zipfile.BadZipFile,RuntimeError):skipped+=1;continue
        record=public_record(value,expected)
        if record is None:unmatched+=1;continue
        row=rows.setdefault(record['id'],dict(id=record['id'],versions=set(),license_ids=set(),source_candidates=set(),metadata_entries=0))
        if record['version'] is not None:row['versions'].add(record['version'])
        row['license_ids'].update(record['license_ids']);row['source_candidates'].update(record['source_candidates']);row['metadata_entries']+=1
    result=[]
    for key in sorted(rows):
        row=rows[key]
        result.append(dict(id=key,versions=sorted(row['versions']),license_ids=sorted(row['license_ids']),
            source_candidates=sorted(row['source_candidates']),multiple_metadata_entries=row['metadata_entries']>1))
    return dict(mods=result,expected_mod_ids=len(expected),observed_expected_mod_ids=len(rows),
        missing_mod_ids=sorted(expected-set(rows)),jars_seen=len(paths),skipped_jars=skipped,unmatched_jars=unmatched,
        mods_without_source_candidates=[r['id'] for r in result if not r['source_candidates']],
        inventory_complete=set(rows)==expected and skipped==0 and unmatched==0)


def fingerprint():
    values=json.loads(command('docker','inspect',*NAMES))
    result={v['Name']:dict(id=v['Id'],image=v['Image'],running=v['State']['Running'],started=v['State']['StartedAt']) for v in values}
    if set(result)!={'/'+name for name in NAMES} or not all(v['running'] for v in result.values()):raise RuntimeError('Production is not ready; no inventory.')
    for path in PROFILES:
        no_links(path);result[str(path)]=hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def main():
    os.umask(0o077);revision=os.environ.get('VECTOR_FEGCRAFT_REV','')
    if os.geteuid()!=0 or not re.fullmatch('[a-f0-9]{40}',revision):raise RuntimeError('Root and exact VECTOR_FEGCRAFT_REV required.')
    command('git','-C',str(REPO),'merge-base','--is-ancestor',revision,'origin/main')
    with (ROOT/'.chat-release.lock').open('r') as lock:
        fcntl.flock(lock,fcntl.LOCK_SH|fcntl.LOCK_NB)
        before=fingerprint();no_links(INVENTORY)
        if not INVENTORY.is_file() or INVENTORY.stat().st_size>32768:raise RuntimeError('Reviewed public mod inventory unavailable.')
        expected=json.loads(INVENTORY.read_bytes())
        if not isinstance(expected,list) or not 1<=len(expected)<=200 or any(not isinstance(x,str) or not ID.fullmatch(x) for x in expected) or len(set(expected))!=len(expected):raise RuntimeError('Invalid public mod inventory.')
        print('Lese nur öffentliche Fabric-Metadaten. Keine Welt-, Spieler- oder Konfigurationsdaten, keine Modellanfrage und kein Neustart.',flush=True)
        report=collect(MODS,set(expected))
        report.update(revision=revision,production_unchanged=fingerprint()==before,quality_passed=False,
            documentation_coverage_qualified=False,sources_are_unreviewed_candidates=True,
            model_calls=0,cloud_calls=0,network_fetches=0,database_calls=0,messages_sent=0,production_activated=False)
        report['passed']=report['inventory_complete'] and report['production_unchanged']
        directory=ROOT/'releases'/('vector-fegcraft-public-sources-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+secrets.token_hex(3));directory.mkdir(mode=0o700)
        (directory/'result.json').write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(report,indent=2));print('Report:',directory/'result.json')
        if not report['production_unchanged']:raise RuntimeError('Production changed during read-only inventory.')
        if not report['inventory_complete']:raise RuntimeError('Public metadata coverage incomplete; preserve report for review. No activation.')
        print('Metadaten gelesen. Quellen zuerst prüfen und passende Dokumentversionen zuordnen; allgemeine Modellfunktion bleibt aus.')


if __name__=='__main__':
    try:main()
    except Exception as exc:
        print('ERROR:',str(exc) if isinstance(exc,RuntimeError) else type(exc).__name__)
        raise SystemExit(1)
