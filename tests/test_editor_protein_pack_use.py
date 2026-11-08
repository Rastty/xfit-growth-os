import hashlib
import json
from fractions import Fraction
from pathlib import Path
import unittest

from scripts.xfit_editorial_gate import Inspector, check_document


class ProteinPackUseTests(unittest.TestCase):
    def test_snapshot_preview_and_exact_rollback(self):
        revision = json.loads(Path(
            'content/revisions/editor-protein-pack-use.json'
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
        self.assertEqual(before.headers, after.headers)

    def test_planned_use_example_and_limits(self):
        # These are hypothetical pack/portion sizes, not product or dose data.
        portions = Fraction(1000, 25)
        self.assertEqual(portions, 40)
        self.assertEqual(portions / 2, 20)
        body = json.loads(Path(
            'content/revisions/editor-protein-pack-use.json'
        ).read_text(encoding='utf-8'))['replacement']
        for text in ('1 000 g ÷ 25 g = 40 porcí', '20 týdnů',
                     'Nejde o doporučenou dávku ani četnost',
                     'výpočet trvanlivost neurčuje', 'po otevření',
                     'zvažte menší', 'protein nemusíte kupovat'):
            self.assertIn(text, body)


if __name__ == '__main__':
    unittest.main()
