"""Declare the projects included in a standalone repository export."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROJECTS = ["01_release_transfer", "02_polymer_targeting"]


def selected_projects():
    manifest = ROOT / "project_selection.json"
    projects = json.loads(manifest.read_text(encoding="utf-8"))["projects"] if manifest.exists() else PROJECTS
    if not projects or len(projects) != len(set(projects)) or any(project not in PROJECTS for project in projects):
        raise ValueError("Invalid project selection manifest.")
    for project in projects:
        if not (ROOT / project / "run.py").is_file():
            raise FileNotFoundError(f"Declared project is missing: {project}")
    return projects
