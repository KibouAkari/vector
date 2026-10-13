#!/usr/bin/env python3
"""Validate repository-local documentation links, image alts and SVGs."""

import argparse
from html.parser import HTMLParser
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit
from xml.etree import ElementTree

INLINE_LINK = re.compile(
    r'!?\[[^\]\n]*\]\(\s*(?:<([^>]+)>|([^\s)]+))'
)

REFERENCE_DEF = re.compile(
    r'^\s{0,3}\[[^\]]+\]:\s*(?:<([^>]+)>|(\S+))',
    re.M
)

CODE_FENCE = re.compile(r'^\s*(`{3,}|~{3,})')


def without_code_fences(text):
    output = []
    fence = None

    for line in text.splitlines():
        match = CODE_FENCE.match(line)

        if match:
            symbol = match.group(1)[0]
            length = len(match.group(1))

            if fence is None:
                fence = (symbol, length)
                continue

            if symbol == fence[0] and length >= fence[1]:
                fence = None
                continue

        if fence is None:
            output.append(line)

    return '\n'.join(output)


class HtmlReferences(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.references = []
        self.errors = []

    def handle_starttag(self, tag, attrs):
        fields = dict(attrs)

        for key in ('href', 'src'):
            if fields.get(key):
                self.references.append(fields[key])

        if tag == 'img' and fields.get('alt') is None:
            self.errors.append(
                'HTML image is missing alt '
                '(use alt="" if decorative)'
            )


def local_target(root, source, link):
    link = link.strip()

    if not link or link.startswith(('#', '//')):
        return None

    parsed = urlsplit(link)

    if parsed.scheme or parsed.netloc or not parsed.path:
        return None

    raw = unquote(parsed.path)

    if raw.startswith('/'):
        path = root / raw.lstrip('/')
    else:
        path = source.parent / raw

    return path.resolve()


def check_document(root, source):
    errors = []

    text = without_code_fences(
        source.read_text(encoding='utf-8')
    )

    html = HtmlReferences()
    html.feed(text)

    errors.extend(
        f'{source.relative_to(root)}: {error}'
        for error in html.errors
    )

    links = list(html.references)

    for regex in (INLINE_LINK, REFERENCE_DEF):
        links.extend(
            m.group(1) or m.group(2)
            for m in regex.finditer(text)
        )

    for link in links:
        target = local_target(root, source, link)

        if target is None:
            continue

        try:
            target.relative_to(root)
        except ValueError:
            errors.append(
                f'{source.relative_to(root)}: '
                f'link escapes repository: {link}'
            )
            continue

        if not target.exists():
            errors.append(
                f'{source.relative_to(root)}: '
                f'missing link target: {link}'
            )

    return errors


def validate(root):
    root = Path(root).resolve()

    docs = [
        root / name
        for name in (
            'README.md',
            'VISION.md',
            'CHANGELOG.md',
            'CONTRIBUTING.md',
            'AGENTS.md',
            '.github/PULL_REQUEST_TEMPLATE.md',
        )
    ]

    if (root / 'docs').is_dir():
        docs += list((root / 'docs').rglob('*.md'))

    docs = sorted(
        path for path in set(docs)
        if path.is_file()
    )

    errors = []

    for source in docs:
        errors.extend(
            check_document(root, source)
        )

    assets = root / 'docs/assets'

    if assets.exists():
        for svg in assets.rglob('*.svg'):
            try:
                ElementTree.parse(svg)
            except ElementTree.ParseError as exc:
                errors.append(
                    f'{svg.relative_to(root)}: '
                    f'invalid SVG: {exc}'
                )

    return docs, errors


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', default='.')

    args = parser.parse_args()
    checked, errors = validate(args.root)

    for error in errors:
        print('ERROR:', error)

    if errors:
        print(
            f'FAILED: {len(errors)} '
            'documentation issue(s)'
        )
        raise SystemExit(1)

    print(
        f'OK: {len(checked)} Markdown documents, '
        'local links, image alts and SVGs'
    )
