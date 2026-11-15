import hashlib
import json
from html.parser import HTMLParser
from pathlib import Path
import unittest

from scripts.xfit_editorial_gate import Inspector, check_document


class TableReader(HTMLParser):
    def __init__(self):
        super().__init__()
        self.cells = []
        self.caption = []
        self.active = None

    def handle_starttag(self, tag, attrs):
        if tag in ('td', 'th', 'caption'):
            self.active = []
            if tag == 'caption':
                self.caption.append(self.active)
            else:
                self.cells.append((tag, dict(attrs), self.active))

    def handle_data(self, data):
        if self.active is not None:
            self.active.append(data)

    def handle_endtag(self, tag):
        if tag in ('td', 'th', 'caption'):
            self.active = None


class ProteinTableAccessibilityTests(unittest.TestCase):
    def test_snapshot_preview_and_rollback(self):
        r = json.loads(Path(
            'content/revisions/editor-protein-table-accessibility.json'
        ).read_text(encoding='utf-8'))
        raw = Path(r['source_file']).read_bytes()
        source = json.loads(raw)
        self.assertEqual(hashlib.sha256(raw).hexdigest(), r['source_file_sha256'])
        self.assertEqual(hashlib.sha256(source['content'].encode()).hexdigest(),
                         r['source_content_sha256'])
        for field in ('wp_post_id', 'slug'):
            self.assertEqual(source[field], r[field])
        self.assertEqual(r['operation'], 'replace_exact_once')
        self.assertEqual(source['content'].count(r['original']), 1)
        preview = dict(source)
        preview['content'] = source['content'].replace(
            r['original'], r['replacement'], 1)
        self.assertTrue(check_document(preview)['passed'])
        self.assertEqual(preview['content'].replace(
            r['replacement'], r['original'], 1), source['content'])
        before, after = TableReader(), TableReader()
        before.feed(r['original'])
        after.feed(r['replacement'])
        self.assertEqual([c[2] for c in before.cells],
                         [c[2] for c in after.cells])
        self.assertEqual(len(after.cells), 18)  # Three columns, six rows.
        for index, (tag, attrs, _) in enumerate(after.cells):
            if index < 3:
                self.assertEqual((tag, attrs.get('scope')), ('th', 'col'))
            elif index % 3 == 0:
                self.assertEqual((tag, attrs.get('scope')), ('th', 'row'))
            else:
                self.assertEqual(tag, 'td')
        self.assertEqual(len(after.caption), 1)
        self.assertIn('Nejde o žebříček výrobků.', ''.join(after.caption[0]))
        original_links, preview_links = Inspector(), Inspector()
        original_links.feed(source['content'])
        preview_links.feed(preview['content'])
        self.assertEqual(original_links.links, preview_links.links)


if __name__ == '__main__':
    unittest.main()
