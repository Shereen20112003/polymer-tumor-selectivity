"""Render the existing research content with the unmodified official ACL template."""
import hashlib
import html
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import textwrap
import unicodedata

import numpy as np
import pandas as pd
from pypdf import PdfReader
from publication_figures import MODEL_NAMES, prepare_figures

ROOT = Path(__file__).resolve().parent
AUTHOR = "Shereen Anand"
AFFILIATION = "PES University"
EMAIL = "pes1202201328@pesu.pes.edu"
TEMPLATE_COMMIT = "d5adc823ff0f80f98c80405ca0ab66c68e684409"
PRINT_YEARS = {
    "10.1038/s41573-020-0090-8": 2021,
    "10.1080/01621459.2022.2060112": 2023,
}
BOOK_AUTHORS = {
    # The book's Crossref record omits creators; verified at https://alrw.net/.
    "10.1007/b106715": ["Vladimir Vovk", "Alex Gammerman", "Glenn Shafer"],
}
CITATIONS = {
    "Bao et al., 2025": "10.1038/s41597-025-04621-9",
    "Chen et al., 2023": "10.1021/acsnano.3c04037",
    "Mitchell et al., 2021": "10.1038/s41573-020-0090-8",
    "Wilhelm et al., 2016": "10.1038/natrevmats.2016.14",
    "Sindhwani et al., 2020": "10.1038/s41563-019-0566-2",
    "Cabral et al., 2011": "10.1038/nnano.2011.166",
    "Salvati et al., 2013": "10.1038/nnano.2012.237",
    "Geurts et al., 2006": "10.1007/s10994-006-6226-1",
    "Vovk et al., 2005": "10.1007/b106715",
    "Dunn et al., 2023": "10.1080/01621459.2022.2060112",
    "Angelopoulos and Bates, 2023": "10.1561/2200000101",
    "Roberts et al., 2017": "10.1111/ecog.02881",
}


def citation_key(doi):
    return "ref" + hashlib.sha256(doi.encode("ascii")).hexdigest()[:12]


def reference_authors(doi, reference):
    authors = BOOK_AUTHORS.get(doi, reference["authors"])
    if not authors:
        raise ValueError(f"No verified authors available for {doi}")
    return authors


def escape(text, breaks=False):
    replacements = {
        "\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$",
        "#": r"\#", "_": r"\_", "{": r"\{", "}": r"\}",
        "~": r"\textasciitilde{}", "^": r"\textasciicircum{}",
    }
    text = unicodedata.normalize("NFC", html.unescape(str(text))).replace("\u00a0", " ")
    text = text.replace("\u2010", "-").replace("\u2011", "-")
    result = "".join(replacements.get(char, char) for char in text)
    if breaks:
        result = result.replace(r"\_", r"\_\allowbreak{}")
        result = result.replace("/", r"/\allowbreak{}")
    return result


def latex_text(text):
    """Translate only known markup/citations; all other source characters are escaped."""
    narrative = {key.replace(", ", " (") + ")": doi for key, doi in CITATIONS.items()}
    tokens = re.compile(
        r"(<b>.*?</b>|<br\s*/?>|https?://[^\s<>]+|\[[^\[\]]+\]|"
        r"\b[a-f0-9]{64}\b|\bR2\b|" + "|".join(re.escape(key) for key in narrative) + ")",
        re.DOTALL)
    parts, end = [], 0
    for match in tokens.finditer(text):
        parts.append(escape(text[end:match.start()]))
        value = match.group()
        if value.startswith("<b>"):
            parts.append(r"\textbf{" + latex_text(value[3:-4]) + "}")
        elif value.startswith("<br"):
            parts.append(r"\newline{}")
        elif value.startswith("http"):
            url = value.rstrip(".,;)")
            parts.append(r"\url{" + url.replace("%", r"\%") + "}" + escape(value[len(url):]))
        elif value.startswith("["):
            citations = [item.strip() for item in value[1:-1].split(";")]
            if all(item in CITATIONS for item in citations):
                parts.append(r"\citep{" + ",".join(citation_key(CITATIONS[item]) for item in citations) + "}")
            else:
                parts.append(escape(value))
        elif re.fullmatch(r"[a-f0-9]{64}", value):
            parts.append(r"\texttt{" + r"\allowbreak{}".join(
                value[i:i+8] for i in range(0, 64, 8)) + "}")
        elif value == "R2":
            parts.append(r"\(R^2\)")
        elif value in narrative:
            parts.append(r"\citet{" + citation_key(narrative[value]) + "}")
        end = match.end()
    parts.append(escape(text[end:]))
    return "".join(parts)


