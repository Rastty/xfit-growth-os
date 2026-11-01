import hashlib
import json
from pathlib import Path
import unittest

from scripts.xfit_editorial_gate import Inspector, check_document


class ProteinComparisonHandoffTests(unittest.TestCase):
    def test_source_identity_preview_and_rollback(self):
        revision = json.loads(Path(
            'content/revisions/editor-protein-comparison-handoff.json'
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
        # The handoff must expose the limitation before the purchase checklist.
        body = revision['replacement']
        self.assertLess(body.index('Nejnižší cena prášku'),
                        body.index('Před nákupem'))
        for text in ('nikoli za 100 g bílkovin', 'konkrétní varianty',
                     'části 3', 'dopravu i alergeny', 'vyžádejte si etiketu',
                     'protein nemusíte kupovat', 'Affiliate odkazy'):
            self.assertIn(text, body)


if __name__ == '__main__':
    unittest.main()
