import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import fetch_mod


class DownloadTests(unittest.TestCase):
    def test_missing_dependency_download_preserves_existing_manifest_entries(self):
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder) / 'plano.json'
            p.write_text(json.dumps({'minecraft': '1.21.1', 'loader': 'neoforge',
                                     'mods': [{'file': 'downloads/create.jar', 'project_id': 'existing'}]}))
            stream = io.BytesIO()
            with zipfile.ZipFile(stream, 'w') as z:
                z.writestr('test.txt', 'valid archive')
            payload = stream.getvalue()
            project = {'id': 'dep', 'title': 'Dependency', 'slug': 'dep'}
            version = {'id': 'version', 'project_id': 'dep', 'version_number': '1.0',
                       'game_versions': ['1.21.1'], 'loaders': ['neoforge'], 'dependencies': [],
                       'version_type': 'release', 'files': [{'filename': 'dep.jar', 'primary': True,
                       'url': 'https://cdn.modrinth.com/data/dep.jar',
                       'hashes': {'sha512': hashlib.sha512(payload).hexdigest()}}]}
            def api(endpoint):
                return [version] if '/version?' in endpoint else project
            with patch.object(fetch_mod, 'api', side_effect=api), patch.object(fetch_mod, 'request', return_value=payload):
                result = fetch_mod.fetch('dep', p)
            self.assertFalse(result['installed'])
            self.assertEqual(len(json.loads(p.read_text())['mods']), 2)
            self.assertEqual((Path(folder) / 'downloads/dep.jar').read_bytes(), payload)
            before = p.read_text()
            version['files'][0]['hashes']['sha512'] = 'bad'
            with patch.object(fetch_mod, 'api', side_effect=api), patch.object(fetch_mod, 'request', return_value=payload):
                with self.assertRaisesRegex(ValueError, 'SHA-512'):
                    fetch_mod.fetch('dep', p)
            self.assertEqual(p.read_text(), before)


if __name__ == '__main__':
    unittest.main()
