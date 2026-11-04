"""Download public research inputs; record provenance without uploading local data."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import urllib.request
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent


def fetch(url, destination):
    destination = destination.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    downloaded = not destination.exists()
    if downloaded:
        request = urllib.request.Request(url, headers={"User-Agent": "Research-reanalysis/1.0"})
        with urllib.request.urlopen(request, timeout=90) as response:
            data = response.read()
        destination.write_bytes(data)
    return {
        "url": url, "file": str(destination.relative_to(ROOT)),
        "sha256": hashlib.sha256(destination.read_bytes()).hexdigest(),
        "bytes": destination.stat().st_size,
        "checked_utc": datetime.now(timezone.utc).isoformat(),
        "downloaded_now": downloaded,
    }


def main():
    plga = ROOT / "01_release_transfer" / "data"
    tumor = ROOT / "02_polymer_targeting" / "data"
    mirror = "https://raw.githubusercontent.com/SananCh/plga-inverse-pinn/387a2f831853a0d6ff1f7f8a91a75bc64b6d19b8/plga_dataset/"
    records = [
        fetch(mirror + name, plga / name)
        for name in ["mp_dataset_initial_formulation.xlsx", "mp_dataset_processed.xlsx"]
    ]
    records.append(fetch("https://www.ebi.ac.uk/europepmc/webservices/rest/PMC11873201/fullTextXML",
                         plga / "source_article.xml"))
    records.append(fetch("https://api.figshare.com/v2/articles/24274513", tumor / "figshare_metadata.json"))
    metadata = json.loads((tumor / "figshare_metadata.json").read_text())
    for file in metadata["files"]:
        destination = tumor / file["name"]
        records.append(fetch(file["download_url"], destination))
        digest = hashlib.md5(destination.read_bytes()).hexdigest()
        if digest != file["computed_md5"] or destination.stat().st_size != file["size"]:
            raise ValueError(f"Figshare file integrity mismatch: {file['name']}")
    records.append(fetch("https://www.ebi.ac.uk/europepmc/webservices/rest/PMC10604101/fullTextXML",
                         tumor / "source_article_2023.xml"))
    for directory, subset in [(plga, records[:3]), (tumor, records[3:])]:
        (directory / "download_manifest.json").write_text(json.dumps(subset, indent=2), encoding="utf-8")
    for file in [plga / "source_article.xml", tumor / "source_article_2023.xml"]:
        root = ET.parse(file).getroot()
        print(file.parent.parent.name, "LICENSE:", " ".join(
            "".join(node.itertext()) for node in root.findall(".//permissions")))
        for node in root.findall(".//supplementary-material"):
            print("SUPPLEMENT", ET.tostring(node, encoding="unicode")[:1500])
    import pandas as pd
    for directory in [plga, tumor]:
        for file in directory.glob("*.xlsx"):
            book = pd.ExcelFile(file)
            print("\nFILE", file.name, "SHEETS", book.sheet_names)
            for sheet in book.sheet_names[:5]:
                frame = pd.read_excel(file, sheet_name=sheet)
                print("SHEET", sheet, frame.shape, "COLUMNS", frame.columns.tolist())
                print(frame.head(3).to_string(index=False))


if __name__ == "__main__":
    main()
