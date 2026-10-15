#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

python3 - "$@" <<'RANKING_COST_STAGING_PYTHON'
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
                'vector-control-staging-': 'vector-ranking-cost-staging-',
                'vector-app:staging-1f74236-': 'vector-app:staging-' + revision[:7] + '-',
                'vector-control-': 'vector-ranking-cost-',
                '=== BUILD SERVER CONTROL CENTER 1f74236 ===':
                    '=== BUILD LOCAL JSON RANKINGS ' + revision[:7] + ' ===',
                '\n=== CONTROL CENTER STAGING PASSED ===':
                    '\n=== RANKING COST STAGING PASSED ==='
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
            'app/page.js', 'components/dashboard-client.js')
        original_command = stage['command']

        def command(*args, **kwargs):
            if '--test' in args and 'tests/project-file-view.test.mjs' in args:
                args = (*args, 'tests/server-json-rankings.test.mjs', 'tests/provider-call-usage.test.mjs')
            return original_command(*args, **kwargs)

        stage['command'] = command
        return stage

    namespace.update(
        REV=revision,
        BRANCH='perf/local-json-rankings-20261015',
        LIVE_IMAGE='sha256:b969e856bb7f3a2c27a4e753a83101c0bb8d31def2c0e956261422744fbb086b',
        LIVE_TAG='vector-app:staging-47e80ea-20261015T083251Z-8b0f5e',
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
RANKING_COST_STAGING_PYTHON

# END VECTOR RANKING COST STAGING
