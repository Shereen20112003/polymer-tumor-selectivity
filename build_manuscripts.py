"""Build evidence-linked research drafts using the official ACL final template."""
from collections import Counter
import json
from pathlib import Path

import numpy as np
import pandas as pd
from acl_documents import render as render_acl
from expanded_manuscripts import expand
from project_scope import selected_projects

ROOT = Path(__file__).resolve().parent
AUTHOR = "Shereen Anand"
AFFILIATION = "PES University"
EMAIL = "pes1202201328@pesu.pes.edu"
REFERENCES = json.loads((ROOT / "reference_metadata.json").read_text(encoding="utf-8"))


def load(folder, file):
    return json.loads((ROOT / folder / "results" / file).read_text(encoding="utf-8"))


def para(text):
    return ("paragraph", text)


def table(frame, caption):
    return ("table", (frame, caption))


def image(file, caption, height=210):
    return ("image", (file, caption, height))


def page(title, *blocks):
    return {"title": title, "blocks": list(blocks)}


def reference_blocks(dois, dataset):
    return [("bibliography", (dois, dataset))]


def summary_table(metrics):
    result = metrics.groupby(["split", "model"])[["mae", "study_macro_mae", "r2"]].mean().reset_index()
    result.columns = ["Split", "Model", "MAE", "Study-macro MAE", "R2"]
    return result


def feature_table_release(audit):
    return pd.DataFrame([
        ["Drug MW", "Da", "Molecular mass", audit["missing_features"]["Drug MW"]],
        ["Drug TPSA", "angstrom squared", "Topological polar surface area", 0],
        ["Drug LogP", "unitless", "Calculated lipophilicity", 0],
        ["Polymer MW", "kDa", "Mixed MW convention in source; not uniform Mw", 0],
        ["LA/GA", "molar ratio", "Lactide / glycolide", 0],
        ["Initial Drug-to-Polymer Ratio", "w/w", "Input drug / polymer", 0],
        ["Particle Size", "micrometres", "Microparticle diameter", 0],
        ["Drug Loading Capacity", "%", "Drug / loaded particle mass", 0],
        ["Drug Encapsulation Efficiency", "%", "Encapsulated / input drug", 0],
        ["Solubility Enhancer Concentration", "%", "Release-medium additive", 0],
    ], columns=["Variable", "Source unit", "Interpretation", "Missing"])


