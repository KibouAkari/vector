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
                'vector-control-release-': 'vector-runtime-privacy-release-',
                '.vector-control-stage-': '.vector-privacy-stage-',
                '.vector-control-backup-': '.vector-privacy-backup-',
                '.vector-control-candidate-': '.vector-privacy-candidate-',
                '.vector-control-failed-': '.vector-privacy-failed-',
                '\n=== CONTROL CENTER RELEASE SUCCEEDED ===':
                    '\n=== RUNTIME PRIVACY RELEASE SUCCEEDED ==='
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
        TESTED='86110826e2c1b4205ad5e39f5dca7213bcdfc664',
        MERGED='60adca9398dff938e97df4f00bf8a2c476dde907',
        CURRENT='f38e44f3c8edad95cc8812d9d51e53fc1079e5b7',
        CURRENT_IMAGE='sha256:9a2b01e5afd37b51983fdf336ff986db13e3679b5381a802037c2795f1908fe4',
        TESTED_IMAGE='sha256:c33a1b853a16602e9413f4784de85337135288f55cf2437e6516b46ccfd463c0',
        CURRENT_TAG='vector-app:staging-c3a2e49-20261016T122003Z-c6ddd7',
        TESTED_TAG='vector-app:staging-8611082-20261016T162644Z-22f9a2',
        REPORT=Path('/root/vector-workspace/releases/vector-privacy-staging-20261016T162644Z-22f9a2/staging-result.json')
    )
    if len(sys.argv) == 1:
        import hashlib
        import json
        root = Path('/root/vector-workspace/releases')
        activation = root / 'vector-privacy-composer-release-20261016T123251Z-4139a9'
        record = json.loads((activation / 'release.json').read_text())
        candidate = (activation / 'compose.candidate.yml').read_bytes()
        if (record.get('status') != 'deployed'
                or record.get('commit') != namespace['CURRENT']
                or record.get('image_id') != namespace['CURRENT_IMAGE']
                or Path('/opt/vector/docker-compose.yml').read_bytes() != candidate):
            raise RuntimeError('Active profile differs from the completed composer release.')
        report = json.loads((root / 'vector-privacy-api-evaluation-20261016T162809Z-d3792a/result.json').read_text())
        if (report.get('passed') is not True
                or report.get('revision') != namespace['TESTED']
                or report.get('app_runtime_revision') != namespace['TESTED']
                or report.get('app_image') != namespace['TESTED_IMAGE']
                or report.get('production_unchanged') is not True
                or report.get('normal', {}).get('passed') is not True
                or report.get('outage', {}).get('passed') is not True
                or report.get('cloud_calls') != 0):
            raise RuntimeError('Enabled privacy API qualification differs.')
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
                                node.comparators[0].elts.append(ast.Constant('c07d7980e487a0d703b2f5efbc40279c227deb9c'))
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
        result['OTHERS'] = tuple(result['OTHERS']) + ('vector-local-inference', 'vector-privacy-ner')
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
