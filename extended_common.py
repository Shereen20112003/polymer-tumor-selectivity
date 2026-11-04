"""Additional exploratory diagnostics on frozen publication-disjoint partitions."""
import hashlib
import time
from pathlib import Path

from research_common import SEEDS, fit_model, predict, save_json, score
import numpy as np
import pandas as pd
import psutil
from sklearn.metrics import r2_score


def budget_guard(start):
    if time.perf_counter() - start > 6600:
        raise RuntimeError("Extension analysis reached its 110-minute safety cutoff.")
    if psutil.Process().memory_info().rss > 3800 * 1024**2:
        raise MemoryError("Extension analysis reached its 3.8 GB safety cutoff.")


def frozen_indices(frame, splits, seed):
    rows = splits[(splits["split"] == "publication") & (splits["seed"] == seed)]
    if rows["id"].duplicated().any() or set(rows["id"]) != set(frame["id"]):
        raise ValueError(f"Incomplete or duplicated frozen partition for seed {seed}.")
    if (rows.groupby("study")["role"].nunique() > 1).any():
        raise ValueError("Frozen partition leaks publication groups.")
    joined = frame[["id", "study"]].merge(rows[["id", "study"]], on="id", suffixes=("", "_split"))
    if not (joined["study"].astype(str) == joined["study_split"].astype(str)).all():
        raise ValueError("Frozen partition publication labels differ from the analysis cohort.")
    roles = {}
    for role, block in rows.groupby("role"):
        roles[role] = np.flatnonzero(frame["id"].isin(block["id"]).to_numpy())
    return roles


def nested_training(groups, train, fractions, seed):
    order = np.random.default_rng(seed + 804).permutation(np.unique(groups[train]))
    result = {}
    for fraction in fractions:
        count = max(2, int(np.ceil(fraction * len(order))))
        result[fraction] = train[np.isin(groups[train], order[:count])]
    return result


def configurations(features, blocks):
    result = [
        {"name": "Trees 128 leaf3", "kind": "trees", "columns": features},
        *[{"name": f"Ridge alpha{alpha}", "kind": "ridge", "columns": features, "alpha": alpha}
          for alpha in [1, 10, 100]],
        *[{"name": f"Trees 128 leaf{leaf}", "kind": "trees", "columns": features, "min_samples_leaf": leaf}
          for leaf in [1, 8]],
        {"name": "Trees 32 leaf3", "kind": "trees", "columns": features, "n_estimators": 32},
    ]
    for name, dropped in blocks.items():
        unknown = set(dropped) - set(features)
        if unknown:
            raise ValueError(f"Unknown ablation features: {unknown}")
        retained = [column for column in features if column not in dropped]
        if not retained:
            raise ValueError(f"Ablation {name} has no retained predictors.")
        result.append({"name": f"Without {name}", "kind": "trees", "columns": retained})
    return result


def support_table(frame, train, test, features, seed):
    rows = []
    for column in features:
        a, b = frame.iloc[train][column], frame.iloc[test][column]
        if pd.api.types.is_numeric_dtype(a):
            reference = a.dropna()
            if reference.empty:
                raise ValueError(f"No training support for numeric predictor {column}.")
            unsupported = b.notna() & ((b < reference.min()) | (b > reference.max()))
            kind = "Outside training range"
        else:
            unsupported = b.notna() & ~b.isin(a.dropna().unique())
            kind = "Unseen category"
        rows.append({"seed": seed, "feature": column, "support_type": kind,
                     "test_n": len(test), "unsupported_n": int(unsupported.sum()),
                     "unsupported_fraction": float(unsupported.mean()),
                     "missing_fraction": float(b.isna().mean())})
    return rows


