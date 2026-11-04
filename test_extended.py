"""Regression tests for the expanded analyses and their data contracts."""
from importlib import import_module
from pathlib import Path
import unittest

from extended_common import configurations, frozen_indices, nested_training
from research_common import fit_model
from validate_extended import validate_project
from project_scope import selected_projects
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent


class ExtensionTests(unittest.TestCase):
    def test_nested_learning_keeps_whole_publications(self):
        groups = np.repeat(np.arange(20).astype(str), 3)
        train = np.arange(45)
        subsets = nested_training(groups, train, [0.25, 0.5, 0.75, 1], 11)
        previous = set()
        for indices in subsets.values():
            self.assertTrue(previous <= set(indices) <= set(train))
            for group in np.unique(groups[indices]):
                self.assertEqual(set(indices[groups[indices] == group]), set(train[groups[train] == group]))
            previous = set(indices)
        np.testing.assert_array_equal(subsets[1], train)

    def test_frozen_partitions_require_complete_matching_groups(self):
        frame = pd.DataFrame({"id": [1, 2, 3], "study": ["a", "b", "c"]})
        splits = pd.DataFrame({"id": [1, 2, 3], "study": ["a", "b", "c"],
                               "seed": [11]*3, "split": ["publication"]*3,
                               "role": ["train", "calibration", "test"]})
        self.assertEqual(frozen_indices(frame, splits, 11)["test"].tolist(), [2])
        with self.assertRaises(ValueError):
            frozen_indices(frame, splits.iloc[:2], 11)
        splits.loc[2, "study"] = "a"
        with self.assertRaises(ValueError):
            frozen_indices(frame, splits, 11)

    def test_parameter_variants_change_the_actual_estimator(self):
        model = fit_model(pd.DataFrame({"x": np.arange(20)}), np.arange(20), "trees", 11,
                          n_estimators=7, min_samples_leaf=2)
        self.assertEqual(model.steps[-1][1].n_estimators, 7)
        self.assertEqual(model.steps[-1][1].min_samples_leaf, 2)
        ridge = fit_model(pd.DataFrame({"x": np.arange(20)}), np.arange(20), "ridge", 11, alpha=100)
        self.assertEqual(ridge.steps[-1][1].alpha, 100)

    def test_empty_or_unknown_feature_ablations_are_rejected(self):
        with self.assertRaises(ValueError):
            configurations(["a"], {"all": ["a"]})
        with self.assertRaises(ValueError):
            configurations(["a"], {"unknown": ["b"]})

    @unittest.skipUnless("02_polymer_targeting" in selected_projects(), "Polymer project not included")
    def test_pareto_frontier_uses_high_tumour_low_liver_and_preserves_ties(self):
        module = import_module("02_polymer_targeting.extended")
        np.testing.assert_array_equal(module.pareto_mask([1, 2, 2, 3], [2, 1, 1, 3]),
                                      [False, True, True, True])

    @unittest.skipUnless("02_polymer_targeting" in selected_projects(), "Polymer project not included")
    def test_objective_extremes_recover_original_objectives(self):
        module = import_module("02_polymer_targeting.extended")
        frame = pd.DataFrame({"id": range(20), "tumor": np.arange(1, 21),
                              "liver": np.arange(20, 0, -1)})
        frame["log_ratio"] = np.log10(frame["tumor"]/frame["liver"])
        results = module.objective_grid(frame)
        self.assertTrue((results.loc[results["liver_weight"] == 0, "uptake_overlap"] == 1).all())
        self.assertTrue((results.loc[results["liver_weight"] == 1, "ratio_overlap"] == 1).all())

    def test_both_executed_extensions_recalculate(self):
        for folder in selected_projects():
            result = validate_project(ROOT / folder)
            self.assertEqual(result["prediction_recalculation"], "passed")


if __name__ == "__main__":
    unittest.main(verbosity=2)
