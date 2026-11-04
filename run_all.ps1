param(
    [switch]$FetchData,
    [switch]$VerifyCitations
)

$ErrorActionPreference = "Stop"
$python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) {
    throw "Create .venv and install requirements.txt first; see README.md."
}

Push-Location $PSScriptRoot
try {
    if ($FetchData) {
        & $python "fetch_sources.py"
        if ($LASTEXITCODE -ne 0) { throw "Data retrieval failed." }
    }
    if ($VerifyCitations) {
        & $python "verify_references.py"
        if ($LASTEXITCODE -ne 0) { throw "Citation verification failed." }
    }
    $projects = & $python -c "from project_scope import selected_projects; print('\n'.join(selected_projects()))"
    if ($LASTEXITCODE -ne 0) { throw "Project selection failed." }
    foreach ($project in $projects) {
        & $python (Join-Path $project "run.py")
        if ($LASTEXITCODE -ne 0) { throw "$project primary analysis failed." }
        & $python (Join-Path $project "extended.py")
        if ($LASTEXITCODE -ne 0) { throw "$project extension failed." }
    }
    & $python -m unittest test_research.py test_acl_documents.py test_extended.py
    if ($LASTEXITCODE -ne 0) { throw "Scientific code/output tests failed." }
    & $python "build_manuscripts.py"
    if ($LASTEXITCODE -ne 0) { throw "Manuscript build failed." }
    & $python "validate_outputs.py"
    if ($LASTEXITCODE -ne 0) { throw "Output validation failed." }
} finally {
    Pop-Location
}