def bibliography_entry(doi, reference):
    fields = {
        "author": " and ".join(reference_authors(doi, reference)),
        "title": "{" + escape(reference["title"]) + "}",
        "year": str(PRINT_YEARS.get(doi, reference["year"])),
        "url": reference["url"],
        "doi": doi,
    }
    kind = "book" if doi == "10.1007/b106715" else "article"
    if kind == "book":
        fields["publisher"] = "Springer"
    else:
        fields["journal"] = escape(reference["journal"])
        if reference.get("volume"):
            fields["volume"] = reference["volume"]
        if reference.get("pages"):
            fields["pages"] = reference["pages"].replace("-", "--")
    body = ",\n".join(f"  {key} = {{{value}}}" for key, value in fields.items())
    return f"@{kind}{{{citation_key(doi)},\n{body}\n}}\n"


def make_bibliography(dois, dataset, references):
    entries = [bibliography_entry(doi, references[doi]) for doi in dois]
    if "10.17632/zzvtdrcy76.2" in dataset:
        doi = "10.17632/zzvtdrcy76.2"
        authors = references["10.1038/s41597-025-04621-9"]["authors"]
        title = "A Dataset on Formulation Parameters and Characteristics of Drug-Loaded PLGA Microparticles"
        year, repository, license_name = 2024, "Mendeley Data, version 2", "CC BY 4.0"
    elif "10.1021/acsnano.3c04037.s002" in dataset:
        doi = "10.1021/acsnano.3c04037.s002"
        authors = references["10.1021/acsnano.3c04037"]["authors"]
        title = "Supporting data for Meta-Analysis of Nanoparticle Distribution in Tumors and Major Organs in Tumor-Bearing Mice"
        year, repository, license_name = 2023, "ACS Figshare", "CC BY-NC 4.0"
    else:
        raise ValueError("Unrecognized dataset citation.")
    entries.append(
        f"@misc{{{citation_key(doi)},\n"
        f"  author = {{{' and '.join(authors)}}},\n"
        f"  title = {{{{{escape(title)}}}}},\n"
        f"  year = {{{year}}},\n"
        f"  howpublished = {{{repository}}},\n"
        f"  note = {{{license_name}}},\n"
        f"  url = {{https://doi.org/{doi}}},\n"
        f"  doi = {{{doi}}}\n}}\n"
    )
    return "\n".join(entries), [citation_key(doi) for doi in dois] + [citation_key(doi)]


def table_rows(frame):
    if isinstance(frame.columns, pd.MultiIndex):
        frame = frame.copy()
        frame.columns = [" ".join(str(x) for x in column if x) for column in frame.columns]
    rows = [[str(x) for x in frame.columns]]
    for row in frame.itertuples(index=False, name=None):
        rows.append([f"{value:.4f}" if isinstance(value, (float, np.floating)) else str(value)
                     for value in row])
    return rows


