$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) { $Python = "python" }
& $Python -m pytest -q tests/test_r13_24_1_username_recovery.py tests/test_r13_24_adaptive_relevance_connector_health.py tests/test_r13_21_4_strict_url_candidate_quality.py tests/test_qml_desktop_bridge.py
