"""Paired-organ polymer nanoparticle analysis. Observational, not causal."""
from pathlib import Path
import sys
import re

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent))
from research_common import (
    SEEDS, cluster_bootstrap, fit_model, input_hashes, predict,
    resources, save_json, score, split_indices,
)
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import spearmanr

NUMERIC = ["size_nm", "zeta_mv"]
CATEGORICAL = ["strategy", "shape", "core", "tumor_cell"]
FEATURES = NUMERIC + CATEGORICAL


def reference_groups(references):
    parent = {}

    def find(value):
        parent.setdefault(value, value)
        if parent[value] != value:
            parent[value] = find(parent[value])
        return parent[value]

    tokens = []
    for value in references:
        text = str(value).strip()
        if re.fullmatch(r"\d+\.0", text):
            text = text[:-2]
        if not re.fullmatch(r"\d+(?:/\d+)*", text):
            raise ValueError(f"Unrecognized publication reference: {value!r}")
        members = text.split("/")
        tokens.append(members)
        for member in members:
            parent[find(member)] = find(members[0])
    components = {}
    for member in parent:
        components.setdefault(find(member), []).append(member)
    labels = {root: "+".join(sorted(members, key=int)) for root, members in components.items()}
    return [labels[find(members[0])] for members in tokens]


def hydrodynamic_size(value):
    if pd.isna(value):
        return np.nan
    text = str(value).strip()
    if re.search(r"(?:^|;)\s*HD:\s*NA\s*(?=;|$)", text):
        return np.nan
    if "HD:" not in text:
        return np.nan
    matches = re.findall(r"(?:^|;)\s*HD:\s*(\d+(?:\.\d+)?)\s*(?:nm)?\s*(?=;|$)", text)
    if len(matches) != 1:
        raise ValueError(f"Ambiguous hydrodynamic diameter: {value!r}")
    return float(matches[0])


def load_long():
    raw = pd.read_excel(ROOT / "data" / "nn3c04037_si_002.xlsx", sheet_name=0, header=None)
    if str(raw.iloc[0, 14]).strip() != "Biodistribution (%ID)":
        raise ValueError("Unexpected biodistribution unit header.")
    if str(raw.iloc[1, 14]).strip() != "Tumor" or str(raw.iloc[1, 16]).strip() != "Liver":
        raise ValueError("Unexpected paired organ columns.")
    data = raw.iloc[2:, :21].copy()
    data.columns = ["id", "particle_type", "core", "strategy", "nm_id", "shape", "pdi",
                    "size_raw", "zeta_raw", "tumor_cell", "tumor_size", "dose", "animal",
                    "hours", "tumor", "heart", "liver", "spleen", "lung", "kidney", "study"]
    data["id"] = pd.to_numeric(data["id"], errors="coerce").ffill()
    for column in ["hours", "tumor", "liver"]:
        data[column] = pd.to_numeric(data[column], errors="coerce")
    data = data[data["id"].notna() & data["hours"].notna()].copy()
    metadata = ["particle_type", "core", "strategy", "shape", "size_raw", "zeta_raw",
                "tumor_cell", "study"]
    for column in metadata:
        data[column] = data.groupby("id")[column].transform("first")
    for column in ["core", "strategy", "shape", "tumor_cell"]:
        data[column] = data[column].astype("string").str.strip()
    data = data[data["particle_type"].isin(["ONM", "INM", "Hybrid"])].copy()
    if data["study"].isna().any():
        raise ValueError("Publication reference missing for eligible measurement rows.")
    data["study"] = reference_groups(data["study"].tolist())
    data["size_nm"] = data["size_raw"].map(hydrodynamic_size)
    data["zeta_mv"] = pd.to_numeric(data["zeta_raw"], errors="coerce")
    return data


def endpoint(long, hours=24):
    rows, exclusions = [], []
    for identifier, block in long.groupby("id", sort=True):
        paired = (block.dropna(subset=["hours", "tumor", "liver"])
                  .groupby("hours", as_index=False)[["tumor", "liver"]].mean().sort_values("hours"))
        if len(paired) == 0 or paired["hours"].min() > hours or paired["hours"].max() < hours:
            exclusions.append({"id": int(identifier), "reason": "no_paired_bracket"})
            continue
        tumor, liver = [float(np.interp(hours, paired["hours"], paired[column]))
                        for column in ["tumor", "liver"]]
        if not (0 < tumor <= 100 and 0 < liver <= 100):
            exclusions.append({"id": int(identifier), "reason": "nonpositive_or_above_100_percent_ID"})
            continue
        record = block.iloc[0][FEATURES + ["study"]].to_dict()
        record.update({"id": int(identifier), "tumor": tumor, "liver": liver,
                       "log_ratio": np.log10(tumor / liver),
                       "exact_time": bool((paired["hours"] == hours).any())})
        rows.append(record)
    frame = pd.DataFrame(rows, columns=FEATURES + [
        "study", "id", "tumor", "liver", "log_ratio", "exact_time",
    ])
    for column in CATEGORICAL:
        frame[column] = frame[column].astype(object).where(frame[column].notna(), np.nan)
    return frame, exclusions


