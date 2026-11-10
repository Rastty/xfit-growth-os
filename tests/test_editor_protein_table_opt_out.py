import hashlib
import json
from html.parser import HTMLParser
from pathlib import Path
import unittest

from scripts.xfit_editorial_gate import Inspector, check_document


class TableRows(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows = []
        self.row = None
        self.cell = None

    def handle_starttag(self, tag, attrs):
        if tag == 'tr':
            self.row = []
        elif tag in ('td', 'th'):
            self.cell = ''

    def handle_data(self, data):
        if self.cell is not None:
            self.cell += data

    def handle_endtag(self, tag):
        if tag in ('td', 'th'):
            self.row.append(self.cell)
            self.cell = None
        elif tag == 'tr':
            self.rows.append(self.row)
            self.row = None


class ProteinTableOptOutTests(unittest.TestCase):
    def test_snapshot_preview_decision_order_and_rollback(self):
        r = json.loads(Path(
            'content/revisions/editor-protein-table-opt-out.json'
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
        self.assertNotIn(r['replacement'], source['content'])
        preview = dict(source)
        preview['content'] = source['content'].replace(
            r['original'], r['replacement'], 1)
        self.assertTrue(check_document(preview)['passed'])
        self.assertEqual(preview['content'].count(r['replacement']), 1)
        self.assertEqual(preview['content'].replace(
            r['replacement'], r['original'], 1), source['content'])

        before, after = TableRows(), TableRows()
        before.feed(source['content'])
        after.feed(preview['content'])
        self.assertEqual(len(after.rows[1]), 3)
        self.assertEqual(after.rows[1][1], 'Žádný proteinový doplněk')
        self.assertIn('běžným jídlem', after.rows[1][0])
        self.assertIn('zda vám vůbec bílkoviny chybí', after.rows[1][2])
        self.assertEqual(after.rows[:1] + after.rows[2:], before.rows)
        self.assertIn('<h2>1. Kolik bílkovin vlastně potřebujete?</h2>',
                      preview['content'])
        old_links, new_links = Inspector(), Inspector()
        old_links.feed(source['content'])
        new_links.feed(preview['content'])
        self.assertEqual(old_links.links, new_links.links)


if __name__ == '__main__':
    unittest.main()
