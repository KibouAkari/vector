#!/usr/bin/env python3
"""Replace the known long-offline cron entrypoint; install a bounded incremental job."""
import ast
from datetime import datetime,timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import stat
import subprocess
import sys

ROOT=Path('/root/vector-workspace')
REPO=ROOT/'github/vector'
BASE=Path('/opt/fegcraft-updated')
BACKUPS=BASE/'backups'
STATE=BACKUPS/'.vector-incremental'
OLD='bf874c025ed3d8e95b623016237345d7f5be26bb'
CRON=Path('/etc/cron.d/vector-fegcraft-backup')
CRON_CONTENT=b'0 3 * * * root /opt/fegcraft-updated/backup_minecraft.sh >> /opt/fegcraft-updated/backup.log 2>&1\n'
HOLD=b"#!/usr/bin/env python3\nprint('BACKUP_PAUSED_PENDING_INCREMENTAL_SETUP: Minecraft bleibt online. Kein Backup erstellt.', flush=True)\nraise SystemExit(75)\n"


def sha(raw):return hashlib.sha256(raw).hexdigest()


def safe(path):
    if any(p.is_symlink() for p in (path,*path.parents)):raise RuntimeError('INCREMENTAL_INSTALL_SYMLINK')


def read(path):
    safe(path);meta=path.stat()
    if not stat.S_ISREG(meta.st_mode) or meta.st_uid!=0 or meta.st_mode&0o022 or meta.st_size>2_000_000:
        raise RuntimeError('INCREMENTAL_INSTALL_UNEXPECTED_FILE')
    return path.read_bytes()


def run(args,*,input=None,timeout=30):
    result=subprocess.run(args,input=input,capture_output=True,timeout=timeout)
    if result.returncode:raise RuntimeError('INCREMENTAL_SETUP_COMMAND_FAILED:'+args[0])
    return result.stdout


def atomic(path,raw,mode=0o600):
    safe(path);temporary=path.parent/('.vector-incremental-'+secrets.token_hex(8))
    try:
        fd=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,mode)
        with os.fdopen(fd,'wb') as handle:
            os.fchmod(handle.fileno(),mode);handle.write(raw);handle.flush();os.fsync(handle.fileno())
        os.replace(temporary,path)
        fd=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
        try:os.fsync(fd)
        finally:os.close(fd)
    finally:temporary.unlink(missing_ok=True)


def pause_lines(raw):
    text=raw.decode();lines=text.splitlines(keepends=True);count=0;result=[]
    for line in lines:
        active=line.lstrip()
        match=(not active.startswith('#') and '/opt/fegcraft-updated' in line
               and re.search(r'\bbackup_minecraft\.(?:sh|py)\b',line))
        if match:result.append('# VECTOR_INCREMENTAL_REPLACED '+line);count+=1
        else:result.append(line)
    return ''.join(result).encode(),count


def pause_cron(directory):
    count=0
    result=subprocess.run(['crontab','-l'],capture_output=True,timeout=15)
    if result.returncode==0:
        new,n=pause_lines(result.stdout)
        if n:
            atomic(directory/'root-crontab.before',result.stdout)
            run(['crontab','-'],input=new);count+=n
    elif result.returncode!=1 or b'no crontab' not in result.stderr.lower():
        raise RuntimeError('INCREMENTAL_ROOT_CRON_UNREADABLE')
    paths=[Path('/etc/crontab'),*sorted(Path('/etc/cron.d').glob('*'))]
    for path in paths:
        if path==CRON or not path.is_file():continue
        raw=read(path);new,n=pause_lines(raw)
        if n:
            atomic(directory/('cron-'+sha(str(path).encode())+'.before'),raw)
            atomic(path,new,stat.S_IMODE(path.stat().st_mode));count+=n
    return count


