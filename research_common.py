"""Small, single-threaded, publication-aware benchmark utilities."""
import os

for variable in ["OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"]:
    os.environ[variable] = "1"

from contextlib import contextmanager
import hashlib
import json
import platform
import threading
import time
from pathlib import Path

import numpy as np
import pandas as pd
import psutil
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import ExtraTreesRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import GroupShuffleSplit, train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

SEEDS = [11, 29, 47, 71, 101]


def save_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False), encoding="utf-8")


@contextmanager
def resources(directory):
    start = time.perf_counter()
    process = psutil.Process()
    samples = [process.memory_info().rss]
    stop = threading.Event()

    def monitor():
        while not stop.wait(0.1):
            samples.append(process.memory_info().rss)

    thread = threading.Thread(target=monitor, daemon=True)
    thread.start()
    try:
        yield
    finally:
        stop.set()
        thread.join()
        save_json(Path(directory) / "resources.json", {
            "elapsed_seconds": time.perf_counter() - start,
            "sampled_peak_rss_mb": max(samples) / 1024**2,
            "memory_sampling_seconds": 0.1,
            "python": platform.python_version(),
            "platform": platform.platform(),
            "cpu_threads": 1,
        })


def fit_model(frame, target, kind, seed, *, alpha=10.0, min_samples_leaf=3, n_estimators=128):
    numeric = frame.select_dtypes(include="number").columns.tolist()
    categorical = [column for column in frame if column not in numeric]
    transformers = []
    if numeric:
        transformers.append(("numeric", make_pipeline(
            SimpleImputer(strategy="median", add_indicator=True, keep_empty_features=True),
            StandardScaler()), numeric))
    if categorical:
        transformers.append(("categorical", make_pipeline(
            SimpleImputer(strategy="most_frequent"),
            OneHotEncoder(handle_unknown="ignore", sparse_output=False)), categorical))
    estimator = (Ridge(alpha=alpha) if kind == "ridge" else
                 ExtraTreesRegressor(n_estimators=n_estimators, min_samples_leaf=min_samples_leaf,
                                     max_features=1.0, n_jobs=1, random_state=seed))
    pipeline = make_pipeline(ColumnTransformer(transformers), estimator)
    y = np.asarray(target)
    pipeline.fit(frame, y.ravel() if y.ndim == 2 and y.shape[1] == 1 else y)
    return pipeline


def predict(model, frame):
    return np.asarray(model.predict(frame)).reshape(len(frame), -1)


def split_indices(groups, seed, grouped=True):
    indices = np.arange(len(groups))
    if not grouped:
        train_cal, test = train_test_split(indices, test_size=0.2, random_state=seed)
        train, calibration = train_test_split(train_cal, test_size=0.25, random_state=seed + 1)
    else:
        train_cal, test = next(GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=seed)
                               .split(indices, groups=groups))
        a, b = next(GroupShuffleSplit(n_splits=1, test_size=0.25, random_state=seed + 1)
                    .split(train_cal, groups=np.asarray(groups)[train_cal]))
        train, calibration = train_cal[a], train_cal[b]
        assert not (set(groups[train]) & set(groups[calibration]))
        assert not (set(groups[train]) & set(groups[test]))
        assert not (set(groups[calibration]) & set(groups[test]))
    return train, calibration, test


def conformal_quantile(scores, alpha=0.1):
    scores = np.asarray(scores, dtype=float)
    if not len(scores) or not np.isfinite(scores).all():
        raise ValueError("Calibration scores must be nonempty and finite.")
    rank = int(np.ceil((len(scores) + 1) * (1 - alpha)))
    if rank > len(scores):
        raise ValueError(f"Only {len(scores)} calibration units: finite {1-alpha:.0%} interval unavailable.")
    return float(np.sort(scores)[rank - 1])


def group_scores(residuals, groups):
    maxima = np.max(np.asarray(residuals).reshape(len(groups), -1), axis=1)
    return pd.Series(maxima).groupby(np.asarray(groups)).max().to_numpy()


def group_mean(values, groups):
    return float(pd.Series(values).groupby(np.asarray(groups)).mean().mean())


def cluster_bootstrap(frame, group, statistic, repeats=2000, seed=601):
    rng = np.random.default_rng(seed)
    blocks = [block for _, block in frame.groupby(group, sort=True)]
    if len(blocks) < 2:
        raise ValueError("Cluster bootstrap requires at least two publications.")
    values = []
    for _ in range(repeats):
        selected = rng.integers(0, len(blocks), len(blocks))
        sample = pd.concat([blocks[index] for index in selected], ignore_index=True)
        values.append(float(statistic(sample)))
    return {
        "estimate": float(statistic(frame)),
        "lower": float(np.quantile(values, 0.025)),
        "upper": float(np.quantile(values, 0.975)),
        "repeats": repeats, "seed": seed, "clusters": len(blocks),
    }


def input_hashes(directory):
    return {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(Path(directory).glob("*.xlsx"))}


def score(y, prediction, groups):
    errors = np.abs(y - prediction)
    return {
        "mae": float(mean_absolute_error(y, prediction)),
        "study_macro_mae": group_mean(errors.mean(axis=1), groups),
        "r2": float(r2_score(y, prediction)),
    }
