"""Replot saved results at readable single-column size without rerunning models."""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

MODEL_NAMES = {
    "median": "Median", "ridge": "Ridge", "trees": "Extra trees",
    "trees_no_drug": "No drug features", "trees_polymer_only": "Polymer only",
    "trees_no_projection": "Unconstrained", "trees_permuted": "Shuffled targets",
    "trees_no_targeting": "No targeting", "trees_physchem_only": "Physicochemical",
}


def save(figure, directory, name):
    figure.tight_layout(pad=0.4)
    figure.savefig(directory / f"{name}.pdf", bbox_inches="tight", pad_inches=0.02)
    figure.savefig(directory / f"{name}.png", dpi=200, bbox_inches="tight", pad_inches=0.02)
    plt.close(figure)


def prepare_figures(directory):
    directory = Path(directory)
    results = directory / "results"
    output = directory / "figures"
    output.mkdir(exist_ok=True)
    release = directory.name == "01_release_transfer"
    if not release and directory.name != "02_polymer_targeting":
        raise ValueError(f"Unknown publication figure set: {directory.name}")
    settings = {
        "font.family": "STIXGeneral", "font.size": 9.5, "axes.labelsize": 9.5,
        "xtick.labelsize": 9.5, "ytick.labelsize": 9.5, "legend.fontsize": 9.5,
        "pdf.fonttype": 42, "mathtext.fontset": "stix",
    }
    with plt.rc_context(settings):
        metrics = pd.read_csv(results / "metrics.csv")
        primary = metrics[metrics["split"] == "publication"]
        statistics = primary.groupby("model")["mae"].agg(["mean", "std"])
        figure, axis = plt.subplots(figsize=(3.05, 2.45))
        axis.barh([MODEL_NAMES[name] for name in statistics.index], statistics["mean"],
                  xerr=statistics["std"], color="#245c78", capsize=2)
        axis.invert_yaxis()
        axis.set_xlabel("MAE (release fraction)" if release else "MAE (log10 tumour/liver)")
        axis.spines[["top", "right"]].set_visible(False)
        save(figure, output, "ablation")

        if release:
            intervals = pd.read_csv(results / "intervals.csv")
            calibration = (intervals[intervals["split"] == "publication"]
                           .groupby("method").mean(numeric_only=True))
            order = ["pooled_point", "formulation_max", "publication_max"]
            labels = ["Pointwise", "Formulation", "Publication"]
            figure, axes = plt.subplots(2, 1, figsize=(3.05, 2.9))
            for axis, column, color, label in [
                (axes[0], "publication_coverage", "#245c78", "Publication coverage"),
                (axes[1], "mean_width", "#a25138", "Mean interval width"),
            ]:
                axis.barh(labels, calibration.loc[order, column], color=color)
                axis.invert_yaxis()
                axis.set_xlim(0, 1)
                axis.set_xticks([0, 0.5, 1])
                axis.set_xlabel(label)
                axis.spines[["top", "right"]].set_visible(False)
            axes[0].axvline(0.9, color="black", linestyle="--", linewidth=1)
            save(figure, output, "coverage")
        else:
            frame = pd.read_csv(results / "analysis_dataset.csv")
            figure, axis = plt.subplots(figsize=(3.05, 2.65))
            for label, block in frame.groupby("strategy"):
                axis.scatter(block["tumor"], block["liver"], label=label, alpha=0.7, s=12)
            axis.set(xscale="log", yscale="log",
                     xlabel="Tumour accumulation (%ID)",
                     ylabel="Liver accumulation (%ID)")
            lower = min(frame["tumor"].min(), frame["liver"].min())
            upper = max(frame["tumor"].max(), frame["liver"].max())
            axis.plot([lower, upper], [lower, upper], "--", color="black", linewidth=1)
            axis.legend(loc="lower right", frameon=False, handletextpad=0.25)
            save(figure, output, "paired_organs")