def install():
    revision=os.environ.get('VECTOR_BACKUP_REV','')
    if not re.fullmatch('[a-f0-9]{40}',revision) or os.geteuid()!=0:raise RuntimeError('ROOT_AND_PIN_REQUIRED')
    for path in (ROOT,BASE,BACKUPS,STATE,CRON,ROOT/'.chat-release.lock',BACKUPS/'.backup.lock'):safe(path)
    with (ROOT/'.chat-release.lock').open('a') as release,(BACKUPS/'.backup.lock').open('a') as backup:
        fcntl.flock(release,fcntl.LOCK_EX|fcntl.LOCK_NB);fcntl.flock(backup,fcntl.LOCK_EX|fcntl.LOCK_NB)
        engine=run(['git','-C',str(REPO),'show',revision+':scripts/maintenance/fegcraft-incremental-backup.py']);ast.parse(engine)
        old=run(['git','-C',str(REPO),'show',OLD+':scripts/maintenance/fegcraft-backup.py'])
        shell=run(['git','-C',str(REPO),'show',OLD+':scripts/maintenance/fegcraft-backup.sh'])
        target=BASE/'backup_minecraft.py'
        if read(BASE/'backup_minecraft.sh')!=shell or read(target) not in (old,HOLD,engine):
            raise RuntimeError('INCREMENTAL_EXISTING_BACKUP_CHANGED')
        if CRON.exists() and read(CRON) not in (CRON_CONTENT,b'# VECTOR_DISABLED '+CRON_CONTENT):raise RuntimeError('INCREMENTAL_CRON_FILE_ALREADY_EXISTS')
        directory=ROOT/'releases'/('vector-incremental-backup-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+secrets.token_hex(3))
        directory.mkdir(mode=0o700);print('Einrichtung und private Originalsicherung: '+str(directory),flush=True)
        atomic(directory/'backup.before.py',read(target));atomic(directory/'backup.before.sh',shell)
        atomic(directory/'installer.py',Path(__file__).read_bytes(),0o700)
        atomic(directory/'expected-engine.sha256',(sha(engine)+'\n').encode())
        atomic(directory/'disable.sh',('#!/bin/sh\nset -eu\nexec python3 '+str(directory/'installer.py')+' --disable '+str(directory)+'\n').encode(),0o700)
        # First prevent the existing 03:00 job from invoking the long offline path.
        atomic(target,HOLD,0o700)
        print('Alter Offline-Backup-Einstieg pausiert. Minecraft bleibt unverändert; bei Einrichtungsfehlern wird kein Backup ausgeführt.',flush=True)
        paused=pause_cron(directory)
        missing=[name for name in ('restic','rsync','ionice','nice') if shutil.which(name) is None]
        if missing:
            if os.environ.get('VECTOR_INSTALL_BACKUP_PACKAGES')!='1':
                print(json.dumps({'old_offline_backup_held':True,'old_cron_entries_paused':paused,'missing_dependencies':missing,'minecraft_changed':False}))
                raise RuntimeError('INCREMENTAL_DEPENDENCIES_REQUIRE_SETUP_FLAG')
            # Signed distribution packages; no upgrade or removal of existing services.
            log=directory/'packages.log'
            with log.open('wb') as output:
                packages=sorted({{'restic':'restic','rsync':'rsync','ionice':'util-linux','nice':'coreutils'}[name] for name in missing})
                for args in (['apt-get','update'],['apt-get','install','-y','--no-upgrade','--no-install-recommends',*packages]):
                    value=subprocess.run(args,stdout=output,stderr=subprocess.STDOUT,timeout=300,env={**os.environ,'DEBIAN_FRONTEND':'noninteractive'})
                    if value.returncode:raise RuntimeError('INCREMENTAL_PACKAGE_SETUP_FAILED')
        if any(shutil.which(name) is None for name in ('restic','rsync','ionice','nice')):raise RuntimeError('INCREMENTAL_DEPENDENCIES_MISSING')
        safe(STATE)
        if not STATE.exists():STATE.mkdir(mode=0o700)
        if STATE.stat().st_uid!=0 or STATE.stat().st_mode&0o077:raise RuntimeError('INCREMENTAL_STATE_PERMISSIONS')
        stage=STATE/'staging';repo=STATE/'repository';password=STATE/'password';owner=STATE/'owner.json'
        for path in (stage,repo,password,owner):safe(path)
        if not stage.exists():stage.mkdir(mode=0o700)
        if not password.exists():atomic(password,(secrets.token_hex(32)+'\n').encode())
        def restic(*args):return ['restic','--repo',str(repo),'--password-file',str(password),*args]
        if not owner.exists():
            if repo.exists():raise RuntimeError('INCREMENTAL_UNOWNED_REPOSITORY_PRESERVED')
            run(restic('init','--repository-version','2'),timeout=120)
            config=json.loads(run(restic('cat','config')))
            if config.get('version')!=2 or not re.fullmatch('[a-f0-9]{64}',config.get('id','')):raise RuntimeError('INCREMENTAL_REPOSITORY_INVALID')
            atomic(owner,(json.dumps({'schema':1,'repository_id':config['id']})+'\n').encode())
        config=json.loads(read(owner));actual=json.loads(run(restic('cat','config')))
        for path in (password,owner):
            if path.stat().st_uid!=0 or path.stat().st_mode&0o077:raise RuntimeError('INCREMENTAL_PRIVATE_FILE_PERMISSIONS')
        if set(config)!={'schema','repository_id'} or config['schema']!=1 or not re.fullmatch('[a-f0-9]{64}',config.get('repository_id','')):
            raise RuntimeError('INCREMENTAL_OWNER_METADATA_INVALID')
        if actual.get('id')!=config.get('repository_id') or actual.get('version')!=2:raise RuntimeError('INCREMENTAL_REPOSITORY_ID_CHANGED')
        # New job becomes active only after dependencies and the owned repo work.
        atomic(target,engine,0o700);atomic(CRON,CRON_CONTENT,0o644)
        atomic(directory/'result.json',(json.dumps({'installed':True,'engine_sha256':sha(engine),'old_cron_entries_paused':paused,
              'schedule_server_local_time':'03:00','first_copy_online':True,'final_sync_seconds':45,
              'retention':{'daily':7,'weekly':4,'monthly':2},'backup_performed':False,'minecraft_changed':False,
              'legacy_archives_deleted':0},indent=2)+'\n').encode())
        print((directory/'result.json').read_text())
        print('Nightly-Backup eingerichtet. Keine Sicherung, kein Minecraft-Stop und keine Archivlöschung bei dieser Einrichtung.')
        print('Die erste Vorabkopie läuft online. Nur der finale Delta-Abgleich benötigt einen regulären Stop; Start und Stop selbst sind zusätzlich zur 45-Sekunden-Grenze.')
        print('Job bei Bedarf sicher deaktivieren: '+str(directory/'disable.sh'))


def disable(directory):
    if os.geteuid()!=0:raise RuntimeError('ROOT_REQUIRED')
    safe(directory)
    if directory.parent!=ROOT/'releases' or not directory.name.startswith('vector-incremental-backup-'):
        raise RuntimeError('INCREMENTAL_DISABLE_RELEASE_INVALID')
    with (ROOT/'.chat-release.lock').open('a') as release,(BACKUPS/'.backup.lock').open('a') as backup:
        fcntl.flock(release,fcntl.LOCK_EX|fcntl.LOCK_NB);fcntl.flock(backup,fcntl.LOCK_EX|fcntl.LOCK_NB)
        expected=read(directory/'expected-engine.sha256').decode().strip()
        target=BASE/'backup_minecraft.py'
        if sha(read(target))!=expected and read(target)!=HOLD:raise RuntimeError('INCREMENTAL_DISABLE_ENTRYPOINT_CHANGED')
        if CRON.exists() and read(CRON) not in (CRON_CONTENT,b'# VECTOR_DISABLED '+CRON_CONTENT):
            raise RuntimeError('INCREMENTAL_DISABLE_CRON_CHANGED')
        atomic(target,HOLD,0o700)
        if CRON.exists():atomic(CRON,b'# VECTOR_DISABLED '+CRON_CONTENT,0o644)
        print('Backup pausiert. Repository, Passwort, Staging und alte Archive bleiben erhalten. Alter Offline-Job bleibt deaktiviert.')


if __name__=='__main__':
    os.umask(0o077)
    try:
        if len(sys.argv)==1:install()
        elif len(sys.argv)==3 and sys.argv[1]=='--disable':disable(Path(sys.argv[2]))
        else:raise RuntimeError('INCREMENTAL_INSTALL_ARGUMENTS_INVALID')
    except Exception as exc:
        print('ERROR: '+(str(exc) if isinstance(exc,RuntimeError) else type(exc).__name__)+'. Prüfe die privaten Einrichtungsbelege; kein Minecraft-Neustart durch dieses Skript.',file=sys.stderr)
        raise SystemExit(1)
