"""Exercise real Excel parsing and the Streamlit widget/rerun path."""
import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest


class DashboardTests(unittest.TestCase):
    def test_four_compound_analysis_and_report(self):
        app_path = str(Path(__file__).with_name("app.py"))
        script = '''
import io
import runpy
import streamlit as st
from unittest.mock import patch
from test_biod_mollim import multi_compound_fixture
from biod_analysis import prepare, summarize, auc_table, rank_candidates, ratio_tables
if "four_compound_bytes" not in st.session_state:
    upload = io.BytesIO()
    data = multi_compound_fixture()
    data["Compound"] = data.Compound.replace({"Reference": "AC-SK-001", "Candidate A": "AC-SK-004", "Candidate B": "AC-SK-048", "Candidate C": "AC-SK-002"})
    data["Timepoint"] = data.Timepoint.replace({"24h": "48h"})
    data.to_excel(upload, index=False, startrow=3)
    st.session_state.four_compound_bytes = upload.getvalue()
upload = io.BytesIO(st.session_state.four_compound_bytes)
upload.name = "Synthetic_Four_Compounds.xlsx"
with patch("streamlit.file_uploader", return_value=[upload]):
    result = runpy.run_path(APP_PATH, run_name="__main__")
raw = result["analysis_input"]
assert raw.group_id.nunique() == 4
assert set(raw.group_id) == {"AC-SK-001", "AC-SK-004", "AC-SK-048", "AC-SK-002"}
assert result["master"].group_id.nunique() == 4
assert all(set(g.timepoint_hour) == {1, 4, 48} for _, g in raw.groupby("group_id"))
assert len(raw) == 108
assert raw.compound_column.eq("Compound").all()
valid, _ = prepare(raw)
summary = summarize(valid)
aucs = auc_table(summary, "observed", 1, 48)
ranking = rank_candidates(aucs, "Tumor", "Kidney")
assert "AC-SK-048" in ranking.iloc[0].label
assert abs(ranking.iloc[0].tumor_auc - 300) < 1e-8
assert abs(ranking.iloc[0].auc_ratio - 8) < 1e-8
'''.replace("APP_PATH", repr(app_path))
        app = AppTest.from_string(script, default_timeout=90).run()
        self.assertEqual(len(app.exception), 0, [e.message for e in app.exception])
        self.assertTrue(any(w.label == "One-click BioD Report 다운로드" for w in app.get("download_button")))
        tab_labels = [t.label for t in app.tabs]
        self.assertLess(tab_labels.index("Candidate Analysis"), tab_labels.index("BioD Report"))
        self.assertNotIn("🧬 BioD Report & Candidate Analysis", tab_labels)
        self.assertEqual(len(app.number_input), 0)
        self.assertFalse(any("가중치" in w.label for w in app.slider))
        candidate = next(t for t in app.tabs if t.label == "Candidate Analysis")
        report = next(t for t in app.tabs if t.label == "BioD Report")
        self.assertEqual(len(candidate.get("download_button")), 0)
        self.assertEqual(len(report.get("download_button")), 1)

    def test_excel_upload_and_analysis_controls(self):
        app_path = str(Path(__file__).with_name("app.py"))
        script = '''
import io
import runpy
import streamlit as st
from unittest.mock import patch
from test_biod_analysis import fixture
data = fixture().rename(columns={"group_id": "Group", "animal_id": "Mouse", "organ": "Organ", "timepoint": "Timepoint", "percent_id_per_g": "Uptake (%ID/g)"})
upload = io.BytesIO()
data[["Group", "Mouse", "Organ", "Timepoint", "Uptake (%ID/g)"]].to_excel(upload, index=False)
if "test_upload_bytes" not in st.session_state:
    st.session_state.test_upload_bytes = upload.getvalue()
upload = io.BytesIO(st.session_state.test_upload_bytes)
upload.name = "mollim_study.xlsx"
upload.seek(0)
with patch("streamlit.file_uploader", return_value=[upload]):
    runpy.run_path(APP_PATH, run_name="__main__")
'''.replace("APP_PATH", repr(app_path))
        app = AppTest.from_string(script, default_timeout=90).run()
        self.assertEqual(len(app.exception), 0, [e.message for e in app.exception])
        self.assertGreater(len(app.dataframe), 10)
        auc_select = next(w for w in app.selectbox if w.label == "AUC 계산 방식")
        auc_select.set_value("hold")
        next(w for w in app.checkbox if "독립된 개체군" in w.label).check()
        app.run()
        self.assertEqual(len(app.exception), 0, [e.message for e in app.exception])
        self.assertEqual(app.select_slider(key="analysis_auc_window_hold").value, (0.0, 24.0))
        next(w for w in app.selectbox if w.label == "AUC 계산 방식").set_value("observed").run()
        self.assertEqual(len(app.exception), 0, [e.message for e in app.exception])
        self.assertEqual(app.select_slider(key="analysis_auc_window_observed").value, (1.0, 24.0))
        app.multiselect(key="analysis_profiles").set_value([]).run()
        self.assertEqual(len(app.exception), 0)
        self.assertTrue(any("분석 대상을 선택" in w.value for w in app.info))

    def test_minerva_and_kirams_summary_uploads(self):
        app_path = str(Path(__file__).with_name("app.py"))
        script = '''
import io
import runpy
from unittest.mock import patch
import pandas as pd
from test_biod_analysis import fixture
data = fixture().rename(columns={"group_id": "Group", "animal_id": "Animal ID", "organ": "Organ", "timepoint": "Timepoint", "percent_id_per_g": "Uptake (%ID/g) - Tail corrected"})
minerva = io.BytesIO()
data.to_excel(minerva, sheet_name="TC ex vivo", index=False)
minerva.name = "minerva_study.xlsx"
minerva.seek(0)
graph = pd.DataFrame([
    ["#101", "1d", None, None, None, None],
    [None, "Tumor", "Blood", "Kidney", "Liver", "Heart"],
    ["Mean", 10, 2, 3, 4, 1],
    ["#101", "2d", None, None, None, None],
    ["Mean", 5, 1, 1.5, 2, 0.5],
])
kirams = io.BytesIO()
graph.to_excel(kirams, sheet_name="graph", header=False, index=False)
kirams.name = "kirams_study.xlsx"
kirams.seek(0)
with patch("streamlit.file_uploader", return_value=[minerva, kirams]):
    result = runpy.run_path(APP_PATH, run_name="__main__")
    parsed = result["analysis_input"]
    kirams_data = parsed[parsed.source_cro == "KIRAMS"]
    assert len(kirams_data) == 10
    assert set(kirams_data.timepoint_hour) == {24, 48}
    assert kirams_data.row_type.eq("mean").all()
    assert len(parsed[parsed.source_cro == "Minerva"]) == 54
'''.replace("APP_PATH", repr(app_path))
        app = AppTest.from_string(script, default_timeout=90).run()
        self.assertEqual(len(app.exception), 0, [e.message for e in app.exception])


if __name__ == "__main__":
    unittest.main()
