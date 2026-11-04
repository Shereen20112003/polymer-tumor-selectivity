"""Focused tests for units, leakage prevention, interval ranks and output integrity."""
import importlib.util
from pathlib import Path
import unittest

from research_common import conformal_quantile, group_scores, split_indices
from project_scope import selected_projects
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent


def module(folder):
    if folder not in selected_projects():
        raise unittest.SkipTest(f"{folder} is not part of this standalone repository.")
    specification = importlib.util.spec_from_file_location(folder, ROOT / folder / "run.py")
    loaded = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(loaded)
    return loaded


class CalibrationTests(unittest.TestCase):
    def test_exact_finite_sample_rank(self):
        self.assertEqual(conformal_quantile(np.arange(1, 10)), 9)
        self.assertEqual(conformal_quantile(np.arange(1, 20)), 18)

    def test_insufficient_groups_is_error(self):
        with self.assertRaises(ValueError):
            conformal_quantile([1, 2, 3])

    def test_group_maximum_includes_all_endpoints(self):
        result = group_scores(np.array([[1, 2], [5, 1], [3, 4]]), np.array(["a", "a", "b"]))
        np.testing.assert_array_equal(result, [5, 4])

    def test_publications_disjoint(self):
        groups = np.repeat(np.arange(100), 3)
        for seed in [11, 29, 47, 71, 101]:
            train, calibration, test = split_indices(groups, seed)
            self.assertFalse(set(groups[train]) & set(groups[calibration]))
            self.assertFalse(set(groups[train]) & set(groups[test]))
            self.assertFalse(set(groups[calibration]) & set(groups[test]))
            self.assertEqual(len(train) + len(calibration) + len(test), len(groups))


class DatasetTests(unittest.TestCase):
    def test_explicit_hydrodynamic_size_not_tem(self):
        tumor = module("02_polymer_targeting")
        self.assertEqual(tumor.hydrodynamic_size("TEM: 25; HD: 37"), 37)
        self.assertTrue(np.isnan(tumor.hydrodynamic_size("TEM: 25")))
        self.assertTrue(np.isnan(tumor.hydrodynamic_size("HD: NA")))
        with self.assertRaises(ValueError):
            tumor.hydrodynamic_size("HD: 20/30")

    def test_linked_publication_references_share_group(self):
        tumor = module("02_polymer_targeting")
        self.assertEqual(tumor.reference_groups([67, "67/200", 200, 201]),
                         ["67+200", "67+200", "67+200", "201"])
        self.assertEqual(tumor.reference_groups(["1/2", "2/3", 3]), ["1+2+3"] * 3)
        with self.assertRaises(ValueError):
            tumor.reference_groups(["unresolved"])

    def test_release_days_and_exact_interpolation(self):
        release = module("01_release_transfer")
        frame, audit = release.prepare()
        self.assertEqual(audit["time_unit"], "days")
        np.testing.assert_array_equal(release.TIMES, [1, 3, 7])
        self.assertGreater(frame["study"].nunique(), 20)
        self.assertFalse(frame["id"].duplicated().any())
        endpoints = frame[["day1", "day3", "day7"]]
        self.assertTrue(((endpoints >= 0) & (endpoints <= 1)).all().all())
        raw = pd.read_excel(ROOT / "01_release_transfer" / "data" / "mp_dataset_processed.xlsx")
        identifier = frame.iloc[0]["id"]
        curve = raw[raw["Formulation Index"] == identifier].groupby("Time")["Release"].mean()
        self.assertAlmostEqual(frame.iloc[0]["day1"], np.interp(1, curve.index, curve.values))

    def test_projection_is_bounded_and_monotone(self):
        release = module("01_release_transfer")
        projected = release.monotone(np.array([[0.7, 0.2, 1.4], [-0.1, 0.2, 0.3]]))
        self.assertTrue((np.diff(projected, axis=1) >= 0).all())
        self.assertTrue(((projected >= 0) & (projected <= 1)).all())

    def test_paired_organ_interpolation_no_extrapolation(self):
        tumor = module("02_polymer_targeting")
        long = pd.DataFrame({
            "id": [1, 1], "hours": [0, 48], "tumor": [1., 3.], "liver": [4., 8.],
            "study": ["a", "a"], "size_nm": [100., 100.], "zeta_mv": [-5., -5.],
            "strategy": ["Active", "Active"], "shape": ["Sphere", "Sphere"],
            "core": ["Polymeric", "Polymeric"], "tumor_cell": ["test", "test"],
        })
        frame, excluded = tumor.endpoint(long, 24)
        self.assertEqual(len(excluded), 0)
        self.assertAlmostEqual(frame.iloc[0]["tumor"], 2.)
        self.assertAlmostEqual(frame.iloc[0]["liver"], 6.)
        self.assertAlmostEqual(frame.iloc[0]["log_ratio"], np.log10(1/3))
        frame, excluded = tumor.endpoint(long, 72)
        self.assertTrue(frame.empty)
        self.assertEqual(excluded[0]["reason"], "no_paired_bracket")

    def test_analysis_outputs_have_no_group_leakage(self):
        for folder in selected_projects():
            path = ROOT / folder / "results" / "splits.csv"
            self.assertTrue(path.exists(), f"Run {folder} before output validation.")
            split = pd.read_csv(path)
            split = split[split["split"] == "publication"]
            self.assertTrue((split.groupby(["seed", "study"])["role"].nunique() == 1).all())
            self.assertFalse(split.duplicated(["seed", "id"]).any())


if __name__ == "__main__":
    unittest.main(verbosity=2)