def rank_summary(frame):
    top_n = max(1, int(np.ceil(len(frame) / 4)))
    tumor_ids = set(frame.nlargest(top_n, "tumor")["id"])
    ratio_ids = set(frame.nlargest(top_n, "log_ratio")["id"])
    return {
        "spearman_tumor_vs_selectivity": float(spearmanr(frame["tumor"], frame["log_ratio"]).statistic),
        "top_quartile_count": top_n,
        "top_quartile_overlap_fraction": len(tumor_ids & ratio_ids) / top_n,
        "median_tumor_percent_id": float(frame["tumor"].median()),
        "median_liver_percent_id": float(frame["liver"].median()),
        "median_tumor_liver_ratio": float((frame["tumor"] / frame["liver"]).median()),
    }


def targeting_effect(frame):
    eligible = frame[frame["strategy"].isin(["Active", "Passive"])].copy()
    counts = eligible.groupby("strategy").size().to_dict()
    means = eligible.groupby(["study", "strategy"])["log_ratio"].mean().unstack()
    matched = means.dropna(subset=["Active", "Passive"])
    result = {"counts": counts, "overlap_publications": len(matched),
              "observational_warning": "Not a causal targeting effect; no randomization or composition matching."}
    if len(matched) >= 2:
        contrasts = (matched["Active"] - matched["Passive"]).to_numpy()
        rng = np.random.default_rng(907)
        draws = np.array([rng.choice(contrasts, len(contrasts), replace=True).mean()
                          for _ in range(5000)])
        result["within_publication"] = {
            "estimate_log10": float(contrasts.mean()),
            "lower": float(np.quantile(draws, 0.025)),
            "upper": float(np.quantile(draws, 0.975)), "repeats": 5000,
            "seed": 907, "study_contrasts": contrasts.tolist(),
        }
    else:
        result["within_publication"] = {"status": "not_estimable", "reason": "Fewer than two overlapping publications."}
    if set(counts) == {"Active", "Passive"}:
        result["pooled_cluster_bootstrap"] = cluster_bootstrap(
            eligible, "study",
            lambda x: x.loc[x["strategy"] == "Active", "log_ratio"].mean()
            - x.loc[x["strategy"] == "Passive", "log_ratio"].mean(),
            repeats=2000, seed=601)
    else:
        result["pooled_cluster_bootstrap"] = {"status": "not_estimable", "reason": "Missing targeting category."}
    return result


