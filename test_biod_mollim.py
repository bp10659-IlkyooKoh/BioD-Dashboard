import io
import unittest

import pandas as pd

from biod_mollim import parse_mollim_workbook


def workbook(table, **kwargs):
    stream = io.BytesIO()
    table.to_excel(stream, index=False, **kwargs)
    stream.seek(0)
    return stream


class MolimParserTests(unittest.TestCase):
    def test_explicit_compound_takes_priority_over_cohort(self):
        table = pd.DataFrame({"Group": ["G1"] * 4, "Compound": ["C1", "C2", "C3", "C4"],
                              "Timepoint": ["1h"] * 4, "Organ": ["Tumor"] * 4,
                              "Mouse": [1, 2, 3, 4], "%ID/g": [1, 2, 3, 4]})
        parsed = parse_mollim_workbook(workbook(table), lambda t: 1)
        self.assertEqual(parsed.group_id.tolist(), ["C1", "C2", "C3", "C4"])
        self.assertTrue(parsed.original_cohort.eq("G1").all())
        self.assertTrue(parsed.compound_column.eq("Compound").all())

    def test_korean_header_title_rows_and_merged_cells(self):
        table = pd.DataFrame({"물질명": ["C1", None, "C2", None], "시간": ["1h", None, "4h", None],
                              "장기": ["Tumor", "Kidney"] * 2, "개체번호": [1, 1, 2, 2],
                              "Uptake (%ID/g)": [10, 3, 20, 6]})
        parsed = parse_mollim_workbook(workbook(table, startrow=3), lambda t: float(t[:-1]))
        self.assertEqual(parsed.group_id.tolist(), ["C1", "C1", "C2", "C2"])
        self.assertEqual(parsed.timepoint_hour.tolist(), [1, 1, 4, 4])
        self.assertEqual(parsed.animal_id.tolist(), [1, 1, 2, 2])

    def test_legacy_sheet_and_group_fallback(self):
        table = pd.DataFrame({"Timepoint": ["1h"], "Organ": ["Tumor"], "%ID/g": [5]})
        self.assertEqual(parse_mollim_workbook(workbook(table, sheet_name="C1"), lambda t: 1).group_id.tolist(), ["C1"])
        table["Group"] = "C2"
        self.assertEqual(parse_mollim_workbook(workbook(table), lambda t: 1).group_id.tolist(), ["C2"])

    def test_unrecognized_sheet_is_reported(self):
        parsed = parse_mollim_workbook(workbook(pd.DataFrame({"notes": ["No measurements"]})), lambda t: 1)
        self.assertTrue(parsed.empty)
        self.assertNotEqual(parsed.attrs["parse_diagnostics"][0]["status"], "ok")


if __name__ == "__main__":
    unittest.main()
