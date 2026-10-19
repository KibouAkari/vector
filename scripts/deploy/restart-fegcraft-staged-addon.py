#!/usr/bin/env python3
"""Load the already staged addon by a regular restart of the SAME game container."""
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import re
import secrets
import signal
import subprocess
import sys
import time
from types import SimpleNamespace

ROOT=Path('/root/vector-workspace');REPO=ROOT/'github/vector'
BASE='a0ea5de2348ad14788949d15c006e4282738fc36'
RELEASE=ROOT/'releases/vector-fegcraft-reviewed-help-20261019T064939Z-d1f1fc'
DATA=Path('/opt/fegcraft-updated/data');CONTROL=DATA/'DiscordIntegration-Data/vector'
POINTER=ROOT/'fegcraft-addon-restart.json'
REGISTERED=b'Vector bridge registered; Discord input enabled in the linked chat channel.'


def inspect(p):
    return json.loads(p.run('docker','inspect','fegcraft-updated'))[0]


def same(p,expected):
    value=inspect(p)
    if (value['Id'],value['Image'])!=(expected['Id'],expected['Image']):
        raise RuntimeError('ADDON_RESTART_CONTAINER_REPLACED_NO_ACTION')
    return value


def differences(before,after):
    # No other field/configuration or service restart is authorized.
    left=json.loads(json.dumps(before));right=json.loads(json.dumps(after))
    right['/fegcraft-updated']['StartedAt']=left['/fegcraft-updated']['StartedAt']
    return left!=right


def wait_ready(p,game):
    deadline=time.monotonic()+240;last=0
    while time.monotonic()<deadline:
        current=same(p,game);state=current['State']
        if not state['Running'] or state.get('OOMKilled') or state.get('Restarting'):
            raise RuntimeError('ADDON_RESTART_GAME_NOT_RUNNING')
        if state.get('Health',{}).get('Status')=='healthy':return current
        if time.monotonic()-last>=20:
            print('Minecraft startet; warte auf die bestätigte Bereitschaft ...',flush=True);last=time.monotonic()
        time.sleep(2)
    raise RuntimeError('ADDON_RESTART_HEALTH_TIMEOUT_NO_RECREATION')


def restart(p,game):
    # Defer Ctrl-C/TERM until the normal stop/start completes, never abandon a stopped game.
    signals={s:signal.getsignal(s) for s in (signal.SIGINT,signal.SIGTERM)}
    def deferred(*_):print('Neustart läuft; derselbe Container wird zuerst wieder gestartet.',flush=True)
    for s in signals:signal.signal(s,deferred)
    stopped=False
    try:
        same(p,game)
        print('Stoppe Minecraft regulär. Danach starte ich denselben Container.',flush=True)
        p.run('docker','stop','--time','120',game['Id'],timeout=180);stopped=True
        state=same(p,game)['State']
        if state['Running'] or state.get('OOMKilled') or state.get('ExitCode') not in (0,143):
            raise RuntimeError('ADDON_RESTART_CLEAN_STOP_NOT_CONFIRMED')
    finally:
        try:
            current=same(p,game)
            if not stopped and current['State']['Running']:
                # A CLI timeout does not cancel a Docker daemon stop operation.
                p.run('docker','wait',game['Id'],timeout=180)
                current=same(p,game)
            if not current['State']['Running']:
                print('Starte denselben Minecraft-Container ...',flush=True)
                p.run('docker','start',game['Id'],timeout=90)
        finally:
            for s,handler in signals.items():signal.signal(s,handler)
    return wait_ready(p,game)


def loaded(p,game):
    # Game health can become ready slightly before the linked bridge finishes loading.
    instance=CONTROL/'owner-welcome-v2.instance';p.safe(instance)
    born=datetime.fromisoformat(game['State']['StartedAt'].replace('Z','+00:00')).timestamp()
    for attempt in range(23):
        same(p,game)
        logs=subprocess.run(['docker','logs','--since',game['State']['StartedAt'],'--tail','2000',game['Id']],capture_output=True,timeout=25)
        if logs.returncode:raise RuntimeError('ADDON_RESTART_REGISTRATION_LOG_UNAVAILABLE')
        if REGISTERED in logs.stdout+logs.stderr and instance.exists():
            boot=p.read(instance)
            if re.fullmatch(b'[a-f0-9-]{36}\n',boot) and instance.stat().st_mtime>=born:return
        if attempt%5==0:print('Minecraft läuft; warte auf die Vector-Registrierung ...',flush=True)
        if attempt<22:time.sleep(2)
    raise RuntimeError('ADDON_RESTART_CURRENT_LOAD_NOT_OBSERVED')