def latex_table(frame, caption, index):
    rows = table_rows(frame)
    if len(rows[0]) > 2 and (rows[0][0], rows[0][1]) in {
        ("Split", "Model"), ("seed", "method"), ("seed", "role"),
        ("id", "day"), ("hours", "cohort"),
    }:
        rows = [[row[0] + " / " + row[1], *row[2:]] for row in rows]
    names = {
        **MODEL_NAMES, "formulation_random": "Random", "publication": "Publication",
        "pooled_point": "Pointwise", "formulation_max": "Formulation-max",
        "publication_max": "Publication-max", "calibration_units": "Cal. units",
        "publication_coverage": "Study coverage", "point_coverage": "Point coverage",
        "vector_coverage": "Vector coverage", "study_macro_mae": "Study MAE",
        "spearman_tumor_vs_selectivity": "Rank correlation",
        "top_quartile_overlap_fraction": "Top-list overlap",
        "test_publications": "Test studies", "n_test": "Test n",
        "formulations": "Formul. n", "publications": "Pub. n",
    }

    def display(cell):
        return " / ".join(names.get(part, part.replace("_", " ")) for part in cell.split(" / "))

    rows = [[display(cell) for cell in row] for row in rows]
    caption = re.sub(r"^Table\s+(?:S)?\d+\.\s*", "", caption)
    panels = []
    wide_text = any(len(cell) > 30 for row in rows for cell in row)
    long_value_words = any(len(word) > 9 for row in rows for cell in row[1:] for word in cell.split())
    value_columns = 2 if wide_text or long_value_words else 3
    for start in range(1, len(rows[0]), value_columns):
        selected = [0, *range(start, min(start + value_columns, len(rows[0])))]
        panel = [[row[column] for column in selected] for row in rows]
        widths = [22] + [12] * (len(selected)-1) if len(selected) == 4 else [20] * len(selected)
        height = 0
        chunk = []
        for row in panel[1:]:
            row_height = 12 * max(len(textwrap.wrap(cell, width=width)) or 1
                                  for cell, width in zip(row, widths)) + 4
            if chunk and height + row_height > 190:
                panels.append([panel[0], *chunk])
                chunk, height = [], 0
            chunk.append(row)
            height += row_height
        if chunk:
            panels.append([panel[0], *chunk])
    if not panels:
        raise ValueError(f"Table {index} has no data rows.")
    lines = []
    for part, panel in enumerate(panels, 1):
        count = len(panel[0])
        specifications = (
            r">{\hsize=1.6\hsize\raggedright\arraybackslash}X" +
            r">{\hsize=.8\hsize\raggedright\arraybackslash}X" * 3
            if count == 4 else r">{\raggedright\arraybackslash}X" * count
        )
        lines.extend([r"\begin{table}[H]", r"\centering", r"\small"])
        if part > 1:
            lines.append(r"\ContinuedFloat")
        lines.extend([r"\begin{tabularx}{\linewidth}{@{}" + specifications + r"@{}}", r"\toprule",
                      " & ".join(r"\textbf{" + escape(cell, breaks=True) + "}" for cell in panel[0]) + r" \\",
                      r"\midrule"])
        lines.extend(" & ".join(escape(cell, breaks=True) for cell in row) + r" \\" for row in panel[1:])
        suffix = f" (Part {part} of {len(panels)}.)" if len(panels) > 1 else ""
        lines.extend([r"\bottomrule", r"\end{tabularx}",
                      r"\caption{" + latex_text(caption + suffix) + "}"])
        if part == 1:
            lines.append(rf"\label{{tab:result-{index}}}")
        lines.append(r"\end{table}")
    return "\n".join(lines)


def executable(name):
    found = shutil.which(name)
    if found:
        return found
    candidate = (Path(os.environ["LOCALAPPDATA"]) / "Programs" / "MiKTeX" /
                 "miktex" / "bin" / "x64" / (name + ".exe"))
    if not candidate.exists():
        raise FileNotFoundError(f"{name} is required. Install a LaTeX distribution or add it to PATH.")
    return str(candidate)


