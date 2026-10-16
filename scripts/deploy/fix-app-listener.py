#!/usr/bin/env python3
"""Repair the confirmed multi-network Next.js bind without rebuilding the image."""
import ast
import copy
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys
import time

ROOT=Path('/root/vector-workspace')
COMPOSE=Path('/opt/vector/docker-compose.yml')
BASE=ROOT/'releases/vector-chat-controls-release-20261016T233346Z-341cd8'
IMAGE='sha256:5a2ee0f4b1b169114da5608a8a33f0ca08ce00c4016873208fa1d5518901f87d'
OTHERS=('vector-worker','vector-runner','vector-postgres','vector-redis','vector-local-inference','vector-privacy-ner','fegcraft-updated')


def candidate(raw):
    text=raw.decode();lines=text.splitlines(keepends=True)
    starts=[i for i,line in enumerate(lines) if re.fullmatch(r'  app:\s*\n',line)]
    if len(starts)!=1 or '\r' in text:raise RuntimeError('Unexpected app configuration layout.')
    start=starts[0];end=next((i for i in range(start+1,len(lines)) if re.match(r'^\S|^  [^\s#]',lines[i])),len(lines))
    entries=[i for i in range(start+1,end) if re.fullmatch(r'    environment:\s*\n',lines[i])]
    if len(entries)!=1:raise RuntimeError('Expected one app environment mapping.')
    env=entries[0];env_end=next((i for i in range(env+1,end) if re.match(r'^    [^\s#]',lines[i])),end)
    if any(re.match(r'^\s*- ',line) for line in lines[env+1:env_end]):raise RuntimeError('Environment list requires separate review.')
    host=[i for i in range(env+1,env_end) if re.match(r'^      HOSTNAME\s*:',lines[i])]
    if len(host)>1:raise RuntimeError('Ambiguous HOSTNAME setting.')
    if host:lines[host[0]]='      HOSTNAME: "0.0.0.0"\n'
    else:lines.insert(env+1,'      HOSTNAME: "0.0.0.0"\n')
    return ''.join(lines).encode()


def helpers():
    path=BASE/'release.sh';source=path.read_text()
    begin="<<'CHAT_CONTROLS_RELEASE_PYTHON'\n";end='\nCHAT_CONTROLS_RELEASE_PYTHON\n'
    if source.count(begin)!=1 or source.count(end)!=1:raise RuntimeError('Unexpected release helper structure.')
    n={'__name__':'listener_repair_helpers'}
    exec(compile(ast.parse(source.split(begin,1)[1].split(end,1)[0]),str(path),'exec'),n)
    if n.get('TESTED_IMAGE')!=IMAGE:raise RuntimeError('Unexpected release helper image.')
    return n['prepare']()['prepare']()


PROBE=r"""
(async()=>{
 const os=require('node:os');
 const hosts=[...new Set(['127.0.0.1',...Object.values(os.networkInterfaces()).flat().filter(x=>x.family==='IPv4').map(x=>x.address)])];
 if(hosts.length<2)throw Error('No app network address');
 for(const host of hosts){
  const r=await fetch('http://'+host+':'+(process.env.PORT||'3000')+'/api/health',{signal:AbortSignal.timeout(2000),redirect:'manual'});
  const body=await r.json();if(r.status!==200||body.database!=='ok'||body.redis!=='ok')throw Error('Unhealthy app interface');
 }
 console.log(JSON.stringify({all_interfaces_healthy:true,count:hosts.length}));
})().catch(()=>process.exitCode=1);
"""


