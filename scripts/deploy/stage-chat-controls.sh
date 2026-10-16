#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

python3 - "$@" <<'CHAT_CONTROLS_STAGING_PYTHON'
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
                'vector-control-staging-': 'vector-chat-controls-staging-',
                'vector-app:staging-1f74236-': 'vector-app:staging-' + revision[:7] + '-',
                'vector-control-': 'vector-chat-controls-',
                '=== BUILD SERVER CONTROL CENTER 1f74236 ===':
                    '=== BUILD CHAT CONTROLS ' + revision[:7] + ' ===',
                '\n=== CONTROL CENTER STAGING PASSED ===':
                    '\n=== CHAT CONTROLS STAGING PASSED ==='
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
            'lib/router.js', 'lib/execution-router.js', 'lib/host-agent.js')
        original_command = stage['command']

        def command(*args, **kwargs):
            if '--test' in args and 'tests/project-file-view.test.mjs' in args:
                args = (*args, 'tests/server-json-rankings.test.mjs', 'tests/provider-call-usage.test.mjs', 'tests/local-workers.test.mjs', 'tests/privacy-review.test.mjs', 'tests/privacy-routes.test.mjs', 'tests/privacy-ner-client.test.mjs', 'tests/privacy-send-controller.test.mjs', 'tests/local-routing-regression.test.mjs', 'tests/chat-controls.test.mjs')
            if args[:2]==('docker','run') and 'HOSTNAME=0.0.0.0' in args:
                index=args.index('HOSTNAME=0.0.0.0')+1
                args=(*args[:index],'-e','VECTOR_LOCAL_WORKERS=1',*args[index:])
            return original_command(*args, **kwargs)

        stage['HTTP_TEST'] += r'''
console.log('=== CHAT CONTROLS API CHECKS ===');
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
} finally {await chatDb.end();}
'''
        stage['SERVICES'] += ('vector-privacy-ner', 'vector-local-inference', 'fegcraft-updated')
        stage['command'] = command
        return stage

    namespace.update(
        REV=revision,
        BRANCH='feat/chat-controls-local-data-20261017',
        LIVE_IMAGE='sha256:c33a1b853a16602e9413f4784de85337135288f55cf2437e6516b46ccfd463c0',
        LIVE_TAG='vector-app:staging-8611082-20261016T162644Z-22f9a2',
        prepare=prepare
    )
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
CHAT_CONTROLS_STAGING_PYTHON

# END VECTOR CHAT CONTROLS STAGING

