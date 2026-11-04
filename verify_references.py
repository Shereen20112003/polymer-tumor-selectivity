"""Resolve citation metadata from Crossref; never generate bibliographic details."""
import json
from pathlib import Path
import urllib.parse
import urllib.request
import sys

sys.stdout.reconfigure(errors="backslashreplace")

ROOT = Path(__file__).resolve().parent
DOIS = [
    "10.1038/s41597-025-04621-9",
    "10.17632/zzvtdrcy76.2",
    "10.3390/pharmaceutics18070805",
    "10.1021/acsnano.3c04037",
    "10.1021/acsnano.3c04037.s002",
    "10.1038/s41573-020-0090-8",
    "10.1038/natrevmats.2016.14",
    "10.1038/s41563-019-0566-2",
    "10.1038/nnano.2011.166",
    "10.1038/nnano.2012.237",
    "10.1007/s10994-006-6226-1",
    "10.1016/j.patter.2023.100804",
    "10.1111/ecog.02881",
    "10.1561/2200000101",
    "10.1007/b106715",
    "10.1002/jps.2600501018",
    "10.1016/0168-3659(87)90034-4",
    "10.1080/01621459.2022.2060112",
    "10.1016/j.jconrel.2026.115103",
]


def retrieve(url):
    with urllib.request.urlopen(urllib.request.Request(
            url, headers={"User-Agent": "Research-reference-verification/1.0"}), timeout=90) as response:
        return json.load(response)


def main():
    path = ROOT / "reference_metadata.json"
    records = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    for doi in DOIS:
        if doi in records:
            continue
        # Mendeley/Figshare data DOIs have their own checked metadata endpoints.
        if doi in ["10.17632/zzvtdrcy76.2", "10.1021/acsnano.3c04037.s002"]:
            continue
        message = retrieve("https://api.crossref.org/works/" + urllib.parse.quote(doi, safe=""))["message"]
        records[doi] = {
            "doi": message["DOI"], "title": message["title"][0],
            "authors": [a.get("given", "") + " " + a.get("family", "") for a in message.get("author", [])],
            "year": message["issued"]["date-parts"][0][0],
            "journal": next(iter(message.get("container-title", [])), ""),
            "volume": message.get("volume", ""), "pages": message.get("page", ""),
            "url": message["URL"], "verification": "Crossref exact DOI lookup",
        }
        path.write_text(json.dumps(records, indent=2), encoding="utf-8")
        print(doi, records[doi]["title"])


if __name__ == "__main__":
    main()
