import unittest

from biod_analysis import prepare, summarize, auc_table, rank_candidates, retention_table, reference_comparison, AUC_METHODS
from biod_reporting import summarize_results
from test_biod_analysis import fixture


class ReportingTests(unittest.TestCase):
    def test_summary_preserves_unavailable_and_untested_results(self):
        raw, _ = prepare(fixture())
        summary = summarize(raw)
        reference = raw.loc[raw.group_id == "Reference", "profile"].iloc[0]
        names = raw.drop_duplicates("profile").set_index("profile").display_group_id.to_dict()
        settings = dict(target="Tumor", comparator="Kidney", selected_profiles=list(names), start_h=1, end_h=24,
                        reference_name="Reference", auc_method=AUC_METHODS["observed"], early_h=24, late_h=1,
                        retention_organ="Tumor", reference_view_organ="Tumor", reference_view_time_h=24)
        ranking = rank_candidates(auc_table(summary, "observed", 1, 48), "Tumor", "Kidney")
        retention = retention_table(summary, 24, 1)
        comparison = reference_comparison(raw, summary, reference, False)
        comparison = comparison[(comparison.organ == "Tumor") & (comparison.timepoint_hour == 24)]
        sections = dict(summarize_results(ranking, retention, comparison, settings, names))
        self.assertIn("순위를 산출하지 못했습니다", sections["주요 관찰"])
        self.assertIn("유지율을 산출하지 못했습니다", sections["유지율·감소율"])
        self.assertIn("0건에서 검정", sections["Reference 비교 및 통계"])
        self.assertIn("미산출 사유", sections["Reference 비교 및 통계"])
        self.assertNotIn("q<0.05인 비교는 0건", sections["Reference 비교 및 통계"])
        self.assertIn("AI 해석은 포함하지 않습니다", sections["해석 범위"])


if __name__ == "__main__":
    unittest.main()
