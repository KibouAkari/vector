#!/usr/bin/env python3
"""Owner-authorized fixed welcome, before manual tests, with no restart/retry."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tomllib

ROOT=Path('/root/vector-workspace')
DATA=Path('/opt/fegcraft-updated/data')
SERVICE='vector-fegcraft-assistant'
TEXT='[Vector] Hallo zusammen, ich bin Vector, euer neuer Assistent für Minecraft. Ich helfe bei Statistiken, Mods und Grundrezepten. Fragt mich mit hey Vector oder yoo Vector.'


def run(*args):
    result=subprocess.run(args,capture_output=True,timeout=20)
    if result.returncode:raise RuntimeError('WELCOME_COMMAND_FAILED_DELIVERY_UNCONFIRMED')
    return result.stdout


def no_links(path):
    if any(p.is_symlink() for p in (path,*path.parents)):raise RuntimeError('SYMLINK_REFUSED')


def read(path):
    no_links(path)
    meta=path.stat()
    if not stat.S_ISREG(meta.st_mode) or meta.st_size>131072:raise RuntimeError('INVALID_INSTALLATION_FILE')
    return path.read_bytes()


def installation(service):
    labels=service['Config'].get('Labels') or {}
    profile=Path(labels.get('com.docker.compose.project.config_files',''))
    directory=profile.parent
    if (profile.name!='compose.json' or directory.parent!=ROOT/'releases'
            or not re.fullmatch(r'vector-fegcraft-install-[0-9]{8}T[0-9]{6}Z-[a-f0-9]{6}',directory.name)):
        raise RuntimeError('UNRECOGNIZED_INSTALLATION')
    manifest=json.loads(read(directory/'manifest.json'))
    if (manifest.get('status') not in ('installed_pending_real_channel','welcome_attempted_pending_real_channel')
            or labels.get('com.vector.installation')!=manifest.get('owner')
            or hashlib.sha256(read(profile)).hexdigest()!=manifest.get('compose_sha256')):
        raise RuntimeError('INSTALLATION_NOT_COMPLETED_OR_CHANGED')
    expected={str(DATA/'DiscordIntegration-Data/vector/token'),str(DATA/'DiscordIntegration-Data/vector/bridge.properties'),
              str(DATA/'DiscordIntegration-Data/addons/vector-minecraft-0.1.0.jar')}
    if set(manifest.get('files',{}))!=expected:raise RuntimeError('INSTALLATION_FILES_MISMATCH')
    for name,digest in manifest['files'].items():
        path=Path(name);no_links(path)
        if hashlib.sha256(path.read_bytes()).hexdigest()!=digest:raise RuntimeError('INSTALLATION_FILES_CHANGED')
    return directory,manifest


def claim(path,uid,gid):
    no_links(path)
    try:fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    except FileExistsError:return False
    with os.fdopen(fd,'wb') as handle:
        handle.write(b'attempted by owner-authorized fixed console welcome; delivery acknowledgement unavailable\n')
        handle.flush();os.fsync(handle.fileno())
    os.chown(path,uid,gid)
    fd=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:os.fsync(fd)
    finally:os.close(fd)
    return True


def send_once(marker,uid,gid):
    if not claim(marker,uid,gid):return False
    # One closed constant, no user-controlled command, shell or model route.
    # The durable claim remains on failure/timeout/uncertain delivery.
    run('docker','exec','-u',str(uid)+':'+str(gid),'fegcraft-updated','mc-send-to-console','say '+TEXT)
    return True


def main():
    service=json.loads(run('docker','inspect',SERVICE))[0]
    game=json.loads(run('docker','inspect','fegcraft-updated'))[0]
    directory,manifest=installation(service)
    if (not service['State'].get('Running') or service['State'].get('Health',{}).get('Status')!='healthy'
            or not game['State'].get('Running') or game['Image']!=manifest['minecraft_image']
            or game['State'].get('Health',{}).get('Status','healthy')!='healthy'):
        raise RuntimeError('INSTALLATION_NOT_HEALTHY_NO_MESSAGE_SENT')
    user=service['Config'].get('User','')
    if not re.fullmatch(r'[1-9][0-9]*:[1-9][0-9]*',user):raise RuntimeError('UNEXPECTED_SERVICE_USER')
    uid,gid=map(int,user.split(':'))
    marker=DATA/'DiscordIntegration-Data/vector/introduction-v1.attempted'
    if marker.exists():
        no_links(marker)
        print('Welcome was already attempted. No automatic resend. Check the game/Discord chat before any manual recovery.')
        return
    run('docker','exec',SERVICE,'python3','/code/health.py')
    run('docker','exec','-u',user,'fegcraft-updated','which','mc-send-to-console')
    relay=None
    try:
        config=tomllib.loads(read(DATA/'config/Discord-Integration.toml').decode())
        messages=config.get('messages',{})
        prefix=messages.get('sayCommandIgnoredPrefix','')
        relay=messages.get('sendOnSayCommand') is True and not (prefix and TEXT.startswith(prefix))
    except (OSError,ValueError,RuntimeError):pass
    sent=send_once(marker,uid,gid)
    print(json.dumps({'welcome_console_accepted':sent,'durable_attempt_marker':True,
                      'delivery_acknowledged':False,'discord_say_relay_configured':relay,
                      'restart_performed':False,'model_calls':0,'cloud_calls':0,
                      'real_question_routing_still_unverified':True},indent=2))
    print('Check the welcome in Minecraft now, then test an addressed question. Do not rerun to recover an uncertain delivery.')


if __name__=='__main__':
    try:
        with (ROOT/'.chat-release.lock').open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            main()
    except Exception as exc:
        print('ERROR: '+(str(exc) if isinstance(exc,RuntimeError) else type(exc).__name__)+'. Existing welcome markers are never removed or retried automatically.',file=sys.stderr)
        sys.exit(1)
