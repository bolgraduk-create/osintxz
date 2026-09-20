$ErrorActionPreference = "Stop"
$root = Resolve-Path (Join-Path $PSScriptRoot "..")
$python = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) { $python = "python" }
& $python -m pytest -q tests/test_r13_24_adaptive_relevance_connector_health.py tests/test_r13_22_corroborating_mentions.py tests/test_r13_21_4_strict_url_candidate_quality.py tests/test_qml_desktop_bridge.py
