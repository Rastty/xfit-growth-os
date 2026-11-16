import hashlib
import json
from pathlib import Path
import unittest

from scripts.xfit_editorial_gate import Inspector, check_document


class ProteinFirstScreenTests(unittest.TestCase):
    def test_exact_source_preview_and_rollback(self):
        revision = json.loads(Path(
            'content/revisions/editor-protein-first-screen.json'
        ).read_text(encoding='utf-8'))
        raw = Path(revision['source_file']).read_bytes()
        source = json.loads(raw)
        self.assertEqual(hashlib.sha256(raw).hexdigest(),
                         revision['source_file_sha256'])
        self.assertEqual(hashlib.sha256(source['content'].encode()).hexdigest(),
                         revision['source_content_sha256'])
        for key in ('slug', 'wp_post_id'):
            self.assertEqual(source[key], revision[key])
        self.assertEqual(revision['operation'], 'replace_exact_once')
        original, replacement = revision['original'], revision['replacement']
        self.assertTrue(source['content'].startswith(original + '\n'))
        self.assertEqual(source['content'].count(original), 1)
        preview = dict(source)
        preview['content'] = source['content'].replace(original, replacement, 1)
        self.assertTrue(check_document(preview)['passed'])
        self.assertEqual(preview['content'].replace(replacement, original, 1),
                         source['content'])
        # The new verdict must preserve the rest of the guide and all links.
        self.assertEqual(preview['content'].split('\n', 1)[1],
                         source['content'].split('\n', 1)[1])
        before, after = Inspector(), Inspector()
        before.feed(source['content'])
        after.feed(preview['content'])
        self.assertEqual(before.links, after.links)
        steps = ('nemusíte kupovat nic', 'v části 1', 'podle části 2',
                 'v části 3', 'bez etikety')
        positions = [replacement.index(step) for step in steps]
        self.assertEqual(positions, sorted(positions))
        for heading in ('1. Kolik bílkovin', '2. Koncentrát',
                        '3. Jak poznat skutečně výhodnou cenu'):
            self.assertIn('<h2>' + heading, source['content'])
        self.assertIn('alergeny konkrétní varianty', replacement)
        self.assertIn('stejné množství skutečných bílkovin', replacement)


if __name__ == '__main__':
    unittest.main()
