#!/usr/bin/env python3
"""Check the current source tree, never claim to scrub Git history."""
import argparse
from pathlib import Path
import re

SKIP = {'.git', 'node_modules', '.next', 'build', '__pycache__', '.pytest_cache'}
PRIVATE = re.compile(r'/root/vector-workspace|/releases/vector-[\w-]+-20\d{6}T\d{6}Z|owner-confirmed|NEXT owner command', re.I)

def audit(root, denied=()):
    failures=[]
    for path in sorted(root.rglob('*')):
        if set(path.relative_to(root).parts)&SKIP:continue
        if path.is_symlink():
            failures.append((str(path.relative_to(root)),'symlink-review'));continue
        if not path.is_file():continue
        try:text=path.read_text()
        except UnicodeError:continue
        if path.resolve()!=Path(__file__).resolve() and PRIVATE.search(text):
            failures.append((str(path.relative_to(root)),'private-operating-material'))
        if any(term.casefold() in text.casefold() for term in denied):
            failures.append((str(path.relative_to(root)),'operator-deny-list'))
    return failures

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=Path('.'))
    parser.add_argument('--deny-file',type=Path,help='Private local newline-separated search terms; never commit this file')
    args=parser.parse_args()
    terms=[line.strip() for line in args.deny_file.read_text().splitlines() if line.strip()] if args.deny_file else []
    failures=audit(args.root.resolve(),terms)
    # Only categories and counts: no potentially private lines or names in CI.
    print('Source publication check:', 'FAILED' if failures else 'passed', '; findings:',len(failures))
    print('Git history, PRs, artifacts and live deployments are outside this check.')
    return bool(failures)

if __name__=='__main__':raise SystemExit(main())
