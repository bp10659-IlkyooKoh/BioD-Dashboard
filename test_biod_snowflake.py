"""Verify the distributed sources, independent of the checkout and OS fonts."""
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

from build_snowflake_package import ROOT, RUNTIME_FILES, build


class SnowflakePackageTests(unittest.TestCase):
    def test_archive_runs_without_checkout_or_system_fonts(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            _, archive = build(output)
            extracted = output / "unpacked"
            with zipfile.ZipFile(archive) as bundle:
                self.assertEqual(set(bundle.namelist()), set(RUNTIME_FILES))
                for relative in RUNTIME_FILES:
                    self.assertEqual(bundle.read(relative), (ROOT / relative).read_bytes())
                bundle.extractall(extracted)
            # -I excludes both the checkout and PYTHONPATH. Only the ZIP's sources
            # are added back, with a working directory outside the app directory.
            script = '''
import io, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import pandas as pd
from pypdf import PdfReader
from reportlab.pdfbase import pdfmetrics
from biod_reporting import report_pdf
from streamlit.testing.v1 import AppTest
for name in ("biod_analysis", "biod_ui", "biod_labels", "biod_mollim"):
    __import__(name)
payload = report_pdf([("분석 범위", "한글 표적 장기 유지율·감소율과 Reference 비교")],
                     {"핵심 수치": pd.DataFrame({"물질": ["AC-SK-001"], "평균": [1.5]})})
reader = PdfReader(io.BytesIO(payload))
text = "".join(page.extract_text() for page in reader.pages)
assert "한글 표적 장기" in text and "AC-SK-001" in text
for name in ("BioDText", "BioDBold"):
    font = pdfmetrics.getFont(name)
    assert Path(font.face.filename).is_relative_to(Path(sys.argv[1]) / "fonts")
    for character in "한글결과보고서유지율감소율":
        assert font.face.charToGlyph.get(ord(character), 0) != 0
app = AppTest.from_file(str(Path(sys.argv[1]) / "streamlit_app.py"), default_timeout=60).run()
assert not app.exception, [e.message for e in app.exception]
app.run()
assert not app.exception, [e.message for e in app.exception]
'''
            result = subprocess.run([sys.executable, "-I", "-c", script, str(extracted)],
                                    cwd=output, capture_output=True, text=True, timeout=150)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_package_refuses_unexpected_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            directory, _ = build(output)
            (directory / "private_data.xlsx").write_bytes(b"do not distribute")
            with self.assertRaisesRegex(RuntimeError, "private_data.xlsx"):
                build(output)


if __name__ == "__main__":
    unittest.main()
