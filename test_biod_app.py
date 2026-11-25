"""Exercise real Excel parsing and the Streamlit widget/rerun path."""
import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest


class DashboardTests(unittest.TestCase):
    def test_shared_calculation_pipeline_across_every_tab(self):
        app_path = str(Path(__file__).with_name("app.py"))
        script = '''
import io
import runpy
from unittest.mock import patch
import numpy as np
import pandas as pd
import streamlit as st
import biod_ui
from biod_analysis import prepare, summarize, auc_table
if "shared_pipeline_uploads" not in st.session_state:
    blobs = {}
    for number, scale in [(1, 1), (2, 2)]:
        records = []
        for time, tvalue, kvalue in [("1h", 10, 2), ("4h", 8, 1), ("24h", 4, 0.5), ("1d", 6, 1.5)]:
            for organ, value in [("tumour", tvalue), ("KIDNEY", kvalue)]:
                records.append({"Compound": "AC-SK-001", "Timepoint": time, "Mouse": time, "Organ": organ, "%ID/g": value * scale})
        for time, value in [("1h", -100), ("4h", np.inf), ("unknown", 9999)]:
            records.append({"Compound": "AC-SK-001", "Timepoint": time, "Mouse": "invalid", "Organ": "Tumor", "%ID/g": value})
        stream = io.BytesIO()
        pd.DataFrame(records).to_excel(stream, index=False)
        blobs[f"study{number}.xlsx"] = stream.getvalue()
    st.session_state.shared_pipeline_uploads = blobs
uploads = []
for name, blob in st.session_state.shared_pipeline_uploads.items():
    file = io.BytesIO(blob)
    file.name = name
    uploads.append(file)
with patch("streamlit.file_uploader", return_value=uploads), patch("biod_analysis.prepare", wraps=prepare) as cleaning, patch("biod_analysis.summarize", wraps=summarize) as aggregation, patch("biod_ui.auc_table", wraps=auc_table) as integration, patch("streamlit.download_button", wraps=st.download_button) as downloads:
    result = runpy.run_path(APP_PATH, run_name="__main__")
assert cleaning.call_count == aggregation.call_count == integration.call_count == 1
master, summary, chart = result["master"], result["shared_summary"], result["chart_data"]
assert master is result["analysis_input"]
assert len(master) == 16 and len(summary) == 12
assert set(master.timepoint) == {"1h", "4h", "24h"}
assert len(result["quality_issues"]) and result["quality_issues"].rows.iloc[0] == 6
assert summary.profile.nunique() == summary.label.nunique() == 2
pd.testing.assert_frame_equal(summary[["profile", "organ", "timepoint_hour", "mean", "sd"]], chart[["profile", "organ", "timepoint_hour", "mean_id_g", "std_id_g"]].rename(columns={"mean_id_g": "mean", "std_id_g": "sd"}))
mean_table = result["pivot_df"]
assert "1d" not in mean_table
tumor_rows = mean_table[mean_table["장기(Organ)"] == "Tumor"]
assert set(tumor_rows["24h"]) == {5, 10}
context = result["analysis_context"]
expected_tumor = {"observed": 157, "hold": 167, "zero": 162}[context["method"]]
expected_kidney = {"observed": 24.5, "hold": 26.5, "zero": 25.5}[context["method"]]
aucs = context["aucs"]
assert set(aucs[aucs.organ == "Tumor"].auc) == {expected_tumor, expected_tumor * 2}
assert set(aucs[aucs.organ == "Kidney"].auc) == {expected_kidney, expected_kidney * 2}
pk = result["auc_df"]
for _, row in pk.iterrows():
    source = aucs[(aucs.label == row["물질명"]) & (aucs.organ == row["장기(Organ)"])].iloc[0]
    assert row["AUC"] == source.auc and row["시작(h)"] == source.start_h and row["종료(h)"] == source.end_h
exports = {call.kwargs.get('key'): call.kwargs for call in downloads.call_args_list}
report_ranking = pd.read_excel(io.BytesIO(exports['report_excel']['data']), sheet_name='후보 비교')
assert set(report_ranking['Tumor AUC']) == {expected_tumor, expected_tumor * 2}
assert set(report_ranking['Kidney AUC']) == {expected_kidney, expected_kidney * 2}
mean_export = next(call.kwargs['data'] for call in downloads.call_args_list if call.kwargs.get('label') == '📥 현재 표를 Excel로 다운로드')
mean_export = pd.read_excel(io.BytesIO(mean_export), sheet_name='Mean_Table')
assert set(mean_export[mean_export['장기(Organ)']=='Tumor']['24h']) == {5, 10}
'''.replace("APP_PATH", repr(app_path))
        app = AppTest.from_string(script, default_timeout=90).run()
        self.assertEqual(len(app.exception), 0, [e.message for e in app.exception])
        next(w for w in app.selectbox if w.label == "AUC 계산 방식").set_value("hold").run()
        self.assertEqual(len(app.exception), 0, [e.message for e in app.exception])
        self.assertFalse(any(w.key == "legacy_auc_method" for w in app.selectbox))

    def test_four_compound_analysis_and_report(self):
        app_path = str(Path(__file__).with_name("app.py"))
        script = '''
import io
import runpy
import streamlit as st
from unittest.mock import patch
from test_biod_mollim import multi_compound_fixture
from biod_analysis import prepare, summarize, auc_table, rank_candidates, ratio_tables, AUC_METHODS
if "four_compound_bytes" not in st.session_state:
    upload = io.BytesIO()
    data = multi_compound_fixture()
    data["Compound"] = data.Compound.replace({"Reference": "AC-SK-001", "Candidate A": "AC-SK-004", "Candidate B": "AC-SK-048", "Candidate C": "AC-SK-002"})
    data["Timepoint"] = data.Timepoint.replace({"24h": "48h"})
    data.to_excel(upload, index=False, startrow=3)
    st.session_state.four_compound_bytes = upload.getvalue()
upload = io.BytesIO(st.session_state.four_compound_bytes)
upload.name = "Synthetic_Four_Compounds.xlsx"
with patch("streamlit.file_uploader", return_value=[upload]), patch("streamlit.download_button", wraps=st.download_button) as export_calls:
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
downloads = {call.kwargs.get("key"): call.kwargs for call in export_calls.call_args_list}
for key, sheet in [("ratio_excel", "Organ_Ratio"), ("auc_ratio_excel", "Organ_AUC_Ratio")]:
    contents = downloads[key]["data"]
    from openpyxl import load_workbook
    assert load_workbook(io.BytesIO(contents)).active.title == sheet
    import pandas as pd
    table = pd.read_excel(io.BytesIO(contents), sheet_name=sheet)
    assert table.shape == ((12, 5) if key == "ratio_excel" else (4, 4))
    assert abs(table.loc[table["물질"].str.endswith("AC-SK-048"), table.columns[-1]].iloc[0] - 8) < 1e-8
    settings = pd.read_excel(io.BytesIO(contents), sheet_name="Settings").set_index("setting")["value"]
    assert settings["organ"] == "Kidney"
    if key == "ratio_excel":
        assert set(table["시간 (h)"]) == {1, 4, 48}
        assert settings["time_scope"] == "All observed timepoints"
    else:
        assert float(settings["start_h"]) == 1 and float(settings["end_h"]) == 48
        assert settings["auc_method"] == AUC_METHODS["observed"]
from pypdf import PdfReader
pdf = PdfReader(io.BytesIO(downloads["report_pdf"]["data"]))
assert 2 <= len(pdf.pages) <= 4
pdf_text = ''.join(page.extract_text() for page in pdf.pages)
assert "BioD 결과 보고서" in pdf_text and "Student" in pdf_text
assert "AC-SK-048" in pdf_text and "AI 해석은 포함하지 않습니다" in pdf_text
report_tables = pd.read_excel(io.BytesIO(downloads["report_excel"]["data"]), sheet_name=None)
assert list(report_tables)[0] == "결과 요약"
assert set(report_tables["시간별 장기 비율"]["시간 (h)"]) == {1, 4, 48}
'''.replace("APP_PATH", repr(app_path))
        app = AppTest.from_string(script, default_timeout=90).run()
        self.assertEqual(len(app.exception), 0, [e.message for e in app.exception])
        self.assertTrue(any(w.label == "📄 결과 보고서 PDF 다운로드" for w in app.get("download_button")))
        tab_labels = [t.label for t in app.tabs]
        self.assertLess(tab_labels.index("🧪 Candidate Analysis"), tab_labels.index("📄 BioD Report"))
        self.assertNotIn("🧬 BioD Report & Candidate Analysis", tab_labels)
        self.assertEqual(len(app.number_input), 0)
        self.assertFalse(any("가중치" in w.label for w in app.slider))
        candidate = next(t for t in app.tabs if t.label == "🧪 Candidate Analysis")
        report = next(t for t in app.tabs if t.label == "📄 BioD Report")
        self.assertEqual(len(candidate.get("download_button")), 2)
        self.assertEqual(len(report.get("download_button")), 2)
        ratio_tab = next(t for t in app.tabs if t.label == "장기 비율")
        self.assertEqual(len(ratio_tab.get("download_button")), 2)
        overview = next(t for t in app.tabs if t.label == "후보 비교")
        import json
        plot = json.loads(overview.get("plotly_chart")[0].proto.spec)
        self.assertEqual([t["type"] for t in plot["data"]], ["bar", "bar"])
        self.assertTrue(all("AC-SK-" in name for t in plot["data"] for name in t["y"]))
        self.assertEqual(plot["layout"]["xaxis"]["range"], plot["layout"]["xaxis2"]["range"])
        headings = [m.value for m in ratio_tab.markdown]
        self.assertIn("#### Tumor-Organ ratio", headings)
        self.assertIn("#### Tumor-Organ ratio (AUC)", headings)
        ratios, auc_ratios = [d.value for d in ratio_tab.dataframe]
        self.assertEqual(list(ratios), ["물질", "Kidney Mean", "Tumor Mean", "Tumor/Organ ratio"])
        self.assertEqual(list(auc_ratios), ["물질", "Kidney AUC", "Tumor AUC", "Tumor/Organ AUC ratio"])
        row = ratios[ratios["물질"].str.endswith("AC-SK-048")].iloc[0]
        self.assertAlmostEqual(row["Tumor/Organ ratio"], 8)
        retention_tab = next(t for t in app.tabs if t.label == "유지율·감소율")
        retention = retention_tab.dataframe[0].value
        self.assertEqual(list(retention), ["물질", "유지율 (%)", "감소율 (%)"])
        self.assertTrue(retention["유지율 (%)"].eq(25).all())
        self.assertEqual(len(retention_tab.get("plotly_chart")), 1)
        reference_tab = next(t for t in app.tabs if t.label == "Reference 비교")
        comparison = reference_tab.dataframe[0].value
        self.assertEqual(list(comparison), ["물질", "후보 Mean", "Reference Mean", "증감률 (%)", "p값 (Student t-test)", "보정 p값 (BH q)", "검정 결과"])
        self.assertTrue(comparison["p값 (Student t-test)"].eq("—").all())
        self.assertTrue(any("양측 Student" in c.value and "Benjamini" in c.value for c in reference_tab.caption))

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
        reference_tab = next(t for t in app.tabs if t.label == "Reference 비교")
        self.assertTrue(reference_tab.dataframe[0].value["p값 (Student t-test)"].ne("—").all())
        app.selectbox(key="reference_time_filter").set_value(1.0).run()
        self.assertEqual(len(app.exception), 0, [e.message for e in app.exception])
        next(w for w in app.selectbox if w.label == "AUC 계산 방식").set_value("observed").run()
        self.assertEqual(len(app.exception), 0, [e.message for e in app.exception])
        self.assertEqual(app.select_slider(key="analysis_auc_window_observed").value, (1.0, 24.0))
        selected = app.multiselect(key="analysis_profiles").value
        app.multiselect(key="analysis_profiles").set_value(selected[:1]).run()
        self.assertEqual(len(app.exception), 0, [e.message for e in app.exception])
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
    assert result["chart_data"].loc[result["chart_data"].summary_input, "std_id_g"].isna().all()
'''.replace("APP_PATH", repr(app_path))
        app = AppTest.from_string(script, default_timeout=90).run()
        self.assertEqual(len(app.exception), 0, [e.message for e in app.exception])


if __name__ == "__main__":
    unittest.main()