def compile_latex(directory):
    build = directory / ".latex-build"
    build.mkdir(exist_ok=True)
    latex = [executable("pdflatex"), "-interaction=nonstopmode", "-halt-on-error",
             "-file-line-error", "-disable-installer", "-output-directory=.latex-build",
             "manuscript.tex"]
    commands = [latex, [executable("bibtex"), r".latex-build\manuscript"], latex, latex, latex]
    for index, command in enumerate(commands, 1):
        completed = subprocess.run(command, cwd=directory, capture_output=True, text=True,
                                   encoding="utf-8", errors="replace", timeout=180)
        (build / f"pass-{index}.txt").write_text(completed.stdout + completed.stderr, encoding="utf-8")
        if completed.returncode:
            raise RuntimeError(f"{directory.name}: LaTeX/BibTeX pass {index} failed:\n"
                               + (completed.stdout + completed.stderr)[-6500:])
    log = (build / "manuscript.log").read_text(encoding="utf-8", errors="replace")
    errors = ["There were undefined references", "There were undefined citations",
              "Citation `", "Missing character:", "Label(s) may have changed"]
    if any(error in log for error in errors):
        raise RuntimeError(f"{directory.name}: unresolved LaTeX references or missing characters; inspect manuscript.log.")
    overflows = re.findall(r"Overfull \\[hv]box \(([\d.]+)pt too (?:wide|high)\)", log)
    if any(float(value) > 1 for value in overflows):
        raise RuntimeError(f"{directory.name}: content exceeds the ACL text area: {overflows}.")
    return build / "manuscript.pdf"


def verify_template(directory):
    manifest = json.loads((ROOT / "acl_template_manifest.json").read_text())
    if manifest["commit"] != TEMPLATE_COMMIT:
        raise ValueError("ACL template commit does not match the recorded version.")
    for item in manifest["files"]:
        if item["project"] == directory.name:
            digest = hashlib.sha256((directory / item["file"]).read_bytes()).hexdigest()
            if digest != item["sha256"]:
                raise ValueError(f"Official ACL file was modified: {item['file']}")


def heading_page(reader, heading):
    for number, pdf_page in enumerate(reader.pages, 1):
        found = []

        def visitor(text, _cm, _tm, _font, size):
            if text.strip() == heading and size >= 11.5:
                found.append(True)

        pdf_page.extract_text(visitor_text=visitor)
        if found:
            return number
    raise ValueError(f"Rendered heading is missing: {heading}")


def figure_heading_spacing(reader, main_pages):
    positions = []
    for number, pdf_page in enumerate(reader.pages[:main_pages], 1):
        headings, plots = [], []

        def collect_heading(value, _cm, tm, font, size):
            name = str(font.get("/BaseFont", "")) if font else ""
            if value.strip() and abs(size - 11.9552) < 0.05 and ("Medi" in name or "Bold" in name):
                headings.append({"text": value.strip(), "x": tm[4], "y": tm[5]})

        def collect_plot(operator, operands, cm, _tm):
            if operator != b"Do" or not str(operands[0]).startswith("/Im"):
                return
            form = pdf_page["/Resources"]["/XObject"][operands[0]].get_object()
            box = form.get("/BBox")
            if box is None or cm[1] != 0 or cm[2] != 0:
                raise ValueError("Expected an unrotated vector publication figure.")
            plots.append({"x": cm[4], "top": cm[5] + cm[3] * float(box[3])})

        pdf_page.extract_text(visitor_text=collect_heading, visitor_operand_before=collect_plot)
        for plot in plots:
            preceding = [heading for heading in headings
                         if abs(heading["x"] - plot["x"]) < 35 and heading["y"] > plot["top"]]
            if not preceding:
                raise ValueError(f"Page {number}: figure has no preceding section heading in its column.")
            heading = min(preceding, key=lambda item: item["y"])
            gap = heading["y"] - plot["top"]
            if gap > 40:
                raise ValueError(f"Page {number}: figure is {gap:.1f} pt below its heading; maximum is 40 pt.")
            positions.append({"page": number, "heading": heading["text"],
                              "heading_to_plot_gap_pt": round(gap, 2)})
    return positions