def release_pages():
    folder = "01_release_transfer"
    out = ROOT / folder / "results"
    audit = load(folder, "data_audit.json")
    resource = load(folder, "resources.json")
    frame = pd.read_csv(out / "analysis_dataset.csv")
    metrics = pd.read_csv(out / "metrics.csv")
    intervals = pd.read_csv(out / "intervals.csv")
    predictions = pd.read_csv(out / "predictions.csv")
    splits = pd.read_csv(out / "splits.csv")
    m = metrics.groupby(["split", "model"]).mean(numeric_only=True)
    c = intervals[intervals["split"] == "publication"].groupby("method").mean(numeric_only=True)
    tree = m.loc[("publication", "trees")]
    median = m.loc[("publication", "median")]
    random = m.loc[("formulation_random", "trees")]
    per_seed = metrics[metrics["split"] == "publication"]
    methods = c[["point_coverage", "vector_coverage", "publication_coverage", "mean_width"]].reset_index()
    cohort = pd.DataFrame([
        ["Release observations in mirrored source", audit["raw_observations"]],
        ["Source formulations", audit["raw_formulations"]],
        ["Eligible formulations", audit["included_formulations"]],
        ["Eligible DOI groups", audit["included_publications"]],
        ["Excluded formulations", len(audit["excluded"])],
        ["Raw curves with a decreasing segment", audit["raw_nonmonotone_curves"]],
    ], columns=["Quantity", "Count"])
    title = "Publication-block calibration reveals wide uncertainty in PLGA release endpoint prediction"
    pages = [
        page(title,
             para("<b>Abstract.</b> Literature-mined release curves can support model development while "
                  "overstating applicability to an unseen publication. We test the consequences of changing "
                  "the uncertainty unit from a release observation to a formulation and then an entire "
                  "publication block. A unit-audited public PLGA dataset provides 1-, 3-, and 7-day "
                  f"endpoints for {len(frame)} formulations from {frame['study'].nunique()} DOI groups. "
                  "Fixed single-threaded baselines are evaluated with five prespecified 60/20/20 "
                  "publication train/calibration/test partitions. The primary outcome is simultaneous "
                  "coverage of every eligible formulation endpoint within a held-out publication."),
             para(f"Extra-trees MAE was {tree['mae']:.3f} release fraction under publication splitting, "
                  f"versus {random['mae']:.3f} under formulation-random splitting; mean publication-split "
                  f"R2 was {tree['r2']:.3f}. Pooled-point calibration yielded "
                  f"{c.loc['pooled_point','publication_coverage']:.0%} empirical publication coverage, "
                  f"compared with {c.loc['publication_max','publication_coverage']:.0%} for publication-max "
                  f"calibration. Mean widths were {c.loc['pooled_point','mean_width']:.3f} and "
                  f"{c.loc['publication_max','mean_width']:.3f}, respectively, on a physical 0-1 scale."),
             para("Respecting the deployment unit improves empirical simultaneous "
                  "coverage but produces wide intervals and does not create useful mechanistic prediction. "
                  "The observed coverage is not a prospective guarantee. These results identify a "
                  "tradeoff between simultaneous coverage and informative interval width."),
             para("<b>Keywords:</b> PLGA; controlled release; publication shift; group calibration; uncertainty; reproducibility.")),
        page("1. Introduction",
             para("Long-acting polymer depots couple molecular transport, water uptake, degradation, "
                  "particle microstructure, drug partitioning, and test-medium effects. Descriptors such as "
                  "polymer molecular weight and drug lipophilicity encode only part of that system. "
                  "A computationally inexpensive predictor can therefore be precise on familiar formulations "
                  "yet fail on a new publication's preparation and measurement conditions. Precision drug "
                  "delivery requires honest uncertainty as well as a point estimate [Mitchell et al., 2021]."),
             para("Bao et al. (2025) released a literature-mined PLGA microparticle resource containing "
                  "321 formulations and 4,913 release observations. The 2026 study 'Diagnosing the Information "
                  "Limits of In Vitro Drug Release from PLGA Microparticle Data' already investigated "
                  "formulation- and study-level generalization on this resource. Building on that work, "
                  "we examine the calibration unit and the uncertainty-width cost of simultaneous coverage."),
             para("Classical Higuchi and Ritger-Peppas models provide important mechanistic and empirical "
                  "release descriptions, but their assumptions do not automatically hold across all PLGA "
                  "literature curves. We do not fit a mechanistic diffusivity or interpret feature associations "
                  "as transport parameters. Our endpoint model is deliberately simpler and cheaper than "
                  "physics-informed network training. Its limited performance is itself a relevant outcome."),
             para("Conformal prediction supplies finite-sample rank calibration under appropriate "
                  "exchangeability assumptions. Hierarchical prediction is established prior art "
                  "[Vovk et al., 2005; Dunn et al., 2023; Angelopoulos and Bates, 2023]. "
                  "We compare pooled-point, formulation-max, "
                  "and publication-max residual calibration for the same bounded endpoint vector and "
                  "reporting all three levels of empirical coverage alongside interval width."),
             para("<b>Research questions.</b> Does publication separation change "
                  "prediction error relative to a formulation-random split? Does a publication-max score "
                  "improve held-out publication simultaneous coverage? Does any improvement retain intervals "
                  "narrow enough to discriminate practical release profiles? We evaluate these questions "
                  "using fixed baselines and repeated publication-grouped partitions.")),
        page("2. Data provenance, units and endpoint cohort",
             para("The experimental observations originate from Bao et al., Mendeley Data V2 "
                  "(10.17632/zzvtdrcy76.2; CC BY 4.0). The retrieved workbooks are an attributed mirror "
                  "pinned to repository commit 387a2f831853a0d6ff1f7f8a91a75bc64b6d19b8. "
                  "They are not independently certified byte-identical to the original deposit. "
                  "The measured source totals match the published 321 formulations and 4,913 points. "
                  "All used workbook SHA-256 values are retained."),
             table(cohort, "Table 1. Auditable cohort flow. Counts refer to this run, not newly generated experiments."),
             para("Table 2 of the original data paper explicitly defines Time in days and Release as "
                  "a mass fraction. Therefore the endpoints are evaluated at source times 1, 3 and 7, "
                  "not 24, 72 and 168. A one-day endpoint is not obtained by querying source time 24. "
                  "This unit check is essential before interpreting a burst-release or long-horizon target."),
             para("For each formulation, observations at identical times are averaged and sorted. "
                  "Linear interpolation is permitted only when the observed time range brackets all "
                  "three endpoints; no temporal extrapolation or added zero-time observation is used. "
                  "A curve with any release value outside [0,1] is excluded rather than silently clipped. "
                  "Decreasing digitized segments are counted and retained in the observed targets."),
             para("DOIs are joined from the initial-formulation table by formulation index, stripped and "
                  "lowercased. Duplicate mappings, missing DOIs, nonfinite observations, and descriptors "
                  "that change within a formulation stop the run. The eligibility rule changes the "
                  "population: conclusions apply to retained day-7-bracketing curves, not all PLGA systems. "
                  "The literature source itself has selection and reporting biases.")),
        page("3. Prediction and publication-level calibration",
             para("Ten numerical descriptors cover drug properties, polymer molecular weight, LA/GA, "
                  "particle size, loading, encapsulation, input composition, and release-medium enhancer. "
                  "Neither DOI nor formulation index is a predictor. A training-fitted median imputer and "
                  "scaler precede ridge regression (alpha=10) or 128 extremely randomized trees "
                  "(minimum leaf size=3, one worker). A componentwise training median is the reference. "
                  "Hyperparameters are fixed; no test-guided search is performed [Geurts et al., 2006]."),
             para("Seeds 11, 29, 47, 71 and 101 define repeated publication partitions. Approximately "
                  "60% of DOI groups fit the model, 20% calibrate intervals, and 20% evaluate it. "
                  "These proportions describe publication counts, not guaranteed formulation counts. "
                  "The formulation-random comparison uses the same nominal row proportions and allows "
                  "publication overlap deliberately; it is not the deployment-valid primary analysis."),
             para("Predictions are clipped to [0,1] and projected by equal-weight isotonic regression "
                  "across the three increasing times. This enforces nondecreasing predicted cumulative "
                  "release without altering the observed endpoint vectors. A no-projection ablation "
                  "measures whether the constraint changes performance."),
             para("<b>Calibration equations.</b> For calibration formulation i and endpoint j, "
                  "r(i,j)=|y(i,j)-f(x(i),j)|. Scores are either all pooled r(i,j), "
                  "max_j r(i,j) for each formulation, or S(g)=max_(i in g,j) r(i,j) "
                  "for each publication g. For n score units and alpha=0.1, q is the "
                  "ceil((n+1)(1-alpha))-th ordered score. If that rank exceeds n, the implementation "
                  "raises an explicit insufficient-calibration error. Intervals are [f-q,f+q] intersected "
                  "with [0,1]. The calibration model is never refitted with calibration labels."),
             para("The primary metric asks whether all evaluated endpoints of all eligible formulations "
                  "in a test DOI group lie inside their intervals. Secondary metrics are endpoint and "
                  "formulation-vector coverage, average interval width, MAE, study-macro MAE and R2. "
                  "Publication exchangeability is a hypothetical condition, not established by random "
                  "splitting a heterogeneous literature compilation [Roberts et al., 2017].")),
        page("4. Predictive performance and ablations",
             table(summary_table(metrics).iloc[:5], "Table 2. Mean scores across five overlapping partitions; full table in Appendix E."),
             para(f"Figure 1 compares the publication-separated baselines and controls. "
                  f"The primary tree MAE of {tree['mae']:.3f} corresponds to "
                  f"{100*tree['mae']:.1f} percentage points of fractional release. "
                  f"The median baseline MAE was {median['mae']:.3f}. The tree model's mean "
                  f"R2 of {tree['r2']:.3f} provides little evidence of strong transferable prediction. "
                  f"Formulation-random MAE was lower by {tree['mae']-random['mae']:.3f}, but "
                  "the two holdout schemes contain different evaluation compositions; that contrast "
                  "is an optimism diagnostic, not a paired causal estimate of leakage."),
             image("ablation.png", "Figure 1. Publication-split ablation MAE. Error bars are split-to-split SD, not independent-sample confidence intervals.", 205),
             para("Drug-descriptor removal, polymer-only inputs, target permutation and no-projection "
                  "controls are reported even when their performance is worse or indistinguishable. "
                  "A permutation diagnostic is not a calibrated hypothesis test. The fixed baseline "
                  "comparison does not establish that no better model exists; it tests this inexpensive "
                  "benchmark under the stated information and partitioning constraints.")),
        page("5. Coverage improves at a substantial width cost",
             table(methods, "Table 3. Publication-split empirical coverage and width, averaged equally over five partitions."),
             para(f"Figure 2 shows the coverage-width tradeoff. "
                  f"Pooled-point residuals gave {c.loc['pooled_point','point_coverage']:.1%} endpoint "
                  f"coverage but only {c.loc['pooled_point','publication_coverage']:.1%} publication "
                  "coverage. A pointwise statement therefore cannot be substituted for a statement "
                  "that an entire new publication block is covered. Moving to formulation maxima "
                  f"raised publication coverage to {c.loc['formulation_max','publication_coverage']:.1%}; "
                  f"publication maxima reached {c.loc['publication_max','publication_coverage']:.1%}."),
             image("coverage.png", "Figure 2. Simultaneous publication coverage and mean width. Dashed line denotes the nominal 90% target, not a validated guarantee.", 200),
             para(f"The corresponding publication-max mean width of "
                  f"{c.loc['publication_max','mean_width']:.3f} spans most of the physically possible "
                  "release range. Empirical mean publication coverage remains below 90%, although "
                  "the test blocks are few and repeated partitions overlap. We neither recalibrate "
                  "against these test failures nor report an invalid binomial confidence interval "
                  "that treats repeated test publications as independent observations."),
             para("This result is primarily a caution about informative uncertainty. A model can become "
                  "more conservative without becoming useful for selecting a depot formulation. "
                  "Finite-sample theory does not rescue missing process variables, inconsistent assay "
                  "conditions, or changing study-selection mechanisms.")),
        page("6. Discussion",
             para("The strongest supported conclusion is operational: publication-level simultaneous "
                  "coverage is a different target from pointwise coverage, and a calibration audit "
                  "should expose that distinction. The study also makes the day-based time convention "
                  "explicit, preserving a crucial data contract. Neither observation establishes a "
                  "new release mechanism or a deployable drug-delivery technology."),
             para("The eligible resource is heterogeneous and literature-selected. Source polymer MW "
                  "mixes weight-average, number-average and unspecified conventions when more precise "
                  "information is unavailable. Particle porosity, end groups, mixing energy, solvent "
                  "removal, and degradation state are not harmonized predictors. Interpolation converts "
                  "digitized curves into endpoints but does not restore experimental uncertainty. "
                  "Measurement errors and repeated measurements are not modeled separately."),
             para("A DOI is not a laboratory identifier. Different publications from the same laboratory "
                  "may appear in different partitions; publication separation is stricter than row splitting "
                  "but weaker than verified laboratory separation. Conversely, publications contain "
                  "different numbers and types of formulations, making maximum residuals sensitive "
                  "to block size. Calibration should not be advertised as robust to arbitrary domain shift."),
             para("The maximum-over-endpoints rule applies established calibration theory to a "
                  "publication-level deployment event. The weak predictive transfer is consistent "
                  "with the information-limits literature. More conservative intervals improve "
                  "coverage without resolving missing process information or identifying a release mechanism."),
             para("External evaluation should use prospectively specified laboratory datasets, "
                  "explicit batch and laboratory identifiers, mechanistic microstructure covariates, "
                  "and useful-width thresholds tied to an assay decision. Additional hierarchical "
                  "calibration methods should be compared under the same deployment conditions.")),
        page("7. Conclusions and data availability",
             para("Changing the uncertainty unit from release points to publication blocks produces "
                  "more conservative intervals, while the inexpensive predictor shows weak transfer "
                  "to unseen publications. The uncertainty-width tradeoff, rather than a favorable "
                  "single prediction score, should determine whether such a model can support an "
                  "experimental screening decision. No dosing, clinical efficacy, safety or in vivo "
                  "performance conclusion follows from this in vitro reanalysis."),
             para("<b>Data and code.</b> The accompanying directory contains attributed source workbooks, "
                  "download URLs and hashes, the frozen analysis cohort, every split, endpoint predictions "
                  "and interval bounds, all ablations, audit files, and executable Python code. "
                  "The upstream dataset is available under CC BY 4.0. The source article has "
                  "separate reuse terms. The analysis uses the pinned mirror identified in Section 2; "
                  "byte-level equivalence to the primary deposit has not been independently established."),
             para(f"<b>Compute.</b> The instrumented analysis used {resource['elapsed_seconds']:.1f} seconds "
                  f"and sampled peak process RSS {resource['sampled_peak_rss_mb']:.1f} MB, with one "
                  "estimator/BLAS worker. Timing excludes environment installation, initial imports "
                  "before the instrumentation context, downloads and manuscript generation. "
                  "A 0.1-second sampler may miss short memory peaks. This was not a GPU experiment."),
             para("This study reanalyses public aggregate in vitro measurements. No new human "
                  "or animal observations were collected.")),
        page("References",
             *reference_blocks([
                 "10.1038/s41597-025-04621-9", "10.3390/pharmaceutics18070805",
                 "10.1038/s41573-020-0090-8", "10.1002/jps.2600501018",
                 "10.1016/0168-3659(87)90034-4", "10.1007/s10994-006-6226-1",
                 "10.1080/01621459.2022.2060112", "10.1561/2200000101",
                 "10.1007/b106715", "10.1016/j.patter.2023.100804", "10.1111/ecog.02881",
             ], "Bao Z, Kim J, Kwok C, Le Devedec F, Allen C. A Dataset on Formulation Parameters "
                "and Characteristics of Drug-Loaded PLGA Microparticles. Mendeley Data, V2 (2024). "
                "https://doi.org/10.17632/zzvtdrcy76.2. CC BY 4.0.")),
        page("Appendix A. Source integrity and provenance",
             para("This project is a secondary analysis, not independent experimental replication. "
                  "The processed workbook and initial-formulation mapping are retrieved from a pinned "
                  "third-party mirror that attributes them to Bao et al. Their hashes fix the inputs "
                  "used here but do not prove equivalence to the original Mendeley release. The source "
                  "data paper's totals are reproduced. The article XML was downloaded unmodified "
                  "for checking data definitions; no source figure or article prose is republished."),
             para("The literature scan included PLGA predictor repositories and published information-limit "
                  "work, hierarchical conformal prediction, controlled-release transport models and "
                  "general leakage literature. It was targeted and nonexhaustive. Source data, "
                  "identifiers and preprocessing are distinguished from the subsequent calibration analysis.")),
        page("Appendix B. Predictor dictionary and dimensional checks",
             table(feature_table_release(audit), "Table S2. Predictors, units and missingness in the included cohort."),
             para("Time is not a free model predictor because the targets are a fixed three-component "
                  "vector. Formulation index and DOI are identifiers used only for joins, splitting "
                  "and auditing. Release fraction is distinct from release percentage: an MAE of "
                  "0.17 is approximately 17 percentage points, not 0.17 percentage points."),
             para("Polymer molecular weight is retained as supplied. Mixing Mw, Mn and an unspecified "
                  "molecular-weight field limits mechanistic interpretation even though all are in "
                  "kDa. Ratios and loading-related variables may be algebraically or experimentally "
                  "related; feature removal therefore cannot establish a causal material contribution."),
             para("All transformations are fitted on training data only. The present included dataset "
                  "has no missing values among these ten processed features; the imputation step "
                  "supports the declared pipeline but does not introduce information from held-out labels. "
                  "No extrapolating conversion between days and hours occurs in target construction.")),
        page("Appendix C. Endpoint construction and exclusions",
             table(pd.DataFrame(Counter(x["reason"] for x in audit["excluded"]).items(),
                                columns=["Exclusion reason", "Count"]), "Table S3. Mutually exclusive first-failure reasons."),
             table(frame[["day1", "day3", "day7"]].describe().reset_index(),
                   "Table S4. Included endpoint distributions, in release fractions."),
             para("The original observations, not the model, determine whether a curve brackets "
                  "the requested window. Requiring all endpoints makes the prediction problem a "
                  "complete-vector task and avoids evaluating models on different endpoint populations. "
                  "The cost is selection toward curves followed through day 7. A curve ending earlier "
                  "is not a failed treatment and is not assigned a synthetic endpoint."),
             para(f"{audit['raw_nonmonotone_curves']} original curves contain at least one decreasing "
                  "segment. Such segments may reflect digitization, assay noise, normalization or "
                  "other source issues. They are counted rather than automatically corrected. "
                  "The model projection constrains predictions only; it cannot certify that observed "
                  "cumulative release is measured without error."),
             para("The audit stores every excluded formulation ID and reason. Unit tests independently "
                  "recompute interpolation for an included formulation, verify target bounds and check "
                  "that the code's time grid is exactly [1,3,7] source days.")),
        page("Appendix D. Partition manifest",
             table(splits[splits["split"] == "publication"].groupby(["seed", "role"]).agg(
                 formulations=("id", "size"), publications=("study", "nunique")).reset_index(),
                   "Table S5. Executed publication partitions, not nominal row fractions."),
             para("GroupShuffleSplit first reserves test publications and then splits the remainder "
                  "into training and calibration publications. The calibration split uses seed+1. "
                  "The exact lists are saved in splits.csv; re-deriving a partition with a different "
                  "library version or different cohort ordering should not replace this manifest silently."),
             para("No DOI appears in more than one role within a primary seed. Different repeated "
                  "seeds reuse publications, as expected. Thus the five estimates are sensitivity "
                  "summaries, not five independent experiments. Neither their SD nor their standard "
                  "error is an independently calibrated uncertainty interval for generalization."),
             para("The formulation-random diagnostic uses the same cohort but intentionally breaks "
                  "publication isolation. It estimates performance when source-publication context "
                  "can recur, not performance on an unseen research group.")),
        page("Appendix E. Complete benchmark summary",
             table(summary_table(metrics), "Table S6. Mean scores for all executed model and split conditions."),
             table(per_seed[per_seed["model"] == "trees"][["seed", "n_test", "test_publications", "mae", "study_macro_mae", "r2"]],
                   "Table S7. Primary tree results by seed."),
             para("MAE averages absolute errors over formulations and endpoints. Study-macro MAE "
                  "first averages within each publication and then weights publications equally. "
                  "R2 follows scikit-learn's uniform multi-output convention. Negative R2 means "
                  "worse squared-error performance than the test-target mean comparator."),
             para("Results are not selected by lowest seed error. All five seeds are reported. "
                  "The comparison does not account for source experimental standard errors, which "
                  "are not harmonized in this processed resource. Predictive utility should not be "
                  "inferred solely from improvement over the median baseline.")),
        page("Appendix F. Calibration results by partition",
             table(intervals[intervals["split"] == "publication"][
                 ["seed", "method", "calibration_units", "q", "publication_coverage", "mean_width"]],
                   "Table S8. Finite-sample calibration counts, radii, publication coverage and widths."),
             para("A pooled-point method calibrates against correlated entries of a vector and "
                  "potentially multiple vectors from the same publication. Its score count must not "
                  "be interpreted as the number of independent laboratories. Publication-max "
                  "calibration uses one maximum per retained DOI group."),
             para("At nominal 90% coverage, the rank includes the n+1 finite-sample correction. "
                  "It is not the ordinary 90th empirical percentile with unspecified interpolation. "
                  "Physical clipping narrows interval widths without excluding an in-range target "
                  "that the original symmetric interval would cover."),
             para("Calibration and test publication sizes vary. A new publication containing a "
                  "different number of formulations can change the distribution of a maximum score. "
                  "This limitation is not fixed by pooling more time points.")),
        page("Appendix G. Endpoint diagnostics and saved predictions",
             table(predictions[(predictions["split"] == "publication") &
                               (predictions["method"] == "publication_max")].assign(
                 absolute_error=lambda x: (x["observed"]-x["predicted"]).abs(),
                 covered=lambda x: ((x["observed"] >= x["lower"]) &
                                    (x["observed"] <= x["upper"]))).groupby("day").agg(
                     test_records=("id", "size"), mean_absolute_error=("absolute_error", "mean"),
                     point_coverage=("covered", "mean")).reset_index(),
                   "Table S9. Endpoint-level descriptive diagnostics, pooling overlapping holdouts."),
             table(predictions[(predictions["split"] == "publication") &
                               (predictions["method"] == "publication_max") &
                               (predictions["seed"] == 11)].head(12)[
                 ["id", "day", "observed", "predicted", "lower", "upper"]],
                   "Table S10. First four test formulations under seed 11; not selected for good predictions."),
             para("The complete long-form prediction file links each endpoint to seed, split, "
                  "calibration method, formulation ID and source DOI. This supports independent "
                  "recalculation of coverage. The illustrative rows above follow input order and "
                  "are not evidence of general prediction quality."),
             para("Pooling endpoint records here is a visualization-level summary. The same source "
                  "formulation can appear in more than one held-out seed, so these row counts "
                  "cannot be used as independent biological replication counts.")),
        page("Appendix H. Controls and interpretability boundaries",
             table(per_seed.groupby("model")[["mae", "r2"]].agg(["mean", "std"]).reset_index(),
                   "Table S11. Across-partition mean and SD for all primary-split controls."),
             para("The no-drug ablation removes molecular weight, TPSA, LogP, loading capacity "
                  "and encapsulation efficiency because their source names begin 'Drug '. It "
                  "retains input drug-to-polymer ratio. This is a declared feature-block ablation, "
                  "not a pure molecular-descriptor causal intervention. The polymer-only block "
                  "contains polymer MW, LA/GA and particle diameter."),
             para("The no-projection condition omits both clipping and isotonic projection. "
                  "Extra trees average training endpoint vectors; when those averages are already "
                  "bounded and ordered, this ablation may be numerically identical. Identical "
                  "results are reported, not discarded or described as a successful new constraint."),
             para("The permuted-target condition shuffles complete endpoint vectors within the "
                  "training set for each seed. It preserves within-vector structure but destroys "
                  "the formulation-target correspondence. It is a single negative-control draw "
                  "per partition, not a distribution of permutation-test p-values."),
             para("No feature importance is promoted to a polymer mechanism. Correlated composition "
                  "variables and publication-specific reporting practices make such interpretations "
                  "particularly vulnerable to confounding.")),
        page("Appendix I. Conditional coverage argument and its limits",
             para("<b>Established rank argument.</b> Conditional on a fixed training set and fitted "
                  "predictor, suppose the n calibration publication blocks and one future publication "
                  "block are exchangeable under the same block-level data-generating process. "
                  "Apply the same deterministic scoring rule to each block: the maximum absolute "
                  "error over every included formulation endpoint. The rank of the future block's "
                  "score among the n+1 scores is uniform or conservative in the presence of ties."),
             para("Choosing the ceil((n+1)(1-alpha))-th calibration score gives block-level "
                  "coverage at least 1-alpha when that finite rank exists. If the future maximum "
                  "does not exceed q, all its included endpoints fall in the symmetric intervals. "
                  "Intersecting with the known [0,1] support does not remove any valid in-support "
                  "covered target. This is an application of split conformal rank reasoning, "
                  "not a new result."),
             para("<b>Why the theorem is not a clinical guarantee.</b> Literature inclusion depends "
                  "on publication, reporting completeness and release follow-up. Formulation counts "
                  "per paper differ. Researchers may change assays, drugs, process protocols or "
                  "the number of reported formulations. DOI blocks are not independent laboratory "
                  "samples by design. These departures can violate the exchangeability premise."),
             para("Pointwise and formulation-wise scores target different events. Their nominal "
                  "calibration levels do not imply simultaneous coverage of all outcomes in a "
                  "new publication. Conversely, high block coverage with nearly full-range "
                  "intervals is statistically conservative but may be scientifically uninformative."),
             para("Hierarchical prediction literature offers alternative constructions and "
                  "estimands. Further evaluation could benchmark those methods on a "
                  "prespecified deployment population and useful-width criterion. Those comparisons "
                  "are not claimed to have been performed here.")),
        page("Appendix J. Reproduction and resource record",
             para("From the workspace root on Windows: create an isolated Python 3.12 environment; "
                  "install requirements.txt; run fetch_sources.py; run 01_release_transfer\\run.py; "
                  "run 02_polymer_targeting\\run.py; run python -m unittest test_research.py; "
                  "then run build_manuscripts.py. Use the environment's Python executable explicitly. "
                  "No API key, paid service or GPU is required."),
             table(pd.DataFrame(resource.items(), columns=["Instrumented property", "Value"]),
                   "Table S12. Analysis-only resource measurements."),
             *[para(f"<b>{name}</b><br/>SHA-256: {digest}") for name, digest in audit["input_sha256"].items()],
             para("Environment pins are recorded in requirements.txt; the installed full package "
                  "snapshot is retained in environment-lock.txt. Sampling measures the analysis "
                  "process RSS every 0.1 seconds and may miss very short peaks. No subprocess "
                  "workers are used by these estimators."),
             para("Reproduction should verify both numerical files and artifact shape: disjoint "
                  "publication roles, correct day grid, finite-sample quantile rank, valid interval "
                  "bounds, readable figures and the official ACL layout. A manuscript rebuilt from "
                  "different data hashes must be treated as a different analysis version.")),
        page("Appendix K. External validation design",
             table(pd.DataFrame([
                 ["Holdout unit", "Entire laboratory or temporally later publication"],
                 ["Primary outcome", "Simultaneous coverage of all eligible endpoints"],
                 ["Utility outcome", "Interval width relative to an assay-specific tolerance"],
                 ["Covariates", "Polymer end groups, porosity, mixing and solvent removal"],
                 ["Uncertainty", "Calibration and test units kept disjoint"],
             ], columns=["Design element", "Proposed evaluation"]), "Table S13. Design for an independent validation study."),
             para("A prospective evaluation should define the laboratory deployment population and "
                  "practical release-profile tolerance before collecting new data. Hold out entire "
                  "laboratories or temporally later publications, record unreported process covariates, "
                  "and evaluate both calibration and decision-relevant interval width. Such a "
                  "study could test whether better reporting resolves the uncertainty observed here."),
             para("The proposed evaluation would distinguish improved calibration from improved "
                  "formulation discrimination. It has not been performed in the present study.")),
    ]
    return folder, title, pages


