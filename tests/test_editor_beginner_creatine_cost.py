import hashlib
import json
from fractions import Fraction
from pathlib import Path
import unittest

from scripts.xfit_editorial_gate import check_document


class BeginnerCreatineCostTests(unittest.TestCase):
    def test_source_preview_and_exact_rollback(self):
        revision = json.loads(Path(
            'content/revisions/editor-beginner-creatine-cost.json'
        ).read_text(encoding='utf-8'))
        raw = Path(revision['source_file']).read_bytes()
        source = json.loads(raw)
        self.assertEqual(hashlib.sha256(raw).hexdigest(),
                         revision['source_file_sha256'])
        self.assertEqual(hashlib.sha256(source['content'].encode()).hexdigest(),
                         revision['source_content_sha256'])
        self.assertEqual(source['slug'], revision['slug'])
        self.assertEqual(revision['operation'], 'replace_exact_once')
        self.assertEqual(source['content'].count(revision['original']), 1)
        preview = dict(source)
        preview['content'] = source['content'].replace(
            revision['original'], revision['replacement'], 1)
        self.assertTrue(check_document(preview)['passed'])
        self.assertEqual(preview['content'].replace(
            revision['replacement'], revision['original'], 1), source['content'])

    def test_portion_arithmetic_and_boundaries(self):
        body = json.loads(Path(
            'content/revisions/editor-beginner-creatine-cost.json'
        ).read_text(encoding='utf-8'))['replacement']
        self.assertEqual(divmod(500, 3), (166, 2))
        # Proportional cost includes the remainder, rather than rounding
        # the number of portions and silently overstating cost per portion.
        self.assertEqual(Fraction(3, 500) * Fraction(500, 3), 1)
        for text in ('166 celých porcí', 'zbývají 2 g',
                     'skutečná cena balení × hmotnost porce v g',
                     'Nejde o ověřený výrobek ani doporučenou dávku',
                     'U směsí', 'neodhadujte', 'nemusíte kupovat nic'):
            self.assertIn(text, body)
        for text in ('Kč', '<a ', 'denně'):
            self.assertNotIn(text, body)


if __name__ == '__main__':
    unittest.main()