def render(folder, title, sections, references):
    directory = ROOT / folder
    verify_template(directory)
    prepare_figures(directory)
    bibliography_section = next(item for item in sections if item["title"] == "References")
    last_main_heading = sections[sections.index(bibliography_section)-1]["title"]
    dois, dataset = next(value for kind, value in bibliography_section["blocks"] if kind == "bibliography")
    bib, keys = make_bibliography(dois, dataset, references)
    (directory / "references.bib").write_text(bib, encoding="utf-8")
    tex = [
        r"\documentclass[11pt]{article}",
        r"\usepackage[final]{acl}",
        r"\usepackage{times}", r"\usepackage{latexsym}",
        r"\usepackage[T1]{fontenc}", r"\usepackage[utf8]{inputenc}",
        r"\usepackage{microtype}", r"\usepackage{inconsolata}",
        r"\usepackage{graphicx}", r"\usepackage{booktabs}", r"\usepackage{tabularx}",
        r"\usepackage{placeins}", r"\usepackage{float}",
        r"\usepackage{amsmath}",
        r"\usepackage{needspace}",
        r"\title{" + escape(title) + "}",
        r"\author{" + escape(AUTHOR) + r" \\ " + escape(AFFILIATION) +
        r" \\ \texttt{" + escape(EMAIL) + "}}",
        r"\begin{document}", r"\raggedbottom", r"\maketitle",
    ]
    markdown = [f"# {title}\n", f"{AUTHOR} | {AFFILIATION} | {EMAIL}\n"]
    first = sections[0]["blocks"]
    paragraphs = [value for kind, value in first if kind == "paragraph"]
    abstract = [value for value in paragraphs if not value.startswith("<b>Keywords:</b>")]
    keywords = [value for value in paragraphs if value.startswith("<b>Keywords:</b>")]
    if not abstract or not abstract[0].startswith("<b>Abstract.</b>") or len(keywords) != 1:
        raise ValueError(f"{folder}: expected an abstract followed by one keywords paragraph.")
    abstract[0] = abstract[0].removeprefix("<b>Abstract.</b> ")
    tex.append(r"\begin{abstract}")
    tex.append(" ".join(latex_text(value) for value in abstract))
    tex.append(r"\end{abstract}")
    markdown.extend(["## Abstract\n", *[value.replace("<b>", "**").replace("</b>", "**") + "\n"
                                      for value in abstract]])
    tex.append(latex_text(keywords[0]) + "\n")
    markdown.append(keywords[0] + "\n")
    table_index = figure_index = 0
    appendix = False
    for section in sections[1:]:
        heading = section["title"]
        if heading == "References":
            tex.extend([r"\label{main-text-end}",
                        r"\clearpage",
                        r"\nocite{" + ",".join(keys) + "}", r"\bibliography{references}"])
        elif heading.startswith("Appendix "):
            if not appendix:
                tex.extend([r"\clearpage", r"\appendix", r"\setcounter{table}{0}",
                            r"\renewcommand{\thetable}{S\arabic{table}}"])
                appendix = True
            heading = re.sub(r"^Appendix [A-Z]\.\s*", "", heading)
            tex.append(r"\section{" + escape(heading) + "}")
        else:
            if heading == last_main_heading:
                tex.append(r"\FloatBarrier")
            heading = re.sub(r"^\d+\.\s*", "", heading)
            if section["blocks"] and section["blocks"][0][0] == "image":
                file, caption, _ = section["blocks"][0][1]
                plot_page = PdfReader(directory / "figures" / Path(file).with_suffix(".pdf").name).pages[0]
                aspect = float(plot_page.mediabox.height) / float(plot_page.mediabox.width)
                caption_lines = max(1, len(textwrap.wrap(caption, width=45)))
                heading_lines = max(1, len(textwrap.wrap(heading, width=35)))
                extra = 65 + 14 * heading_lines + 12 * caption_lines
                tex.append(r"\Needspace{\dimexpr " + f"{aspect:.6f}" +
                           r"\columnwidth+" + f"{extra}pt" + r"\relax}")
            tex.append(r"\section{" + escape(heading) + "}")
        markdown.append(f"\n## {heading}\n")
        for kind, value in section["blocks"]:
            if kind == "paragraph":
                tex.append(latex_text(value) + "\n")
                markdown.append(value.replace("<b>", "**").replace("</b>", "**").replace("<br/>", "\n") + "\n")
            elif kind == "table":
                table_index += 1
                frame, caption = value
                tex.append(latex_table(frame, caption, table_index))
                rows = table_rows(frame)
                markdown.append("| " + " | ".join(rows[0]) + " |")
                markdown.append("|" + "|".join("---" for _ in rows[0]) + "|")
                markdown.extend("| " + " | ".join(row) + " |" for row in rows[1:])
                markdown.append("\n" + caption + "\n")
            elif kind == "image":
                figure_index += 1
                file, caption, _ = value
                caption = re.sub(r"^Figure\s+\d+\.\s*", "", caption)
                plot = Path(file).with_suffix(".pdf").name
                tex.extend([r"\begin{figure}[H]", r"\centering",
                            r"\includegraphics[width=\linewidth]{figures/" + plot + "}",
                            r"\caption{" + latex_text(caption) + "}",
                            rf"\label{{fig:result-{figure_index}}}", r"\end{figure}"])
                markdown.append(f"![{caption}](figures/{file})\n")
            elif kind == "equation":
                tex.extend([r"\begin{equation}", value, r"\end{equation}"])
                markdown.append("$$\n" + value + "\n$$\n")
            elif kind == "bibliography":
                for doi in dois:
                    ref = references[doi]
                    markdown.append(f"{'; '.join(reference_authors(doi, ref))}. {ref['title']}. "
                                    f"{PRINT_YEARS.get(doi, ref['year'])}. https://doi.org/{doi}\n")
                markdown.append(dataset + "\n")
            else:
                raise ValueError(f"Unsupported content block: {kind}")
    tex.extend([r"\FloatBarrier", r"\end{document}", ""])
    source = "\n".join(tex)
    (directory / "manuscript.tex").write_text(source, encoding="utf-8")
    built_pdf = compile_latex(directory)
    reader = PdfReader(built_pdf)
    aux = (directory / ".latex-build" / "manuscript.aux").read_text(encoding="utf-8")
    main_end = re.search(r"\\newlabel\{main-text-end\}\{\{[^}]*\}\{(\d+)\}", aux)
    if main_end is None:
        raise ValueError(f"{folder}: main-text boundary label is missing.")
    text = [p.extract_text() for p in reader.pages]
    figure_positions = figure_heading_spacing(reader, int(main_end.group(1)))
    if len(figure_positions) != figure_index:
        raise ValueError(f"{folder}: could not verify every figure's heading adjacency.")
    reference_page = heading_page(reader, "References")
    appendix_page = next(i+1 for i, body in enumerate(text)
                         if re.search(r"A\s+Source (?:integrity|provenance)", body))
    for pdf_page in reader.pages:
        width, height = float(pdf_page.mediabox.width), float(pdf_page.mediabox.height)
        if abs(width - 595.276) > 1 or abs(height - 841.89) > 1:
            raise ValueError("ACL PDF is not A4.")
    if any(len(body.strip()) < 100 for body in text):
        raise ValueError(f"{folder}: unexpectedly blank rendered page.")
    shutil.copyfile(built_pdf, directory / "manuscript.pdf")
    (directory / "manuscript.md").write_text("\n".join(markdown), encoding="utf-8")
    validation = {
        "pages": len(reader.pages), "main_text_pages": int(main_end.group(1)),
        "references_start_page": reference_page, "appendix_start_page": appendix_page,
        "references_appendix_pages": len(reader.pages)-reference_page+1,
        "appendix_pages": len(reader.pages)-appendix_page+1,
        "characters_per_page": [len(body) for body in text], "author": AUTHOR,
        "format": "Official ACL LaTeX, final mode", "template_commit": TEMPLATE_COMMIT,
        "pagination": "Natural flow; no fixed page count or custom font/margin overrides",
        "boundary_note": "Main text, references and appendices start on separate pages.",
        "content_sections": len(sections), "tables": table_index, "figures": figure_index,
        "bibliography_notes": {
            "print_years": PRINT_YEARS,
            "print_year_verification": "Crossref published-print dates, exact DOI lookups",
            "book_creators_verification": "https://alrw.net/ (2005 first edition)",
        },
        "figure_layout": "Column-width vector plots placed within the results text",
        "figure_heading_spacing": figure_positions,
    }
    (directory / "document_validation.json").write_text(json.dumps(validation, indent=2), encoding="utf-8")
    print(folder, "ACL final PDF:", validation)
