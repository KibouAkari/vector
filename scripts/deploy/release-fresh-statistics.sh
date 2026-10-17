#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
VECTOR_RELEASE_SCRIPT="${BASH_SOURCE[0]}" python3 - "$@" <<'FRESH_STATISTICS_RELEASE_PYTHON'
import ast
import json
import os
import re
import sys
from pathlib import Path

ROOT=Path('/root/vector-workspace')
SCRIPT=ROOT/'archive/phases/vector-control-release.sh'
TESTED='b9d34da3f07b91f27de1800aba214d507922b760'
MERGED='fe12d19bbc079074c51de8654e8c830b187923aa'
CURRENT='2f5b8e866f613b336ed24b5242dc93e535c985bc'
CURRENT_IMAGE='sha256:5a2ee0f4b1b169114da5608a8a33f0ca08ce00c4016873208fa1d5518901f87d'
TESTED_IMAGE='sha256:8d4645d72630974981ceb9985332473d41f03563b9a8f52a2b808f63387ec9cd'


def private_json(path):
    if path.is_symlink() or path.parent.is_symlink() or not path.is_file() or path.stat().st_size>200000:
        raise RuntimeError('Unexpected qualification report path.')
    return json.loads(path.read_text())


def qualification_gate():
    previous=ROOT/'releases/vector-chat-controls-release-20261016T233346Z-341cd8'
    repair=ROOT/'releases/vector-listener-fix-20261016T235002Z-913eee'
    repaired=private_json(repair/'result.json')
    record=private_json(previous/'release.json')
    if (record.get('status')!='deployed' or record.get('commit')!=CURRENT
            or record.get('image_id')!=CURRENT_IMAGE
            or repaired.get('status')!='deployed' or repaired.get('image_id')!=CURRENT_IMAGE
            or repaired.get('source_hash')!=record.get('new_source_hash')
            or repaired.get('all_interfaces_healthy') is not True or repaired.get('nginx_http_status')!=200
            or Path('/opt/vector/docker-compose.yml').read_bytes()!=(repair/'compose.candidate.yml').read_bytes()):
        raise RuntimeError('Active profile differs from the confirmed repaired listener baseline. No deployment performed.')
    read=private_json(ROOT/'releases/vector-chat-server-read-20261016T231729Z-306171/result.json')
    if (any(read.get(k) is not True for k in ('passed','snapshot_available','statistics_complete','production_unchanged'))
            or read.get('revision')!='e8b6b6e690aa893e3fc0a0641e07261c0414ffc6' or type(read.get('files')) is not int
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


PROBE=r"""
(async()=>{
 const os=require('node:os');
 const hosts=new Set(['127.0.0.1',...Object.values(os.networkInterfaces()).flat().filter(x=>x.family==='IPv4').map(x=>x.address)]);
 for(const host of hosts){
  const r=await fetch('http://'+host+':'+(process.env.PORT||'3000')+'/api/health',{signal:AbortSignal.timeout(2000),redirect:'manual'});
  const body=await r.json();if(r.status!==200||body.database!=='ok'||body.redis!=='ok')throw Error('interface');
 }
})().catch(()=>process.exitCode=1);
"""


def ingress_passes(h):
    try:
        data=h['text']('curl','--silent','--show-error','--connect-timeout','3','--max-time','10',
            '--resolve','vector.kibouakari.com:443:127.0.0.1','--write-out','\\n%{http_code}',
            'https://vector.kibouakari.com/api/health',timeout=15)
        raw,status=data.rsplit('\n',1)
        body=json.loads(raw)
        return status=='200' and body.get('database')=='ok' and body.get('redis')=='ok'
    except (RuntimeError,ValueError):
        return False


def strong_health(h,original,expected,attempts=45):
    if not original(expected,attempts=attempts):return False
    try:
        h['run']('docker','exec','vector-app','node','-e',PROBE,timeout=20)
        if ingress_passes(h):return True
        # A recreated app can change its address. Refresh only a valid host
        # Nginx configuration, and require its actual TLS ingress to recover.
        h['run']('nginx','-t')
        h['run']('systemctl','reload','nginx')
        return ingress_passes(h)
    except (RuntimeError,h['subprocess'].TimeoutExpired):
        return False


def prepare():
    source=SCRIPT.read_text();begin="<<'CONTROL_RELEASE_PYTHON'\n";end='\nCONTROL_RELEASE_PYTHON\n'
    if source.count(begin)!=1 or source.count(end)!=1:raise RuntimeError('Unexpected archived release structure.')
    tree=ast.parse(source.split(begin,1)[1].split(end,1)[0])
    class Labels(ast.NodeTransformer):
        def visit_Constant(self,node):
            replacements={'vector-control-release-':'vector-fresh-statistics-release-',
                '.vector-control-stage-':'.vector-fresh-statistics-stage-',
                '.vector-control-backup-':'.vector-fresh-statistics-backup-',
                '.vector-control-candidate-':'.vector-fresh-statistics-candidate-',
                '.vector-control-failed-':'.vector-fresh-statistics-failed-',
                '\n=== CONTROL CENTER RELEASE SUCCEEDED ===':'\n=== FRESH STATISTICS RELEASE SUCCEEDED ==='}
            if isinstance(node.value,str) and node.value in replacements:
                return ast.copy_location(ast.Constant(replacements[node.value]),node)
            return node
    n={'__name__':'chat_controls_release_factory'}
    exec(compile(ast.fix_missing_locations(Labels().visit(tree)),str(SCRIPT),'exec'),n)
    if n.get('TESTED')!='1f742366856a17ff7ab3ab01542d1eb7aca0a4a7' or n.get('MERGED')!='d73f6f982db62532a80696d230dd77b01246c057':
        raise RuntimeError('Unexpected archived factory baseline.')
    n.update(TESTED=TESTED,MERGED=MERGED,CURRENT=CURRENT,CURRENT_IMAGE=CURRENT_IMAGE,TESTED_IMAGE=TESTED_IMAGE,
        CURRENT_TAG='vector-app:staging-e8b6b6e-20261016T231731Z-6a08fa',
        TESTED_TAG='vector-app:staging-b9d34da-20261017T001416Z-b7e4cf',
        REPORT=ROOT/'releases/vector-fresh-statistics-staging-20261017T001416Z-b7e4cf/staging-result.json')
    original=n['prepare']
    def guarded_prepare():
        result=original()
        result['OTHERS']=tuple(result['OTHERS'])+('vector-local-inference','vector-privacy-ner','fegcraft-updated')
        old_health=result['healthy']
        result['healthy']=lambda expected,attempts=45:strong_health(result,old_health,expected,attempts)
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
FRESH_STATISTICS_RELEASE_PYTHON

