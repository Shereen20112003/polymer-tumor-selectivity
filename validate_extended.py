"""Recalculate the exploratory extension tables from their saved row-level outputs."""
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.metrics import r2_score


def read(path):
    return pd.read_csv(path, float_precision="round_trip")


def assert_close(actual, expected):
    np.testing.assert_allclose(actual, expected, rtol=1e-9, atol=1e-10)


def validate_project(directory):
    directory = Path(directory)
    output = directory / "results" / "extended"
    protocol = json.loads((output / "protocol.json").read_text())
    summary = json.loads((output / "extension_summary.json").read_text())
    if summary["primary_reproduction"] != "passed" or protocol["automatic_test_set_selection"]:
        raise AssertionError("Extension protocol or primary reproduction contract failed.")
    for name, digest in protocol["source_sha256"].items():
        if hashlib.sha256((directory / "results" / name).read_bytes()).hexdigest() != digest:
            raise AssertionError(f"Changed extension source: {name}")
    resource = json.loads((output / "resources.json").read_text())
    original = json.loads((directory / "results" / "resources.json").read_text())
    if resource["elapsed_seconds"] + original["elapsed_seconds"] > 7200:
        raise AssertionError("Combined primary and extension analysis exceeded two hours.")
    if max(resource["sampled_peak_rss_mb"], original["sampled_peak_rss_mb"]) > 4096:
        raise AssertionError("Analysis exceeded the 4 GB measured process-memory budget.")
    metrics, predictions = read(output / "metrics.csv"), read(output / "predictions.csv")
    frame = read(directory / "results" / "analysis_dataset.csv")
    splits = pd.read_csv(directory / "results" / "splits.csv", dtype={"study": str})
    targets = ["day1", "day3", "day7"] if directory.name == "01_release_transfer" else ["log_ratio"]
    actual_targets = frame.set_index("id")[targets].stack()
    primary_scores = read(directory / "results" / "metrics.csv").query(
        "split == 'publication' and model == 'trees'").set_index("seed")
    reproduced = metrics[metrics["configuration"] == "Trees 128 leaf3"].set_index("seed")
    for metric in ["mae", "study_macro_mae", "r2"]:
        assert_close(reproduced.loc[primary_scores.index, metric], primary_scores[metric])
    expected_cases = {(seed, config["name"]) for seed in protocol["seeds"] for config in protocol["configurations"]}
    if set(zip(metrics["seed"], metrics["configuration"])) != expected_cases:
        raise AssertionError("Extension configuration grid is incomplete.")
    if metrics.duplicated(["seed", "configuration"]).any():
        raise AssertionError("Duplicated extension scores.")
    for (seed, configuration), block in predictions.groupby(["seed", "configuration"]):
        test_ids = set(splits.loc[(splits["seed"] == seed) & (splits["split"] == "publication")
                                 & (splits["role"] == "test"), "id"])
        if set(block["id"]) != test_ids or set(block["target"]) != set(targets):
            raise AssertionError("Extension prediction cohort differs from the frozen test partition.")
        if block.duplicated(["id", "target"]).any():
            raise AssertionError("Duplicated extension endpoint prediction.")
        expected = actual_targets.reindex(pd.MultiIndex.from_frame(block[["id", "target"]]))
        assert_close(block["observed"].to_numpy(), expected.to_numpy())
        observed = block.pivot(index="id", columns="target", values="observed")
        predicted = block.pivot(index="id", columns="target", values="predicted")
        absolute = np.abs(observed.to_numpy()-predicted.to_numpy())
        row = metrics[(metrics["seed"] == seed) & (metrics["configuration"] == configuration)].iloc[0]
        assert_close(absolute.mean(), row["mae"])
        assert_close(r2_score(observed, predicted), row["r2"])
        group_errors = block.assign(error=(block["observed"]-block["predicted"]).abs())
        assert_close(group_errors.groupby("study")["error"].mean().mean(), row["study_macro_mae"])
    manifest = pd.read_csv(output / "learning_manifest.csv", dtype={"study": str})
    learning = read(output / "learning.csv")
    if len(learning) != 4*len(protocol["seeds"]):
        raise AssertionError("Learning-curve grid is incomplete.")
    full_learning = learning[learning["fraction"] == 1].set_index("seed")
    assert_close(full_learning.loc[primary_scores.index, "mae"], primary_scores["mae"])
    for seed, rows in manifest.groupby("seed"):
        allowed = set(splits.loc[(splits["seed"] == seed) & (splits["split"] == "publication")
                                & (splits["role"] == "train"), "id"])
        last_ids = set()
        for fraction in protocol["learning_fractions"]:
            block = rows[rows["fraction"] == fraction]
            ids = set(block["id"])
            if not last_ids <= ids <= allowed or len(ids) != len(block):
                raise AssertionError("Nested learning subsets are duplicated, nonnested, or leak held-out data.")
            row = learning[(learning["seed"] == seed) & (learning["fraction"] == fraction)].iloc[0]
            assert_close(len(block), row["train_n"])
            assert_close(block["study"].nunique(), row["train_groups"])
            last_ids = ids
        if last_ids != allowed:
            raise AssertionError("Full learning-curve subset differs from the original training partition.")
    if directory.name == "01_release_transfer":
        calibration = read(output / "calibration.csv")
        intervals = read(output / "interval_predictions.csv")
        for (seed, nominal, method), block in intervals.groupby(["seed", "nominal", "method"]):
            row = calibration[(calibration["seed"] == seed) & (calibration["nominal"] == nominal)
                              & (calibration["method"] == method)].iloc[0]
            covered = (block["observed"] >= block["lower"]) & (block["observed"] <= block["upper"])
            assert_close(covered.mean(), row["point_coverage"])
            assert_close(covered.groupby(block["id"]).all().mean(), row["vector_coverage"])
            assert_close(covered.groupby(block["study"]).all().mean(), row["publication_coverage"])
            assert_close((block["upper"]-block["lower"]).mean(), row["width"])
            if not ((block["lower"] >= 0) & (block["upper"] <= 1)
                    & (block["lower"] <= block["predicted"]) & (block["predicted"] <= block["upper"])).all():
                raise AssertionError("Invalid exploratory conformal interval.")
        original_intervals = read(directory / "results" / "intervals.csv").query("split == 'publication'")
        mapping = {"pooled_point": "Pointwise", "formulation_max": "Formulation-max", "publication_max": "Publication-max"}
        for row in original_intervals.itertuples():
            actual = calibration[(calibration["seed"] == row.seed) & (calibration["nominal"] == 0.9)
                                 & (calibration["method"] == mapping[row.method])].iloc[0]
            assert_close(actual["publication_coverage"], row.publication_coverage)
            assert_close(actual["radius"], row.q)
    else:
        objectives = read(output / "objectives.csv")
        for row in objectives.itertuples():
            k = int(np.ceil(len(frame)*row.fraction))
            weighted = np.log10(frame["tumor"])-row.liver_weight*np.log10(frame["liver"])
            ids = set(frame.loc[weighted.nlargest(k).index, "id"])
            assert_close(len(ids & set(frame.nlargest(k, "tumor")["id"]))/k, row.uptake_overlap)
            assert_close(len(ids & set(frame.nlargest(k, "log_ratio")["id"]))/k, row.ratio_overlap)
        influence = pd.read_csv(output / "influence.csv", dtype={"omitted_group": str})
        frame["study"] = frame["study"].astype(str)
        for row in influence.itertuples():
            block = frame[frame["study"] != row.omitted_group]
            assert_close(spearmanr(block["tumor"], block["log_ratio"]).statistic, row.rank_correlation)
            means = block.groupby(["study", "strategy"])["log_ratio"].mean().unstack().dropna()
            assert_close((means["Active"]-means["Passive"]).mean(), row.within_contrast)
        frontier = read(output / "pareto.csv")
        for row in frontier.itertuples():
            dominated = ((frame["tumor"] >= row.tumor) & (frame["liver"] <= row.liver)
                         & ((frame["tumor"] > row.tumor) | (frame["liver"] < row.liver))).any()
            if bool(row.pareto) != (not dominated):
                raise AssertionError("Incorrect paired-organ Pareto membership.")
    return {"prediction_recalculation": "passed", "nested_training_partitions": "passed",
            "primary_reproduction": "passed", "configurations": len(protocol["configurations"]),
            "measured_total_seconds": resource["elapsed_seconds"] + original["elapsed_seconds"],
            "sampled_peak_rss_mb": max(resource["sampled_peak_rss_mb"], original["sampled_peak_rss_mb"])}
