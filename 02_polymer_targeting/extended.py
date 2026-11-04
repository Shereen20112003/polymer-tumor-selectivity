"""Exploratory objective, confounding and model diagnostics on the frozen cohort."""
from pathlib import Path
from importlib import import_module
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent))
from research_common import resources, save_json
from extended_common import run_benchmarks
FEATURES = import_module("02_polymer_targeting.run").FEATURES
from publication_figures import save
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import spearmanr


def paired_contrast(frame):
    means = frame.groupby(["study", "strategy"])["log_ratio"].mean().unstack()
    if not {"Active", "Passive"}.issubset(means.columns):
        raise ValueError("Both targeting categories are required.")
    matched = means.dropna(subset=["Active", "Passive"])
    if len(matched) < 2:
        raise ValueError("At least two overlapping reference groups are required.")
    return float((matched["Active"]-matched["Passive"]).mean()), len(matched)


def pareto_mask(tumor, liver):
    tumor, liver = np.asarray(tumor), np.asarray(liver)
    dominates = ((tumor[:, None] >= tumor[None, :]) & (liver[:, None] <= liver[None, :])
                 & ((tumor[:, None] > tumor[None, :]) | (liver[:, None] < liver[None, :])))
    return ~dominates.any(axis=0)


def objective_grid(frame):
    rows = []
    for fraction in [0.1, 0.2, 0.25, 0.33, 0.5]:
        count = int(np.ceil(len(frame)*fraction))
        uptake_ids = set(frame.nlargest(count, "tumor")["id"])
        ratio_ids = set(frame.nlargest(count, "log_ratio")["id"])
        for weight in [0, 0.25, 0.5, 1, 1.5, 2]:
            value = np.log10(frame["tumor"]) - weight*np.log10(frame["liver"])
            chosen = frame.loc[value.nlargest(count).index]
            selected = set(chosen["id"])
            rows.append({"fraction": fraction, "liver_weight": weight, "top_n": count,
                         "uptake_overlap": len(selected & uptake_ids)/count,
                         "ratio_overlap": len(selected & ratio_ids)/count,
                         "median_tumor": float(chosen["tumor"].median()),
                         "median_liver": float(chosen["liver"].median()),
                         "rank_vs_uptake": float(spearmanr(value, frame["tumor"]).statistic)})
    return pd.DataFrame(rows)


def main():
    output = ROOT / "results" / "extended"
    output.mkdir(exist_ok=True)
    with resources(output):
        frame, _ = run_benchmarks(ROOT, FEATURES, ["log_ratio"], {
            "targeting": ["strategy"], "tumour label": ["tumor_cell"],
            "size": ["size_nm"], "zeta": ["zeta_mv"], "shape": ["shape"],
        })
        objective_grid(frame).to_csv(output / "objectives.csv", index=False)
        influence = []
        for study in sorted(frame["study"].unique()):
            subset = frame[frame["study"] != study]
            contrast, matched = paired_contrast(subset)
            means = subset.groupby("strategy")["log_ratio"].mean()
            influence.append({"omitted_group": study, "remaining_n": len(subset),
                              "rank_correlation": float(spearmanr(subset["tumor"], subset["log_ratio"]).statistic),
                              "median_log_ratio": float(subset["log_ratio"].median()),
                              "within_contrast": contrast, "matched_groups": matched,
                              "pooled_contrast": float(means["Active"]-means["Passive"])})
        pd.DataFrame(influence).to_csv(output / "influence.csv", index=False)
        tails = []
        for label, subset in [
            ("Primary", frame),
            ("Complete size and zeta", frame.dropna(subset=["size_nm", "zeta_mv"])),
            *[(f"Liver at least {limit}", frame[frame["liver"] >= limit]) for limit in [0.01, 0.1, 1]],
        ]:
            contrast, matched = paired_contrast(subset)
            tails.append({"cohort": label, "n": len(subset), "groups": subset["study"].nunique(),
                          "rank_correlation": float(spearmanr(subset["tumor"], subset["log_ratio"]).statistic),
                          "median_log_ratio": float(subset["log_ratio"].median()),
                          "within_contrast": contrast, "matched_groups": matched})
        pd.DataFrame(tails).to_csv(output / "cohorts.csv", index=False)
        balance = []
        for feature in ["size_nm", "zeta_mv"]:
            active = frame.loc[frame["strategy"] == "Active", feature].dropna()
            passive = frame.loc[frame["strategy"] == "Passive", feature].dropna()
            scale = np.sqrt((active.var(ddof=1)+passive.var(ddof=1))/2)
            if not np.isfinite(scale) or scale <= 0:
                raise ValueError(f"Cannot standardize covariate balance for {feature}.")
            means = frame.groupby(["study", "strategy"])[feature].mean().unstack()
            matched = means.dropna(subset=["Active", "Passive"])
            balance.append({"feature": feature, "active_n": len(active), "passive_n": len(passive),
                            "active_mean": float(active.mean()), "passive_mean": float(passive.mean()),
                            "standardized_difference": float((active.mean()-passive.mean())/scale),
                            "overlap_groups": len(matched),
                            "within_mean_difference": float((matched["Active"]-matched["Passive"]).mean())})
        pd.DataFrame(balance).to_csv(output / "balance.csv", index=False)
        rng = np.random.default_rng(20261103)
        log_t, log_l = np.log10(frame["tumor"]), np.log10(frame["liver"])
        coupling = [{"repeat": repeat, "rank_correlation": float(
            spearmanr(log_t, log_t-rng.permutation(log_l)).statistic)} for repeat in range(1000)]
        pd.DataFrame(coupling).to_csv(output / "coupling.csv", index=False)
        frontier = frame[["id", "study", "tumor", "liver", "log_ratio", "strategy"]].copy()
        frontier["pareto"] = pareto_mask(frame["tumor"], frame["liver"])
        frontier.to_csv(output / "pareto.csv", index=False)
        destination = ROOT / "figures"
        destination.mkdir(exist_ok=True)
        with plt.rc_context({"font.family": "STIXGeneral", "font.size": 9.5, "pdf.fonttype": 42}):
            objectives = pd.read_csv(output / "objectives.csv")
            ratio = objectives[objectives["liver_weight"] == 1]
            figure, axis = plt.subplots(figsize=(3.05, 2.2))
            axis.plot(ratio["fraction"]*100, ratio["uptake_overlap"], marker="o")
            axis.set(xlabel="Selected cohort fraction (%)", ylabel="Uptake / ratio shortlist overlap", ylim=(0, 1))
            save(figure, destination, "objectives_extended")
            learning = pd.read_csv(output / "learning.csv")
            summary = learning.groupby("fraction")["mae"].agg(["mean", "std"])
            figure, axis = plt.subplots(figsize=(3.05, 2.2))
            axis.errorbar(summary.index*100, summary["mean"], yerr=summary["std"], marker="o", capsize=2)
            axis.set(xlabel="Retained training publications (%)", ylabel="Test MAE (log10 tumour/liver)")
            save(figure, destination, "learning_extended")
        save_json(output / "extension_summary.json", {
            "pareto_formulations": int(frontier["pareto"].sum()),
            "omission_contrast_min": float(pd.DataFrame(influence)["within_contrast"].min()),
            "omission_contrast_max": float(pd.DataFrame(influence)["within_contrast"].max()),
            "coupling_correlation_median": float(pd.DataFrame(coupling)["rank_correlation"].median()),
            "primary_reproduction": "passed", "causal_interpretation": False,
        })
    print("Polymer extension complete:", output, flush=True)


if __name__ == "__main__":
    main()
