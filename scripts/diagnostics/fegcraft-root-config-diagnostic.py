#!/usr/bin/env python3
"""Read failed preservation evidence; print field shapes, never private values."""
import fcntl
import hashlib
import json
from pathlib import Path
import re
import stat
import subprocess
import sys
ROOT = Path('/root/vector-workspace')
RELEASE = ROOT / 'releases/vector-fegcraft-chat-identity-20261018T170016Z-a8c95f'
LABEL = 'com.vector.fegcraft-root-preservation'
KEYS = ('Entrypoint','Cmd','Env','User','WorkingDir','Volumes','ExposedPorts','Healthcheck','StopSignal','Shell','OnBuild')


def read(path):
    if any(p.is_symlink() for p in (path, *path.parents)): raise RuntimeError('DIAGNOSTIC_SYMLINK')
    meta = path.stat()
    if not stat.S_ISREG(meta.st_mode) or meta.st_size > 2000000: raise RuntimeError('DIAGNOSTIC_FILE_LIMIT')
    return path.read_bytes()


def inspect(kind, name):
    r = subprocess.run(['docker',kind,'inspect',name],capture_output=True,timeout=15)
    if r.returncode or len(r.stdout)>2000000: raise RuntimeError('DIAGNOSTIC_INSPECT_FAILED')
    return json.loads(r.stdout)[0]


def shape(value):
    result={'type':type(value).__name__}
    if isinstance(value,(dict,list,str)): result['length']=len(value)
    return result


def differences(expected, actual):
    rows=[]
    for key in KEYS:
        left,right=expected.get(key),actual.get(key)
        if left==right: continue
        row={'field':key,'container':shape(left),'committed_image':shape(right)}
        if isinstance(left,list) and isinstance(right,list):
            row['equal_ignoring_order']=sorted(json.dumps(x,sort_keys=True) for x in left)==sorted(json.dumps(x,sort_keys=True) for x in right)
        if isinstance(left,dict) and isinstance(right,dict):
            row['same_key_set']=set(left)==set(right)
            row['changed_value_count']=sum(left.get(k)!=right.get(k) for k in set(left)|set(right))
        rows.append(row)
    return rows


def main():
    sys.dont_write_bytecode=True
    lock=ROOT/'.chat-release.lock'
    if lock.is_symlink(): raise RuntimeError('DIAGNOSTIC_SYMLINK')
    with lock.open('rb') as handle:
        fcntl.flock(handle,fcntl.LOCK_SH|fcntl.LOCK_NB)
        raw=read(RELEASE/'plan.json'); plan=json.loads(raw)
        if plan.get('revision')!='3cabf8cf82b042deeac88f6bc4ac6ccfde090f30' or plan.get('recreation_started') is not False:
            raise RuntimeError('DIAGNOSTIC_UNEXPECTED_RELEASE')
        game=inspect('container','fegcraft-updated')
        intent=json.loads(read(RELEASE/'root-preservation-intent.json')); record=json.loads(read(RELEASE/'root-preservation-image.json'))
        if (game['Id']!=plan['original_container'] or game['Image']!=plan['original_image']
            or intent.get('container')!=game['Id'] or intent.get('parent_image')!=game['Image']
            or intent.get('owner')!=record.get('owner') or intent.get('tag')!=record.get('tag')):
            raise RuntimeError('DIAGNOSTIC_PRESERVATION_OWNER_CHANGED')
        image=inspect('image',record['image']); parent=inspect('image',game['Image'])
        if image['Config'].get('Labels',{}).get(LABEL)!=record['owner']: raise RuntimeError('DIAGNOSTIC_IMAGE_OWNER_CHANGED')
        rows=differences(game['Config'],image['Config'])
        labels=dict(game['Config'].get('Labels') or {},**{LABEL:record['owner']})
        if image['Config'].get('Labels')!=labels:
            rows.append({'field':'Labels','expected':shape(labels),'committed_image':shape(image['Config'].get('Labels'))})
        addon_rows=[r for r in plan['files'] if Path(r['path']).suffix=='.jar']
        addon_restored=len(addon_rows)==1 and hashlib.sha256(read(Path(addon_rows[0]['path']))).hexdigest()==addon_rows[0]['before']
        bridge_rows=[r for r in plan['files'] if Path(r['path']).name=='bridge.properties']
        if len(bridge_rows)!=1: raise RuntimeError('DIAGNOSTIC_BRIDGE_AMBIGUOUS')
        bridge={}
        for line in read(Path(bridge_rows[0]['path'])).decode().splitlines():
            key,separator,value=line.partition('=')
            if separator and key.strip() in ('discordInputEnabled','avatarUrl','logoTexture'): bridge[key.strip()]=value.strip()
        state=game['State']; after=inspect('container','fegcraft-updated')
        print(json.dumps(dict(read_only=True,release_status=plan.get('status'),recreation_started=False,
            same_original_game=True,previous_addon_restored=addon_restored,discord_input_enabled=bridge.get('discordInputEnabled')=='true',avatar_configured=bool(bridge.get('avatarUrl')),head_configured=bool(bridge.get('logoTexture')),game_running=state['Running'],game_health=state.get('Health',{}).get('Status'),
            game_oom_killed=state.get('OOMKilled',False),image_config_differences=rows,
            parent_layers_retained=image['RootFS']['Layers'][:len(parent['RootFS']['Layers'])]==parent['RootFS']['Layers'],
            os_matches=image.get('Os')==parent.get('Os'),architecture_matches=image.get('Architecture')==parent.get('Architecture'),
            observed_game_unchanged=all(game.get(k)==after.get(k) for k in ('Id','Image','Config','HostConfig')) and state['StartedAt']==after['State']['StartedAt'],
            release_evidence_unchanged=read(RELEASE/'plan.json')==raw,model_calls=0,messages_sent=0),indent=2))


if __name__=='__main__':
    try: main()
    except Exception as exc:
        value=str(exc)
        print('ERROR: '+(value if type(exc) is RuntimeError and re.fullmatch('[A-Z_]{3,100}',value) else type(exc).__name__),file=sys.stderr)
        raise SystemExit(1)
