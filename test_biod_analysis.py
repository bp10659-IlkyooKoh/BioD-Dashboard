import io
import json
import unittest
import zipfile

import numpy as np
import pandas as pd
from openpyxl import load_workbook

from biod_analysis import (prepare, summarize, integrate_curve, auc_table, ratio_tables,
                           retention_table, reference_comparison, rank_candidates,
                           bh_adjust, build_report)


def fixture():
    rows = []
    for group, factor in [("Reference", 1), ("Candidate", 2)]:
        for organ, base in [("TUMOR", 8), ("KIDNEY", 4), ("BLOOD", 2)]:
            for time, decay in [(1, 1), (4, 0.5), (24, 0.25)]:
                for i, variation in enumerate([0.9, 1, 1.1]):
                    # Candidate has greater tumor exposure and lower organ exposure.
                    effect = factor if organ == "TUMOR" else 1 / factor
                    rows.append(dict(group_id=group, display_group_id=group, source_file="study.xlsx",
                                     source_cro="CRO", animal_id=f"{group}-{time}-{i}", organ=organ,
                                     timepoint_hour=time, percent_id_per_g=base * decay * effect * variation,
                                     row_type="raw", timepoint=f"{time}h"))
    return pd.DataFrame(rows)


class AnalysisTests(unittest.TestCase):
    def setUp(self):
        self.raw, self.issues = prepare(fixture())
        self.summary = summarize(self.raw)
        self.reference = self.raw.loc[self.raw.group_id == "Reference", "profile"].iloc[0]

    def test_auc_origins_and_measured_zero(self):
        self.assertAlmostEqual(integrate_curve([1, 3], [4, 2], "observed", 1, 3)[0], 6)
        self.assertAlmostEqual(integrate_curve([1, 3], [4, 2], "hold", 0, 3)[0], 10)
        self.assertAlmostEqual(integrate_curve([1, 3], [4, 2], "zero", 0, 3)[0], 8)
        self.assertAlmostEqual(integrate_curve([0, 3], [8, 2], "hold", 0, 3)[0], 15)
        self.assertAlmostEqual(integrate_curve([0, 3], [8, 2], "zero", 0, 3)[0], 15)

    def test_auc_common_window_and_missing_data(self):
        self.assertTrue(np.isnan(integrate_curve([1, 3], [4, 2], "observed", 0, 3)[0]))
        self.assertTrue(np.isnan(integrate_curve([1, 3], [4, 2], "hold", 0, 4)[0]))
        self.assertTrue(np.isnan(integrate_curve([1], [4], "hold", 0, 1)[0]))
        self.assertAlmostEqual(integrate_curve([1, 3], [4, 2], "observed", 1.5, 2.5)[0], 3)

    def test_ratio_and_rank(self):
        auc = auc_table(self.summary, "observed", 1, 24)
        ratios, ar = ratio_tables(self.summary, auc, "Tumor")
        cand = ratios[(ratios.label.str.startswith("Candidate")) & (ratios.organ == "Kidney")]
        np.testing.assert_allclose(cand.tumor_to_organ, 8)
        np.testing.assert_allclose(ar[(ar.label.str.startswith("Candidate")) & (ar.organ == "Kidney")].auc_ratio, 8)
        ranked = rank_candidates(auc, "Tumor", "Kidney")
        self.assertTrue(ranked.iloc[0].label.startswith("Candidate"))
        self.assertEqual(ranked.iloc[0]["rank"], 1)
        invalid = auc.copy()
        invalid.loc[invalid.organ == "Kidney", "auc"] = 0
        zero_ratios = ratio_tables(self.summary, invalid, "Tumor")[1]
        self.assertTrue(zero_ratios[zero_ratios.organ == "Kidney"].auc_ratio.isna().all())

    def test_retention(self):
        ret = retention_table(self.summary, 1, 4)
        np.testing.assert_allclose(ret.retention_pct, 50)
        np.testing.assert_allclose(ret.apparent_half_life_h, 3)
        self.assertTrue(retention_table(self.summary, 4, 1).retention_pct.isna().all())

    def test_stats_gates_and_change(self):
        out = reference_comparison(self.raw, self.summary, self.reference)
        self.assertTrue(out.p_value.isna().all())
        np.testing.assert_allclose(out[out.organ == "Tumor"].change_pct, 100)
        np.testing.assert_allclose(out[out.organ == "Kidney"].change_pct, -50)
        tested = reference_comparison(self.raw, self.summary, self.reference, True)
        self.assertTrue(tested.p_value.notna().all())
        self.assertTrue((tested.q_bh >= tested.p_value).all())
        mean_input = self.raw.copy()
        mean_input["row_type"] = "mean"
        self.assertTrue(reference_comparison(mean_input, summarize(mean_input), self.reference, True).p_value.isna().all())
        duplicate = pd.concat([fixture(), fixture().iloc[[0]]], ignore_index=True)
        duplicate, _ = prepare(duplicate)
        blocked = reference_comparison(duplicate, summarize(duplicate), self.reference, True)
        self.assertTrue(blocked[(blocked.organ == "Tumor") & (blocked.timepoint_hour == 1)].p_value.isna().all())

    def test_bh_known_values(self):
        np.testing.assert_allclose(bh_adjust([0.01, 0.04, 0.03, np.nan]), [0.03, 0.04, 0.04, np.nan])

    def test_reference_uses_two_sided_student_test(self):
        from scipy.stats import ttest_ind
        comparison = reference_comparison(self.raw, self.summary, self.reference, True)
        actual = comparison[(comparison.organ == "Tumor") & (comparison.timepoint_hour == 1)].p_value.iloc[0]
        expected = ttest_ind([14.4, 16, 17.6], [7.2, 8, 8.8], equal_var=True, alternative="two-sided").pvalue
        welch = ttest_ind([14.4, 16, 17.6], [7.2, 8, 8.8], equal_var=False, alternative="two-sided").pvalue
        self.assertAlmostEqual(actual, expected, places=12)
        self.assertGreater(abs(actual - welch), 1e-5)

    def test_missing_and_study_separation(self):
        other = fixture().assign(source_file="other.xlsx", percent_id_per_g=100)
        combined, _ = prepare(pd.concat([fixture(), other], ignore_index=True))
        self.assertEqual(combined.profile.nunique(), 4)
        self.assertEqual(len(summarize(combined)), 36)
        invalid = fixture().iloc[:2].copy()
        invalid.loc[0, "timepoint_hour"] = np.nan
        invalid.loc[1, "percent_id_per_g"] = -1
        clean, issues = prepare(invalid)
        self.assertTrue(clean.empty)
        self.assertEqual(issues.rows.iloc[0], 2)

    def test_same_filename_distinct_content_and_labels(self):
        first = fixture().assign(source_id="content-a")
        second = fixture().assign(source_id="content-b", percent_id_per_g=100)
        raw, _ = prepare(pd.concat([first, second], ignore_index=True))
        self.assertEqual(raw.profile.nunique(), 4)
        self.assertEqual(raw.label.nunique(), 4)

    def test_report_contains_results_and_escapes_uploads(self):
        report = build_report({"Summary": self.summary, "Labels": pd.DataFrame({"name": ["=1+1", "<script>alert(1)</script>"]})}, {"auc": "observed", "start": 1}, [])
        archive = zipfile.ZipFile(io.BytesIO(report))
        self.assertEqual(set(archive.namelist()), {"BioD_Report.html", "BioD_Analysis.xlsx", "settings.json"})
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", archive.read("BioD_Report.html").decode())
        wb = load_workbook(io.BytesIO(archive.read("BioD_Analysis.xlsx")))
        self.assertEqual(wb["Labels"]["A2"].data_type, "s")
        self.assertEqual(wb["Labels"]["A2"].value, "=1+1")
        self.assertEqual(json.loads(archive.read("settings.json"))["start"], 1)


if __name__ == "__main__":
    unittest.main()
