#!/usr/bin/env python3
"""Build a private installed-base catalog and test real HTTP without activation."""
from datetime import datetime, timezone
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys

ROOT = Path('/root/vector-workspace')
REPO = ROOT / 'github/vector'
BASE = Path('/opt/fegcraft-updated/data')
PYTHON = 'sha256:eca0b83a886fcc9952ef13755853ef63134e5c76733d40564460398776c92dd7'
SOURCE_SHA = '183c0499c5f855570ee487dd38e141a53f0121f83a0b07a3bac2d8b6698823e8'
NAMES = ('vector-app', 'vector-worker', 'vector-runner', 'vector-postgres',
         'vector-redis', 'vector-local-inference', 'vector-privacy-ner', 'fegcraft-updated')

HARNESS = r'''
import hashlib,hmac,json,sys,tempfile,threading,time,uuid
from http.client import HTTPConnection
from pathlib import Path
sys.path.insert(0,'/code')
from recipes import RecipeBook
from runtime import Assistant,State
from server import Service
catalog=RecipeBook.load('/inputs/recipes.json')
key=b'fixture-only-private-http-key'
clock=1_000_000_000
checks=[];answers=[]
class ForbiddenModel:
 calls=0
 def answer(self,*args):
  self.calls+=1
  raise AssertionError('UNEXPECTED_MODEL_CALL')
model=ForbiddenModel()
with tempfile.TemporaryDirectory() as folder:
 root=Path(folder);stats=root/'stats';stats.mkdir();users=root/'users.json';mods=root/'mods.json'
 uid=str(uuid.UUID(int=1));users.write_text(json.dumps([{'uuid':uid,'name':'ExampleOne'}]));mods.write_text('["fabric-api"]')
 stat=stats/(uid+'.json')
 def write_stats(n):stat.write_text(json.dumps({'stats':{'minecraft:custom':{'minecraft:mob_kills':n}}}))
 write_stats(12)
 assistant=Assistant(State(root/'events.sqlite',key,lambda:clock),stats,users,mods,model,catalog)
 service=Service(('127.0.0.1',0),assistant,key,lambda:clock)
 worker=threading.Thread(target=service.serve_forever,daemon=True);worker.start()
 def send(message,event,user=1,authorized=True):
  principal=str(uuid.UUID(int=user))
  raw=json.dumps({'principal':principal,'name':'ExampleOne','event':principal+':'+str(event),'message':message}).encode()
  stamp=str(clock);sig=hmac.new(key,stamp.encode()+b'\n'+raw,hashlib.sha256).hexdigest() if authorized else '0'*64
  conn=HTTPConnection(*service.server_address,timeout=3)
  conn.request('POST','/v1/minecraft',raw,{'X-Vector-Time':stamp,'X-Vector-Signature':sig})
  response=conn.getresponse();result=response.status,json.loads(response.read());conn.close();return result
 try:
  for i,(question,expected) in enumerate([
   ('Werkbank',('4x Holzbretter',)),('Ofen',('8x Steinmaterial',)),('Trichter',('5x Eisenbarren','1x Truhe'))],1):
   start=time.monotonic();status,result=send('yoo Vector, wie craftet man '+question+'?',i)
   text=result.get('text','')
   assert status==200 and result.get('status')=='answered' and text.startswith('Yoo ExampleOne, ')
   assert all(part in text for part in expected) and 'Minecraft 26.2' in text and 'Mod-Anpassungen sind nicht geprüft.' in text
   answers.append({'case':question,'milliseconds':round((time.monotonic()-start)*1000,2),'text':text})
  checks.append('three-installed-base-recipes-via-authenticated-http')
  assert send('yoo Vector, wie craftet man Werkbank?',1)[1]['status']=='duplicate'
  assert send('hey Vector, Rezept Werkbank',4)[1]['status']=='limited'
  checks.append('durable-replay-and-per-user-limit')
  assert 'keine administrativen' in send('hey Vector, was ist der seed?',1,2)[1]['text']
  assert 'kein eindeutig' in send('hey Vector, Rezept unbekanntes Item',2,2)[1]['text']
  assert send('Rezept Werkbank',1,3)[1]['status']=='ignored'
  assert send('hey Vector, Rezept Werkbank',2,3,False)[0]==401
  checks.append('private-unknown-ordinary-chat-and-signature-boundaries')
  assert '12 Kills' in send('hey Vector, wer hat die meisten Mobkills?',3,3)[1]['text']
  write_stats(13)
  assert '13 Kills' in send('hey Vector, wer hat die meisten Mobkills?',4,3)[1]['text']
  checks.append('statistics-read-fresh-after-recipe-requests')
  assistant.recipes=RecipeBook()
  assert 'kein eindeutig' in send('hey Vector, Rezept Werkbank',5,3)[1]['text']
  checks.append('missing-catalog-does-not-use-model')
  assert model.calls==0
 finally:
  service.shutdown();service.server_close();worker.join(timeout=3)
print(json.dumps({'passed':True,'checks':checks,'answers':answers,'recipes':len(catalog.recipes),
 'model_calls':model.calls,'cloud_calls':0,'api_cost_chf':0,'production_activated':False,
 'messages_sent':0,'effective_recipes_qualified':False,'scope':'installed-vanilla-base'},ensure_ascii=False))
'''


def command(*args, timeout=30):
    result = subprocess.run(args, capture_output=True, timeout=timeout)
    if result.returncode:
        raise RuntimeError('QUALIFICATION_COMMAND_FAILED')
    return result.stdout


