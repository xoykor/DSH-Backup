import argparse
import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1] / "scripts" / "ocr_local.py"
spec = importlib.util.spec_from_file_location("ocr_local", MODULE)
ocr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ocr)


class OCRTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def args(self, source, **kw):
        data = dict(input=source, output_dir=self.root / "out", pages=None, lang="por", tessdata_dir=None,
                    dpi=150, psm=6, timeout_seconds=30)
        data.update(kw)
        return argparse.Namespace(**data)

    def make_image(self):
        from PIL import Image, ImageDraw, ImageFont
        image = Image.new("RGB", (1100, 300), "white")
        font = ImageFont.truetype("/usr/share/fonts/TTF/DejaVuSans.ttf", 42)
        ImageDraw.Draw(image).text((40, 80), "Relatório local: ação e saúde 12345", fill="black", font=font)
        path = self.root / "source.png"
        image.save(path)
        return path, image

    def test_page_ranges(self):
        self.assertEqual(ocr.select_pages("3,1-2", 4), [3, 1, 2])
        for value in ["1,1", "0", "1-101", "4-2", "5", "1,,2"]:
            with self.assertRaises(ocr.OCRError):
                ocr.select_pages(value, 4)

    @unittest.skipUnless(shutil.which("tesseract"), "Tesseract required")
    def test_portuguese_image_and_preserved_source(self):
        path, _ = self.make_image()
        before = ocr.digest(path)
        result = ocr.ocr(self.args(path))
        self.assertEqual(result["status"], "completed", result)
        text = Path(result["pages"][0]["text"]).read_text()
        self.assertIn("12345", text)
        self.assertIn("saúde", text.lower())
        self.assertTrue(Path(result["pages"][0]["tsv"]).exists())
        self.assertEqual(before, ocr.digest(path))
        self.assertEqual(result["languages"], ["por"])
        with self.assertRaises(FileExistsError):
            ocr.ocr(self.args(path))

    @unittest.skipUnless(shutil.which("tesseract") and shutil.which("pdftoppm") and shutil.which("pdfinfo"), "OCR/Poppler required")
    def test_scanned_pdf_selected_page(self):
        _, image = self.make_image()
        from PIL import Image
        pdf = self.root / "scanned.pdf"
        blank = Image.new("RGB", image.size, "white")
        blank.save(pdf, save_all=True, append_images=[image], resolution=100)
        result = ocr.ocr(self.args(pdf, pages="2"))
        self.assertEqual(result["status"], "completed", result)
        self.assertEqual(result["source_pages"], 2)
        self.assertEqual(result["requested_pages"], [2])
        self.assertIn("12345", Path(result["pages"][0]["text"]).read_text())
        self.assertFalse((self.root / "out/page-001.txt").exists())

    @unittest.skipUnless(shutil.which("tesseract"), "Tesseract required")
    def test_missing_language_no_output(self):
        path, _ = self.make_image()
        with self.assertRaisesRegex(ocr.OCRError, "missing Tesseract language"):
            ocr.ocr(self.args(path, lang="missing_dsh_language"))
        self.assertFalse((self.root / "out").exists())

    @unittest.skipUnless(shutil.which("tesseract"), "Tesseract required")
    def test_blank_image_reported_empty(self):
        from PIL import Image
        path = self.root / "blank.png"
        Image.new("RGB", (300, 100), "white").save(path)
        result = ocr.ocr(self.args(path))
        self.assertEqual(result["status"], "completed_empty", result)
        self.assertTrue(result["pages"][0]["empty"])


if __name__ == "__main__":
    unittest.main()
