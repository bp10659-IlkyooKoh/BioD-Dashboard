import unittest

from biod_labels import clean_group_with_tp


class CompoundLabelTests(unittest.TestCase):
    def test_numeric_compound_suffix_is_never_a_timepoint(self):
        for code in ["AC-SK-001", "AC-SK-004", "AC-SK-048", "Drug-1", "Drug(001)", "Drug[001]"]:
            for hour in [1, 4, 48]:
                with self.subTest(code=code, hour=hour):
                    self.assertEqual(clean_group_with_tp({"group_id": code, "timepoint": f"{hour}h", "timepoint_hour": hour}), code)

    def test_only_explicit_time_suffix_is_removed(self):
        for suffix in [" 1h", "-4h", "_48 hr", " (1h)", "[48 hours]", " / 30 min", " 2시간"]:
            with self.subTest(suffix=suffix):
                self.assertEqual(clean_group_with_tp({"group_id": "AC-SK-001" + suffix}), "AC-SK-001")
        self.assertEqual(clean_group_with_tp({"group_id": "AC-SK-001-1"}), "AC-SK-001-1")


if __name__ == "__main__":
    unittest.main()
