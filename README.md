# Polymer tumour/liver selectivity

Author: Shereen Anand, PES University.

[Manuscript PDF](manuscript.pdf) | [Supplementary ZIP](supplementary.zip) | [PNG pictures](pictures) | [Project documentation](02_polymer_targeting/README.md)

## Contents

The project is in `02_polymer_targeting`; shared analysis and ACL document tools are at the repository root. The explicit project-selection manifest lets the build, tests and validation run independently of the companion study. Saved data, source attribution, predictions, partitions, ablations and vector/PNG figures are included. Virtual environments, build caches, credentials and third-party article XML are excluded.

## Reproduce

Python 3.12 is the tested runtime. From this repository root:

```powershell
python -m venv .venv
& ".\.venv\Scripts\python.exe" -m pip install -r requirements.txt
& ".\run_all.ps1"
```

For validation without rerunning the analyses:

```powershell
& ".\.venv\Scripts\python.exe" -m unittest test_research.py test_acl_documents.py test_extended.py
& ".\.venv\Scripts\python.exe" ".\validate_outputs.py"
```

PDF rebuilding requires pdfLaTeX, BibTeX and the unmodified included ACL files. Required packages include times, latexsym, microtype, inconsolata, graphicx, booktabs, tabularx, placeins, float, amsmath and needspace. The original saved inputs are included; downloading again is optional. Tests explicitly skip checks belonging only to the companion project, not missing files within this declared project.

## Attribution and reuse

Chen et al., ACS Figshare supporting workbook, DOI 10.1021/acsnano.3c04037.s002: CC BY-NC 4.0. Noncommercial and attribution restrictions apply to the source dataset.

The included ACL template files retain their upstream notices and pinned hashes; see `acl_template_manifest.json` and https://github.com/acl-org/acl-style-files. No blanket license for original research code is granted by this repository. Source dataset and template licenses remain separate.

These are exploratory secondary-data analyses, not new therapeutic experiments. Scientific limitations and the post-primary status of the extended analyses remain in the manuscript. No journal acceptance or treatment efficacy is implied.
