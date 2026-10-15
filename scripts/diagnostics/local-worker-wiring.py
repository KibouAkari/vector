#!/usr/bin/env python3
"""Read-only deployment shape; never print resolved secrets or full Compose YAML."""
import hashlib
import json
from pathlib import Path
import re
import subprocess

COMPOSE = Path('/opt/vector/docker-compose.yml')


def run(*args):
    result = subprocess.run(args, capture_output=True, text=True, timeout=30)
    if result.returncode:
        raise RuntimeError('Read-only deployment inspection failed; no configuration changed.')
    return result.stdout


def flag(value):
    text = str(value).lower()
    if text in ('0', 'false', 'none', ''):
        return 'disabled'
    if text in ('1', 'true'):
        return 'enabled'
    return 'unexpected-value-redacted'


def app_layout(source):
    lines = source.splitlines()
    starts = [index for index,line in enumerate(lines) if re.fullmatch(r'  app:\s*(?:#.*)?', line)]
    if len(starts) != 1:
        return {'style': 'requires-review'}
    start = starts[0]
    end = next((index for index in range(start+1,len(lines))
        if lines[index].strip() and not lines[index].lstrip().startswith('#')
        and len(lines[index])-len(lines[index].lstrip()) <= 2), len(lines))
    result = {}
    for key in ('environment', 'networks'):
        found = [index for index in range(start+1,end) if re.match(r'    '+key+r':', lines[index])]
        if not found:
            result[key] = 'absent'
        elif len(found) != 1:
            result[key] = 'requires-review'
        else:
            index = found[0]
            tail = lines[index].split(':',1)[1].split('#',1)[0].strip()
            children = [line.strip() for line in lines[index+1:end] if line.strip() and not line.lstrip().startswith('#')]
            result[key] = 'inline' if tail else ('list' if children and children[0].startswith('- ') else 'mapping')
    return result


def public_profile(config, containers, source):
    app = config['services']['app']
    reports = {}
    for name,info in containers.items():
        reports[name] = dict(image_id=info['Image'], configured_image=info['Config']['Image'],
            running=info['State']['Running'], networks=sorted(info['NetworkSettings']['Networks']),
            local_workers=flag(next((entry.split('=',1)[1] for entry in info['Config'].get('Env',[])
                if entry.startswith('VECTOR_LOCAL_WORKERS=')), None)))
    return dict(compose_path=str(COMPOSE),compose_sha256=hashlib.sha256(source.encode()).hexdigest(),
        compose_project=config.get('name'),app_image=app.get('image'),app_layout=app_layout(source),
        app_network_keys=sorted(app.get('networks') or {'default':None}),
        app_local_workers=flag((app.get('environment') or {}).get('VECTOR_LOCAL_WORKERS')),
        root_network_keys=sorted(config.get('networks') or {}),
        root_networks={name:dict(external=bool(value.get('external')),name=value.get('name'))
            for name,value in (config.get('networks') or {}).items()},
        containers=reports,read_only=True)


def main():
    if not COMPOSE.is_file() or COMPOSE.is_symlink():
        raise RuntimeError('Expected regular production Compose file missing.')
    source = COMPOSE.read_bytes().decode('utf-8')
    config = json.loads(run('docker','compose','--project-directory',str(COMPOSE.parent),
        '-f',str(COMPOSE),'config','--format','json'))
    containers = {name:json.loads(run('docker','inspect',name))[0]
        for name in ('vector-app','vector-worker','vector-local-inference')}
    print(json.dumps(public_profile(config,containers,source),indent=2))


if __name__ == '__main__':
    main()
