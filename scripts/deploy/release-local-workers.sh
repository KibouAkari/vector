#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

VECTOR_RELEASE_SCRIPT="${BASH_SOURCE[0]}" python3 - "$@" <<'LOCAL_WORKER_RELEASE_PYTHON'
import ast
import sys
from pathlib import Path

SCRIPT = Path('/root/vector-workspace/archive/phases/vector-control-release.sh')

def main():
    source = SCRIPT.read_text()
    begin = "<<'CONTROL_RELEASE_PYTHON'\n"
    end = '\nCONTROL_RELEASE_PYTHON\n'
    if source.count(begin) != 1 or source.count(end) != 1:
        raise RuntimeError('Unexpected archived release structure.')
    tree = ast.parse(source.split(begin, 1)[1].split(end, 1)[0])

    class Labels(ast.NodeTransformer):
        def visit_Constant(self, node):
            replacements = {
                'vector-control-release-': 'vector-local-worker-release-',
                '.vector-control-stage-': '.vector-local-worker-stage-',
                '.vector-control-backup-': '.vector-local-worker-backup-',
                '.vector-control-candidate-': '.vector-local-worker-candidate-',
                '.vector-control-failed-': '.vector-local-worker-failed-',
                '\n=== CONTROL CENTER RELEASE SUCCEEDED ===':
                    '\n=== LOCAL WORKER RELEASE SUCCEEDED ==='
            }
            if isinstance(node.value, str) and node.value in replacements:
                return ast.copy_location(ast.Constant(replacements[node.value]), node)
            return node

    tree = ast.fix_missing_locations(Labels().visit(tree))
    namespace = {'__name__': 'vector_pdf_release'}
    exec(compile(tree, str(SCRIPT), 'exec'), namespace)
    if (
        namespace.get('TESTED') != '1f742366856a17ff7ab3ab01542d1eb7aca0a4a7'
        or namespace.get('MERGED') != 'd73f6f982db62532a80696d230dd77b01246c057'
    ):
        raise RuntimeError('Unexpected archived release baseline.')

    namespace.update(
        TESTED='b7bf796613d4d0073ae4388004020b784a2f4fcd',
        MERGED='37130b59a6dad080076e1dea7ded563f996b1672',
        CURRENT='a7af7966b19ec2890e8374ed6b1047ca610537e0',
        CURRENT_IMAGE='sha256:0131e29a797cb74b04ceeeea6765cc0ccc46e331e62b4b8fe73a98794df8ea28',
        TESTED_IMAGE='sha256:d1b5b1f6c463627ba1daa20d44e9450c3862cdc4c80df245e0f94f1187f675bf',
        CURRENT_TAG='vector-app:staging-5e3f304-20261015T101446Z-7008e3',
        TESTED_TAG='vector-app:staging-b7bf796-20261015T132209Z-e0be3d',
        REPORT=Path('/root/vector-workspace/releases/vector-local-worker-staging-20261015T132209Z-e0be3d/staging-result.json')
    )
    if len(sys.argv) == 1:
        import hashlib
        path = Path('/opt/vector/docker-compose.yml')
        if hashlib.sha256(path.read_bytes()).hexdigest() != 'ae1be307d986c7361cef9c1ee670acfa64a41a2a59f94530a59833098b90df70':
            raise RuntimeError('Production Compose changed since the approved wiring profile.')
    namespace['main']()

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('Interrupted. Inspect release status before retrying.', file=sys.stderr)
        sys.exit(130)
    except Exception as exc:
        print('ERROR:', str(exc) if isinstance(exc, RuntimeError) else type(exc).__name__, file=sys.stderr)
        sys.exit(1)
LOCAL_WORKER_RELEASE_PYTHON

# END VECTOR LOCAL WORKER RELEASE
