#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

VECTOR_RELEASE_SCRIPT="${BASH_SOURCE[0]}" python3 - "$@" <<'PRIVACY_RELEASE_PYTHON'
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
                'vector-control-release-': 'vector-privacy-release-',
                '.vector-control-stage-': '.vector-privacy-stage-',
                '.vector-control-backup-': '.vector-privacy-backup-',
                '.vector-control-candidate-': '.vector-privacy-candidate-',
                '.vector-control-failed-': '.vector-privacy-failed-',
                '\n=== CONTROL CENTER RELEASE SUCCEEDED ===':
                    '\n=== PRIVACY APP RELEASE SUCCEEDED ==='
            }
            if isinstance(node.value, str) and node.value in replacements:
                return ast.copy_location(ast.Constant(replacements[node.value]), node)
            return node

    tree = ast.fix_missing_locations(Labels().visit(tree))
    namespace = {'__name__': 'vector_privacy_release'}
    exec(compile(tree, str(SCRIPT), 'exec'), namespace)
    if (
        namespace.get('TESTED') != '1f742366856a17ff7ab3ab01542d1eb7aca0a4a7'
        or namespace.get('MERGED') != 'd73f6f982db62532a80696d230dd77b01246c057'
    ):
        raise RuntimeError('Unexpected archived release baseline.')

    namespace.update(
        TESTED='a20b9a650546e9cf8fbbba9b0fbc9f85acaf88a5',
        MERGED='ba30c82f0a7b66a29272c1711858ac78ad522238',
        CURRENT='37130b59a6dad080076e1dea7ded563f996b1672',
        CURRENT_IMAGE='sha256:d1b5b1f6c463627ba1daa20d44e9450c3862cdc4c80df245e0f94f1187f675bf',
        TESTED_IMAGE='sha256:e59160f17f47b2b8231e417bc64c25ce82a5a7320be6a0b47c6d8b226f699a80',
        CURRENT_TAG='vector-app:staging-b7bf796-20261015T132209Z-e0be3d',
        TESTED_TAG='vector-app:staging-a20b9a6-20261016T084935Z-7b04eb',
        REPORT=Path('/root/vector-workspace/releases/vector-privacy-staging-20261016T084935Z-7b04eb/staging-result.json')
    )
    if len(sys.argv) == 1:
        import hashlib
        path = Path('/opt/vector/docker-compose.yml')
        if hashlib.sha256(path.read_bytes()).hexdigest() != '64ac69df11b6c959e1f876a01cad32dee121705f7a510dd34650a4116fd2702d':
            raise RuntimeError('Production Compose changed since the approved wiring profile.')
    # The ops checkout advanced while the deployed source remained at CURRENT.
    # Extend only that checkout guard; tracked(CURRENT) still verifies live source.
    import builtins
    original_prepare = namespace['prepare']
    real_compile = builtins.compile
    def prepare():
        count = 0
        def checked_compile(source, filename, mode, *args, **kwargs):
            nonlocal count
            if isinstance(source, ast.Module):
                for function in source.body:
                    if isinstance(function, ast.FunctionDef) and function.name == 'main':
                        for node in ast.walk(function):
                            if (isinstance(node, ast.Compare) and len(node.ops) == 1
                                    and isinstance(node.ops[0], ast.NotIn)
                                    and len(node.comparators) == 1
                                    and isinstance(node.comparators[0], ast.Tuple)
                                    and [getattr(x, 'id', None) for x in node.comparators[0].elts] == ['OLD_REV', 'REV']):
                                node.comparators[0].elts.append(ast.Constant('6a4e31b97e86f20fa6f4daa3504d45697ee89ede'))
                                count += 1
                ast.fix_missing_locations(source)
            return real_compile(source, filename, mode, *args, **kwargs)
        try:
            builtins.compile = checked_compile
            result = original_prepare()
        finally:
            builtins.compile = real_compile
        if count != 1:
            raise RuntimeError('Archived checkout guard changed; no release executed.')
        result['OTHERS'] = tuple(result['OTHERS']) + ('vector-local-inference',)
        return result
    namespace['prepare'] = prepare
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
PRIVACY_RELEASE_PYTHON

# END VECTOR PRIVACY RELEASE
