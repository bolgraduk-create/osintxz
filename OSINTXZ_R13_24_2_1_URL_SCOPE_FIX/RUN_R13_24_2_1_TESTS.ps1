$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) { $python = "python" }
& $python -m pytest -q tests/test_r13_24_2_1_url_scope_fix.py tests/test_r13_24_2_balanced_relevance.py tests/test_r13_21_4_strict_url_candidate_quality.py
