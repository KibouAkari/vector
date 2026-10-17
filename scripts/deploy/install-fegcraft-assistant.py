#!/usr/bin/env python3
"""Guarded deterministic Minecraft pilot. No cloud/model or welcome message."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
import zipfile

ROOT = Path('/root/vector-workspace')
REPO = ROOT / 'github/vector'
DATA = Path('/opt/fegcraft-updated/data')
SERVICE = 'vector-fegcraft-assistant'
IMAGE = 'sha256:eca0b83a886fcc9952ef13755853ef63134e5c76733d40564460398776c92dd7'
QUALIFIED = '98bad3fba4b0f8ed9d90a845d66b4d4c3f896059'
RECIPES = ROOT / 'releases/vector-fegcraft-base-recipes-20261017T122615Z-5504b8'
CAPTURE = ROOT / 'releases/vector-fegcraft-bridge-evaluation-20261016T224316Z-280627'
ADDON_SHA = '0be86352e50597fc5e8e82742d87bba3ef924b8d1a8c2230c03bc89d261bc671'
CATALOG_SHA = 'd63d09054ddd1195bbd10c5dbeecc78ee43aadd6989eff48d6b429a6901b89ad'
INTEGRATION_SHA = '75e039ac6c8edad3c9423c91638ffd15d7c9b95dadb60bf69349da838afbf337'
OTHERS = ('vector-app','vector-worker','vector-runner','vector-postgres','vector-redis','vector-local-inference','vector-privacy-ner')

HEALTH = r'''import hashlib,hmac,json,time,urllib.request
from pathlib import Path
key=bytes.fromhex(Path('/run/secrets/vector_fegcraft_token').read_text().strip())
body=json.dumps({'principal':'00000000-0000-0000-0000-000000000000','name':'Probe','event':'00000000-0000-0000-0000-000000000000:0','message':'health probe'}).encode()
stamp=str(int(time.time()));sig=hmac.new(key,stamp.encode()+b'\n'+body,hashlib.sha256).hexdigest()
req=urllib.request.Request('http://127.0.0.1:8090/v1/minecraft',body,{'X-Vector-Time':stamp,'X-Vector-Signature':sig})
opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
with opener.open(req,timeout=3) as response:result=json.load(response)
assert result=={'status':'ignored'}
'''
READ_PROBE = r'''import json,sys
sys.path.insert(0,'/code')
import stats
from recipes import RecipeBook
from runtime import Assistant
data=stats.snapshot('/inputs/stats','/inputs/usercache.json');stats.require_complete(data)
assert data['players']
book=RecipeBook.load('/inputs/recipes.json');assert len(book.recipes)==975
mods=Assistant(None,None,None,'/inputs/mods.json').mods();assert mods
print(json.dumps({'complete_statistics':True,'player_files':len(data['players']),'mod_ids':len(mods),'recipes':len(book.recipes)}))
'''


def run(*args, timeout=30):
    result = subprocess.run(args,capture_output=True,timeout=timeout)
    if result.returncode:
        raise RuntimeError('COMMAND_FAILED_'+args[0].upper())
    return result.stdout


def no_links(path):
    if any(p.is_symlink() for p in (path,*path.parents)):
        raise RuntimeError('SYMLINK_REFUSED')


def digest(path):
    no_links(path)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inspect(name):
    return json.loads(run('docker','inspect',name))[0]


def existing_service():
    return bool(run('docker','ps','-aq','--filter','name=^/'+SERVICE+'$').strip())


def profile(directory, uid, gid, token):
    def bind(source,target,readonly=True):
        return {'type':'bind','source':str(source),'target':target,'read_only':readonly,'bind':{'create_host_path':False}}
    return {'services':{'assistant':{
        'image':IMAGE,'container_name':SERVICE,'user':str(uid)+':'+str(gid),
        'entrypoint':['python3','/code/server.py'],'read_only':True,
        'environment':{'PYTHONDONTWRITEBYTECODE':'1','VECTOR_FEGCRAFT_RECIPES':'1','VECTOR_FEGCRAFT_KNOWLEDGE':'0'},
        'restart':'unless-stopped','cap_drop':['ALL'],'security_opt':['no-new-privileges:true'],
        'cpus':1,'mem_limit':'256m','memswap_limit':'256m','pids_limit':64,
        'tmpfs':['/tmp:rw,noexec,nosuid,nodev,size=16m,mode=1777'],
        'networks':['mc-net'],'volumes':[
            bind(directory/'code','/code'),bind(directory/'state','/state',False),
            bind(DATA/'world/players/stats','/inputs/stats'),bind(DATA/'usercache.json','/inputs/usercache.json'),
            bind(directory/'mods.json','/inputs/mods.json'),bind(directory/'recipes.json','/inputs/recipes.json'),
            bind(token,'/run/secrets/vector_fegcraft_token')],
        'healthcheck':{'test':['CMD','python3','/code/health.py'],'interval':'30s','timeout':'5s','retries':3,'start_period':'10s'},
        'logging':{'driver':'json-file','options':{'max-size':'5m','max-file':'2'}}}},
        'networks':{'mc-net':{'external':True,'name':'mc-net'}}}


def compose(directory,*args):
    return run('docker','compose','-p',SERVICE,'-f',str(directory/'compose.json'),*args,timeout=90)


def evidence():
    for directory in (RECIPES,CAPTURE):
        no_links(directory)
    for path in (RECIPES/'result.json',CAPTURE/'result.json'):
        no_links(path)
        if not path.is_file() or path.stat().st_size>131072:raise RuntimeError('EVIDENCE_FILE_INVALID')
    recipe = json.loads((RECIPES/'result.json').read_bytes())
    capture = json.loads((CAPTURE/'result.json').read_bytes())
    if (recipe.get('passed') is not True or recipe.get('cleanup_verified') is not True
            or recipe.get('production_unchanged') is not True or recipe.get('revision')!=QUALIFIED
            or recipe.get('model_calls')!=0 or recipe.get('cloud_calls')!=0
            or recipe.get('native_image')!=IMAGE or recipe.get('scope')!='installed-vanilla-base'
            or recipe.get('recipes')!=975 or recipe.get('catalog_sha256')!=CATALOG_SHA
            or digest(RECIPES/'recipes.json')!=CATALOG_SHA
            or capture.get('passed') is not True or capture.get('cleanup_verified') is not True
            or capture.get('addon_sha256')!=ADDON_SHA
            or digest(CAPTURE/'vector-minecraft-0.1.0.jar')!=ADDON_SHA):
        raise RuntimeError('QUALIFICATION_EVIDENCE_MISMATCH')


def publish_file(path, content, uid, gid, mode):
    no_links(path)
    temporary=path.parent/('.vector-write-'+secrets.token_hex(12))
    fd=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    try:
        with os.fdopen(fd,'wb') as handle:
            handle.write(content);handle.flush();os.fsync(handle.fileno())
        os.chown(temporary,uid,gid);temporary.chmod(mode)
        os.link(temporary,path,follow_symlinks=False)
    finally:
        temporary.unlink(missing_ok=True)
    sync_directory(path.parent)


def sync_directory(path):
    fd=os.open(path,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:os.fsync(fd)
    finally:os.close(fd)


def owned_files(manifest):
    expected={str(DATA/'DiscordIntegration-Data/addons/vector-minecraft-0.1.0.jar'),
              str(DATA/'DiscordIntegration-Data/vector/bridge.properties'),
              str(DATA/'DiscordIntegration-Data/vector/token')}
    records=manifest['files']
    if not records or not set(records)<=expected:
        raise RuntimeError('ROLLBACK_PATH_MISMATCH')
    for name,value in records.items():
        path=Path(name)
        if not path.is_file() or digest(path)!=value:
            raise RuntimeError('MANAGED_FILE_CHANGED')
    return [Path(name) for name in records]


def save(directory, manifest):
    temporary=directory/'manifest.next.json'
    no_links(temporary)
    fd=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'w') as handle:
        json.dump(manifest,handle,indent=2);handle.flush();os.fsync(handle.fileno())
    os.replace(temporary,directory/'manifest.json')
    sync_directory(directory)


def rollback(directory):
    no_links(directory)
    if directory.parent!=ROOT/'releases' or not directory.name.startswith('vector-fegcraft-install-'):
        raise RuntimeError('ROLLBACK_DIRECTORY_REFUSED')
    manifest=json.loads((directory/'manifest.json').read_bytes())
    paths=owned_files(manifest)
    if inspect('fegcraft-updated')['Image']!=manifest['minecraft_image']:
        raise RuntimeError('MINECRAFT_IMAGE_CHANGED')
    if existing_service():
        if digest(directory/'compose.json')!=manifest.get('compose_sha256'):
            raise RuntimeError('SERVICE_PROFILE_CHANGED')
        if inspect(SERVICE)['Config']['Labels'].get('com.vector.installation')!=manifest['owner']:
            raise RuntimeError('UNEXPECTED_SERVICE')
        compose(directory,'down','--timeout','15')
    for path in paths:path.unlink()
    if manifest.get('minecraft_restart_started'):
        run('docker','restart','--time','120','fegcraft-updated',timeout=180)
    manifest['status']='rolled_back';save(directory,manifest)
    print('Owned Vector files/service removed. Minecraft restarted only if cutover had begun. State and evidence retained.')


def install():
    revision=os.environ.get('VECTOR_FEGCRAFT_REV','')
    if not re.fullmatch(r'[a-f0-9]{40}',revision):raise RuntimeError('PIN_REQUIRED')
    evidence()
    run('git','-C',str(REPO),'diff','--quiet',QUALIFIED,revision,'--','services/fegcraft-assistant')
    run('git','-C',str(REPO),'diff','--quiet','5f5eb4185480ea9ea095d37ff1cdb273498f2031',revision,'--','integrations/fegcraft-addon')
    if existing_service():raise RuntimeError('SERVICE_ALREADY_EXISTS_CHECK_ITS_RELEASE_RECORD')
    mc=inspect('fegcraft-updated')
    if not mc['State']['Running'] or mc['State'].get('Restarting') or 'mc-net' not in mc['NetworkSettings']['Networks']:
        raise RuntimeError('MINECRAFT_NOT_READY')
    if not any(m.get('Source')==str(DATA) and m.get('Destination')=='/data' and m.get('RW') is True for m in mc['Mounts']):
        raise RuntimeError('UNEXPECTED_GAME_DATA_MOUNT')
    if digest(DATA/'mods/dcintegration-fabric-MC26.2-3.2.1.jar')!=INTEGRATION_SHA:
        raise RuntimeError('INTEGRATION_CHANGED')
    env=dict(x.split('=',1) for x in mc['Config']['Env'] if '=' in x)
    if not re.fullmatch(r'[0-9]{1,6}',env.get('UID','1000')) or not re.fullmatch(r'[0-9]{1,6}',env.get('GID','1000')):
        raise RuntimeError('UNEXPECTED_GAME_UID')
    uid,gid=int(env.get('UID','1000')),int(env.get('GID','1000'))
    if uid==0 or gid==0:raise RuntimeError('ROOT_GAME_USER_REFUSED')
    bridge=DATA/'DiscordIntegration-Data/vector';addons=DATA/'DiscordIntegration-Data/addons'
    no_links(bridge);no_links(addons)
    if bridge.exists() or not addons.is_dir() or any('vector' in p.name.casefold() for p in addons.iterdir()):
        raise RuntimeError('EXISTING_VECTOR_GAME_FILES')
    others={name:inspect(name)['Id'] for name in OTHERS}
    configs={str(p):digest(p) for p in (Path('/opt/vector/docker-compose.yml'),DATA.parent/'docker-compose.yml')}
    run('docker','image','inspect',IMAGE)
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    directory=ROOT/'releases'/('vector-fegcraft-install-'+stamp+'-'+secrets.token_hex(3));no_links(directory)
    directory.mkdir(mode=0o700);code=directory/'code';code.mkdir();code.chmod(0o755)
    print('Installation evidence: '+str(directory),flush=True)
    for filename in ('runtime.py','server.py','stats.py','policy.py','recipes.py'):
        raw=run('git','-C',str(REPO),'show',revision+':services/fegcraft-assistant/'+filename)
        compile(raw,filename,'exec');publish_file(code/filename,raw,0,0,0o644)
    publish_file(code/'health.py',HEALTH.encode(),0,0,0o644)
    publish_file(code/'read-probe.py',READ_PROBE.encode(),0,0,0o644)
    publish_file(directory/'recipes.json',(RECIPES/'recipes.json').read_bytes(),0,0,0o644)
    mods=[]
    for path in sorted((DATA/'mods').glob('*.jar')):
        no_links(path)
        if path.stat().st_size>128*1024*1024:raise RuntimeError('MOD_ARCHIVE_LIMIT')
        with zipfile.ZipFile(path) as jar:
            if 'fabric.mod.json' not in jar.namelist():continue
            entry=jar.getinfo('fabric.mod.json')
            if entry.file_size>65536:raise RuntimeError('MOD_METADATA_LIMIT')
            value=json.loads(jar.read(entry)).get('id')
            if not isinstance(value,str) or not re.fullmatch(r'[a-z0-9_.-]{1,64}',value):raise RuntimeError('MOD_ID_INVALID')
            mods.append(value)
    if not mods:raise RuntimeError('NO_MOD_METADATA')
    publish_file(directory/'mods.json',json.dumps(sorted(set(mods))).encode(),0,0,0o644)
    state=directory/'state';state.mkdir();os.chown(state,uid,gid);state.chmod(0o700)
    bridge.mkdir(mode=0o700);os.chown(bridge,uid,gid)
    token=bridge/'token';config=bridge/'bridge.properties';addon=addons/'vector-minecraft-0.1.0.jar'
    manifest={'status':'preparing','revision':revision,'owner':secrets.token_hex(16),
              'minecraft_image':mc['Image'],'files':{},'introduction_enabled':False,
              'model_calls':0,'cloud_calls':0,'real_channel_verified':False}
    shutil.copyfile(__file__,directory/'install.py');(directory/'install.py').chmod(0o700)
    publish_file(directory/'rollback.sh',('#!/bin/bash\nset -Eeuo pipefail\nexec python3 '+str(directory/'install.py')+' --rollback '+str(directory)+'\n').encode(),0,0,0o700)
    # Install owned files exclusively. Failure preserves an exact rollback record.
    try:
        for path,content,mode in ((token,(secrets.token_hex(32)+'\n').encode(),0o400),
             (config,b'enabled=true\nintroductionEnabled=false\ntokenFile=/data/DiscordIntegration-Data/vector/token\navatarUrl=\n',0o600),
             (addon,(CAPTURE/'vector-minecraft-0.1.0.jar').read_bytes(),0o644)):
            publish_file(path,content,uid,gid,mode);manifest['files'][str(path)]=digest(path);save(directory,manifest)
        value=profile(directory,uid,gid,token)
        value['services']['assistant']['labels']={'com.vector.installation':manifest['owner']}
        publish_file(directory/'compose.json',json.dumps(value).encode(),0,0,0o600)
        manifest['compose_sha256']=digest(directory/'compose.json');save(directory,manifest)
        compose(directory,'config','--quiet')
        compose(directory,'up','-d','--no-build','--pull','never')
        deadline=time.monotonic()+45
        while time.monotonic()<deadline:
            item=inspect(SERVICE)
            if item['State'].get('Health',{}).get('Status')=='healthy':break
            if not item['State']['Running']:raise RuntimeError('SERVICE_START_FAILED')
            time.sleep(1)
        else:raise RuntimeError('SERVICE_HEALTH_TIMEOUT')
        # A normal game save may briefly replace a stats/cache file. Retry the
        # read-only probe twice; persistent errors still stop before cutover.
        for attempt in range(3):
            try:
                coverage=json.loads(run('docker','exec',SERVICE,'python3','/code/read-probe.py'))
                break
            except RuntimeError:
                if attempt==2:raise
                time.sleep(1)
        manifest['live_input_coverage']=coverage;manifest['status']='service_ready';save(directory,manifest)
        # Only now perform the owner-authorized Minecraft cutover. Docker stop
        # uses the image's normal graceful shutdown, never a chat/console command.
        since=datetime.now(timezone.utc).isoformat()
        manifest['minecraft_restart_started']=True;save(directory,manifest)
        run('docker','restart','--time','120','fegcraft-updated',timeout=180)
        deadline=time.monotonic()+240
        registered=False
        while time.monotonic()<deadline:
            item=inspect('fegcraft-updated')
            if not item['State']['Running']:raise RuntimeError('MINECRAFT_STOPPED')
            output=subprocess.run(['docker','logs','--since',since,'--tail','500','fegcraft-updated'],capture_output=True,timeout=20)
            if output.returncode:raise RuntimeError('GAME_LOG_CHECK_FAILED')
            logs=(output.stdout+output.stderr).decode(errors='replace')
            if 'Vector bridge initialization failed' in logs:raise RuntimeError('ADDON_INITIALIZATION_FAILED')
            registered=registered or 'Vector Minecraft bridge registered; no Discord listener.' in logs
            health=item['State'].get('Health',{}).get('Status')
            ready=health=='healthy' if health else 'Done (' in logs
            if registered and ready:break
            time.sleep(2)
        else:raise RuntimeError('ADDON_REGISTRATION_TIMEOUT')
        if any(inspect(n)['Id']!=identity for n,identity in others.items()) or any(digest(Path(p))!=d for p,d in configs.items()):
            raise RuntimeError('OTHER_PRODUCTION_STATE_CHANGED')
        manifest['status']='installed_pending_real_channel';save(directory,manifest)
    except Exception as failure:
        manifest['status']='failed';manifest['failure']=str(failure) if isinstance(failure,RuntimeError) else type(failure).__name__;save(directory,manifest)
        # A partial file install is retained for explicit reconciliation; never
        # remove unrecognized files or restart against an unknown changed state.
        if manifest['files']:
            rollback(directory)
        raise
    print(json.dumps({'installed':True,'service_healthy':True,'addon_registered':True,
        'coverage':coverage,'introduction_enabled':False,'real_channel_verified':False,
        'freeform_knowledge_enabled':False,'model_calls':0,'cloud_calls':0,
        'other_services_retained':True,'compose_files_unchanged':True,
        'release':str(directory),'rollback':str(directory/'rollback.sh')},indent=2))
    print('Pilot installed. Test an addressed question in Minecraft and confirm the existing Discord relay. Introduction is still disabled.')


if __name__=='__main__':
    os.umask(0o077)
    try:
        with (ROOT/'.chat-release.lock').open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            if len(sys.argv)==3 and sys.argv[1]=='--rollback':rollback(Path(sys.argv[2]))
            elif len(sys.argv)==1:install()
            else:raise RuntimeError('INVALID_ARGUMENTS')
    except Exception as exc:
        print('ERROR: '+(str(exc) if isinstance(exc,RuntimeError) else type(exc).__name__)+'. Inspect the private installation manifest; no welcome was sent by this script.',file=sys.stderr)
        sys.exit(1)
