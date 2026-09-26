import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from PIL import Image

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'assemble.py'
spec = importlib.util.spec_from_file_location('assemble', SCRIPT)
assemble = importlib.util.module_from_spec(spec)
spec.loader.exec_module(assemble)


class AssembleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.pages = self.root / 'pages'
        self.pages.mkdir()
        Image.new('RGB', (20, 10), 'red').save(self.pages / '000.png')
        Image.new('RGB', (20, 10), 'blue').save(self.pages / '002.png')

    def manifest(self, **extra):
        value = {'pages': [{'file': '002.png'}, {'file': '000.png'}], **extra}
        (self.root / 'manifest.json').write_text(json.dumps(value))

    def test_completed_manifest_preserves_authoritative_order(self):
        self.manifest(completed=True, completionEvidence='viewer-restart-visible')
        images = assemble.order_pages(str(self.pages))
        try:
            self.assertEqual([image.getpixel((0, 0)) for image in images], [(0, 0, 255), (255, 0, 0)])
        finally:
            for image in images:
                image.close()

    def test_incomplete_and_legacy_are_rejected_before_pdf_creation(self):
        for fields in (
            {'completed': False, 'stopReason': 'deadline'}, {},
            {'completed': True, 'stopReason': 'frozen'},
        ):
            with self.subTest(fields=fields):
                self.manifest(**fields)
                output = self.root / 'result.pdf'
                result = subprocess.run([sys.executable, str(SCRIPT), str(self.pages), str(output)], capture_output=True, text=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('sem conclusão confirmada', result.stderr)
                self.assertFalse(output.exists())

    def test_explicit_partial_export_produces_pdf_with_warning(self):
        self.manifest(completed=False, stopReason='deadline')
        output = self.root / 'partial.pdf'
        result = subprocess.run([sys.executable, str(SCRIPT), str(self.pages), str(output), '--partial-export'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('em todas as páginas como PARCIAL', result.stderr)
        self.assertTrue(output.read_bytes().startswith(b'%PDF'))
        rendered = Image.new('RGB', (1920, 1080), 'white')
        assemble.add_label(rendered, 1, 2, partial=True)
        stripe = rendered.crop((20, 1010, 700, 1070))
        self.assertTrue(any(max(pixel) < 100 for pixel in stripe.get_flattened_data()))

    def test_manifest_cannot_reference_outside_frames(self):
        (self.root / 'manifest.json').write_text(json.dumps({'completed': True, 'completionEvidence': 'viewer-next-disabled', 'pages': [{'file': '../outside.png'}]}))
        with self.assertRaises(SystemExit):
            assemble.order_pages(str(self.pages))


if __name__ == '__main__':
    unittest.main()