def main():
    out = ROOT / "results"
    out.mkdir(exist_ok=True)
    with resources(out):
        long = load_long()
        all_frame, exclusions = endpoint(long)
        frame = all_frame[all_frame["core"] == "Polymeric"].copy().reset_index(drop=True)
        if frame["study"].nunique() < 15:
            raise ValueError("Too few independent polymer publications for planned evaluation.")
        frame.to_csv(out / "analysis_dataset.csv", index=False)
        all_frame.to_csv(out / "all_material_endpoints.csv", index=False)
        audit = {
            "long_rows": len(long), "raw_formulations": long["id"].nunique(),
            "all_material_24h_pairs": len(all_frame), "polymeric_24h_pairs": len(frame),
            "polymeric_publications": frame["study"].nunique(),
            "polymeric_exact_24h": int(frame["exact_time"].sum()),
            "core_counts": all_frame["core"].value_counts().to_dict(),
            "missing_numeric": frame[NUMERIC].isna().sum().to_dict(),
            "size_rule": "Use explicitly labelled HD (hydrodynamic diameter) only; TEM-only sizes remain missing.",
            "time_unit": "hours", "organ_unit": "% injected dose, whole organ",
            "excluded": exclusions, "input_sha256": input_hashes(ROOT / "data"),
            "primary_core_rule": "Exact source category Polymeric; no outcome-based material assignment.",
            "reference_grouping": "Slash-linked references are merged as connected components, including all records of either reference.",
        }
        save_json(out / "data_audit.json", audit)
        effects = {"primary_24h": targeting_effect(frame)}
        sensitivity, ranks = [], []
        for hours in [6, 24, 48]:
            candidate, _ = endpoint(long, hours)
            for label, subset in [
                ("polymeric", candidate[candidate["core"] == "Polymeric"]),
                ("polymer_extended", candidate[candidate["core"].isin(["Polymeric", "Hydrogel", "Dendrimer"])]),
            ]:
                if len(subset) < 3:
                    raise ValueError(f"Too few observations for {hours}h / {label} sensitivity.")
                sensitivity.append({"hours": hours, "cohort": label, "n": len(subset),
                                    "publications": subset["study"].nunique(), **rank_summary(subset)})
        exact = frame[frame["exact_time"]]
        effects["exact_24h"] = targeting_effect(exact)
        effects["rank_summary"] = rank_summary(frame)
        effects["median_log_ratio_bootstrap"] = cluster_bootstrap(
            frame, "study", lambda x: x["log_ratio"].median(), repeats=2000, seed=602)
        effects["spearman_bootstrap"] = cluster_bootstrap(
            frame, "study", lambda x: spearmanr(x["tumor"], x["log_ratio"]).statistic,
            repeats=2000, seed=603)
        save_json(out / "effects.json", effects)
        pd.DataFrame(sensitivity).to_csv(out / "sensitivity.csv", index=False)
        groups = frame["study"].to_numpy()
        y = frame[["log_ratio"]].to_numpy()
        metrics, predictions, splits = [], [], []
        ablations = {
            "median": FEATURES, "ridge": FEATURES, "trees": FEATURES,
            "trees_no_targeting": [x for x in FEATURES if x != "strategy"],
            "trees_physchem_only": NUMERIC + ["shape"],
            "trees_permuted": FEATURES,
        }
        for seed in SEEDS:
            for grouped in [True, False]:
                train, calibration, test = split_indices(groups, seed, grouped)
                split = "publication" if grouped else "formulation_random"
                for role, indices in [("train", train), ("reserved_unused", calibration), ("test", test)]:
                    splits.extend({"seed": seed, "split": split, "role": role,
                                   "id": int(frame.iloc[i]["id"]), "study": groups[i]} for i in indices)
                for name, columns in (ablations if grouped else {"trees": FEATURES}).items():
                    if name == "median":
                        pred = np.full((len(test), 1), np.median(y[train]))
                    else:
                        target = y[train].copy()
                        if name == "trees_permuted":
                            target = target[np.random.default_rng(seed).permutation(len(target))]
                        model = fit_model(frame.iloc[train][columns], target,
                                          "ridge" if name == "ridge" else "trees", seed)
                        pred = predict(model, frame.iloc[test][columns])
                    metrics.append({"seed": seed, "split": split, "model": name,
                                    "n_test": len(test), **score(y[test], pred, groups[test])})
                    if name == "trees":
                        predictions.extend({"seed": seed, "split": split, "id": int(frame.iloc[i]["id"]),
                                            "study": groups[i], "observed": float(y[i, 0]),
                                            "predicted": float(pred[k, 0])}
                                           for k, i in enumerate(test))
        metrics = pd.DataFrame(metrics)
        metrics.to_csv(out / "metrics.csv", index=False)
        pd.DataFrame(predictions).to_csv(out / "predictions.csv", index=False)
        pd.DataFrame(splits).to_csv(out / "splits.csv", index=False)
        metrics.groupby(["split", "model"])[["mae", "study_macro_mae", "r2"]].agg(["mean", "std"]).to_csv(out / "summary.csv")
        save_json(out / "protocol.json", {
            "seeds": SEEDS, "primary_time_hours": 24, "sensitivity_hours": [6, 24, 48],
            "bootstrap_unit": "publication", "target": "log10(tumor %ID / liver %ID)",
            "trees": 128, "min_samples_leaf": 3, "ridge_alpha": 10,
            "hyperparameter_search": False, "causal_claims": False,
            "note": "Exploratory protocol fixed in code before outcomes; not externally preregistered.",
        })
        fig, ax = plt.subplots(figsize=(6.8, 4))
        for label, block in frame.groupby("strategy"):
            ax.scatter(block["tumor"], block["liver"], label=label, alpha=0.65, s=22)
        ax.set(xscale="log", yscale="log", xlabel="Tumour accumulation (%ID, 24 h)",
               ylabel="Liver accumulation (%ID, 24 h)")
        limits = [min(frame["tumor"].min(), frame["liver"].min()),
                  max(frame["tumor"].max(), frame["liver"].max())]
        ax.plot(limits, limits, "--", color="black", label="Tumour = liver")
        ax.legend()
        fig.tight_layout()
        fig.savefig(out / "paired_organs.png", dpi=180)
        plt.close(fig)
        fig, ax = plt.subplots(figsize=(7, 4))
        stats = metrics[metrics["split"] == "publication"].groupby("model")["mae"].agg(["mean", "std"])
        ax.barh(stats.index, stats["mean"], xerr=stats["std"], color="#245c78")
        ax.set_xlabel("MAE in log10 tumour/liver ratio; split-to-split SD")
        fig.tight_layout()
        fig.savefig(out / "ablation.png", dpi=180)
        plt.close(fig)
        print("AUDIT", {k: v for k, v in audit.items() if k != "excluded"})
        print("EFFECTS", effects)
        print(metrics.groupby(["split", "model"])[["mae", "r2"]].mean().round(4).to_string())


if __name__ == "__main__":
    main()