def polymer_pages():
    folder = "02_polymer_targeting"
    out = ROOT / folder / "results"
    audit = load(folder, "data_audit.json")
    resource = load(folder, "resources.json")
    effects = load(folder, "effects.json")
    frame = pd.read_csv(out / "analysis_dataset.csv")
    all_frame = pd.read_csv(out / "all_material_endpoints.csv")
    metrics = pd.read_csv(out / "metrics.csv")
    sensitivity = pd.read_csv(out / "sensitivity.csv")
    splits = pd.read_csv(out / "splits.csv")
    prediction = pd.read_csv(out / "predictions.csv")
    rank = effects["rank_summary"]
    matched = effects["primary_24h"]["within_publication"]
    pooled = effects["primary_24h"]["pooled_cluster_bootstrap"]
    corr = effects["spearman_bootstrap"]
    median_ci = effects["median_log_ratio_bootstrap"]
    stats = metrics.groupby(["split", "model"]).mean(numeric_only=True)
    tree = stats.loc[("publication", "trees")]
    ridge = stats.loc[("publication", "ridge")]
    median = stats.loc[("publication", "median")]
    contrast_table = pd.DataFrame([
        ["Pooled formulation contrast", pooled["estimate"], pooled["lower"], pooled["upper"],
         effects["primary_24h"]["pooled_cluster_bootstrap"]["clusters"]],
        ["Equal-weight publication contrast", matched["estimate_log10"], matched["lower"], matched["upper"],
         effects["primary_24h"]["overlap_publications"]],
    ], columns=["Association estimand", "log10 contrast", "95% lower", "95% upper", "Groups"])
    distribution = frame.groupby("strategy").agg(
        formulations=("id", "size"), publications=("study", "nunique"),
        median_tumor_percent_id=("tumor", "median"), median_liver_percent_id=("liver", "median"),
        median_log10_ratio=("log_ratio", "median")).reset_index()
    title = "Tumour accumulation is not tumour-to-liver selectivity: a publication-aware polymer nanoparticle reanalysis"
    pages = [
        page(title,
             para("<b>Abstract.</b> Selecting a polymer nanoparticle solely for tumour accumulation "
                  "can ignore competing liver uptake. We quantify the relationship between these "
                  "ranking objectives using paired whole-organ biodistribution measurements from "
                  "the publicly archived Nano-Tumor Database. The primary cohort contains "
                  f"{len(frame)} source-labelled Polymeric formulations in "
                  f"{frame['study'].nunique()} connected publication-reference groups, evaluated at "
                  "24 hours without temporal extrapolation. Analyses include publication-cluster "
                  "bootstrap intervals, within-publication active/passive contrasts, fixed baseline "
                  "prediction models and prespecified time/material sensitivity analyses."),
             para(f"Median tumour and liver accumulation were {rank['median_tumor_percent_id']:.3f}%ID "
                  f"and {rank['median_liver_percent_id']:.3f}%ID. Tumour accumulation and the "
                  f"tumour/liver ratio had Spearman correlation {corr['estimate']:.3f} "
                  f"(publication-bootstrap 95% interval {corr['lower']:.3f} to {corr['upper']:.3f}); "
                  f"only {rank['top_quartile_overlap_fraction']:.1%} of the top-quartile formulations "
                  "overlapped between objectives. The equal-weight within-publication active/passive "
                  f"log10-ratio contrast was {matched['estimate_log10']:.3f} "
                  f"({matched['lower']:.3f} to {matched['upper']:.3f}) across "
                  f"{effects['primary_24h']['overlap_publications']} overlapping publication groups."),
             para("Tumour uptake and organ selectivity are not interchangeable "
                  "screening objectives. The targeting contrast is observational and confounded; "
                  "the ratio is not a validated safety, efficacy or blood-brain-barrier endpoint. "
                  "The analysis distinguishes screening objectives while retaining the limitations "
                  "of heterogeneous observational biodistribution data."),
             para("<b>Keywords:</b> polymer nanoparticles; tumour biodistribution; liver uptake; active targeting; publication clustering.")),
        page("1. Introduction",
             para("Nanoparticle delivery is a multiorgan distribution problem. Tumour accumulation "
                  "may coexist with substantial clearance-organ uptake, and a material selected "
                  "for one endpoint need not be preferred under another. Broad nanoparticle design "
                  "and transport literature emphasizes biological barriers and model dependence "
                  "[Mitchell et al., 2021; Wilhelm et al., 2016; Sindhwani et al., 2020]."),
             para("Chen et al. (2023) assembled an expanded Nano-Tumor Database and already analyzed "
                  "tumour and major-organ distribution with multiple pharmacokinetic metrics and "
                  "statistical models. The dataset, experimental curation and general organ-competition "
                  "question were established in that work. Polymeric-micelle targeting has also been the "
                  "subject of a 2026 mouse-model meta-analysis by Sousa-Oliveira and colleagues. "
                  "These resources enable a polymer-specific comparison of paired accumulation objectives."),
             para("Polymer architecture, hydrodynamic size, surface properties and the biomolecular "
                  "corona can all affect biodistribution. Cabral et al. (2011) studied size-dependent "
                  "polymeric micelle accumulation, while Salvati et al. (2013) demonstrated a context "
                  "in which a protein corona impaired targeting capability. These findings motivate "
                  "caution, not a universal material rule or a general claim that ligands do not work."),
             para("We conduct an explicitly paired, same-unit, "
                  "24-hour polymer-specific ranking audit combined with connected-reference "
                  "grouping and a separation of pooled and within-publication targeting associations. "
                  "It asks: how concordant are tumour uptake and tumour/liver selectivity rankings; "
                  "how does the active/passive association depend on the comparison unit; and "
                  "can low-compute predictors transfer across source publications?"),
             para("The scope is cancer biodistribution in mice, not brain targeting. No blood-brain "
                  "barrier transport measurement or brain-tumour-specific efficacy dataset is "
                  "validated here. The underlying data cannot support a claim that a new polymer "
                  "crosses the barrier, treats cancer or is safe for humans.")),
        page("2. Public data, pairing and polymer cohort",
             para("The primary source is the ACS Figshare supporting workbook "
                  "nn3c04037_si_002.xlsx, DOI 10.1021/acsnano.3c04037.s002, associated with "
                  "Chen et al. (2023). Repository metadata specify CC BY-NC 4.0. This is a "
                  "noncommercial secondary research analysis; commercial reuse needs separate "
                  "license review. File size and source MD5 are checked during fetching and "
                  "the analysis additionally records a SHA-256 digest."),
             table(pd.DataFrame([
                 ["Source formulation groups with measurement rows", audit["raw_formulations"]],
                 ["Source measurement rows retained", audit["long_rows"]],
                 ["All-material paired endpoints at 24 h", audit["all_material_24h_pairs"]],
                 ["Primary Polymeric endpoints", audit["polymeric_24h_pairs"]],
                 ["Primary publication-reference groups", audit["polymeric_publications"]],
                 ["Primary endpoints measured exactly at 24 h", audit["polymeric_exact_24h"]],
             ], columns=["Cohort quantity", "Count"]), "Table 1. Executed cohort flow."),
             para("The sheet has a two-row header identifying Biodistribution (%ID) and named "
                  "organs. Only tumour and liver values from the same formulation and same "
                  "source time enter the paired curve. Duplicate same-time pairs are averaged. "
                  "The endpoint is interpolated only within that paired curve's observed range. "
                  "No organ is imputed from an unrelated formulation. Positive values no greater "
                  "than 100%ID are required; zeros are excluded without a pseudocount."),
             para("The primary material rule is exact source category 'Polymeric', not a "
                  "text search selected for good outcomes. Hydrogel and Dendrimer categories "
                  "enter a declared broader sensitivity cohort; other organic and hybrid materials "
                  "are retained in source audits but are not silently relabelled as polymeric. "
                  "Publication references such as 67/200 link both source references: their "
                  "connected component is used for all resampling and prediction splits.")),
        page("3. Endpoints, estimands and statistical design",
             para("Let T and L be paired 24-hour whole-organ tumour and liver accumulation in "
                  "percent injected dose. Define R=T/L and Z=log10(R). Both numerator and "
                  "denominator use the same source unit; no %ID/g tissue concentration is "
                  "substituted. A higher ratio can reflect more tumour uptake, less liver uptake "
                  "or both. It is not necessarily better therapy, and low absolute delivery can "
                  "coexist with a high ratio."),
             para("The primary ranking audit reports Spearman correlation between T and R, "
                  "and overlap between their top ceil(n/4) formulation sets. Ties follow the "
                  "stable source-row ordering in pandas nlargest. Publication-cluster bootstrap "
                  "(2,000 replicates, seed 603) summarizes uncertainty in Spearman correlation. "
                  "The top-quartile overlap is descriptive and has no claimed confidence interval."),
             para("Two active/passive estimands are distinguished. The pooled formulation-weighted "
                  "contrast is mean(Z|Active)-mean(Z|Passive), with 2,000 publication-block "
                  "bootstrap replicates. The within-publication estimand first computes that "
                  "difference in each publication group containing both categories, then "
                  "averages publication differences equally. A 5,000-replicate bootstrap "
                  "resamples those differences. These are associations, not randomized "
                  "or composition-matched ligand effects."),
             para("Fixed prediction baselines use hydrodynamic diameter, zeta potential, "
                  "shape, source material category, targeting category and source tumour-cell "
                  "description. Only an explicitly labelled HD value is treated as hydrodynamic "
                  "size; TEM-only measurements remain missing. Training-only imputation, scaling "
                  "and one-hot encoding precede ridge (alpha=10) or 128 extra trees "
                  "(minimum leaf=3, one worker). Unseen categories are ignored by the encoder."),
             para("Five seeds partition publication groups into approximately 60% training, "
                  "20% reserved/unused and 20% test, matching the research scaffold without "
                  "using the reserved outcomes for tuning. MAE in Z, study-macro MAE and "
                  "R2 are reported. Time sensitivities at 6 and 48 hours and an expanded "
                  "material cohort are prespecified descriptive analyses, not independent "
                  "replication. No multiple-testing-adjusted discovery claim is made.")),
        page("4. Tumour uptake and selectivity rank different formulations",
             para(f"Figure 1 shows the paired organ measurements. "
                  f"The median tumour/liver ratio was {rank['median_tumor_liver_ratio']:.4f}. "
                  "The median of ratios is not generally equal to the ratio of separate tumour "
                  "and liver medians, because pairing matters. The 95% publication-bootstrap "
                  "interval for the median log10 ratio was "
                  f"{median_ci['lower']:.3f} to {median_ci['upper']:.3f}; "
                  "this interval targets the literature-selected cohort summary, not a "
                  "patient-level therapeutic index."),
             image("paired_organs.png", "Figure 1. Paired 24-hour tumour and liver %ID for the primary polymer cohort. The diagonal is equal whole-organ accumulation, not a toxicity threshold.", 250),
             para(f"Rank correlation was {corr['estimate']:.3f}, rather than perfect concordance. "
                  f"The two top-{rank['top_quartile_count']} lists shared "
                  f"{round(rank['top_quartile_count']*rank['top_quartile_overlap_fraction'])} formulations. "
                  "Thus a large part of a top-quartile shortlist changes when the objective "
                  "switches from accumulation to organ selectivity. This does not identify "
                  "which formulation should be used clinically."),
             para("T appears in both ranking variables, so positive correlation is partly "
                  "mathematical and is not evidence that tumour uptake causes favourable "
                  "selectivity. Liver uptake, time, assay design, tumour model and formulation "
                  "composition contribute further variation. Whole-organ ratios are useful "
                  "as a transparent screening objective only when accompanied by absolute "
                  "exposure and an explicit account of what they omit.")),
        page("5. Targeting associations depend on the comparison unit",
             table(distribution, "Table 2. Primary cohort summaries by source targeting category."),
             table(contrast_table, "Table 3. Active-minus-passive log10 selectivity associations. Percentile intervals are publication-aware, not causal."),
             para(f"The pooled contrast was {pooled['estimate']:.3f} log10 units with a "
                  f"bootstrap interval spanning {pooled['lower']:.3f} to {pooled['upper']:.3f}. "
                  "That interval includes zero. The within-publication summary was "
                  f"{matched['estimate_log10']:.3f} "
                  f"({matched['lower']:.3f} to {matched['upper']:.3f}), "
                  "but uses only publications reporting both categories and a different "
                  "weighting scheme. These estimands answer different questions."),
             para(f"Exponentiating the within-publication contrast gives a descriptive "
                  f"{10**matched['estimate_log10']:.2f}-fold ratio of geometric selectivity "
                  f"({10**matched['lower']:.2f} to {10**matched['upper']:.2f}). It must not be "
                  "reported as a causal improvement, an efficacy fold-change, or a recommendation "
                  "to add a particular ligand. Active and passive formulations can differ "
                  "in chemistry, size, dose, surface treatment and assay conditions."),
             para("Restricting to publications containing both categories reduces some "
                  "between-publication heterogeneity but does not ensure matched polymer "
                  "architecture or randomized animal allocation. Publication selection, "
                  "outcome-dependent reporting and the small number of overlapping groups "
                  "remain important. No study-level animal counts or standard errors are "
                  "sufficiently harmonized here for an animal-level meta-analysis."),
             para("The exact-24-hour restriction reproduces the primary cohort because every "
                  "retained primary polymer endpoint is observed at 24 hours. Accordingly, "
                  "that check verifies endpoint timing but is not an independent robustness "
                  "dataset and must not be counted as a replication.")),
        page("6. Prediction, ablations and sensitivity",
             para(f"Figure 2 compares the prediction baselines and controls. "
                  f"Primary extra-trees MAE was {tree['mae']:.3f} log10 units, "
                  f"versus {median['mae']:.3f} for the training-median reference and "
                  f"{ridge['mae']:.3f} for ridge. Tree mean R2 was {tree['r2']:.3f}. "
                  "These results do not demonstrate a reliable prospective selectivity "
                  "predictor. The complete ablation table retains no-targeting, physicochemical-only "
                  "and target-permuted conditions rather than selecting the most favourable result."),
             image("ablation.png", "Figure 2. Publication-separated prediction of log10 tumour/liver ratio. Error bars denote SD across overlapping partitions.", 215),
             table(sensitivity[["hours", "cohort", "n", "publications", "spearman_tumor_vs_selectivity",
                                "top_quartile_overlap_fraction"]],
                   "Table 4. Time and material sensitivities. Changing time also changes the eligible cohort."),
             para("The formulation-random diagnostic allows the same source publication "
                  "to recur across training and test. It is reported but is not a prospective "
                  "validation scheme. Removing targeting from predictors tests a feature block, "
                  "not whether targeting has a causal biological effect. Weak or improved "
                  "ablation performance cannot resolve that question."),
             para("The 6- and 48-hour comparisons conflate temporal evolution with "
                  "changing observation availability. The broader cohort adds hydrogels "
                  "and dendrimers, not arbitrary polymer-coated inorganic hybrids. "
                  "No time-dependent causal or universal material conclusion is inferred.")),
        page("7. Discussion and data availability",
             para("The data support separating tumour accumulation from tumour/liver selectivity "
                  "when reporting polymer nanoparticle screens. They also show that a pooled "
                  "targeting contrast and a within-publication contrast need not have the same "
                  "interpretation. These are modest methodological observations built on an "
                  "existing database, not evidence for a new polymer mechanism or treatment."),
             para("The resource covers published mouse experiments with heterogeneous tumour "
                  "models, doses, sampling times and assays. A connected reference group is "
                  "not a verified independent laboratory. %ID is whole-organ accumulation and "
                  "does not measure free drug, cellular internalization, tumour subregions, "
                  "organ toxicity or pharmacodynamic benefit. Liver is only one competing organ. "
                  "Excluding zero or missing paired measurements may create selection bias."),
             para("Independent evaluation should use composition-matched active/passive comparisons with "
                  "drug exposure, tumour response and toxicity endpoints. Brain targeting "
                  "would require separate evidence of barrier transport and relevant tissue "
                  "distribution. None of those experiments has been performed here."),
             para(f"<b>Availability and compute.</b> Attributed source metadata, hashes, analysis "
                  "cohorts, reference-group manifests, predictions, ablations and bootstrap "
                  f"summaries accompany the code. Instrumented analysis took "
                  f"{resource['elapsed_seconds']:.1f} seconds with sampled process RSS "
                  f"{resource['sampled_peak_rss_mb']:.1f} MB and one worker. Timing excludes "
                  "setup, downloads, pre-context imports and manuscript generation. Dataset "
                  "noncommercial restrictions remain in force."),
             para("This secondary public-data analysis generated no new animal or human observations.")),
        page("References",
             *reference_blocks([
                 "10.1021/acsnano.3c04037", "10.1038/s41573-020-0090-8",
                 "10.1038/natrevmats.2016.14", "10.1038/s41563-019-0566-2",
                 "10.1038/nnano.2011.166", "10.1038/nnano.2012.237",
                 "10.1016/j.jconrel.2026.115103", "10.1007/s10994-006-6226-1",
                 "10.1016/j.patter.2023.100804", "10.1111/ecog.02881",
             ], "Chen Q, Yuan L, Chou WC, Cheng YH, He C, Monteiro-Riviere NA, Riviere JE, Lin Z. "
                "Supporting data for Meta-Analysis of Nanoparticle Distribution in Tumors and Major "
                "Organs in Tumor-Bearing Mice. ACS Figshare (2023). "
                "https://doi.org/10.1021/acsnano.3c04037.s002. CC BY-NC 4.0.")),
        page("Appendix A. Source provenance and reuse",
             para("Source workbook: https://ndownloader.figshare.com/files/42609052. "
                  "Metadata: https://api.figshare.com/v2/articles/24274513. The repository "
                  "lists a 5,216,094-byte XLSX and its expected MD5; downloading verifies "
                  "both before analysis. The SHA-256 digest below fixes the executed input."),
             *[para(f"<b>{name}</b><br/>SHA-256: {digest}") for name, digest in audit["input_sha256"].items()],
             para("The workbook is licensed CC BY-NC 4.0 at the source. It is not relabelled "
                  "as unrestricted data. Source attribution and the license link must "
                  "accompany redistribution. Commercial use or a publisher's incompatible "
                  "reuse requirements should be resolved with the rightsholder."),
             para("Original source studies may have different designs and their observations "
                  "are not independently revalidated here. A public spreadsheet and a "
                  "successful checksum do not establish measurement validity, causal "
                  "identification or therapeutic translation.")),
        page("Appendix B. Data dictionary and unit contract",
             table(pd.DataFrame([
                 ["id", "Source dataset number", "Formulation/time-course identifier"],
                 ["study", "Connected reference label", "Grouping only; not a predictor"],
                 ["tumor / liver", "% injected dose", "Paired whole-organ accumulation"],
                 ["hours", "h", "Source time; primary endpoint=24"],
                 ["log_ratio", "log10(T/L)", "Prediction target and contrast scale"],
                 ["size_nm", "nm", "Explicit source HD only; TEM-only missing"],
                 ["zeta_mv", "mV", "Strict numeric source zeta potential"],
                 ["strategy", "Active / Passive", "Source label, not a causal assignment"],
                 ["shape / core", "Source category", "One-hot encoded in training"],
                 ["tumor_cell", "Source text category", "Heterogeneous model description"],
                 ["exact_time", "Boolean", "Paired 24-h source observation present"],
             ], columns=["Variable", "Unit / representation", "Interpretation"]), "Table S2. Analysis variables and units."),
             para("A same-unit ratio is essential. The original paper discusses both %ID "
                  "and %ID/g metrics, but this workbook's paired sheet explicitly labels "
                  "the selected biodistribution block %ID. No concentration-unit value "
                  "is substituted from a separate model table. A whole-organ ratio "
                  "cannot be interpreted as a tissue-normalized concentration ratio."),
             para("The parser checks organ headers before using fixed columns. It accepts "
                  "numeric source references or explicit slash-linked numeric references "
                  "and rejects unresolved labels. Missing or ambiguous source fields "
                  "must be reported, not repaired by guessing a number.")),
        page("Appendix C. Cohort construction and exclusion audit",
             table(pd.DataFrame(Counter(x["reason"] for x in audit["excluded"]).items(),
                                columns=["First-failure reason at 24 h", "Formulations"]),
                   "Table S3. Exclusions before the primary material filter."),
             table(pd.DataFrame(audit["missing_numeric"].items(), columns=["Predictor", "Missing in primary cohort"]),
                   "Table S4. Missing numerical predictors."),
             para("The source long table uses blank repeated metadata cells within a "
                  "formulation time course. Dataset number is forward filled, and each "
                  "metadata column takes its first available value within that dataset "
                  "group. Metadata are not filled across distinct formulation groups. "
                  "Only rows with a recognized material type and a numeric measurement "
                  "time enter the observation audit."),
             para("The endpoint builder retains only times containing both tumour and "
                  "liver observations. This ensures interpolation uses paired source "
                  "support rather than independently interpolating across incompatible "
                  "organ observation windows. At 24 hours all retained primary polymer "
                  "formulations have an exact paired observation."),
             para("Nonpositive and above-100 %ID endpoints are excluded with explicit "
                  "reasons. No arbitrary epsilon is added to manufacture a finite "
                  "logarithm. The exclusions file identifies source dataset numbers. "
                  "The resulting selection can bias population summaries if low "
                  "accumulation is preferentially missing or reported as zero.")),
        page("Appendix D. Material categories and primary endpoint distribution",
             table(all_frame["core"].value_counts().head(14).rename_axis("Core category").reset_index(name="24-h pairs"),
                   "Table S5. Most frequent all-material endpoint categories; remaining source labels stay in the machine-readable audit."),
             table(frame[["tumor", "liver", "log_ratio"]].describe().reset_index(),
                   "Table S6. Primary polymer endpoint distributions."),
             para("The primary core category is Polymeric exactly as supplied by the "
                  "source. This avoids reclassifying polymer-coated inorganic or "
                  "multi-component particles based on a favourable outcome. Hydrogels "
                  "and dendrimers form a separate broader category in the sensitivity "
                  "analysis; source-labelled hybrids remain outside that rule."),
             para("Material labels are coarse. The analysis does not contain a uniform "
                  "polymer repeat-unit, molecular-weight distribution, block architecture "
                  "or ligand-density representation. Therefore neither the core "
                  "category nor these distribution summaries can define a new "
                  "polymer synthesis target or explain a release/transport mechanism.")),
        page("Appendix E. Rank objective and uncertainty",
             table(pd.DataFrame([
                 ["Spearman tumour vs selectivity", corr["estimate"], corr["lower"], corr["upper"]],
                 ["Median log10 selectivity", median_ci["estimate"], median_ci["lower"], median_ci["upper"]],
                 ["Top-quartile overlap fraction", rank["top_quartile_overlap_fraction"], "Not estimated", "Not estimated"],
             ], columns=["Statistic", "Estimate", "95% lower", "95% upper"]),
                   "Table S7. Primary objective audit. Intervals use publication-cluster resampling."),
             table(frame.nlargest(10, "tumor")[["id", "study", "strategy", "tumor", "liver", "log_ratio"]],
                   "Table S8. Highest tumour-uptake rows, disclosed as an objective illustration, not recommended materials."),
             para("Cluster resampling draws source-publication blocks with replacement "
                  "and carries all their included formulation records. A study with many "
                  "formulations contributes many rows to formulation-level statistics, "
                  "while the resampling unit remains a publication. The median-log-ratio "
                  "interval and median-ratio point estimate are intentionally labelled "
                  "separately; monotone transformation can be used if a ratio-scale "
                  "interval is needed."),
             para("The top-quartile overlap uses source formulation IDs and a fixed "
                  "ceil(n/4) list size. It is a transparent descriptive comparison, "
                  "not an out-of-sample model-selection performance estimate. "
                  "Tie sensitivity and alternative shortlist thresholds have not "
                  "been exhaustively characterized.")),
        page("Appendix F. Targeting estimands and publication contrasts",
             table(contrast_table, "Table S9. Repeated here to preserve the statistical estimands beside the study-level evidence."),
             table(pd.DataFrame({
                 "Contrast index (sorted source group)": np.arange(1, len(matched["study_contrasts"])+1),
                 "Active-minus-passive mean log10 ratio": matched["study_contrasts"],
             }), "Table S10. All overlapping-publication contrasts; no favourable-study selection."),
             para("The pooled contrast estimates a formulation-weighted association "
                  "across the selected literature cohort. The within-publication "
                  "contrast instead conditions on publications reporting both source "
                  "targeting labels and gives each such publication equal weight. "
                  "Their difference is not itself a formal test of confounding."),
             para("Even the within-publication contrast need not compare otherwise "
                  "identical particles. Ligand addition may coincide with altered "
                  "polymer chemistry, hydrodynamic diameter, charge, cargo, "
                  "dose or tumour model. This audit does not harmonize animal "
                  "randomization, blinding or study-level variances.")),
        page("Appendix G. Connected-reference grouping and split manifest",
             table(splits[splits["split"] == "publication"].groupby(["seed", "role"]).agg(
                 formulations=("id", "size"), groups=("study", "nunique")).reset_index(),
                   "Table S11. All executed primary partition roles."),
             para("The source reference 67/200 is not converted to missing and its "
                  "formulations are not discarded. Instead reference IDs are graph "
                  "nodes, a slash-linked record joins its nodes, and connected "
                  "components define group labels. Thus records labelled 67, 200 "
                  "and 67/200 receive the same group even when they occur far "
                  "apart in the workbook."),
             para("The full mapping is visible in the analysis cohort and split "
                  "manifest. Unit tests cover direct and transitive links, "
                  "unknown-reference failure and absence of group overlap "
                  "between roles. This addresses an identifier-integrity issue "
                  "without asserting that all publications from one laboratory "
                  "have been identified."),
             para("The reserved group is unused by this point-prediction study. "
                  "It is not quietly added to training after looking at test "
                  "scores. Changing that design in future work should produce "
                  "a new recorded protocol version and new validation artifacts.")),
        page("Appendix H. Full predictive benchmark",
             table(summary_table(metrics), "Table S12. Mean metrics across all executed prediction conditions."),
             table(metrics[(metrics["split"] == "publication") & (metrics["model"] == "trees")][
                 ["seed", "n_test", "mae", "study_macro_mae", "r2"]],
                   "Table S13. Primary tree scores by seed."),
             para("MAE is measured in log10 ratio units. For perspective, a one-log10-unit "
                  "absolute discrepancy represents a factor of ten in the ratio, but "
                  "10^MAE is not the arithmetic mean multiplicative error. R2 can "
                  "be negative because the test mean is a stronger squared-error "
                  "reference than this predictor."),
             para("The five repeated partitions overlap. Their dispersion is "
                  "sensitivity to this splitting procedure, not an independent "
                  "replication confidence interval. There is no test-set "
                  "hyperparameter search, high-dimensional molecular embedding, "
                  "GPU training or claim that these baselines are optimal.")),
        page("Appendix I. Time/material sensitivities and negative controls",
             table(sensitivity[["hours", "cohort", "n", "publications", "median_tumor_liver_ratio",
                                "spearman_tumor_vs_selectivity", "top_quartile_overlap_fraction"]],
                   "Table S14. All prespecified descriptive sensitivities."),
             para("At each time, the paired curve must bracket that time and the "
                  "endpoint must satisfy the same positivity and %ID range "
                  "rules. Therefore the 6-, 24- and 48-hour cohorts differ. "
                  "This is not a longitudinal analysis of an invariant "
                  "formulation cohort and cannot separate kinetic changes "
                  "from observation-selection differences."),
             para("The no-targeting model removes only the source Active/Passive "
                  "feature. The physicochemical-only model uses hydrodynamic "
                  "diameter, zeta potential and shape. A permuted-target "
                  "control shuffles the training log-ratio target once per "
                  "seed. These controls assess prediction dependence, "
                  "not randomized biological targeting mechanisms."),
             para("The exact-time check is identical to the primary cohort "
                  "and is retained as a transparent audit result. It "
                  "does not multiply the effective sample size or "
                  "justify presenting a separate replication success.")),
        page("Appendix J. Reproduction, environment and saved outputs",
             table(pd.DataFrame(resource.items(), columns=["Instrumented property", "Value"]),
                   "Table S15. Analysis-only measured compute record."),
             para("From the workspace root, install the pinned requirements into "
                  "the local environment and run fetch_sources.py followed by "
                  "02_polymer_targeting\\run.py. To rebuild both papers, run "
                  "both project pipelines first and then build_manuscripts.py. "
                  "The common root utilities are required; the project "
                  "folders are scientifically separate, not standalone "
                  "dependency-free software packages."),
             table(pd.DataFrame([
                 ["analysis_dataset.csv", "Primary polymer endpoint cohort and reference groups"],
                 ["all_material_endpoints.csv", "Paired 24-h endpoints before material filtering"],
                 ["data_audit.json", "Counts, missingness, exclusions, source hash"],
                 ["effects.json", "Ranks, bootstrap intervals and targeting contrasts"],
                 ["metrics.csv / predictions.csv", "Every evaluated split/model score and tree prediction"],
                 ["splits.csv", "Identifiers and roles for every seed"],
                 ["sensitivity.csv / protocol.json", "Declared sensitivity cohorts and frozen settings"],
             ], columns=["Saved result", "Purpose"]), "Table S16. Machine-readable evidence map."),
             para("No clinical or experimental result is generated by building "
                  "the PDF. The manuscript reads measured result files; "
                  "a change in source data requires rerunning analysis. "
                  "Test outputs and document validation are separate from "
                  "scientific peer review and should not be confused "
                  "with confirmation of the biological interpretation.")),
        page("Appendix K. External validation design",
             table(pd.DataFrame([
                 ["Comparison", "Composition-matched active and passive carriers"],
                 ["Exposure", "Separate measurements of carrier and free drug"],
                 ["Distribution", "Paired multiorgan observations at common times"],
                 ["Benefit", "Tumour response evaluated independently of accumulation"],
                 ["Risk", "Organ-specific toxicity assessed separately from selectivity"],
             ], columns=["Design element", "Proposed evaluation"]), "Table S17. Design for independent evaluation of a selectivity objective."),
             para("An independent study could compare composition-matched "
                  "active/passive polymer carriers in a genuinely independent data "
                  "resource, quantify free-drug and carrier distributions separately, "
                  "and test whether a multiorgan objective predicts a meaningful "
                  "therapeutic outcome. Such validation has not been performed here; "
                  "the present results describe published biodistribution observations.")),
    ]
    return folder, title, pages


def render(folder, title, pages):
    pages = expand(folder, pages, para, table, image, page)
    render_acl(folder, title, pages, REFERENCES)


def main():
    builders = {"01_release_transfer": release_pages, "02_polymer_targeting": polymer_pages}
    for project in selected_projects():
        render(*builders[project]())


if __name__ == "__main__":
    main()