def main():
    os.umask(0o077)
    if os.geteuid()!=0:raise RuntimeError('Run as root.')
    with (ROOT/'.chat-release.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        h=helpers();run=h['run'];obj=h['obj'];atomic=h['atomic']
        record=json.loads((BASE/'release.json').read_text())
        original=COMPOSE.read_bytes();meta=COMPOSE.stat()
        if (COMPOSE.is_symlink() or record.get('status')!='deployed' or record.get('image_id')!=IMAGE
                or original!=(BASE/'compose.candidate.yml').read_bytes() or obj('vector-app')['Image']!=IMAGE):
            raise RuntimeError('Current app/profile differs from the confirmed release. No changes made.')
        source_hash=h['tree_hash'](h['LIVE'])
        if source_hash!=record['new_source_hash']:raise RuntimeError('Live source changed.')
        others={name:h['identity'](name) for name in OTHERS}
        sql=b"SELECT COUNT(*) FROM agent_jobs WHERE status IN ('queued','running');\n"
        idle=h['text']('docker','exec','-i','vector-postgres','sh','-ec',
            'exec psql -X -A -t -v ON_ERROR_STOP=1 -U "${POSTGRES_USER:-postgres}" -d "${POSTGRES_DB:-postgres}"',data=sql)
        if idle!='0':raise RuntimeError('Wait until background jobs are idle.')
        run('nginx','-t')
        before=h['config'](COMPOSE);expected=copy.deepcopy(before)
        expected['services']['app'].setdefault('environment',{})['HOSTNAME']='0.0.0.0'
        if before==expected:raise RuntimeError('HOSTNAME is already set; diagnose the startup command instead.')
        new=candidate(original)
        stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+secrets.token_hex(3)
        folder=ROOT/'releases'/('vector-listener-fix-'+stamp);folder.mkdir(mode=0o700)
        atomic(folder/'compose.original.yml',original,0o600,0,0)
        atomic(folder/'compose.candidate.yml',new,0o600,0,0)
        state={'status':'prepared','image_id':IMAGE,'source_hash':source_hash,'other_containers':others}
        def save(): (folder/'result.json').write_text(json.dumps(state,indent=2)+'\n')
        save();print('Repair evidence:',folder,flush=True)
        # Resolve candidate relative mounts/env files using the production project directory.
        if h['config'](folder/'compose.candidate.yml')!=expected:
            raise RuntimeError('Candidate changes more than app.environment.HOSTNAME.')
        if COMPOSE.read_bytes()!=original or h['tree_hash'](h['LIVE'])!=source_hash:
            raise RuntimeError('Production changed during preparation.')
        h['verify_others'](others)
        try:
            atomic(COMPOSE,new,meta.st_mode&0o777,meta.st_uid,meta.st_gid)
            h['compose_up']()
            healthy=False
            for _ in range(30):
                try:
                    run('docker','exec','vector-app','node','-e',PROBE,timeout=20)
                    healthy=True;break
                except (RuntimeError,subprocess.TimeoutExpired):time.sleep(1)
            if not healthy:raise RuntimeError('App does not pass health on every interface.')
            if obj('vector-app')['Image']!=IMAGE or h['config'](COMPOSE)!=expected:
                raise RuntimeError('App image or persistent configuration differs.')
            h['verify_others'](others)
            run('nginx','-t');run('systemctl','reload','nginx')
            # Exercise the actual host Nginx/TLS route, not just any container IP.
            status=h['text']('curl','--silent','--show-error','--output','/dev/null','--write-out','%{http_code}',
                '--connect-timeout','3','--max-time','10','--resolve','vector.kibouakari.com:443:127.0.0.1',
                'https://vector.kibouakari.com/api/health',timeout=15)
            if status!='200':raise RuntimeError('Host Nginx route is not healthy.')
            if h['tree_hash'](h['LIVE'])!=source_hash:raise RuntimeError('App source changed.')
            state.update(status='deployed',all_interfaces_healthy=True,nginx_http_status=200)
            save();print('LISTENER FIX SUCCEEDED: all app interfaces and the Nginx HTTPS route passed.')
            print('Evidence and original Compose:',folder)
            print('Same app image/source; other production containers unchanged. No model requests.')
        except BaseException:
            if COMPOSE.read_bytes()!=new:raise RuntimeError('Compose changed; refusing rollback overwrite.')
            atomic(COMPOSE,original,meta.st_mode&0o777,meta.st_uid,meta.st_gid)
            h['compose_up']();state['status']='rolled-back';save()
            print('Original Compose restored. Inspect the application/proxy before retrying.',file=sys.stderr)
            raise


if __name__=='__main__':
    try:main()
    except Exception as exc:
        print('ERROR:',str(exc) if isinstance(exc,RuntimeError) else type(exc).__name__,file=sys.stderr)
        raise SystemExit(1)
