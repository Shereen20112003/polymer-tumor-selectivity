"""Focused tests for the ACL conversion; no scientific experiments are rerun."""
import unittest
from pathlib import Path

import pandas as pd
from project_scope import selected_projects

from acl_documents import (
    bibliography_entry, citation_key, escape, latex_table, latex_text, make_bibliography,
)


class ACLConversionTests(unittest.TestCase):
    def test_reserved_characters_are_escaped(self):
        self.assertEqual(escape("A&B_50%"), r"A\&B\_50\%")
        self.assertEqual(latex_text("<b>MAE.</b> 5%"), r"\textbf{MAE.} 5\%")

    def test_urls_and_hashes_are_breakable(self):
        self.assertIn(r"\url{https://doi.org/10.1007/b106715}", latex_text("https://doi.org/10.1007/b106715."))
        self.assertEqual(latex_text("a"*64).count(r"\allowbreak{}"), 7)

    def test_author_year_citations_use_natbib(self):
        key = citation_key("10.1038/s41597-025-04621-9")
        self.assertEqual(latex_text("Bao et al. (2025)"), rf"\citet{{{key}}}")
        self.assertEqual(latex_text("[Bao et al., 2025]"), rf"\citep{{{key}}}")
        self.assertEqual(latex_text("[0,1]"), "[0,1]")

    def test_citation_groups_preserve_all_sources(self):
        result = latex_text("[Vovk et al., 2005; Dunn et al., 2023]")
        self.assertEqual(result, r"\citep{" + citation_key("10.1007/b106715") + "," +
                         citation_key("10.1080/01621459.2022.2060112") + "}")

    def test_tables_stay_in_column_without_rescaling_fonts(self):
        frame = pd.DataFrame([[1, 2, 3, 4]], columns=["A", "B", "C", "D"])
        rendered = latex_table(frame, "Table S1. Test caption.", 1)
        self.assertIn(r"\begin{table}[H]", rendered)
        self.assertIn(r"\caption{Test caption.}", rendered)
        self.assertNotIn(r"\resizebox", rendered)
        self.assertNotIn(r"\scriptsize", rendered)
        self.assertNotIn(r"\begin{table*}", rendered)

    def test_wide_table_panels_preserve_values_and_row_identifiers(self):
        frame = pd.DataFrame([["sample", 1, 2, 3, 4, 5]], columns=["ID", "A", "B", "C", "D", "E"])
        rendered = latex_table(frame, "Table 1. All measurements.", 2)
        self.assertEqual(rendered.count("sample"), 2)
        self.assertEqual(rendered.count(r"\ContinuedFloat"), 1)
        self.assertEqual(rendered.count(r"\label{tab:result-2}"), 1)
        for value in range(1, 6):
            self.assertRegex(rendered, rf" & {value}(?: &| \\\\)")

    def test_long_table_continues_without_dropping_rows(self):
        frame = pd.DataFrame([[f"record-{i}", "Long descriptive text " * 4] for i in range(15)],
                             columns=["Record", "Description"])
        rendered = latex_table(frame, "Table 1. Descriptions.", 1)
        self.assertIn(r"\ContinuedFloat", rendered)
        for i in range(15):
            self.assertEqual(rendered.count(f"record-{i} &"), 1)

    def test_print_year_and_missing_creator_handling(self):
        record = {"authors": ["A. Author"], "title": "Title", "year": 2020,
                  "url": "https://doi.org/10.1038/s41573-020-0090-8", "journal": "Journal"}
        entry = bibliography_entry("10.1038/s41573-020-0090-8", record)
        self.assertIn("year = {2021}", entry)
        record["authors"] = []
        with self.assertRaises(ValueError):
            bibliography_entry("unknown-doi", record)
        book = bibliography_entry("10.1007/b106715", record)
        self.assertIn("Vladimir Vovk and Alex Gammerman and Glenn Shafer", book)

    def test_dataset_has_its_own_bibliography_key(self):
        doi = "10.1038/s41597-025-04621-9"
        record = {"authors": ["Zeqing Bao"], "title": "Title", "year": 2025,
                  "url": "https://doi.org/" + doi, "journal": "Scientific Data"}
        bibliography, keys = make_bibliography([doi], "https://doi.org/10.17632/zzvtdrcy76.2", {doi: record})
        self.assertEqual(keys, [citation_key(doi), citation_key("10.17632/zzvtdrcy76.2")])
        self.assertIn("CC BY 4.0", bibliography)

    def test_results_figures_immediately_follow_their_section_heading(self):
        from build_manuscripts import release_pages, polymer_pages, para, table, image, page
        from expanded_manuscripts import expand
        for builder in [release_pages, polymer_pages]:
            expected = "01_release_transfer" if builder == release_pages else "02_polymer_targeting"
            if expected not in selected_projects():
                continue
            folder, _, sections = builder()
            sections = expand(folder, sections, para, table, image, page)
            for section in sections:
                if any(kind == "image" for kind, _ in section["blocks"]):
                    self.assertEqual(section["blocks"][0][0], "image", section["title"])
            source = (Path(__file__).resolve().parent / folder / "manuscript.tex").read_text(encoding="utf-8")
            self.assertIn(r"\raggedbottom", source)
            self.assertEqual(source.count(r"\Needspace"), 4)


if __name__ == "__main__":
    unittest.main(verbosity=2)
