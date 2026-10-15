#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

VECTOR_RELEASE_SCRIPT="${BASH_SOURCE[0]}" python3 - "$@" <<'RANKING_COST_RELEASE_PYTHON'
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
                'vector-control-release-': 'vector-ranking-cost-release-',
                '.vector-control-stage-': '.vector-ranking-cost-stage-',
                '.vector-control-backup-': '.vector-ranking-cost-backup-',
                '.vector-control-candidate-': '.vector-ranking-cost-candidate-',
                '.vector-control-failed-': '.vector-ranking-cost-failed-',
                '\n=== CONTROL CENTER RELEASE SUCCEEDED ===':
                    '\n=== RANKING COST RELEASE SUCCEEDED ==='
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
        TESTED='5e3f3042f7a336abde3e89b9125818e9961fd67d',
        MERGED='a7af7966b19ec2890e8374ed6b1047ca610537e0',
        CURRENT='57de6072aff2ae538705be78f6db440a591ae6ba',
        CURRENT_IMAGE='sha256:b969e856bb7f3a2c27a4e753a83101c0bb8d31def2c0e956261422744fbb086b',
        TESTED_IMAGE='sha256:0131e29a797cb74b04ceeeea6765cc0ccc46e331e62b4b8fe73a98794df8ea28',
        CURRENT_TAG='vector-app:staging-47e80ea-20261015T083251Z-8b0f5e',
        TESTED_TAG='vector-app:staging-5e3f304-20261015T101446Z-7008e3',
        REPORT=Path('/root/vector-workspace/releases/vector-ranking-cost-staging-20261015T101446Z-7008e3/staging-result.json')
    )
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
RANKING_COST_RELEASE_PYTHON

# END VECTOR RANKING COST RELEASE
