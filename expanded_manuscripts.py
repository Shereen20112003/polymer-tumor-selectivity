"""Substantive manuscript extensions tied to the executed additional analyses."""
import json
from pathlib import Path
import re

import pandas as pd

ROOT = Path(__file__).resolve().parent


def expand(folder, sections, para, table, image, page):
    directory = ROOT / folder
    output = directory / "results" / "extended"

    def read(name):
        return pd.read_csv(output / f"{name}.csv", float_precision="round_trip")

    def equation(source):
        return ("equation", source)

    metrics, learning = read("metrics"), read("learning")
    support, permutation = read("support"), read("permutation")
    protocol = json.loads((output / "protocol.json").read_text())
    extension = json.loads((output / "extension_summary.json").read_text())
    resource = json.loads((output / "resources.json").read_text())
    means = metrics.groupby("configuration")[["mae", "study_macro_mae", "r2"]].mean()
    learning_means = learning.groupby("fraction")[["mae", "train_groups", "train_n"]].mean()
    support_means = support.groupby("feature")[["unsupported_fraction", "missing_fraction"]].mean()
    permutation_means = permutation.groupby("feature")["mae_increase"].agg(["mean", "std"])
    baseline = means.loc["Trees 128 leaf3", "mae"]
    endpoint = read("endpoint_metrics")
    release = folder == "01_release_transfer"
    reference_index = next(i for i, section in enumerate(sections) if section["title"] == "References")
    main = sections[:reference_index]
    back = sections[reference_index:]
    if release:
        main[0]["blocks"][2] = para(
            "Additional capacity, feature-block and learning-curve ablations use the same "
            f"publication holdouts. Only {extension['interpolation_exact_fraction']:.1%} of "
            "harmonized endpoints coincide with a recorded source time, motivating a "
            "resolution audit. Publication-level calibration improves empirical simultaneous "
            "coverage at the cost of wide intervals; exchangeability and prospective "
            "performance remain unestablished.")
    else:
        main[0]["blocks"][2] = para(
            "Additional objective-weight, publication-omission and capacity ablations preserve "
            "the primary cohort. Leave-one-group-out within-publication contrasts range from "
            f"{extension['omission_contrast_min']:.3f} to {extension['omission_contrast_max']:.3f} "
            "log10 units. The observational contrast remains confounded, and organ "
            "selectivity is not a validated safety or efficacy endpoint.")
    main[1]["blocks"].append(para(
        "A deployment question and a screening objective are separate design choices. "
        "The deployment question specifies which experimental context must be new at evaluation, "
        "whereas the objective specifies which measured outcome a candidate should optimize. "
        "Both choices should be explicit before interpreting a favourable average score. "
        "Here we retain the original publication-disjoint benchmark and add exploratory diagnostics "
        "that probe information content, sample efficiency and decision sensitivity without "
        "replacing unfavourable primary results. These extensions were developed after inspecting "
        "the primary analysis and are not preregistered confirmatory tests."))
    main[2]["blocks"].append(para(
        "<b>Analysis hierarchy.</b> The formulation is the prediction unit, but the publication-reference "
        "group is the partitioning unit. Multiple formulations can share experimental protocols "
        "and reporting conventions, so counting them as independently sampled research settings "
        "would overstate the information available. We retain all eligible formulations within a "
        "selected group. Group sizes therefore vary across partitions and learning-curve subsets; "
        "nominal percentages of groups should not be read as exact percentages of formulations. "
        "No target-dependent exclusion is added to the primary cohort during the model comparisons."))
    main[3]["blocks"].extend([
        para("<b>Exploratory extension design.</b> Every additional configuration uses the saved five "
             "publication partitions. Ridge penalties of 1, 10 and 100 probe regularization; tree "
             "leaf sizes of 1, 3 and 8 probe local averaging; 32 versus 128 trees probes ensemble "
             "size. Feature-block removal is evaluated separately from changing model capacity. "
             "All configurations are reported rather than choosing a winner using held-out errors. "
             "Consequently this is a sensitivity grid, not a hyperparameter-selection procedure "
             "or a claim about the optimally achievable prediction error."),
        para("<b>Paired comparisons.</b> Within a seed, configurations share the same training and "
             "test formulations. Their MAE differences can therefore be compared on a common "
             "evaluation composition. Across seeds, however, publications are reused. The five "
             "scores are descriptive repeated-partition results, not independent replications. "
             "We report their full values and dispersion, and avoid significance tests that treat "
             "the five partitions as independently sampled laboratories."),
    ])
    settings = ["Trees 128 leaf3", "Trees 128 leaf1", "Trees 128 leaf8",
                "Trees 32 leaf3", "Ridge alpha1", "Ridge alpha10", "Ridge alpha100"]
    model_table = means.loc[settings, ["mae", "r2"]].reset_index()
    model_table.columns = ["Setting", "MAE", "R2"]
    predictive_section = main[4] if release else main[6]
    predictive_section["blocks"].extend([
        para("<b>Model-capacity sensitivity.</b> The extended grid holds the source cohort, "
             "partition manifests and scoring definitions fixed. A smaller ensemble changes "
             "Monte Carlo averaging but does not add process measurements. Changing leaf size "
             "changes the degree of local smoothing. A stronger ridge penalty changes shrinkage "
             "after training-only standardization. These interventions distinguish sensitivity "
             "to the learner from sensitivity to the available descriptors."),
        table(model_table, "Table 5. Capacity and regularization sensitivity on the original publication holdouts."),
        para(f"The tree leaf-size variants had mean MAEs of "
             f"{means.loc['Trees 128 leaf1','mae']:.3f}, {baseline:.3f}, and "
             f"{means.loc['Trees 128 leaf8','mae']:.3f} for leaf sizes 1, 3 and 8. "
             f"The 32-tree result was {means.loc['Trees 32 leaf3','mae']:.3f}. "
             "These are observations about the fixed grid, not evidence that the best observed "
             "configuration will retain its ranking on another dataset. The complete seed-level "
             "scores, including group-weighted MAE, are reported in Appendix M."),
    ])
    main[-1]["blocks"].append(para(
        f"The additional analyses used {resource['elapsed_seconds']:.1f} instrumented seconds "
        f"and sampled peak process RSS {resource['sampled_peak_rss_mb']:.1f} MB with one worker. "
        "The primary cohort and original results remain unchanged; the extension independently "
        "reproduces the original publication-split tree scores before interpreting additional "
        "comparisons. Setup and manuscript compilation are excluded."))

    if release:
        calibration, resolution = read("calibration"), read("resolution")
        interpolation, utility = read("interpolation"), read("utility")
        cal_means = calibration.groupby(["nominal", "method"])[["publication_coverage", "width"]].mean()
        primary_utility = utility[(utility["nominal"] == 0.9) & (utility["method"] == "Publication-max")]
        util_means = primary_utility.groupby("width_limit")[
            ["fraction_within_limit", "fraction_covered_and_within_limit"]].mean()
        resolution_summary = resolution.groupby(["target", "exact"]).agg(
            records=("n", "sum"), mean_mae=("mae", "mean"), mean_gap=("mean_gap_days", "mean")).reset_index()
        main[2]["blocks"].extend([
            para("<b>Endpoint information is not measurement precision.</b> Interpolating a release "
                 "curve supplies a value at a common time, but the source observations can be "
                 "widely separated. A three-day endpoint bracketed by dense measurements is "
                 "not supported in the same way as one bracketed by distant digitized points. "
                 "We therefore record the two supporting times and their separation for each "
                 "eligible endpoint. Exact observations receive a zero gap. The gap is a reporting "
                 "diagnostic, not an estimate of assay error or a replacement for experimental "
                 "replicates. The release values themselves are not smoothed or corrected."),
            para("The feature groups deliberately distinguish molecular descriptors, polymer "
                 "descriptors, formulation properties and release-medium additive concentration. "
                 "Molecular descriptors comprise drug molecular weight, TPSA and LogP; the "
                 "polymer block contains molecular weight and LA/GA ratio. The formulation block "
                 "contains particle diameter, loading, encapsulation efficiency and input "
                 "drug-to-polymer ratio. These groups describe recorded information channels, "
                 "not independent physical mechanisms: changing loading can also change porosity, "
                 "and polymer molecular weight can interact with processing history."),
        ])
        main[3]["blocks"].extend([
            equation(r"\begin{aligned}s_g&=\max_{i\in g}\max_{j\in\{1,3,7\}}"
                     r"|y_{ij}-\widehat f_j(x_i)|,\\"
                     r"q_\alpha&=s_{(\lceil(G_{\rm cal}+1)(1-\alpha)\rceil)}.\end{aligned}"),
            para("The publication score is a maximum over both formulations and endpoints. "
                 "Increasing the number of formulations in a block can increase its score even "
                 "when formulation-wise residual distributions do not change. The finite-sample "
                 "rank is applied to publication scores, not to the total number of release "
                 "measurements. The same fitted predictor and calibration partition are reused "
                 "when the nominal level changes, isolating the calibration rule from refitting "
                 "or outcome-dependent feature selection."),
            equation(r"\widehat C_{\rm pub}=\frac{1}{G_{\rm test}}\sum_{g=1}^{G_{\rm test}}"
                     r"\mathbf{1}\{\text{all endpoints in }g\text{ covered}\}."),
            para("Mean width and simultaneous coverage describe different properties. Width is "
                 "averaged over endpoint intervals, while publication coverage weights each "
                 "publication once. An interval can have high marginal endpoint coverage yet "
                 "miss one endpoint in many publications. Conversely a wide interval can "
                 "cover nearly every endpoint while contributing little to the ordering of "
                 "candidate formulations. These possibilities motivate reporting all coverage "
                 "levels and the physical scale of the interval, rather than a single score."),
        ])
        removal = means.loc[[name for name in means.index if name.startswith("Without")], ["mae", "r2"]]
        main[4]["blocks"].extend([
            para("<b>Descriptor-block interventions.</b> We remove entire recorded blocks while "
                 "keeping the train/test assignment fixed. This is different from shuffling "
                 "test values: removal allows the predictor to refit using the remaining "
                 "information. Shuffling asks whether a fitted predictor uses a feature under "
                 "an artificial perturbation. Neither operation identifies the physical "
                 "contribution of that variable to release kinetics, because recorded variables "
                 "can substitute for one another and correlate with unrecorded process choices."),
            table(removal.reset_index().rename(columns={"configuration": "Removed block"}),
                  "Table 6. Refit feature-block ablations; all configurations use the same test publications."),
            para("Small changes around a weak baseline should not be interpreted as evidence that "
                 "drug chemistry or polymer architecture is unimportant. They can instead "
                 "indicate that the encoded variables are coarse, that the training cohort is "
                 "small, or that the remaining predictors provide similar proxies. Negative "
                 "permutation importance is retained when shuffling happens to reduce error. "
                 "Appendix P separates this fitted-model diagnostic from the refit ablations."),
        ])
        new_main = [
            page("Data efficiency and publication support",
                 para("The learning experiment reduces only the original training publications. "
                      "For each seed we draw one deterministic ordering of training groups and "
                      "retain nested prefixes containing approximately 25%, 50%, 75% and 100% "
                      "of them. Calibration and test groups remain untouched. Entire groups "
                      "are retained, preserving within-publication formulation dependence. "
                      "This prevents a learning curve from improving merely because its test "
                      "set changes at each training size."),
                 para(f"Figure 3 shows mean MAE changing from "
                      f"{learning_means.loc[0.25,'mae']:.3f} at the smallest subset to "
                      f"{learning_means.loc[1.0,'mae']:.3f} with all original training publications. "
                      f"The corresponding mean numbers of training groups were "
                      f"{learning_means.loc[0.25,'train_groups']:.1f} and "
                      f"{learning_means.loc[1.0,'train_groups']:.1f}. "
                      "A nonmonotone curve is possible because new groups can change the "
                      "mixture of assay protocols, drugs and formulation families. These "
                      "four points do not justify extrapolating a power law or estimating "
                      "the sample size needed for clinical-grade prediction."),
                 image("learning_extended.png", "Figure 3. Nested training-publication sensitivity. Error bars are SD across the five overlapping outer partitions."),
                 table(learning_means.reset_index().rename(columns={
                     "fraction": "Train fraction", "train_groups": "Groups", "train_n": "Formulations",
                 }), "Table 7. Data-efficiency results, averaged over the fixed outer partitions."),
                 para("We additionally compare each test descriptor with its training support. "
                      "A numeric value is outside support when it lies below the training "
                      "minimum or above the training maximum. The diagnostic is simple and "
                      "univariate: being inside every observed range does not imply support "
                      "for the joint formulation or its processing conditions. Missing values "
                      "are reported separately instead of being called out-of-range values. "
                      "The complete per-seed audit is provided in Appendix O."),
                 para("These analyses distinguish a larger literature compilation from a more "
                      "informative one. Adding many formulations from an already represented "
                      "protocol can increase row count without creating an equally large "
                      "number of new experimental settings. A more useful expansion would "
                      "record end groups, porosity, solvent processing, batch identifiers and "
                      "assay conditions consistently, then assess whether these measurements "
                      "reduce publication-held-out error under an unchanged target definition.")),
            page("Calibration sensitivity and endpoint resolution",
                 para("Figure 4 evaluates nominal levels of 80%, 85%, 90% and 95% using "
                      "the same fitted predictions. All methods use the finite-sample corrected "
                      "rank, and all intervals are clipped to the physical release range. "
                      "This comparison tests whether the distinction between pointwise and "
                      "publication-wise coverage persists beyond one chosen nominal level. "
                      "It is not a procedure for selecting a nominal level after observing "
                      "which one happens to match the test coverage."),
                 para(f"At 80% nominal coverage, publication-max calibration gave "
                      f"{cal_means.loc[(0.8,'Publication-max'),'publication_coverage']:.1%} "
                      f"publication coverage and mean width "
                      f"{cal_means.loc[(0.8,'Publication-max'),'width']:.3f}; "
                      f"at 95%, these values were "
                      f"{cal_means.loc[(0.95,'Publication-max'),'publication_coverage']:.1%} "
                      f"and {cal_means.loc[(0.95,'Publication-max'),'width']:.3f}. "
                      "Coverage changes in discrete steps because each test split contains "
                      "a finite number of publication blocks. Averaging the five splits "
                      "does not remove their overlap or certify exchangeability."),
                 image("calibration_extended.png", "Figure 4. Nominal versus empirical publication coverage. The dashed diagonal is equality, not a fitted model or a prospective guarantee."),
                 para("To make width interpretable, we audit maximum endpoint widths of 0.25, "
                      "0.50 and 0.75 release fraction. These are exploratory reporting tolerances, "
                      "not experimentally established formulation-selection thresholds. A "
                      "formulation passes a tolerance only if every one of its three endpoint "
                      "intervals is no wider than that value. We also report the joint event "
                      "of passing the tolerance and covering its observed endpoint vector. "
                      "This prevents narrow but systematically inaccurate intervals from "
                      "looking useful through width alone."),
                 table(util_means.reset_index().rename(columns={
                     "width_limit": "Width limit", "fraction_within_limit": "Narrow fraction",
                     "fraction_covered_and_within_limit": "Narrow and covered",
                 }), "Table 8. Exploratory width utility at 90% publication-max calibration."),
                 para(f"Across the eligible endpoint vectors, "
                      f"{extension['interpolation_exact_fraction']:.1%} of individual endpoints "
                      "coincided with a recorded source time. Error stratification by exact "
                      "versus interpolated endpoints is reported in Appendix R. The strata "
                      "differ in source composition and are not a controlled experiment on "
                      "measurement density. Large bracketing gaps motivate denser prospective "
                      "sampling, but cannot alone quantify the uncertainty of a digitized curve.")),
        ]
        main[-2]["blocks"].extend([
            para("The capacity grid, learning curves and interpolation audit triangulate the "
                 "same deployment limitation from different directions. Capacity changes probe "
                 "the learner; training-group subsampling probes the finite source collection; "
                 "support diagnostics probe recorded descriptor extrapolation; and bracketing "
                 "gaps probe endpoint construction. Agreement between these diagnostics would "
                 "not make their evidence independent, because they share observations and "
                 "partitions. Disagreement is informative and should not be hidden by choosing "
                 "only the diagnostic that gives the most favourable result."),
            para("A practical laboratory decision also requires an asymmetric loss. Missing a "
                 "burst-release failure and discarding a potentially useful depot need not "
                 "have the same cost. The present MAE and coverage metrics do not encode "
                 "those costs, a target therapeutic concentration or an acceptable release "
                 "window. Before using these intervals to screen candidates, an independent "
                 "experiment should define such tolerances and evaluate both the number "
                 "of avoided assays and the number of incorrectly rejected formulations. "
                 "No reduction in experimental cost is claimed from the current reanalysis."),
        ])
        specific = [
            page("Appendix Q. Nominal-level and calibration-unit sensitivity",
                 para("The grid crosses four nominal levels, three score units and five outer "
                      "partitions. A model is fitted once per outer partition and is not refitted "
                      "across the calibration grid. Each publication maximum is computed after "
                      "taking the maximum across the formulation's three endpoints. This order "
                      "is equivalent to a maximum across all eligible endpoints in a block, "
                      "but is not equivalent to averaging formulation residuals within a block."),
                 table(calibration.groupby(["nominal", "method"])[
                     ["radius", "publication_coverage", "width"]].mean().reset_index(),
                     "Table S18. Full nominal-level sensitivity, averaged across the five fixed partitions."),
                 para("A larger score count is not automatically a larger independent sample. "
                      "Pointwise calibration counts three residuals per calibration formulation, "
                      "formulation calibration counts one vector maximum per formulation, and "
                      "publication calibration counts one block maximum per publication. "
                      "The interpretation of the resulting rank depends on the corresponding "
                      "exchangeability assumption. The table therefore reports the calibration "
                      "unit rather than labelling every score as an independent observation."),
                 table(calibration[(calibration["nominal"] == 0.9) &
                                   (calibration["method"] == "Publication-max")][
                     ["seed", "calibration_n", "radius", "point_coverage", "vector_coverage",
                      "publication_coverage", "width"]],
                     "Table S19. Partition-level 90% publication-max calibration details."),
                 para("The saved interval-prediction file contains each bound and target for "
                      "every cell of the grid. Coverage can therefore be recalculated without "
                      "refitting. Finite-sample corrected ranks at very high nominal levels "
                      "may exceed the available score count; the implementation raises rather "
                      "than substituting an ordinary empirical percentile. All levels in "
                      "the reported grid have an estimable finite corrected rank.")),
            page("Appendix R. Interpolation support and endpoint errors",
                 para("For an exact endpoint the left and right supporting times both equal "
                      "the target time. Otherwise the audit uses the closest source time on "
                      "each side of that target. The gap is their difference in days. "
                      "A formulation must bracket all three targets to enter the primary "
                      "cohort, so no endpoint here uses extrapolation. Averaging duplicate "
                      "source-time observations precedes interpolation, matching the original "
                      "cohort construction rather than introducing a new smoothing rule."),
                 table(interpolation.groupby(["target", "exact"]).agg(
                     endpoints=("id", "size"), median_gap=("gap_days", "median"),
                     maximum_gap=("gap_days", "max")).reset_index(),
                     "Table S20. Source-time support for the included endpoints."),
                 table(resolution_summary, "Table S21. Error strata by endpoint and exact-time availability."),
                 para("The reported mean MAE within a stratum first summarizes an outer "
                      "partition and then averages the available partition summaries equally. "
                      "The record count sums held-out endpoint appearances, including repeated "
                      "appearances across seeds. It is not a count of independent assays. "
                      "Differences between exact and interpolated strata can reflect drug, "
                      "publication, assay and endpoint composition as well as interpolation."),
                 table(resolution, "Table S22. All partition-level endpoint-resolution diagnostics."),
                 para("Exact-time observations are not error-free ground truth. They can still "
                      "come from figure digitization or heterogeneous experimental reporting. "
                      "Conversely an interpolated endpoint can be well supported when the "
                      "neighbouring points are dense and the curve is locally smooth. Without "
                      "independent replicate curves, the present resource cannot identify "
                      "a calibrated measurement-error distribution for either stratum.")),
            page("Appendix S. Publication size and interval utility",
                 para("Block coverage treats a publication containing one eligible formulation "
                      "and a publication containing many eligible formulations as one evaluation "
                      "unit each. Their simultaneous events differ in difficulty. The following "
                      "descriptive audit groups test blocks by the number of included formulations; "
                      "the categories are one, two to three, and four or more. They are reporting "
                      "bins and were not used to fit separate calibration rules."),
                 table(_block_summary(read("blocks")),
                       "Table S23. Conditional block-size diagnostics at 90% publication-max calibration."),
                 para("A dependence of maximum residual or empirical coverage on block size "
                      "would not by itself establish failure of a particular conformal theorem. "
                      "Larger publications can differ in drug families, assays and formulation "
                      "diversity. The exchangeability condition concerns the joint block "
                      "distribution, including its size. Conditioning post hoc on block size "
                      "is therefore descriptive and does not create a conditional guarantee."),
                 table(utility[utility["nominal"] == 0.9].groupby(
                     ["method", "width_limit"])[["fraction_within_limit",
                                              "fraction_covered_and_within_limit"]].mean().reset_index(),
                     "Table S24. Full score-unit comparison of the exploratory width criteria."),
                 para("A width of 0.50 denotes fifty percentage points of fractional release, "
                      "not a fifty-percent relative error. A formulation satisfies a width "
                      "limit only when the widest of its three intervals satisfies the limit. "
                      "The covered-and-narrow event additionally requires all three observed "
                      "endpoints to lie within their intervals. Neither event incorporates "
                      "dose, concentration, toxicity or a therapeutic exposure target.")),
        ]
    else:
        objectives, influence = read("objectives"), read("influence")
        cohorts, balance, coupling = read("cohorts"), read("balance"), read("coupling")
        frontier = read("pareto")
        ratio = objectives[objectives["liver_weight"] == 1]
        main[3]["blocks"].extend([
            equation(r"z_i(\lambda)=\log_{10}T_i-\lambda\log_{10}L_i."),
            para("At lambda=0 the objective ranks tumour accumulation alone; at lambda=1 "
                 "it ranks the tumour/liver ratio. Other weights are exploratory preferences "
                 "for liver avoidance, not measured clinical utility. Ranking candidates "
                 "under several weights exposes a choice that is otherwise hidden inside "
                 "a scalar score. Both organ measurements remain in the same whole-organ "
                 "%ID units throughout this comparison."),
            equation(r"\begin{aligned}d_g&=\overline z_{g,\mathrm{Active}}"
                     r"-\overline z_{g,\mathrm{Passive}},\\"
                     r"\widehat\Delta_{\rm within}&=\frac{1}{G_{\rm both}}\sum_{g=1}^{G_{\rm both}}d_g."
                     r"\end{aligned}"),
        ])
        new_main = [
            page("Selection objectives and multiorgan trade-offs",
                 para("Figure 3 repeats the shortlist comparison at selection fractions of "
                      "10%, 20%, 25%, 33% and 50%, using the ceiling of the requested "
                      "fraction times the cohort size. A change in the overlap at different "
                      "fractions need not indicate a change in biology: the lists become "
                      "longer and eventually must overlap more. Reporting several thresholds "
                      "shows whether the original top-quartile result is specific to one "
                      "shortlist length."),
                 para(f"At the 10% and 50% fractions, uptake-versus-ratio shortlist overlaps "
                      f"were {ratio.iloc[0]['uptake_overlap']:.1%} and "
                      f"{ratio.iloc[-1]['uptake_overlap']:.1%}, respectively. "
                      f"The paired high-tumour/low-liver Pareto frontier contains "
                      f"{extension['pareto_formulations']} formulations. A frontier point "
                      "has no other observed formulation with at least as much tumour "
                      "accumulation and at most as much liver accumulation, with one "
                      "strict improvement. Frontier membership does not establish safety "
                      "or superiority under different experimental conditions."),
                 image("objectives_extended.png", "Figure 3. Uptake-versus-ratio shortlist overlap across selection fractions in the fixed primary cohort."),
                 table(objectives[objectives["fraction"] == 0.25][
                     ["liver_weight", "uptake_overlap", "ratio_overlap", "median_tumor", "median_liver"]],
                     "Table 6. Liver-penalty sensitivity for top-quartile selection; organ medians remain %ID."),
                 para("The weighted objectives and Pareto calculation use measurements from "
                      "different publications. They describe the recorded dataset, not a "
                      "head-to-head carrier trial. A candidate can look attractive because "
                      "its assay time, dose or tumour model differs from another candidate. "
                      "The frontier is therefore an illustration of the selection objective, "
                      "not a recommendation to synthesize or administer a listed material.")),
            page("Publication influence, denominator tails and confounding",
                 para("We omit each connected publication group in turn and recompute "
                      "the pooled contrast, equal-weight within-publication contrast and "
                      "rank correlation. This identifies sensitivity to individual source "
                      "groups without calling the omitted datasets independent validation "
                      "cohorts. These omission results are not bootstrap confidence intervals."),
                 para(f"The within-publication contrast ranged from "
                      f"{extension['omission_contrast_min']:.3f} to "
                      f"{extension['omission_contrast_max']:.3f} log10 units under group "
                      "omission. Complete-physicochemical-case and minimum-liver subsets "
                      "are evaluated separately below. A liver floor is a numerical "
                      "sensitivity analysis, not a detection limit supplied by the source "
                      "assay. Excluding small denominators changes the target population."),
                 table(cohorts[["cohort", "n", "groups", "within_contrast"]],
                       "Table 7. Cohort and denominator sensitivities of the observational association."),
                 para("Hydrodynamic size and zeta-potential balance are reported in "
                      "Appendix S, including standardized mean differences and within-group "
                      "numerical contrasts. Publication restriction does not guarantee "
                      "composition-matched carriers: active and passive labels can still "
                      "differ in architecture, surface treatment, dose and assay conditions. "
                      "These diagnostics expose possible confounding rather than estimating "
                      "a causal ligand effect or correcting unmeasured covariates."),
                 para(f"A shuffled-liver diagnostic produced median rank correlation "
                      f"{extension['coupling_correlation_median']:.3f} between tumour uptake "
                      "and the reconstructed ratio. This experiment retains the shared "
                      "tumour numerator while breaking the observed tumour/liver pairing. "
                      "It is a mathematical-coupling diagnostic, not a valid biological "
                      "null model or a publication-adjusted permutation test.")),
            page("Data efficiency and descriptor support",
                 para("Figure 4 retains nested subsets of the original training publications "
                      "at four fractions while keeping each seed's test set fixed. "
                      "The reserved 20% partition is not added to training or used to select "
                      "a preferred configuration. Complete publication groups, rather than "
                      "individual formulations, enter each nested training subset."),
                 para(f"Mean test MAE was {learning_means.loc[0.25,'mae']:.3f} at "
                      f"25% training-group retention and {learning_means.loc[1.0,'mae']:.3f} "
                      "with all original training groups. This curve measures sensitivity "
                      "to the available literature mixture, not the benefit of acquiring "
                      "an equal number of new matched experiments. A larger training "
                      "set can introduce new tumour labels and measurement conventions "
                      "as well as additional examples of familiar carriers."),
                 image("learning_extended.png", "Figure 4. Nested publication-group learning sensitivity. Error bars are SD across overlapping outer partitions."),
                 table(learning_means.reset_index().rename(columns={
                     "fraction": "Train fraction", "train_groups": "Groups", "train_n": "Formulations",
                 }), "Table 8. Full-data-efficiency summary on the fixed publication holdouts."),
                 para("Numeric support checks flag size or zeta values outside the training "
                      "range. Categorical checks flag unseen targeting, shape, core or "
                      "tumour-cell labels. An unseen category is encoded without adding "
                      "a new outcome-informed column. Missing measurements are tracked "
                      "separately. These checks audit the recorded representation; they "
                      "do not measure support for polymer chemistry that the dataset "
                      "does not encode. Appendix O reports every feature and partition.")),
        ]
        main[-1]["blocks"].extend([
            para("The additional analyses separate three potential sources of instability: "
                 "the screening objective, the observational cohort and the fitted predictor. "
                 "Changing a liver penalty changes what is selected; omitting a publication "
                 "changes the literature mixture; and changing model capacity changes the "
                 "mapping from the recorded descriptors to the same target. None of these "
                 "interventions substitutes for measuring free-drug exposure or therapeutic "
                 "response. A future matched study should specify its multiorgan objective "
                 "before using a predictor to choose which carriers receive further assays."),
            para("The numerator and denominator should also be interpreted separately. "
                 "A higher tumour/liver ratio can result from greater tumour accumulation, "
                 "lower liver accumulation, or a decrease in both organs with a larger "
                 "relative decrease in liver. These scenarios are not interchangeable "
                 "for a drug that needs an absolute intratumoural exposure threshold. "
                 "Whole-organ %ID does not distinguish an intact carrier from a released "
                 "label or quantify unbound drug at its molecular target. The ratio "
                 "is therefore most defensible as one component of an explicitly "
                 "multivariate screening report that retains absolute organ values."),
            para("Likewise, lower liver accumulation is not synonymous with lower "
                 "toxicity. A material can redistribute to spleen, lung, kidney "
                 "or circulating compartments, and organ injury can depend on "
                 "local concentration, degradation products and exposure duration. "
                 "The source endpoint is a single 24-hour whole-organ observation, "
                 "not a time-integrated concentration curve. The proposed objective "
                 "does not account for delayed clearance or repeated dosing. "
                 "A screening programme could report paired tumour and liver "
                 "values alongside a wider organ panel, then evaluate toxicity "
                 "as a separate measured outcome rather than inferring it "
                 "from the selectivity score."),
            para("Covariate adjustment would require a biological estimand in "
                 "addition to a statistical model. Size and surface charge "
                 "can be consequences of ligand conjugation as well as "
                 "differences between independently designed carriers. Treating "
                 "them automatically as confounders could remove part of "
                 "a formulation's total effect, while omitting them can "
                 "leave composition imbalance. The current balance table "
                 "does not resolve that causal structure. A matched comparison "
                 "should first specify whether the question concerns "
                 "adding a ligand to a fixed carrier or comparing "
                 "complete carrier designs that differ in several properties."),
            para(f"The recorded tumour-cell descriptor was unseen in training "
                 f"for a mean {support_means.loc['tumor_cell','unsupported_fraction']:.1%} "
                 "of held-out formulations. This is a property of the "
                 "publication-separated representation, not an estimate of "
                 "biological novelty. Coarse source labels can conceal "
                 "substantial heterogeneity, whereas unfamiliar labels "
                 "can sometimes describe related biological settings. "
                 "The result motivates richer, harmonized tumour-model "
                 "metadata rather than allowing source identity "
                 "to leak into training. Negative predictive R2 "
                 "should be interpreted as weak performance of "
                 "this recorded-feature benchmark, not evidence "
                 "that polymer design has no effect on distribution."),
            para("A discriminating follow-up would compare composition-matched "
                 "carriers across laboratories while varying ligand presence "
                 "and density independently of particle size and drug loading. "
                 "Assays would distinguish carrier-associated signal from "
                 "free drug, measure several common sampling times, "
                 "and record tumour response and organ-specific injury "
                 "without substituting accumulation for either endpoint. "
                 "The screening objective, useful exposure threshold "
                 "and acceptable competing-organ exposure would be "
                 "specified before evaluating prediction. Such a "
                 "design could test whether a selectivity-aware "
                 "shortlist changes experimental decisions, whereas "
                 "the present audit establishes only how "
                 "the recorded screening choices differ."),
        ])
        specific = [
            page("Appendix Q. Objective-weight and shortlist-size grid",
                 para("The objective grid crosses five shortlist fractions with six liver "
                      "penalties. Every cell uses the same 142 paired observations. "
                      "A shortlist is constructed by descending score with the source-row "
                      "order resolving exact ties through the same deterministic table "
                      "operation. The uptake and ratio reference shortlists use that same "
                      "requested list length. No cell is labelled the optimal screening rule."),
                 table(objectives, "Table S18. Complete objective-weight and shortlist-fraction grid."),
                 para("For lambda greater than one, the score penalizes liver accumulation "
                      "more strongly than the log ratio does. For lambda between zero and "
                      "one it moves toward tumour accumulation alone. These changes encode "
                      "preferences, not additional information or a new treatment mechanism. "
                      "Median organ accumulation among selected rows is included so that "
                      "an apparently favourable ratio is not read without its numerator "
                      "and denominator."),
                 table(frontier[frontier["pareto"]][["id", "tumor", "liver", "log_ratio", "strategy"]],
                       "Table S19. Recorded paired-organ Pareto-frontier rows; not recommended therapies."),
                 para("The frontier maximizes tumour accumulation and minimizes liver "
                      "accumulation simultaneously. Tied observations remain on the frontier "
                      "when neither strictly dominates the other. Because the comparison "
                      "pools heterogeneous experiments, frontier membership is descriptive "
                      "and may change after harmonizing dose, tumour model, sampling "
                      "conditions or measurement uncertainty.")),
            page("Appendix R. Publication-omission influence analysis",
                 para("One connected publication-reference group is removed per iteration. "
                      "All remaining observations keep their original organ measurements "
                      "and targeting categories. We then recompute the pooled active-minus-"
                      "passive mean, the equal-weight mean of overlapping-group contrasts, "
                      "the median log ratio and the uptake/selectivity rank correlation. "
                      "This deterministic influence analysis differs from repeatedly "
                      "resampling groups with replacement."),
                 table(influence, "Table S20. Complete leave-one-reference-group-out influence audit."),
                 para("A change in the pooled contrast can arise when a group supplies "
                      "many observations from one targeting category. The within-group "
                      "summary responds to a different intervention: omitting a group "
                      "with both categories removes one contrast from an equal-weight "
                      "average. Omission of a group containing only one category leaves "
                      "that within-group average unchanged. This distinction explains "
                      "why the two influence profiles need not track each other."),
                 para("The minimum and maximum omission values are not a 95% interval "
                      "and are not adjusted for publication selection or measurement error. "
                      "They describe sensitivity to the finite source collection. A "
                      "stable omission profile would not remove confounding within each "
                      "publication or establish transportability to a new laboratory. "
                      "The full audit is retained rather than showing only the most "
                      "favourable omissions.")),
            page("Appendix S. Covariate balance and coupling diagnostics",
                 para("For each numerical covariate, the pooled standardized difference "
                      "divides the active-minus-passive mean difference by the square "
                      "root of the average of the two sample variances. It is a "
                      "descriptive balance measure, not a propensity score. The within-"
                      "publication numerical contrast uses only groups with both "
                      "categories and available numerical observations. Thus its "
                      "eligible groups can differ between size and zeta potential."),
                 table(balance, "Table S21. Numerical covariate balance by targeting category."),
                 table(cohorts, "Table S22. Complete physicochemical-case and minimum-liver sensitivity results."),
                 para("Complete-case restriction can select a different set of experiments "
                      "because measurement completeness is not randomized. Minimum-liver "
                      "restrictions select on an observed outcome. Neither restriction "
                      "should be interpreted as correcting confounding. Their role is "
                      "to show how cohort definitions affect the descriptive association "
                      "and how many reference groups continue to support the comparison."),
                 table(pd.DataFrame({
                     "Shuffle summary": ["2.5th percentile", "Median", "97.5th percentile"],
                     "Rank correlation": coupling["rank_correlation"].quantile([0.025, 0.5, 0.975]).to_numpy(),
                 }), "Table S23. Distribution of rank correlation over 1,000 shuffled-liver diagnostics."),
                 para("The shuffled-liver procedure preserves the marginal liver "
                      "distribution and the original tumour numerator. It destroys "
                      "their observed pairing, including within-publication dependence. "
                      "A positive correlation can therefore persist solely because "
                      "the reconstructed ratio contains the tumour term. No p-value "
                      "against this shuffle distribution is reported: the shuffle "
                      "does not represent randomized targeting or a biologically "
                      "exchangeable null population.")),
        ]

    paired = metrics.copy()
    reference = paired[paired["configuration"] == "Trees 128 leaf3"].set_index("seed")["mae"]
    paired["MAE difference"] = paired["mae"]-paired["seed"].map(reference)
    paired["Seed / setting"] = paired["seed"].astype(str)+" / "+paired["configuration"]
    endpoint_summary = endpoint.groupby(["configuration", "target"])[["mae", "r2"]].mean().reset_index()
    config_table = pd.DataFrame([{
        "Setting": config["name"], "Retained predictors": len(config["columns"]),
        "Learner": config["kind"], "Penalty / leaf": config.get("alpha", config.get("min_samples_leaf", 3)),
        "Trees": 0 if config["kind"] == "ridge" else config.get("n_estimators", 128),
    } for config in protocol["configurations"]])
    common = [
        page("Appendix L. Extension protocol and information boundaries",
             para("The extension is exploratory and follows the completed primary "
                  "analysis. It does not retroactively label the additional model "
                  "configurations or robustness questions as preregistered. The "
                  "primary cohort, source exclusions, time units and publication "
                  "partitions are frozen. Additional configurations use the same "
                  "prediction target and the same original holdouts. No test-set "
                  "search selects a new primary model or replaces the primary scores."),
             table(config_table, "Table S13. Complete executed extension configuration grid."),
             para(("Preprocessing remains training-only. Numeric variables are median "
                  "imputed with missingness indicators and standardized. Categorical "
                  "variables are imputed from the training mode and one-hot encoded "
                  "with unknown categories ignored at prediction time. The constant "
                  "source core category in the polymer cohort is retained for "
                  "compatibility with the original pipeline rather than presented "
                  "as a source of discriminative information.") if not release else
                  ("All ten release predictors are numerical. Median imputation, "
                   "missingness indicators and standardization are fitted on training "
                   "formulations only. The present included cohort has no missing "
                   "values among these processed predictors, but the same imputation "
                   "contract is retained for compatibility with the primary pipeline. "
                   "Feature removal occurs before fitting the preprocessing steps, "
                   "so a removed descriptor cannot remain as an imputation indicator "
                   "or a transformed column.")),
             para("The extension reads saved numeric inputs using round-trip "
                  "floating-point parsing. This matters for exact reproducibility: "
                  "rounding a continuous descriptor before standardization can "
                  "alter a randomized tree split. Before interpreting the grid, "
                  "the baseline is refitted and its five publication-split MAEs "
                  "are checked against the original saved results to tight "
                  "numerical tolerance. The extension records hashes of the "
                  "frozen cohort, primary metrics and partition manifest."),
             para("All estimators use one worker. Instrumentation samples process "
                  "memory every 0.1 seconds and excludes dependency installation "
                  "and document compilation. Safety checks stop model-grid "
                  "execution before 110 minutes or 3.8 GB sampled process "
                  "memory. The combined measured primary and extension runtime "
                  "is checked against the two-hour analysis budget.")),
        page("Appendix M. Complete model-grid and paired ablation results",
             para("Every row below identifies an outer seed and an executed "
                  "configuration. Formulation-weighted MAE gives equal weight "
                  "to eligible formulations. Group MAE first averages errors "
                  "within a publication group and then gives groups equal "
                  "weight. R2 uses the same test-target comparator as the "
                  "primary benchmark. A configuration can improve one weighting "
                  "scheme while worsening another when group sizes and error "
                  "patterns differ."),
             table(paired[["Seed / setting", "mae", "study_macro_mae", "r2"]],
                   "Table S14. All per-partition model and refit-ablation scores."),
             table(paired.groupby("configuration")["MAE difference"].agg(
                 ["mean", "min", "max"]).reset_index(),
                 "Table S15. Paired MAE difference from the original tree baseline; negative means lower error."),
             para("The paired differences use the same held-out observations "
                  "within each seed. Their range shows whether a comparison "
                  "changes direction across the reported partitions. It is "
                  "not a confidence interval for population risk. The repeated "
                  "partitions share publications, and the configuration grid "
                  "was evaluated after primary-result inspection. Consequently "
                  "neither the smallest mean error nor a uniformly negative "
                  "five-seed difference supplies a confirmatory discovery claim."),
             table(endpoint_summary, "Table S16. Target-specific mean MAE and R2 for every extension configuration."),
             para(("For release prediction, endpoint-specific rows distinguish "
                  "early from later release errors; the overall score averages "
                  "the three endpoint losses equally. "
                  "No endpoint is selected retrospectively to make a model look better.") if release else
                  ("For polymer selectivity "
                  "there is a single log-ratio target, so the endpoint table "
                  "coincides with the configuration summary. No endpoint "
                  "is selected retrospectively to make a model look better."))),
        page("Appendix N. Nested publication learning curves",
             para("A deterministic seed-specific permutation orders the original "
                  "training publication groups. The four learning subsets "
                  "are nested prefixes of this ordering, with the number "
                  "of groups rounded upward. All formulations belonging "
                  "to a retained group are kept. Calibration or reserved "
                  "groups never enter training, and the original test "
                  "set remains unchanged at every training fraction."),
             table(learning, "Table S17. Every training-fraction and outer-partition result."),
             para("The 100% subset is exactly the original training set, and "
                  "its tree prediction score must reproduce the extension "
                  "baseline. The saved learning manifest contains every "
                  "included formulation identifier, group identifier, "
                  "fraction and seed. Automated checks require nested "
                  "identifier sets, complete groups, no duplicates and "
                  "no overlap with held-out publications."),
             para("Learning curves at this scale need not decrease "
                  "monotonically. Each added block changes the empirical "
                  "training mixture, and the fixed estimator is not "
                  "reoptimized at each size. A flatter curve can reflect "
                  "missing information or limited diversity as well "
                  "as estimator bias. Four exploratory fractions are "
                  "insufficient to support a reliable asymptotic "
                  "learning exponent or a power calculation for a "
                  "future drug-development study.")),
        page("Appendix O. Descriptor support across unseen publications",
             para("Numeric support is the closed interval between the "
                  "minimum and maximum nonmissing training values. "
                  "Categorical support is the set of observed "
                  "nonmissing training labels. A test value outside "
                  "the corresponding set is flagged. Missing test "
                  "values are recorded independently and remain "
                  "subject to the training-only imputation rule."),
             table(support, "Table S25. Complete feature-by-partition support and missingness audit."),
             table(support_means.reset_index(),
                   "Table S26. Mean unsupported and missing fractions across the five partitions."),
             para("The audit does not use target values. Its simple "
                  "univariate definition is deliberately inspectable, "
                  "but it cannot detect every joint covariate shift. "
                  "A test formulation may lie inside each marginal "
                  "range while combining descriptors in a way "
                  "never observed during training. Likewise, a "
                  "slightly out-of-range value is not necessarily "
                  "a more consequential shift than an unrecorded "
                  "change in assay medium or polymer architecture."),
             para(("Unseen tumour-cell or shape labels are not "
                  "automatically evidence of an invalid measurement. "
                  "They show that the fitted categorical "
                  "representation cannot recover a category-specific "
                  "effect from training. Ignoring unseen one-hot "
                  "categories avoids fitting on test data but does "
                  "not solve transportability. The distinction "
                  "between a working encoder and a biologically "
                  "informative representation remains essential.") if not release else
                  ("The release descriptors summarize molecular and bulk formulation "
                   "properties rather than polymer microstructure. Range overlap "
                   "therefore cannot verify matched morphology, polymer end groups "
                   "or fabrication history. A new combination of familiar descriptor "
                   "values may still be a new physical regime. This limits the "
                   "interpretation of descriptor support as an explanation of "
                   "prediction error and motivates explicit process metadata."))),
        page("Appendix P. Held-out permutation diagnostics",
             para("After fitting the original tree baseline within "
                  "each outer partition, we independently permute "
                  "one test-set descriptor at a time. Five "
                  "deterministic shuffles are applied per feature "
                  "and seed. The diagnostic is the shuffled "
                  "MAE minus the unperturbed MAE. It is "
                  "computed on held-out observations but is "
                  "not used to choose features for a "
                  "subsequently reported test score."),
             table(permutation_means.reset_index(),
                   "Table S27. Mean and SD of held-out feature-permutation MAE increases."),
             table(permutation.groupby(["seed", "feature"])["mae_increase"].mean().reset_index(),
                   "Table S28. Every partition-specific permutation diagnostic, averaged over five shuffles."),
             para("A positive value means the fitted predictor "
                  "performed worse after shuffling, not that "
                  "the feature caused improved delivery. "
                  "Correlated predictors can substitute "
                  "for each other, and shuffling can "
                  "create implausible combinations of "
                  "drug, polymer and assay descriptors. "
                  "A negative value is possible under "
                  "weak prediction or finite-sample noise "
                  "and is retained rather than truncated."),
             para("The reported SD pools exploratory perturbation "
                  "results and is not an independent-"
                  "publication confidence interval. "
                  "Refit ablations ask a different "
                  "question by permitting the model "
                  "to adapt to removed information. "
                  "Agreement between the two diagnostics "
                  "can support interpretation of the "
                  "fitted representation, but neither "
                  "identifies a mechanistic contribution "
                  "or justifies changing a material "
                  "without experimental validation.")),
    ]
    final_appendix = page(
        "Appendix T. Recalculation and reproducibility contract",
        para("The accompanying extension directory separates model scores, "
             "row-level predictions, nested learning manifests, descriptor "
             "support and permutation results. Project-specific files "
             "record calibration bounds and source-time brackets for "
             "release, or objective grids, group omissions, numerical "
             "balance and paired-organ frontier membership for polymers. "
             "These files distinguish evaluated observations from "
             "manuscript interpretation."),
        table(pd.DataFrame([
            ["Source cohort and partitions", "SHA-256 fixed; original publication roles retained"],
            ["Primary tree baseline", "Five MAEs independently reproduced before extension reporting"],
            ["Configuration scores", "Recomputed from saved held-out endpoint predictions"],
            ["Nested learning sets", "Whole-group nesting and no held-out overlap checked"],
            ["Project-specific diagnostics", "Coverage or paired-organ objectives independently recalculated"],
            ["Resource budget", "Combined measured analysis time and peak process RSS checked"],
        ], columns=["Contract", "Verification"]), "Table S29. Executable verification of the extended results."),
        para("To reproduce on Windows, run each project's extended.py after "
             "the original run.py, then run the scientific and document "
             "tests before rebuilding the manuscripts. The extension "
             "does not download additional experimental records or "
             "modify the original results. File hashes detect a "
             "changed cohort, partition manifest or primary score "
             "file. Re-execution with a different library version "
             "should not silently replace the saved benchmark."),
        para("Recalculation establishes consistency of the computational "
             "record, not independent experimental replication. "
             "The additional tests share source observations "
             "with the primary analysis. Their purpose is "
             "to expose estimator, representation and "
             "objective sensitivity in a form that "
             "can inform a separately designed validation "
             "study with harmonized measurements."),
    )
    insertion = len(main)-2 if release else len(main)-1
    expanded = main[:insertion] + new_main + main[insertion:] + back + common + specific + [final_appendix]
    number = 0
    for section in expanded[1:]:
        if section["title"] == "References":
            break
        number += 1
        section["title"] = f"{number}. " + re.sub(r"^\d+\.\s*", "", section["title"])
        figures = [block for block in section["blocks"] if block[0] == "image"]
        if figures:
            section["blocks"] = figures + [block for block in section["blocks"] if block[0] != "image"]
    return expanded


def _block_summary(frame):
    rows = frame[(frame["nominal"] == 0.9) & (frame["method"] == "Publication-max")].copy()
    rows["Block size"] = pd.cut(rows["n"], bins=[0, 1, 3, float("inf")], labels=["1", "2-3", "4+"])
    return rows.groupby("Block size", observed=True).agg(
        block_appearances=("study", "size"), coverage=("covered", "mean"),
        mean_max_error=("max_error", "mean"), mean_width=("width", "mean")).reset_index()