def state():
    profiles = [hashlib.sha256(path.read_bytes()).hexdigest() for path in
                (Path('/opt/vector/docker-compose.yml'), BASE.parent / 'docker-compose.yml')]
    values = json.loads(command('docker', 'inspect', *NAMES))
    return profiles, sorted((c['Id'], c['Image']) for c in values)


def no_links(path):
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise RuntimeError('SYMLINK_REFUSED')


def evaluate():
    revision = os.environ.get('VECTOR_FEGCRAFT_REV', '')
    if not re.fullmatch(r'[a-f0-9]{40}', revision):
        raise RuntimeError('PIN_REQUIRED')
    no_links(ROOT)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    directory = ROOT / 'releases' / ('vector-fegcraft-base-recipes-' + stamp + '-' + secrets.token_hex(3))
    no_links(directory.parent)
    directory.mkdir(mode=0o700)
    code = directory / 'code';code.mkdir(mode=0o755);code.chmod(0o755)
    for filename in ('recipes.py', 'runtime.py', 'server.py', 'stats.py', 'policy.py'):
        raw = command('git', '-C', str(REPO), 'show', revision + ':services/fegcraft-assistant/' + filename)
        compile(raw, filename, 'exec')
        path = code / filename;path.write_bytes(raw);path.chmod(0o644)
    (code / 'qualify.py').write_text(HARNESS);(code / 'qualify.py').chmod(0o644)
    spec = importlib.util.spec_from_file_location('installed_base_recipes', code / 'recipes.py')
    module = importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    source = BASE / 'versions/26.2/server-26.2.jar'
    no_links(source)
    before = state()
    owner = secrets.token_hex(12);name = 'vector-base-recipes-' + owner
    report = {'revision': revision, 'passed': False, 'scope': 'installed-vanilla-base',
              'effective_recipes_qualified': False, 'production_activated': False,
              'model_calls': 0, 'cloud_calls': 0, 'api_cost_chf': 0, 'messages_sent': 0}
    launched = False
    try:
        print('Build only the pinned installed Minecraft 26.2 base catalog; qualify authenticated HTTP in an isolated container.',flush=True)
        catalog = module.build_catalog(source, SOURCE_SHA)
        catalog_file = directory / 'recipes.json'
        fd = os.open(catalog_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644)
        with os.fdopen(fd, 'w') as handle:
            json.dump(catalog, handle, ensure_ascii=False)
        catalog_file.chmod(0o644)
        # Parent evidence directory stays 0700; only this public game-asset file
        # is bind-mounted read-only for the unprivileged isolated process.
        command('docker', 'image', 'inspect', PYTHON)
        launched = True
        result = subprocess.run([
            'docker','run','--rm','--name',name,'--label','com.vector.base-recipe-evaluation='+owner,
            '--pull','never','--network','none','--user','65534:65534','--read-only',
            '--cap-drop','ALL','--security-opt','no-new-privileges:true','--cpus','1',
            '--memory','256m','--memory-swap','256m','--pids-limit','64',
            '--tmpfs','/tmp:rw,noexec,nosuid,nodev,size=32m,mode=1777',
            '--mount','type=bind,src='+str(code)+',dst=/code,readonly',
            '--mount','type=bind,src='+str(catalog_file)+',dst=/inputs/recipes.json,readonly',
            '--env','PYTHONDONTWRITEBYTECODE=1','--entrypoint','python3',PYTHON,'/code/qualify.py'
        ],capture_output=True,timeout=90)
        (directory / 'client-stderr.log').write_bytes(result.stderr)
        (directory / 'client-stdout.log').write_bytes(result.stdout)
        if result.returncode:
            raise RuntimeError('ISOLATED_RECIPE_HTTP_FAILED')
        report.update(json.loads(result.stdout))
        report.update({'catalog_source_sha256': SOURCE_SHA,'catalog_sha256': hashlib.sha256(catalog_file.read_bytes()).hexdigest(),
                       'unsupported_recipe_count': catalog['unsupported_count'],'native_image': PYTHON})
    except Exception as exc:
        report['passed'] = False
        report['error'] = str(exc) if isinstance(exc, RuntimeError) else type(exc).__name__
    finally:
        if launched:
            probe = subprocess.run(['docker','inspect',name],capture_output=True,timeout=15)
            if probe.returncode == 0:
                value = json.loads(probe.stdout)[0]
                if (value['Config'].get('Labels') or {}).get('com.vector.base-recipe-evaluation') != owner:
                    raise RuntimeError('UNEXPECTED_EVALUATION_CONTAINER')
                command('docker','rm','-f',name)
            remaining = command('docker','ps','-aq','--filter','name=^/'+name+'$')
            report['cleanup_verified'] = not remaining.strip()
        else:
            report['cleanup_verified'] = True
        report['production_unchanged'] = state() == before
        report['passed'] = bool(report['passed'] and report['cleanup_verified'] and report['production_unchanged'])
        fd = os.open(directory / 'result.json',os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,'w') as handle:json.dump(report,handle,indent=2,ensure_ascii=False)
    print(json.dumps(report,indent=2,ensure_ascii=False),flush=True)
    print('Report: '+str(directory / 'result.json'),flush=True)
    if not report['passed']:
        raise RuntimeError('BASE_RECIPE_QUALIFICATION_FAILED')
    print('Installed base recipes and isolated HTTP passed. No game activation or announcement.')


if __name__ == '__main__':
    os.umask(0o077)
    try:
        with (ROOT / '.chat-release.lock').open('r') as lock:
            fcntl.flock(lock,fcntl.LOCK_SH | fcntl.LOCK_NB)
            evaluate()
    except Exception as exc:
        print('ERROR: '+(str(exc) if isinstance(exc,RuntimeError) else type(exc).__name__)+'. No activation performed.',file=sys.stderr)
        sys.exit(1)
