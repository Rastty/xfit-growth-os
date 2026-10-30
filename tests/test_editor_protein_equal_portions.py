import hashlib
import json
from fractions import Fraction
from pathlib import Path
import unittest

from scripts.xfit_editorial_gate import check_document


class EqualProteinPortionsTests(unittest.TestCase):
    def test_source_identity_preview_and_rollback(self):
        revision = json.loads(Path(
            'content/revisions/editor-protein-equal-portions.json'
        ).read_text(encoding='utf-8'))
        raw = Path(revision['source_file']).read_bytes()
        source = json.loads(raw)
        applied = source['content'].count(revision['replacement']) == 1
        original_content = (source['content'].replace(
            revision['replacement'], revision['original'], 1)
            if applied else source['content'])
        self.assertEqual(hashlib.sha256(original_content.encode()).hexdigest(),
                         revision['source_content_sha256'])
        if not applied:
            self.assertEqual(hashlib.sha256(raw).hexdigest(),
                             revision['source_file_sha256'])
        for field in ('wp_post_id', 'slug'):
            self.assertEqual(source[field], revision[field])
        self.assertEqual(revision['operation'], 'replace_exact_once')
        self.assertEqual(source['content'].count(revision['original']), 1)
        preview = dict(source)
        if applied:
            preview['content'] = source['content']
            self.assertEqual(source['content'].count(revision['replacement']), 1)
        else:
            preview['content'] = source['content'].replace(
                revision['original'], revision['replacement'], 1)
        self.assertTrue(check_document(preview)['passed'])
        self.assertEqual(preview['content'].replace(
            revision['replacement'], revision['original'], 1), original_content)

    def test_equal_protein_comparison(self):
        # Equal powder portions deliver unequal protein; normalize by protein.
        self.assertEqual(20 / Fraction(80, 100), 25)
        self.assertEqual(round(float(20 / Fraction(60, 100)), 1), 33.3)
        self.assertEqual(30 * Fraction(80, 100), 24)
        self.assertEqual(30 * Fraction(60, 100), 18)
        # At equal pack mass and price, lower concentration costs 4/3 as much
        # per equal protein portion. No real product price is assumed.
        self.assertEqual(Fraction(80, 100) / Fraction(60, 100), Fraction(4, 3))


if __name__ == '__main__':
    unittest.main()
