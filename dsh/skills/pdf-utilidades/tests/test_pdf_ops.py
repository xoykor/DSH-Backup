import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "pdf_ops.py"


class PdfOpsTest(unittest.TestCase):
    def test_inspect_split_reorder_merge_and_render(self):
        from pypdf import PdfReader
        from reportlab.pdfgen import canvas
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "entrada.pdf"
            pdf = canvas.Canvas(str(source))
            pdf.drawString(72, 720, "page one")
            pdf.showPage()
            pdf.drawString(72, 720, "page two")
            pdf.save()
            inspect = subprocess.run([sys.executable, str(SCRIPT), "inspect", "--input", str(source)], capture_output=True, text=True)
            self.assertEqual(inspect.returncode, 0, inspect.stderr)
            self.assertEqual(json.loads(inspect.stdout)["classification"], "textual")
            reordered = root / "reordered.pdf"
            result = subprocess.run([sys.executable, str(SCRIPT), "reorder", "--input", str(source), "--output", str(reordered), "--pages", "2,1"], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            pages = PdfReader(str(reordered)).pages
            self.assertIn("page two", pages[0].extract_text())
            split_dir = root / "split"
            split = subprocess.run([sys.executable, str(SCRIPT), "split", "--input", str(source), "--output-dir", str(split_dir)], capture_output=True, text=True)
            self.assertEqual(split.returncode, 0, split.stderr)
            merged = root / "merged.pdf"
            merge = subprocess.run([sys.executable, str(SCRIPT), "merge", "--inputs", str(split_dir / "page-002.pdf"), str(split_dir / "page-001.pdf"), "--output", str(merged)], capture_output=True, text=True)
            self.assertEqual(merge.returncode, 0, merge.stderr)
            rendered = root / "rendered"
            render = subprocess.run([sys.executable, str(SCRIPT), "render", "--input", str(merged), "--output-dir", str(rendered)], capture_output=True, text=True)
            self.assertEqual(render.returncode, 0, render.stderr)
            self.assertEqual(len(list(rendered.glob("*.png"))), 2)


if __name__ == "__main__":
    unittest.main()
