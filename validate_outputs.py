"""Recompute reported primary outcomes and verify manuscript/data artifact contracts."""
import hashlib
import json
from pathlib import Path
import re

import numpy as np
import pandas as pd
from pypdf import PdfReader
from scipy.stats import spearmanr
from sklearn.metrics import r2_score
from acl_documents import TEMPLATE_COMMIT, figure_heading_spacing, heading_page, verify_template
from validate_extended import validate_project
from project_scope import selected_projects

ROOT = Path(__file__).resolve().parent


def close(actual, expected, description):
    if not np.isclose(actual, expected, atol=1e-10, rtol=1e-9):
        raise AssertionError(f"{description}: recalculated {actual}, saved {expected}")


def validate():
    checks = []
    projects = selected_projects()
    for folder in projects:
        directory = ROOT / folder
        out = directory / "results"
        audit = json.loads((out / "data_audit.json").read_text())
        for name, digest in audit["input_sha256"].items():
            actual = hashlib.sha256((directory / "data" / name).read_bytes()).hexdigest()
            if actual != digest:
                raise AssertionError(f"Changed input: {folder}/{name}")
        frame = pd.read_csv(out / "analysis_dataset.csv")
        metrics = pd.read_csv(out / "metrics.csv")
        predictions = pd.read_csv(out / "predictions.csv")
        splits = pd.read_csv(out / "splits.csv")
        primary_splits = splits[splits["split"] == "publication"]
        if (primary_splits.groupby(["seed", "study"])["role"].nunique() > 1).any():
            raise AssertionError(f"Publication leakage in {folder}")
        if primary_splits.duplicated(["seed", "id"]).any():
            raise AssertionError(f"Duplicate partition assignments in {folder}")
        for (split, seed), rows in predictions.groupby(["split", "seed"]):
            if folder == "01_release_transfer":
                rows = rows[rows["method"] == "publication_max"]
                actual = rows.pivot(index="id", columns="day", values="observed").to_numpy()
                predicted = rows.pivot(index="id", columns="day", values="predicted").to_numpy()
            else:
                actual = rows["observed"].to_numpy()
                predicted = rows["predicted"].to_numpy()
            saved = metrics[(metrics["split"] == split) &
                            (metrics["seed"] == seed) & (metrics["model"] == "trees")].iloc[0]
            close(np.abs(actual - predicted).mean(), saved["mae"], f"{folder} MAE {split}/{seed}")
            close(r2_score(actual, predicted), saved["r2"], f"{folder} R2 {split}/{seed}")
        resource = json.loads((out / "resources.json").read_text())
        if resource["elapsed_seconds"] > 7200 or resource["sampled_peak_rss_mb"] > 4096:
            raise AssertionError(f"Measured analysis budget exceeded in {folder}")
        document = PdfReader(directory / "manuscript.pdf")
        validation = json.loads((directory / "document_validation.json").read_text())
        if validation["pages"] != len(document.pages):
            raise AssertionError(f"{folder} recorded page count mismatch")
        if validation["format"] != "Official ACL LaTeX, final mode":
            raise AssertionError(f"{folder} is not recorded as ACL final format")
        if validation["template_commit"] != TEMPLATE_COMMIT:
            raise AssertionError(f"{folder} ACL template version mismatch")
        verify_template(directory)
        reference_index = validation["references_start_page"] - 1
        if heading_page(document, "References") != reference_index + 1:
            raise AssertionError(f"{folder} reference page allocation mismatch")
        if validation["main_text_pages"] not in [reference_index, reference_index + 1]:
            raise AssertionError(f"{folder} recorded main-text extent mismatch")
        source = (directory / "manuscript.tex").read_text(encoding="utf-8")
        if r"\documentclass[11pt]{article}" not in source or r"\usepackage[final]{acl}" not in source:
            raise AssertionError(f"{folder} source is not using the official final-mode template")
        if r"\bibliography{references}" not in source:
            raise AssertionError(f"{folder} bibliography is not built by BibTeX")
        if re.search(r"\\(?:geometry|fontsize|vspace|renewcommand\\baselinestretch)\b", source):
            raise AssertionError(f"{folder} has prohibited layout overrides")
        if validation["main_text_pages"] not in [8, 9] or validation["appendix_pages"] < 10:
            raise AssertionError(f"{folder} does not meet the approximately-eight-page main text and ten-page appendix targets")
        if validation["references_start_page"] <= validation["main_text_pages"]:
            raise AssertionError(f"{folder} references are not additional to the main text")
        text = "\n".join(page.extract_text() for page in document.pages)
        if len(document.pages[validation["main_text_pages"]-1].extract_text().split()) < 250:
            raise AssertionError(f"{folder} has an almost-empty final main-text page")
        if not re.search(r"\bT\s*Recalculation\s+and\s+reproducibility\s+contract", text):
            raise AssertionError(f"{folder} final appendix section is missing")
        for forbidden in [
            "EXPLORATORY COMPUTATIONAL RESEARCH DRAFT", "AI disclosure", "AI assistance",
            "AI generated", "Author and AI", "requester", "Nature endorsement",
            "Nature-level", "responsible submission gate", "named-author verification",
        ]:
            for content in [text, source, (directory / "manuscript.md").read_text(encoding="utf-8")]:
                if forbidden.casefold() in " ".join(content.split()).casefold():
                    raise AssertionError(f"{folder}: removed administrative text remains: {forbidden}")
        if r"\begin{figure*}" in source or r"\begin{table*}" in source:
            raise AssertionError(f"{folder}: detached full-width floats remain")
        if r"\raggedbottom" not in source:
            raise AssertionError(f"{folder}: column spacing may stretch")
        spacing = figure_heading_spacing(document, validation["main_text_pages"])
        if len(spacing) != validation["figures"]:
            raise AssertionError(f"{folder}: some results figures are not adjacent to section headings")
        figure_pages = []
        for number, pdf_page in enumerate(document.pages, 1):
            captions = re.findall(r"\bFigure\s*(\d+)\s*:", pdf_page.extract_text())
            if not captions:
                continue
            body = []

            def collect_body(value, _cm, _tm, _font, size):
                if 10.5 <= size <= 11.5:
                    body.append(value)

            pdf_page.extract_text(visitor_text=collect_body)
            words = len(" ".join(body).split())
            if words < 80:
                raise AssertionError(f"{folder}: figure on page {number} has only {words} body words")
            if number > validation["main_text_pages"]:
                raise AssertionError(f"{folder}: results figure is outside the main text")
            figure_pages.append({"page": number, "figures": captions, "body_words": words})
        if sorted(figure for page in figure_pages for figure in page["figures"]) != [
                str(index) for index in range(1, validation["figures"]+1)]:
            raise AssertionError(f"{folder}: expected every numbered results figure within the text")
        if "Shereen Anand" not in text or "pes1202201328@pesu.pes.edu" not in text:
            raise AssertionError(f"{folder} missing supplied author details")
        for number, p in enumerate(document.pages, 1):
            if len(p.extract_text().strip()) < 100:
                raise AssertionError(f"{folder}: unexpectedly sparse page {number}")
            if abs(float(p.mediabox.width) - 595.276) > 1 or abs(float(p.mediabox.height) - 841.89) > 1:
                raise AssertionError(f"{folder}: page {number} is not A4")
            for font in p["/Resources"].get("/Font", {}).values():
                font = font.get_object()
                descendants = font.get("/DescendantFonts")
                if descendants:
                    font = descendants[0].get_object()
                descriptor = font.get("/FontDescriptor")
                if not descriptor or not any(
                        key in descriptor.get_object() for key in ["/FontFile", "/FontFile2", "/FontFile3"]):
                    raise AssertionError(f"{folder}: page {number} contains an unembedded font")
        checks.append({
            "project": folder, "pages": len(document.pages),
            "cohort": len(frame), "publication_groups": frame["study"].nunique(),
            "score_recalculation": "passed", "input_hashes": "passed",
            "publication_separation": "passed", "measured_budget": "passed",
            "acl_final_format": "passed", "official_template_integrity": "passed",
            "a4_and_embedded_fonts": "passed",
            "removed_administrative_text": "passed", "integrated_figures": figure_pages,
            "figure_heading_spacing": spacing,
            "main_text_pages": validation["main_text_pages"], "appendix_pages": validation["appendix_pages"],
            "extended_analyses": validate_project(directory),
        })

    if "01_release_transfer" in projects:
        validate_release()
    if "02_polymer_targeting" in projects:
        validate_polymer()
    result = {"status": "passed", "projects": checks,
              "interval_recalculation": "passed" if "01_release_transfer" in projects else "not_in_this_repository",
              "polymer_estimand_recalculation": "passed" if "02_polymer_targeting" in projects else "not_in_this_repository",
              "warning": "Computational and document integrity only; not scientific peer review or validation of a treatment."}
    (ROOT / "validation_report.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


def validate_release():
    release = ROOT / "01_release_transfer" / "results"
    intervals = pd.read_csv(release / "intervals.csv")
    predictions = pd.read_csv(release / "predictions.csv")
    for (split, seed, method), rows in predictions.groupby(["split", "seed", "method"]):
        covered = (rows["observed"] >= rows["lower"]) & (rows["observed"] <= rows["upper"])
        if not ((rows["lower"] <= rows["predicted"]) &
                (rows["predicted"] <= rows["upper"]) &
                (rows["lower"] >= 0) & (rows["upper"] <= 1)).all():
            raise AssertionError("Invalid release interval bounds")
        saved = intervals[(intervals["split"] == split) & (intervals["seed"] == seed) &
                          (intervals["method"] == method)].iloc[0]
        close(covered.mean(), saved["point_coverage"], "Endpoint coverage")
        close(covered.groupby(rows["id"]).all().mean(), saved["vector_coverage"], "Vector coverage")
        close(covered.groupby(rows["study"]).all().mean(), saved["publication_coverage"], "Publication coverage")
        close((rows["upper"]-rows["lower"]).mean(), saved["mean_width"], "Interval width")


def validate_polymer():
    tumor = ROOT / "02_polymer_targeting" / "results"
    frame = pd.read_csv(tumor / "analysis_dataset.csv")
    effects = json.loads((tumor / "effects.json").read_text())
    close(np.log10(frame["tumor"]/frame["liver"]).to_numpy().max(),
          frame["log_ratio"].max(), "Ratio definition")
    np.testing.assert_allclose(np.log10(frame["tumor"]/frame["liver"]), frame["log_ratio"], atol=1e-12)
    close(spearmanr(frame["tumor"], frame["log_ratio"]).statistic,
          effects["rank_summary"]["spearman_tumor_vs_selectivity"], "Rank correlation")
    top_n = effects["rank_summary"]["top_quartile_count"]
    overlap = set(frame.nlargest(top_n, "tumor")["id"]) & set(frame.nlargest(top_n, "log_ratio")["id"])
    close(len(overlap)/top_n, effects["rank_summary"]["top_quartile_overlap_fraction"], "Ranking overlap")
    means = frame.groupby(["study", "strategy"])["log_ratio"].mean().unstack()
    matched = means.dropna(subset=["Active", "Passive"])
    close((matched["Active"]-matched["Passive"]).mean(),
          effects["primary_24h"]["within_publication"]["estimate_log10"], "Within-publication association")


if __name__ == "__main__":
    validate()