def main():
    os.umask(0o077);sys.dont_write_bytecode=True
    revision=os.environ.get('VECTOR_FEGCRAFT_REV','')
    if os.geteuid()!=0 or not re.fullmatch('[a-f0-9]{40}',revision) or sys.argv[1:]:
        raise RuntimeError('ADDON_RESTART_ROOT_PIN_NO_ARGUMENTS_REQUIRED')
    raw=subprocess.check_output(['git','-C',str(REPO),'show',BASE+':scripts/deploy/update-fegcraft-companion.py'])
    ns={'__name__':'restart_companion','__file__':'pinned-companion.py'};exec(compile(raw,ns['__file__'],'exec'),ns)
    companion=SimpleNamespace(**ns)
    raw=subprocess.check_output(['git','-C',str(REPO),'show',companion.BASE+':scripts/deploy/prepare-fegcraft-chat-cutover.py'])
    ns={'__name__':'restart_support','__file__':'pinned-preparation.py'};exec(compile(raw,ns['__file__'],'exec'),ns);p=SimpleNamespace(**ns)
    h=p.load(p.HELPER,'scripts/diagnostics/fegcraft-admission-readiness.py')
    support=p.load(p.DEPLOYED,'scripts/deploy/release-fegcraft-reviewed-help.py')
    for path in (ROOT/'.chat-release.lock',DATA.parent/'backups/.backup.lock',POINTER,DATA,DATA/'world',CONTROL):p.safe(path)
    with (DATA.parent/'backups/.backup.lock').open('rb') as backup, (ROOT/'.chat-release.lock').open('rb') as lock:
        fcntl.flock(backup,fcntl.LOCK_EX|fcntl.LOCK_NB);fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        p.run('git','-C',str(REPO),'merge-base','--is-ancestor',revision,'origin/main')
        if companion.verify_current(p,h,support,BASE)!=RELEASE:raise RuntimeError('ADDON_RESTART_BACKEND_RELEASE_CHANGED')
        game=inspect(p);before=h.snapshot()
        if POINTER.exists():
            prior=json.loads(p.read(POINTER))
            if (prior.get('status')=='verified' and prior.get('backend_revision')==BASE
                and prior.get('container')==game['Id'] and prior.get('started_at')==game['State']['StartedAt']
                and prior.get('addon_sha256')==p.sha(p.read(h.ADDON))):
                print('Dieser Minecraft-Start wurde bereits geprüft. Kein weiterer Neustart.');return
            raise RuntimeError('ADDON_RESTART_PRIOR_ATTEMPT_REQUIRES_REVIEW')
        intent=json.loads(p.read(ROOT/'fegcraft-intents.json'))
        if intent.get('revision')!=companion.PREVIOUS or intent.get('release')!=str(companion.PREVIOUS_RELEASE):raise RuntimeError('ADDON_RESTART_INTENT_POINTER_CHANGED')
        addon=json.loads(p.read(companion.PREVIOUS_RELEASE/'addon-plan.json'))
        proof=json.loads(p.read(companion.PREVIOUS_RELEASE/'addon-proof.json'))
        if (addon.get('path')!=str(h.ADDON) or p.sha(p.read(h.ADDON))!=addon.get('after_sha')
            or proof.get('revision')!=companion.PREVIOUS or proof.get('sha256')!=addon['after_sha']
            or proof.get('offline_unit_passed') is not True):
            raise RuntimeError('ADDON_RESTART_STAGED_JAR_CHANGED')
        if game['HostConfig'].get('AutoRemove') or not any(m.get('Type')=='bind' and m.get('Source')==str(DATA) and m.get('Destination')=='/data' and m.get('RW') is True for m in game['Mounts']):
            raise RuntimeError('ADDON_RESTART_PERSISTENCE_CHANGED')
        identity=[(x.stat().st_dev,x.stat().st_ino) for x in (DATA,DATA/'world')]
        files={x:p.read(x) if x.exists() else None for x in (CONTROL/'bridge.properties',CONTROL/'introduction-v1.attempted',CONTROL/'owner-welcome-v2.attempted',CONTROL/'owner-welcome-v2.ready')}
        if files[CONTROL/'owner-welcome-v2.attempted'] is None:raise RuntimeError('ADDON_RESTART_WELCOME_MARKER_REQUIRED')
        directory=ROOT/'releases'/('vector-fegcraft-addon-restart-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+secrets.token_hex(3))
        p.safe(directory);directory.mkdir(mode=0o700)
        record=dict(status='attempting',revision=revision,backend_revision=BASE,backend_release=str(RELEASE),container=game['Id'],started_at=game['State']['StartedAt'],release=str(directory),addon_sha256=addon['after_sha'])
        support.atomic(POINTER,(json.dumps(record)+'\n').encode())
        print('Neustartbelege:',directory,flush=True)
        try:
            current=restart(p,game)
            if current['State']['StartedAt']==game['State']['StartedAt']:raise RuntimeError('ADDON_RESTART_NEW_START_NOT_OBSERVED')
            loaded(p,current)
            if differences(before,h.snapshot()) or identity!=[(x.stat().st_dev,x.stat().st_ino) for x in (DATA,DATA/'world')]:
                raise RuntimeError('ADDON_RESTART_UNEXPECTED_SCOPE_CHANGE')
            if any((p.read(x) if x.exists() else None)!=value for x,value in files.items()):raise RuntimeError('ADDON_RESTART_CONFIG_OR_WELCOME_CHANGED')
            companion.verify_current(p,h,support,BASE)
            record.update(status='verified',started_at=current['State']['StartedAt'],game_healthy=True,same_container=True,staged_addon_loaded=True,
                discord_input_registered=True,other_services_unchanged=True,world_directory_retained=True,model_calls=0,cloud_calls=0,messages_sent=0,welcome_replayed=False,real_chat_tested=False)
            support.atomic(directory/'result.json',(json.dumps(record,indent=2)+'\n').encode());support.atomic(POINTER,(json.dumps(record)+'\n').encode())
            print(json.dumps(record,indent=2))
        except BaseException:
            record['status']='requires_review';support.atomic(directory/'result.json',(json.dumps(record,indent=2)+'\n').encode());support.atomic(POINTER,(json.dumps(record)+'\n').encode());raise


if __name__=='__main__':
    try:main()
    except BaseException as exc:
        value=str(exc);code=value if type(exc) is RuntimeError and re.fullmatch('[A-Z][A-Z0-9_]{2,100}',value) else type(exc).__name__
        print('ERROR: '+code+'. Kein Container wird entfernt oder neu erstellt; Details privat prüfen.',file=sys.stderr);raise SystemExit(1)
