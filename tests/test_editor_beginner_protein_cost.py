import hashlib
import json
from fractions import Fraction
from pathlib import Path
import unittest

from scripts.xfit_editorial_gate import Inspector, check_document


class BeginnerProteinCostTests(unittest.TestCase):
    def test_snapshot_preview_and_exact_rollback(self):
        r = json.loads(Path(
            'content/revisions/editor-beginner-protein-cost.json'
        ).read_text(encoding='utf-8'))
        raw = Path(r['source_file']).read_bytes()
        source = json.loads(raw)
        self.assertEqual(hashlib.sha256(raw).hexdigest(), r['source_file_sha256'])
        self.assertEqual(hashlib.sha256(source['content'].encode()).hexdigest(),
                         r['source_content_sha256'])
        self.assertEqual(source['slug'], r['slug'])
        self.assertEqual(r['wp_post_id'], 25458)
        self.assertIn('WP ID 25458', Path(
            'docs/AUTONOMOUS_OPERATIONS.md').read_text(encoding='utf-8'))
        self.assertEqual(r['operation'], 'replace_exact_once')
        self.assertEqual(source['content'].count(r['original']), 1)
        preview = dict(source)
        preview['content'] = source['content'].replace(
            r['original'], r['replacement'], 1)
        self.assertTrue(check_document(preview)['passed'])
        self.assertEqual(preview['content'].replace(
            r['replacement'], r['original'], 1), source['content'])
        before, after = Inspector(), Inspector()
        before.feed(source['content'])
        after.feed(preview['content'])
        self.assertEqual(before.links, after.links)

    def test_quantity_example_and_price_normalization(self):
        protein = 900 * Fraction(75, 100)
        self.assertEqual(protein, 675)
        # Dimensionless cost units: recover total cost from normalized cost.
        cost = Fraction(7, 3)
        per_100 = cost * 100 / protein
        self.assertEqual(per_100 * protein / 100, cost)
        body = json.loads(Path(
            'content/revisions/editor-beginner-protein-cost.json'
        ).read_text(encoding='utf-8'))['replacement']
        for text in ('675 g bílkovin', 'protein nemusíte kupovat',
                     'konkrétní příchuť', 'nikoli hodnoty nápoje s mlékem',
                     'včetně dopravy a povinných poplatků',
                     'výsledek neodhadujte', 'neurčuje dávkování'):
            self.assertIn(text, body)
        self.assertNotIn('Kč', body)
        self.assertNotIn('<a ', body)


if __name__ == '__main__':
    unittest.main()
