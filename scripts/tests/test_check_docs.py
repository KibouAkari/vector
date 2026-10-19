import sys
import tempfile
import unittest

from pathlib import Path

sys.path.insert(
    0,
    str(Path(__file__).resolve().parents[1])
)

from check_docs import validate


class DocumentationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

        (self.root / 'docs').mkdir()
        (self.root / 'README.md').write_text('# Vector\n')

    def tearDown(self):
        self.temp.cleanup()

    def check(self, content):
        (self.root / 'README.md').write_text(content)
        _, errors = validate(self.root)
        return errors

    def test_changelog_history_cannot_be_replaced_by_a_short_summary(self):
        import json
        index=self.root/'docs/changelog-history-index.json'
        index.write_text(json.dumps({'schema':1,'headings':['## 2026-10-14 — Existing feature']}))
        log=self.root/'CHANGELOG.md'
        log.write_text('# Changelog\n\n## 2026-10-19 — New feature\n')
        self.assertTrue(any('preserved historical entry missing' in e for e in validate(self.root)[1]))
        log.write_text(log.read_text()+'\n## 2026-10-14 — Existing feature\n\nOriginal detail.\n')
        self.assertFalse(validate(self.root)[1])

    def test_existing_markdown_link(self):
        (self.root / 'VISION.md').write_text('# Vision\n')
        self.assertFalse(
            self.check('[Vision](VISION.md)')
        )

    def test_broken_markdown_link(self):
        self.assertTrue(
            self.check('[Vision](VISION.md)')
        )

    def test_broken_root_html_link(self):
        self.assertTrue(
            self.check('<a href="VISION.md">Vision</a>')
        )

    def test_broken_docs_html_link(self):
        self.assertTrue(
            self.check(
                '<img src="docs/missing.png" '
                'alt="Diagram">'
            )
        )

    def test_decorative_icon_empty_alt(self):
        (self.root / 'docs/icon.svg').write_text(
            '<svg xmlns="http://www.w3.org/2000/svg"/>'
        )

        self.assertFalse(
            self.check(
                '<img src="docs/icon.svg" alt=""/>'
            )
        )

    def test_missing_alt(self):
        (self.root / 'docs/icon.svg').write_text(
            '<svg xmlns="http://www.w3.org/2000/svg"/>'
        )

        self.assertTrue(
            self.check('<img src="docs/icon.svg"/>')
        )

    def test_reference_definition(self):
        self.assertTrue(
            self.check(
                '[Vision][v]\n\n[v]: VISION.md'
            )
        )

    def test_relative_nested_document(self):
        (self.root / 'docs/ROADMAP.md').write_text(
            '[Vision](../README.md#overview)'
        )

        _, errors = validate(self.root)
        self.assertFalse(errors)

    def test_ignore_fenced_code_and_external_links(self):
        self.assertFalse(
            self.check(
                '```md\n'
                '[Example](not-here.md)\n'
                '```\n'
                '[Online](https://github.com/)\n'
                '[Jump](#overview)'
            )
        )

    def test_reject_link_outside_repository(self):
        self.assertTrue(
            self.check('[Outside](../../outside.txt)')
        )

    def test_malformed_svg(self):
        (self.root / 'docs/assets').mkdir()

        (self.root / 'docs/assets/invalid.svg').write_text(
            '<svg>'
        )

        _, errors = validate(self.root)
        self.assertTrue(errors)


if __name__ == '__main__':
    unittest.main()
