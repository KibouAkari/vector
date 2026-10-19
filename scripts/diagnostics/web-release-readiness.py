#!/usr/bin/env python3
"""Read-only web deployment inventory. No DB, model, restart or game actions."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

def run(args,timeout=20):
    result=subprocess.run(args,capture_output=True,text=True,timeout=timeout)
    if result.returncode:raise RuntimeError('READ_ONLY_COMMAND_FAILED')
    return result.stdout

def snapshot():
    ids=run(['docker','ps','-aq']).split()
    if not ids:raise RuntimeError('NO_CONTAINERS')
    result={}
    for row in json.loads(run(['docker','inspect',*ids])):
        name=row['Name'].lstrip('/')
        result[name]={
            'id':row['Id'],'image_id':row['Image'],'running':row['State']['Running'],
            'oom_killed':row['State'].get('OOMKilled',False),
            'started_at':row['State'].get('StartedAt'),
            'mount_targets':sorted(m['Destination'] for m in row.get('Mounts',[])),
            'operator_app_source_bound':any(m.get('Source')=='/opt/vector/app' for m in row.get('Mounts',[])),
            'mount_fingerprints':sorted(hashlib.sha256(json.dumps(m,sort_keys=True).encode()).hexdigest() for m in row.get('Mounts',[]))}
    return result

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--app',default='vector-app')
    parser.add_argument('--worker',default='vector-worker')
    parser.add_argument('--source',type=Path,default=Path('/opt/vector/app'))
    parser.add_argument('--compose',type=Path,default=Path('/opt/vector/docker-compose.yml'))
    args=parser.parse_args()
    before=snapshot()
    if args.app not in before:raise RuntimeError('WEB_APP_NOT_FOUND')
    compose=hashlib.sha256(args.compose.read_bytes()).hexdigest() if args.compose.is_file() else None
    # Read only known source files. Never print environment values, tokens, paths or configuration.
    code="""const fs=require('node:fs'),crypto=require('node:crypto');
const hashes={};
for(const file of ['lib/privacy-review.js','lib/local-private-chat.js','lib/chat-controls.mjs','lib/local-context.mjs']) {
 try {hashes[file]=crypto.createHash('sha256').update(fs.readFileSync('/app/'+file)).digest('hex');}
 catch {hashes[file]=null;}
}
console.log(JSON.stringify({source_hashes:hashes,
privacy_enabled:process.env.VECTOR_PRIVACY_REVIEW==='1',
local_enabled:process.env.VECTOR_LOCAL_WORKERS==='1',
statistics_source_configured:Boolean(process.env.VECTOR_MINECRAFT_DATA_PATH),
server_aliases_configured:Boolean(process.env.VECTOR_MINECRAFT_SERVER_ALIASES)}));"""
    source_hashes={}
    for name in ('lib/privacy-review.js','lib/local-private-chat.js','lib/chat-controls.mjs','Dockerfile','package-lock.json'):
        path=args.source/name
        source_hashes[name]=hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() and not path.is_symlink() else None
    runtime=json.loads(run(['docker','exec',args.app,'node','-e',code]))
    after=snapshot()
    unchanged=before==after and (not args.compose.is_file() or hashlib.sha256(args.compose.read_bytes()).hexdigest()==compose)
    print(json.dumps({'read_only':True,'app':before[args.app],'worker':before.get(args.worker),
        'runtime':runtime,'host_source_hashes':source_hashes,'compose_sha256':compose,'production_unchanged':unchanged,
        'containers_observed':len(before),'model_calls':0,'database_writes':False,'messages_sent':0},indent=2))
    if not unchanged:raise RuntimeError('LIVE_STATE_CHANGED_DURING_INSPECTION')

if __name__=='__main__':
    try:main()
    except Exception as exc:raise SystemExit('Read-only inventory failed: '+type(exc).__name__)
