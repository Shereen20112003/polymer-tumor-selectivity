# Polymer nanoparticle tumour/liver selectivity

Run from the parent workspace:

```powershell
& ".\.venv\Scripts\python.exe" ".\02_polymer_targeting\run.py"
```

The experiment uses the experimental Nano-Tumor Database supporting workbook
from Chen et al. (2023), DOI
[10.1021/acsnano.3c04037.s002](https://doi.org/10.1021/acsnano.3c04037.s002),
under **CC BY-NC 4.0**.

- Primary cohort: exact source material category `Polymeric`, paired 24-hour
  tumour/liver whole-organ `%ID`.
- Objectives: tumour accumulation versus the log10 tumour/liver ratio.
- Ranking audit: Spearman correlation and top-quartile shortlist overlap.
- Association audit: pooled and equal-weight within-publication Active/Passive
  contrasts; publication-cluster bootstrap intervals.
- Predictive baselines: median, ridge and extra trees, with no-targeting,
  physicochemical-only and permuted-target ablations.
- Sensitivities: 6/24/48 hours; adding source Hydrogel and Dendrimer categories.
- Integrity: connected slash-linked reference groups; HD-only hydrodynamic
  diameter; no temporal extrapolation, pseudocounts or organ imputation.

See [manuscript.pdf](manuscript.pdf), [editable text](manuscript.md) and
[results](results). Root-level utilities are required for reproduction.

Run the additional exploratory analyses after the primary experiment:

```powershell
& ".\.venv\Scripts\python.exe" ".\02_polymer_targeting\extended.py"
```

The [extended results](results/extended) include parameter/feature-block
ablations, nested publication learning curves, descriptor support and
permutation diagnostics, objective-weight and shortlist-size grids,
publication-omission influence, numerical balance, denominator sensitivities
and a mathematical-coupling diagnostic. The original primary scores are
reproduced. These extensions are exploratory and do not estimate a causal
targeting benefit. The expanded manuscript targets about eight main-text
pages plus at least ten appendix pages, with references additional.

The PDF uses the official **ACL final/camera-ready** two-column LaTeX style,
with natural pagination and visible author details. Editable
[LaTeX source](manuscript.tex), [BibTeX references](references.bib), and the
unmodified ACL style files are included. Rebuild through the parent
`build_manuscripts.py`; no experiment rerun is needed for formatting changes.
Column-width vector plots in [figures](figures) are regenerated from saved results
and embedded beside the results discussion. Continued table panels preserve all
reported values at readable type size. Draft banners and manuscript-preparation
disclosures are omitted; scientific limitations remain.

The targeting association is **not causal**, and the ratio is **not** a
therapeutic index or toxicity measurement. This study does not demonstrate a
new polymer, cancer efficacy, blood-brain-barrier transport or brain targeting.
The original database and organ-distribution analysis are explicitly attributed.
