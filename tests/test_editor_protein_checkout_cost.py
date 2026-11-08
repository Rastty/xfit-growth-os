import hashlib
import json
from fractions import Fraction
from pathlib import Path
import unittest

from scripts.xfit_editorial_gate import Inspector, check_document


class CheckoutCostRevisionTests(unittest.TestCase):
    def test_snapshot_preview_and_rollback(self):
        revision = json.loads(Path(
            'content/revisions/editor-protein-checkout-cost.json'
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
        self.assertNotIn(revision['replacement'], source['content'])
        preview = dict(source)
        preview['content'] = source['content'].replace(
            revision['original'], revision['replacement'], 1)
        self.assertTrue(check_document(preview)['passed'])
        self.assertEqual(preview['content'].replace(
            revision['replacement'], revision['original'], 1), source['content'])
        before, after = Inspector(), Inspector()
        before.feed(source['content'])
        after.feed(preview['content'])
        self.assertEqual(before.links, after.links)

    def test_checkout_comparison_can_reverse_powder_price_order(self):
        # Synthetic dimensionless ratios, not product offers or currency prices.
        protein_a, protein_b = Fraction(1), Fraction(2)
        price_a, price_b = Fraction(1), Fraction(3, 2)
        shipping_a, shipping_b = Fraction(0), Fraction(3, 4)
        self.assertLess(price_b / protein_b, price_a / protein_a)
        self.assertGreater((price_b + shipping_b) / protein_b,
                           (price_a + shipping_a) / protein_a)
        revision = json.loads(Path(
            'content/revisions/editor-protein-checkout-cost.json'
        ).read_text(encoding='utf-8'))
        body = revision['replacement']
        for text in ('po slevách', 'včetně dopravy a povinných poplatků',
                     'její vlastní celkovou částku a obsah bílkovin',
                     'nepřičítejte celou společnou dopravu každému balení',
                     'Nepřidávejte nepotřebné doplňky',
                     'nemusíte objednávat nic'):
            self.assertIn(text, body)
        self.assertNotIn('Kč', body)
        self.assertNotIn('<a ', body)


if __name__ == '__main__':
    unittest.main()
