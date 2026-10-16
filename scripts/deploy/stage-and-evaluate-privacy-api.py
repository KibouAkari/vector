#!/usr/bin/env python3
"""Build/stage the pinned privacy revision, then qualify that exact app image."""
import ast
from collections import deque
import fcntl
import os
from pathlib import Path
import re
import subprocess
import uuid

ROOT=Path('/root/vector-workspace')
REPO=ROOT/'github/vector'
BRANCH='fix/privacy-routing-capabilities-20261016'


def staging_handoff(output,revision):
    if '=== PRIVACY STAGING PASSED ===' not in output:
        raise RuntimeError('No successful privacy staging handoff.')
    commits=re.findall(r'^Commit: ([a-f0-9]{40})$',output,re.M)
    images=re.findall(r'^Image ID: (sha256:[a-f0-9]{64})$',output,re.M)
    tags=re.findall(r'^Image tag: (vector-app:staging-[^\s]+)$',output,re.M)
    if commits!=[revision] or len(images)!=1 or len(tags)!=1 or not tags[0].startswith('vector-app:staging-'+revision[:7]+'-'):
        raise RuntimeError('Staging revision/image handoff is missing or ambiguous.')
    return {'VECTOR_PRIVACY_API_APP_REV':revision,'VECTOR_PRIVACY_API_APP_IMAGE_ID':images[0]}


def prepare(revision,path,target):
    content=subprocess.check_output(['git','-C',str(REPO),'show',revision+':'+path],text=True)
    if target.suffix=='.py':ast.parse(content)
    else:subprocess.run(['bash','-n'],input=content,text=True,check=True)
    fd=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o700)
    with os.fdopen(fd,'w') as handle:handle.write(content)


def execute(script,environment):
    # Keep success metadata at the end of bounded captured output. Full progress
    # is streamed to the owner and the existing runner's private logs.
    lines=deque(maxlen=4000)
    command=['python3' if script.suffix=='.py' else 'bash',str(script)]
    with subprocess.Popen(command,env=environment,
            stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True) as process:
        for line in process.stdout:
            print(line,end='',flush=True);lines.append(line[:32768])
        code=process.wait()
    if code:raise RuntimeError('Privacy subphase failed. See the runner output above; production was not activated.')
    return ''.join(lines)


def main():
    os.umask(0o077)
    revision=os.environ.get('VECTOR_PRIVACY_REV','')
    if os.geteuid()!=0 or not re.fullmatch('[a-f0-9]{40}',revision):
        raise RuntimeError('Run as root with exact VECTOR_PRIVACY_REV.')
    fetched=subprocess.check_output(['git','-C',str(REPO),'rev-parse','refs/remotes/origin/'+BRANCH],text=True).strip()
    if fetched!=revision:raise RuntimeError('Fetched branch revision changed.')
    # Child stages take the ordinary release lock themselves.
    with (ROOT/'.privacy-pipeline.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        suffix=revision[:7]+'-'+uuid.uuid4().hex[:8]
        release=ROOT/'releases'/('vector-privacy-pipeline-'+suffix);release.mkdir(mode=0o700)
        stage=release/'stage.sh'
        evaluate=release/'evaluate.py'
        prepare(revision,'scripts/deploy/stage-privacy-review.sh',stage)
        prepare(revision,'scripts/deploy/evaluate-privacy-api.py',evaluate)
        environment=dict(os.environ,VECTOR_STAGING_REV=revision)
        # Ignore inherited image overrides: only the successful staged output
        # may choose the exact immutable application image for this run.
        environment.pop('VECTOR_PRIVACY_API_APP_REV',None)
        environment.pop('VECTOR_PRIVACY_API_APP_IMAGE_ID',None)
        output=execute(stage,environment)
        environment.update(staging_handoff(output,revision))
        execute(evaluate,environment)
        print('Privacy staging and enabled API qualification passed. No production deployment or feature activation performed.',flush=True)

if __name__=='__main__':
    try:main()
    except Exception as exc:
        print('ERROR:',str(exc) if isinstance(exc,RuntimeError) else type(exc).__name__)
        raise SystemExit(1)
