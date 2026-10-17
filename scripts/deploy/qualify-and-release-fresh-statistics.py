#!/usr/bin/env python3
"""Qualify the observed app image, then release it; never rebuild or call a provider."""
import ast
import os
from pathlib import Path
import re
import subprocess

ROOT=Path('/root/vector-workspace')
REPO=ROOT/'github/vector'
TESTED='b9d34da3f07b91f27de1800aba214d507922b760'
IMAGE='sha256:8d4645d72630974981ceb9985332473d41f03563b9a8f52a2b808f63387ec9cd'
CURRENT_IMAGE='sha256:5a2ee0f4b1b169114da5608a8a33f0ca08ce00c4016873208fa1d5518901f87d'


def git(*args):
    result=subprocess.run(['git','-C',str(REPO),*args],capture_output=True,check=True)
    return result.stdout


def release_file(content):
    # Leave differing/failed scripts intact. This path is unique to this release.
    target=ROOT/'current/vector-fresh-statistics-qualified-release.sh'
    subprocess.run(['bash','-n'],input=content,check=True)
    if target.is_symlink():raise RuntimeError('Unexpected release symlink.')
    if target.exists():
        if not target.is_file() or target.read_bytes()!=content:
            raise RuntimeError('A differing release script already exists.')
    else:
        fd=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o700)
        with os.fdopen(fd,'wb') as handle:handle.write(content)
    return target


def main():
    os.umask(0o077)
    revision=os.environ.get('VECTOR_CHAT_RELEASE_REV','')
    if os.geteuid()!=0 or not re.fullmatch('[a-f0-9]{40}',revision):
        raise RuntimeError('Run as root with exact VECTOR_CHAT_RELEASE_REV.')
    git('merge-base','--is-ancestor',revision,'refs/remotes/origin/main')
    os.environ.update(VECTOR_PRIVACY_REV=revision,VECTOR_PRIVACY_API_SOURCE_REF='refs/remotes/origin/main',
        VECTOR_PRIVACY_API_APP_REV=TESTED,VECTOR_PRIVACY_API_APP_IMAGE_ID=IMAGE,
        VECTOR_PRIVACY_API_PRODUCTION_IMAGE=CURRENT_IMAGE)
    # This guarded image-reuse check rejects every runtime/build-input change.
    source=git('show',revision+':scripts/deploy/evaluate-privacy-api.py').decode()
    ast.parse(source);module={'__name__':'chat_controls_isolated_qualification'}
    exec(compile(source,'evaluate-privacy-api.py','exec'),module)
    release=release_file(git('show',revision+':scripts/deploy/release-fresh-statistics.sh'))
    print('Reuse the observed app image. Native privacy on/off and outage qualification runs first; production is unchanged during qualification.',flush=True)
    report=module['main']()
    if not isinstance(report,Path) or not report.is_file():
        raise RuntimeError('No completed API qualification report. Release blocked.')
    os.environ['VECTOR_CHAT_API_REPORT']=str(report)
    print('Isolated qualification and cleanup passed. Start the guarded app-only release with fresh backups and rollback.',flush=True)
    subprocess.run(['bash',str(release)],check=True)


if __name__=='__main__':
    try:main()
    except Exception as exc:
        print('ERROR:',str(exc) if isinstance(exc,RuntimeError) else type(exc).__name__)
        raise SystemExit(1)

