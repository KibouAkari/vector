#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
VECTOR_RELEASE_SCRIPT="${BASH_SOURCE[0]}" python3 - "$@" <<'CHAT_CONTROLS_RELEASE_PYTHON'
import ast
import json
import os
import re
import sys
from pathlib import Path

ROOT=Path('/root/vector-workspace')
SCRIPT=ROOT/'archive/phases/vector-control-release.sh'
TESTED='e8b6b6e690aa893e3fc0a0641e07261c0414ffc6'
MERGED='2f5b8e866f613b336ed24b5242dc93e535c985bc'
CURRENT='60adca9398dff938e97df4f00bf8a2c476dde907'
CURRENT_IMAGE='sha256:c33a1b853a16602e9413f4784de85337135288f55cf2437e6516b46ccfd463c0'
TESTED_IMAGE='sha256:5a2ee0f4b1b169114da5608a8a33f0ca08ce00c4016873208fa1d5518901f87d'


def private_json(path):
    if path.is_symlink() or path.parent.is_symlink() or not path.is_file() or path.stat().st_size>200000:
        raise RuntimeError('Unexpected qualification report path.')
    return json.loads(path.read_text())


def qualification_gate():
    previous=ROOT/'releases/vector-runtime-privacy-release-20261016T165856Z-c0c023'
    record=private_json(previous/'release.json')
    if (record.get('status')!='deployed' or record.get('commit')!=CURRENT
            or record.get('image_id')!=CURRENT_IMAGE
            or Path('/opt/vector/docker-compose.yml').read_bytes()!=(previous/'compose.candidate.yml').read_bytes()):
        raise RuntimeError('Active profile differs from the confirmed runtime release. No deployment performed.')
    read=private_json(ROOT/'releases/vector-chat-server-read-20261016T231729Z-306171/result.json')
    if (any(read.get(k) is not True for k in ('passed','snapshot_available','statistics_complete','production_unchanged'))
            or read.get('revision')!=TESTED or type(read.get('files')) is not int
            or read['files']<=0 or read.get('cloud_calls')!=0 or read.get('model_calls')!=0):
        raise RuntimeError('Actual server-read qualification differs.')
    path=Path(os.environ.get('VECTOR_CHAT_API_REPORT',''))
    if (path.name!='result.json' or path.parent.parent!=ROOT/'releases'
            or not re.fullmatch(r'vector-privacy-api-evaluation-[0-9]{8}T[0-9]{6}Z-[a-f0-9]{6}',path.parent.name)):
        raise RuntimeError('Expected isolated API report handoff.')
    report=private_json(path)
    revision=os.environ.get('VECTOR_CHAT_RELEASE_REV','')
    if (not re.fullmatch('[a-f0-9]{40}',revision) or report.get('revision')!=revision
            or report.get('app_runtime_revision')!=TESTED or report.get('app_image')!=TESTED_IMAGE
            or report.get('native_image')!='sha256:eca0b83a886fcc9952ef13755853ef63134e5c76733d40564460398776c92dd7'
            or any(report.get(k) is not True for k in ('passed','isolated_database','production_unchanged','cleanup_verified'))
            or report.get('production_activated') is not False or report.get('cloud_calls')!=0):
        raise RuntimeError('Enabled privacy API qualification differs or cleanup is incomplete.')
    for phase,required in [('normal',('explicit-off-preserves-original-and-skips-detector-normal',
            'off-restores-owned-historical-placeholders-without-rescan','privacy-off-cannot-override-local-only-project')),
            ('outage',('native-service-outage-blocks-cloud-send-before-writes',
            'explicit-off-preserves-original-and-skips-detector-outage','local-request-remains-quiet-during-detector-outage'))]:
        result=report.get(phase,{})
        if (result.get('passed') is not True or result.get('phase')!=phase or result.get('cloud_calls')!=0
                or result.get('executed_jobs')!=0 or not set(required).issubset(result.get('checks',[]))):
            raise RuntimeError('Missing privacy switch/outage qualification.')


def prepare():
    source=SCRIPT.read_text();begin="<<'CONTROL_RELEASE_PYTHON'\n";end='\nCONTROL_RELEASE_PYTHON\n'
    if source.count(begin)!=1 or source.count(end)!=1:raise RuntimeError('Unexpected archived release structure.')
    tree=ast.parse(source.split(begin,1)[1].split(end,1)[0])
    class Labels(ast.NodeTransformer):
        def visit_Constant(self,node):
            replacements={'vector-control-release-':'vector-chat-controls-release-',
                '.vector-control-stage-':'.vector-chat-controls-stage-',
                '.vector-control-backup-':'.vector-chat-controls-backup-',
                '.vector-control-candidate-':'.vector-chat-controls-candidate-',
                '.vector-control-failed-':'.vector-chat-controls-failed-',
                '\n=== CONTROL CENTER RELEASE SUCCEEDED ===':'\n=== CHAT CONTROLS RELEASE SUCCEEDED ==='}
            if isinstance(node.value,str) and node.value in replacements:
                return ast.copy_location(ast.Constant(replacements[node.value]),node)
            return node
    n={'__name__':'chat_controls_release_factory'}
    exec(compile(ast.fix_missing_locations(Labels().visit(tree)),str(SCRIPT),'exec'),n)
    if n.get('TESTED')!='1f742366856a17ff7ab3ab01542d1eb7aca0a4a7' or n.get('MERGED')!='d73f6f982db62532a80696d230dd77b01246c057':
        raise RuntimeError('Unexpected archived factory baseline.')
    n.update(TESTED=TESTED,MERGED=MERGED,CURRENT=CURRENT,CURRENT_IMAGE=CURRENT_IMAGE,TESTED_IMAGE=TESTED_IMAGE,
        CURRENT_TAG='vector-app:staging-8611082-20261016T162644Z-22f9a2',
        TESTED_TAG='vector-app:staging-e8b6b6e-20261016T231731Z-6a08fa',
        REPORT=ROOT/'releases/vector-chat-controls-staging-20261016T231731Z-6a08fa/staging-result.json')
    original=n['prepare']
    def guarded_prepare():
        result=original()
        result['OTHERS']=tuple(result['OTHERS'])+('vector-local-inference','vector-privacy-ner','fegcraft-updated')
        idle=result['idle'];checked=False
        def guarded_idle():
            nonlocal checked
            # The original main has acquired the exclusive release lock by now.
            # Rollback retains its existing live-source/image/Compose guards.
            if len(sys.argv)==1 and not checked:
                qualification_gate();checked=True
            return idle()
        result['idle']=guarded_idle
        return result
    n['prepare']=guarded_prepare
    return n


if __name__=='__main__':
    try:prepare()['main']()
    except KeyboardInterrupt:
        print('Interrupted. Inspect release status before retrying.',file=sys.stderr);sys.exit(130)
    except Exception as exc:
        print('ERROR:',str(exc) if isinstance(exc,RuntimeError) else type(exc).__name__,file=sys.stderr);sys.exit(1)
CHAT_CONTROLS_RELEASE_PYTHON
