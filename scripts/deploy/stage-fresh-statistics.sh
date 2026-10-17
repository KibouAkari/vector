#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

python3 - "$@" <<'FRESH_STATISTICS_STAGING_PYTHON'
import ast
import os
import re
import sys
from pathlib import Path

SCRIPT = Path('/root/vector-workspace/archive/phases/vector-control-staging.sh')

def main():
    revision = sys.argv[1] if len(sys.argv) == 2 else os.environ.get('VECTOR_STAGING_REV', '')
    if len(sys.argv) > 2 or not re.fullmatch(r'[0-9a-f]{40}', revision):
        raise RuntimeError('Provide the exact reviewed commit as argument or VECTOR_STAGING_REV.')
    if not SCRIPT.is_file() or SCRIPT.is_symlink():
        raise RuntimeError('Archived control staging script missing or symlinked.')
    source = SCRIPT.read_text()
    begin = "<<'CONTROL_STAGING_PYTHON'\n"
    end = '\nCONTROL_STAGING_PYTHON\n'
    if source.count(begin) != 1 or source.count(end) != 1:
        raise RuntimeError('Unexpected archived staging structure.')
    tree = ast.parse(source.split(begin, 1)[1].split(end, 1)[0])

    class Labels(ast.NodeTransformer):
        def visit_Constant(self, node):
            replacements = {
                'vector-control-staging-': 'vector-fresh-statistics-staging-',
                'vector-app:staging-1f74236-': 'vector-app:staging-' + revision[:7] + '-',
                'vector-control-': 'vector-fresh-statistics-',
                '=== BUILD SERVER CONTROL CENTER 1f74236 ===':
                    '=== BUILD FRESH STATISTICS ' + revision[:7] + ' ===',
                '\n=== CONTROL CENTER STAGING PASSED ===':
                    '\n=== FRESH STATISTICS STAGING PASSED ==='
            }
            if isinstance(node.value, str) and node.value in replacements:
                return ast.copy_location(ast.Constant(replacements[node.value]), node)
            return node

    tree = ast.fix_missing_locations(Labels().visit(tree))
    namespace = {'__name__': 'vector_ranking_cost_staging'}
    exec(compile(tree, str(SCRIPT), 'exec'), namespace)
    if namespace.get('REV') != '1f742366856a17ff7ab3ab01542d1eb7aca0a4a7':
        raise RuntimeError('Unexpected archived staging baseline.')
    original_prepare = namespace['prepare']

    def prepare():
        stage = original_prepare()
        stage['FILES'] += ('lib/server-json-rankings.mjs', 'lib/background-executor.js',
            'lib/provider-call-usage.mjs', 'lib/provider-runtime.js', 'lib/provider-usage-normalization.mjs',
            'lib/workflow-runtime.js', 'lib/db.js', 'lib/usage.js', 'lib/usage-store.mjs',
            'app/page.js', 'components/dashboard-client.js',
            'lib/local-worker-core.mjs', 'lib/local-worker-runtime.js',
            'lib/privacy.js', 'lib/privacy-rules.mjs', 'lib/privacy-review-core.mjs',
            'lib/privacy-review.js', 'lib/privacy-vault.js', 'lib/local-private-chat.js',
            'lib/privacy-ner-client.mjs', 'lib/privacy-ner-core.py', 'services/privacy-ner/server.py',
            'app/api/chat/route.js', 'app/api/projects/[id]/chat/route.js',
            'app/api/privacy/classify/route.js', 'app/projects/[id]/project-workspace.js',
            'components/ui/privacy-review-dialog.js', 'lib/privacy-send-controller.mjs',
            'components/ui/chat-controls.js', 'lib/chat-controls.mjs', 'lib/chat-menu-position.mjs', 'lib/local-server-statistics.mjs',
            'lib/router.js', 'lib/execution-router.js', 'lib/host-agent.js', 'lib/background-jobs.js')
        original_command = stage['command']

        def command(*args, **kwargs):
            if '--test' in args and 'tests/project-file-view.test.mjs' in args:
                args = (*args, 'tests/server-json-rankings.test.mjs', 'tests/provider-call-usage.test.mjs', 'tests/local-workers.test.mjs', 'tests/privacy-review.test.mjs', 'tests/privacy-routes.test.mjs', 'tests/privacy-ner-client.test.mjs', 'tests/privacy-send-controller.test.mjs', 'tests/local-routing-regression.test.mjs', 'tests/chat-controls.test.mjs')
            if args[:2]==('docker','run') and 'HOSTNAME=0.0.0.0' in args:
                index=args.index('HOSTNAME=0.0.0.0')+1
                args=(*args[:index],'-e','VECTOR_LOCAL_WORKERS=1',*args[index:])
            return original_command(*args, **kwargs)

        stage['HTTP_TEST'] += r'''
console.log('=== FRESH STATISTICS API CHECKS ===');
const controlPost=(body,cookie=owner)=>request('/api/chat',cookie,{method:'POST',
  headers:{'content-type':'application/json'},body:JSON.stringify(body)});
check((await controlPost({message:'synthetic',privacyEnabled:false},null)).status===401,
  'privacy off never bypasses login');
check((await controlPost({message:'synthetic',privacyEnabled:'false'})).status===400,
  'privacy preference requires a boolean');
const pgModule=await import('pg');
const chatDb=new pgModule.Client({connectionString:process.env.DATABASE_URL,connectionTimeoutMillis:5000});
await chatDb.connect();
try {
  for(const [mode,destination] of [['auto','local'],['local','local'],['normal','cloud']]) {
    const response=await controlPost({message:'Welche Rekorde hat ExampleOne auf FEGCraft?',mode,privacyEnabled:false});
    check(response.status===202,'chat mode accepted: '+mode);
    const data=await response.json();
    const {rows}=await chatDb.query('SELECT status,attempts,payload FROM agent_jobs WHERE id=$1',[data.jobId]);
    check(rows.length===1&&rows[0].status==='queued'&&rows[0].attempts===0,'job remains unexecuted');
    check(rows[0].payload.privacyDestination===destination,'correct private/cloud destination: '+mode);
    check(destination==='local'?rows[0].payload.privacyPolicy===null:typeof rows[0].payload.privacyPolicy==='string',
      'privacy opt-out is bound to the external job');
  }
  const freshBody={message:'Welche Rekorde hat ExampleOne auf FEGCraft?',mode:'auto',privacyEnabled:false};
  const firstResponse=await controlPost(freshBody);
  check(firstResponse.status===202,'first native statistics request is queued');
  const first=await firstResponse.json();
  const messageId=globalThis.crypto.randomUUID();
  await chatDb.query("INSERT INTO messages(id,conversation_id,role,content,model,cost_chf) VALUES($1,$2,'assistant','synthetic previous statistics','vector-local-statistics',0)",[messageId,first.conversationId]);
  await chatDb.query("UPDATE agent_jobs SET status='completed',assistant_message_id=$2,result=$3::jsonb WHERE id=$1",
    [first.jobId,messageId,JSON.stringify({text:'synthetic previous statistics',meta:{model:'vector-local-statistics'}})]);
  const refreshedResponse=await controlPost({...freshBody,conversationId:first.conversationId});
  check(refreshedResponse.status===202,'completed statistics must queue a new read');
  const refreshed=await refreshedResponse.json();
  check(refreshed.jobId!==first.jobId,'completed native answer is never replayed');
  const duplicateResponse=await controlPost({...freshBody,conversationId:first.conversationId});
  const duplicate=await duplicateResponse.json();
  check(duplicateResponse.status===202&&duplicate.jobId===refreshed.jobId,'in-flight retry shares the current job');
  for(const message of ['kannst du mir einfach nur alle rekordhalter geben?','bitte checke es auf meinem server']) {
    const response=await controlPost({message,mode:'auto',privacyEnabled:false,conversationId:first.conversationId});
    check(response.status===202,'statistics followup accepted');
    const data=await response.json();
    const row=(await chatDb.query('SELECT payload,status,attempts FROM agent_jobs WHERE id=$1',[data.jobId])).rows[0];
    check(row.payload.privacyDestination==='local'&&row.status==='queued'&&row.attempts===0,'followup remains native without a model');
  }
} finally {await chatDb.end();}
'''
        stage['SERVICES'] += ('vector-privacy-ner', 'vector-local-inference', 'fegcraft-updated')
        stage['command'] = command
        return stage

    namespace.update(
        REV=revision,
        BRANCH='fix/fresh-statistics-20261017',
        LIVE_IMAGE='sha256:5a2ee0f4b1b169114da5608a8a33f0ca08ce00c4016873208fa1d5518901f87d',
        LIVE_TAG='vector-app:staging-e8b6b6e-20261016T231731Z-6a08fa',
        prepare=prepare
    )
    import json
    repair=Path('/root/vector-workspace/releases/vector-listener-fix-20261016T235002Z-913eee')
    evidence=json.loads((repair/'result.json').read_text())
    if (evidence.get('status')!='deployed' or evidence.get('all_interfaces_healthy') is not True
            or evidence.get('nginx_http_status')!=200
            or Path('/opt/vector/docker-compose.yml').read_bytes()!=(repair/'compose.candidate.yml').read_bytes()):
        raise RuntimeError('Repaired listener baseline changed. No staging build started.')
    namespace['main']()

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('Interrupted. Inspect staging cleanup before retrying.', file=sys.stderr)
        sys.exit(130)
    except Exception as exc:
        print('ERROR:', str(exc) if isinstance(exc, RuntimeError) else type(exc).__name__, file=sys.stderr)
        sys.exit(1)
FRESH_STATISTICS_STAGING_PYTHON

# END VECTOR FRESH STATISTICS STAGING


