import hashlib
import json
from pathlib import Path
import unittest

from scripts.xfit_editorial_gate import check_document


class CreatineCheckoutProposalTests(unittest.TestCase):
    def test_local_preview_and_reversal(self):
        revision = json.loads(Path(
            'content/revisions/editor-chooser-creatine-checkout.json'
        ).read_text(encoding='utf-8'))
        raw = Path(revision['source_file']).read_bytes()
        document = json.loads(raw)
        body = document['content']
        self.assertEqual(hashlib.sha256(raw).hexdigest(),
                         revision['source_file_sha256'])
        self.assertEqual(hashlib.sha256(body.encode()).hexdigest(),
                         revision['source_content_sha256'])
        self.assertEqual(document['slug'], revision['slug'])
        self.assertEqual(revision['operation'], 'replace_exact_once')
        self.assertEqual(body.count(revision['original']), 1)

        replacement = revision['replacement']
        preview = body.replace(revision['original'], replacement, 1)
        self.assertEqual(preview.count(replacement), 1)
        self.assertEqual(preview.replace(replacement, revision['original'], 1), body)
        self.assertTrue(check_document(dict(document, content=preview))['passed'])
        for text in ('dopravy a povinných poplatků', 'čistou hmotností prášku',
                     'celkovou útratu', 'gramy, které skutečně využijete',
                     'bez uvedeného množství kreatinu cenu za gram kreatinu nepočítejte'):
            self.assertIn(text, replacement)
        self.assertNotIn('Kč', replacement)
        self.assertNotIn('<a ', replacement)
        self.assertIn('Nekupujte zatím nic.', preview)