def run_benchmarks(directory, features, targets, blocks, projection=None):
    directory = Path(directory)
    output = directory / "results" / "extended"
    output.mkdir(exist_ok=True)
    frame = pd.read_csv(directory / "results" / "analysis_dataset.csv", float_precision="round_trip")
    frame["study"] = frame["study"].astype(str)
    splits = pd.read_csv(directory / "results" / "splits.csv", dtype={"study": str})
    groups = frame["study"].to_numpy()
    y = frame[targets].to_numpy()
    project = projection if projection is not None else lambda value: value
    plan = configurations(features, blocks)
    start = time.perf_counter()
    metrics, predictions, learning, manifests, support, importance, endpoints = [], [], [], [], [], [], []
    primary = {}
    for seed in SEEDS:
        roles = frozen_indices(frame, splits, seed)
        train, test = roles["train"], roles["test"]
        support.extend(support_table(frame, train, test, features, seed))
        for config in plan:
            budget_guard(start)
            parameters = {key: config[key] for key in ["alpha", "min_samples_leaf", "n_estimators"] if key in config}
            columns = config["columns"]
            model = fit_model(frame.iloc[train][columns], y[train], config["kind"], seed, **parameters)
            estimate = project(predict(model, frame.iloc[test][columns]))
            metrics.append({"seed": seed, "configuration": config["name"],
                            "train_n": len(train), "test_n": len(test),
                            **score(y[test], estimate, groups[test])})
            for j, target in enumerate(targets):
                endpoints.append({"seed": seed, "configuration": config["name"], "target": target,
                                  "mae": float(np.abs(y[test, j] - estimate[:, j]).mean()),
                                  "r2": float(r2_score(y[test, j], estimate[:, j]))})
                predictions.extend({"seed": seed, "configuration": config["name"], "target": target,
                                    "id": int(frame.iloc[index]["id"]), "study": groups[index],
                                    "observed": float(y[index, j]), "predicted": float(estimate[k, j])}
                                   for k, index in enumerate(test))
            if config["name"] != "Trees 128 leaf3":
                continue
            primary[seed] = {"roles": roles, "prediction": estimate,
                             "calibration_prediction": project(predict(model, frame.iloc[
                                 roles.get("calibration", roles.get("reserved_unused"))][columns]))}
            subsets = nested_training(groups, train, [0.25, 0.5, 0.75, 1.0], seed)
            for fraction, indices in subsets.items():
                budget_guard(start)
                trained = model if fraction == 1 else fit_model(frame.iloc[indices][features], y[indices], "trees", seed)
                value = estimate if fraction == 1 else project(predict(trained, frame.iloc[test][features]))
                learning.append({"seed": seed, "fraction": fraction, "train_n": len(indices),
                                 "train_groups": len(set(groups[indices])),
                                 **score(y[test], value, groups[test])})
                manifests.extend({"seed": seed, "fraction": fraction, "id": int(frame.iloc[i]["id"]),
                                  "study": groups[i]} for i in indices)
            base_mae = np.abs(y[test] - estimate).mean()
            rng = np.random.default_rng(seed + 1701)
            for column in features:
                for repeat in range(5):
                    budget_guard(start)
                    altered = frame.iloc[test][features].copy()
                    altered[column] = rng.permutation(altered[column].to_numpy())
                    value = project(predict(model, altered))
                    importance.append({"seed": seed, "feature": column, "repeat": repeat,
                                       "mae_increase": float(np.abs(y[test] - value).mean() - base_mae)})
    for name, rows in [
        ("metrics", metrics), ("predictions", predictions), ("learning", learning),
        ("learning_manifest", manifests), ("support", support),
        ("permutation", importance), ("endpoint_metrics", endpoints),
    ]:
        pd.DataFrame(rows).to_csv(output / f"{name}.csv", index=False)
    saved_primary = pd.read_csv(directory / "results" / "metrics.csv")
    baseline = saved_primary[(saved_primary["split"] == "publication") & (saved_primary["model"] == "trees")]
    actual = pd.DataFrame(metrics).query("configuration == 'Trees 128 leaf3'").set_index("seed")
    np.testing.assert_allclose(actual.loc[baseline["seed"], "mae"], baseline["mae"], atol=1e-10, rtol=1e-9)
    save_json(output / "protocol.json", {
        "analysis_stage": "Exploratory extension after the primary results; not preregistered",
        "seeds": SEEDS, "configurations": plan, "learning_fractions": [0.25, 0.5, 0.75, 1],
        "permutation_repeats": 5, "automatic_test_set_selection": False,
        "csv_float_parser": "round_trip; preserve exact fitted primary inputs",
        "source_sha256": {name: hashlib.sha256((directory / "results" / name).read_bytes()).hexdigest()
                          for name in ["analysis_dataset.csv", "splits.csv", "metrics.csv"]},
    })
    return frame, primary
