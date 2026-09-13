import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "plot_table.py"


class PlotTableTest(unittest.TestCase):
    def test_chart_and_provenance_are_created(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "metrics.csv"
            source.write_text("month,revenue\nJan,10\nFeb,15\nMar,12\n", encoding="utf-8")
            spec = root / "spec.json"
            spec.write_text(json.dumps({"kind": "line", "x": "month", "y": "revenue", "title": "Revenue", "ylabel": "USD", "marker": "o"}), encoding="utf-8")
            output = root / "chart.png"
            provenance = root / "provenance"
            result = subprocess.run([sys.executable, str(SCRIPT), "--input", str(source), "--spec", str(spec), "--output", str(output), "--provenance-dir", str(provenance)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertGreater(output.stat().st_size, 1000)
            self.assertTrue((provenance / "source-table.csv").exists())
            self.assertTrue((provenance / "chart-spec.json").exists())
            report = json.loads((provenance / "provenance.json").read_text(encoding="utf-8"))
            self.assertEqual((report["rows"], report["x"], report["y"]), (3, "month", ["revenue"]))

    def test_non_numeric_y_fails_before_writing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "metrics.csv"
            source.write_text("x,y\n1,nope\n", encoding="utf-8")
            spec = root / "spec.json"
            spec.write_text(json.dumps({"kind": "bar", "x": "x", "y": "y"}), encoding="utf-8")
            output = root / "chart.png"
            result = subprocess.run([sys.executable, str(SCRIPT), "--input", str(source), "--spec", str(spec), "--output", str(output), "--provenance-dir", str(root / "prov")], capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            self.assertFalse(output.exists())
            self.assertIn("non-numeric", result.stderr)

    def test_non_finite_and_multiseries_bar_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "metrics.csv"
            source.write_text("x,a,b\n1,nan,2\n", encoding="utf-8")
            spec = root / "spec.json"
            spec.write_text(json.dumps({"kind": "bar", "x": "x", "y": ["a", "b"]}), encoding="utf-8")
            result = subprocess.run([sys.executable, str(SCRIPT), "--input", str(source), "--spec", str(spec), "--output", str(root / "chart.png"), "--provenance-dir", str(root / "prov")], capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            self.assertIn("multiple y", result.stderr)
            spec.write_text(json.dumps({"kind": "line", "x": "x", "y": "a"}), encoding="utf-8")
            result = subprocess.run([sys.executable, str(SCRIPT), "--input", str(source), "--spec", str(spec), "--output", str(root / "chart2.png"), "--provenance-dir", str(root / "prov2")], capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            self.assertIn("non-finite", result.stderr)


if __name__ == "__main__":
    unittest.main()
