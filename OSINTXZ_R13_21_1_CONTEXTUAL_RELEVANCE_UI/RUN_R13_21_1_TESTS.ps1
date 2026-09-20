$ErrorActionPreference = "Stop"
$root = Resolve-Path (Join-Path $PSScriptRoot "..")
$python = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) { $python = "python" }
& $python -m pytest -q `
  tests/test_r13_21_1_contextual_relevance.py `
  tests/test_r13_21_identity_resolution.py `
  tests/test_r13_20_2_person_name_relevance.py `
  tests/test_r13_20_1_result_cleanup.py `
  tests/test_r13_20_unified_investigation_search.py `
  tests/test_m021_qml_recursive_collection.py `
  tests/test_qml_desktop_bridge.py
