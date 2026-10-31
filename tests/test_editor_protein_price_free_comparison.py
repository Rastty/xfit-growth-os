import hashlib
import json
from fractions import Fraction
from pathlib import Path
import unittest

from scripts.xfit_editorial_gate import check_document


class PriceFreeComparisonTests(unittest.TestCase):
    def test_source_preview_and_exact_rollback(self):
        revision = json.loads(Path(
            'content/revisions/editor-protein-price-free-comparison.json'
        ).read_text(encoding='utf-8'))
        raw = Path(revision['source_file']).read_bytes()
        source = json.loads(raw)
        self.assertEqual(hashlib.sha256(raw).hexdigest(),
                         revision['source_file_sha256'])
        self.assertEqual(hashlib.sha256(source['content'].encode()).hexdigest(),
                         revision['source_content_sha256'])
        for field in ('wp_post_id', 'slug'):
            self.assertEqual(source[field], revision[field])
        self.assertEqual(revision['operation'], 'replace_exact_once')
        self.assertEqual(source['content'].count(revision['original']), 1)
        preview = dict(source)
        preview['content'] = source['content'].replace(
            revision['original'], revision['replacement'], 1)
        self.assertTrue(check_document(preview)['passed'])
        self.assertNotIn('899 Kč', preview['content'])
        self.assertNotIn('999 Kč', preview['content'])
        self.assertEqual(preview['content'].replace(
            revision['replacement'], revision['original'], 1), source['content'])
        # Preserve every existing link, including the comparison next step.
        from scripts.xfit_editorial_gate import Inspector
        before, after = Inspector(), Inspector()
        before.feed(source['content'])
        after.feed(preview['content'])
        self.assertEqual(before.links, after.links)

    def test_break_even_arithmetic_and_boundaries(self):
        revision = json.loads(Path(
            'content/revisions/editor-protein-price-free-comparison.json'
        ).read_text(encoding='utf-8'))
        body = revision['replacement']
        protein_a = 900 * Fraction(72, 100)
        protein_b = 1000 * Fraction(80, 100)
        self.assertEqual((protein_a, protein_b), (648, 800))
        threshold = protein_b / protein_a
        self.assertEqual(round(float((threshold - 1) * 100), 1), 23.5)
        # Dimensionless price ratios, not fabricated monetary offers.
        for ratio in (threshold - Fraction(1, 100), threshold,
                      threshold + Fraction(1, 100)):
            self.assertEqual(ratio / protein_b < 1 / protein_a,
                             ratio < threshold)
            self.assertEqual(ratio / protein_b == 1 / protein_a,
                             ratio == threshold)
        for text in ('648 g', '800 g', '23,5 %', '800 ÷ 648',
                     'skutečné ceny a etikety', 'protein nemusíte kupovat',
                     'Nejde o ověřené výrobky', 'neurčuje vhodnou dávku'):
            self.assertIn(text, body)
        self.assertNotIn('Kč', body)
        self.assertNotIn('<a ', body)


if __name__ == '__main__':
    unittest.main()
