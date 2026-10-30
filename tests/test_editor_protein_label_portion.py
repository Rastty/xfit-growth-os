import hashlib
import json
from fractions import Fraction
from pathlib import Path
import unittest

from scripts.xfit_editorial_gate import check_document


class ProteinLabelRevisionTests(unittest.TestCase):
    def setUp(self):
        self.revision = json.loads(Path(
            'content/revisions/editor-protein-label-portion.json'
        ).read_text(encoding='utf-8'))
        self.raw = Path(self.revision['source_file']).read_bytes()
        self.source = json.loads(self.raw)

    def test_revision_matches_unchanged_source_and_identity(self):
        r = self.revision
        self.assertEqual(hashlib.sha256(self.raw).hexdigest(), r['source_file_sha256'])
        self.assertEqual(hashlib.sha256(self.source['content'].encode()).hexdigest(),
                         r['source_content_sha256'])
        self.assertEqual(self.source['wp_post_id'], r['wp_post_id'])
        self.assertEqual(self.source['slug'], r['slug'])
        self.assertEqual(self.source['content'].count(r['original']), 1)
        self.assertEqual(r['operation'], 'replace_exact_once')

    def test_preview_passes_gate_and_can_be_rolled_back(self):
        r = self.revision
        preview = dict(self.source)
        preview['content'] = self.source['content'].replace(r['original'], r['replacement'], 1)
        self.assertTrue(check_document(preview)['passed'])
        self.assertEqual(preview['content'].replace(r['replacement'], r['original'], 1),
                         self.source['content'])
        self.assertEqual(preview['slug'], self.source['slug'])

    def test_label_example_and_purchase_boundaries(self):
        body = self.revision['replacement']
        protein_fraction = Fraction(80, 100)
        self.assertEqual(20 / protein_fraction, 25)
        self.assertEqual(30 * protein_fraction, 24)
        for text in ('20 ÷ 0,80', '25 g prášku', '24 g bílkovin',
                     'protein nekupujte', 'konkrétní příchuť',
                     'nikoli nápoj připravený s mlékem',
                     'Nejde o doporučenou dávku', 'neodhadujte'):
            self.assertIn(text, body)
        self.assertNotIn('<a ', body)


if __name__ == '__main__':
    unittest.main()
