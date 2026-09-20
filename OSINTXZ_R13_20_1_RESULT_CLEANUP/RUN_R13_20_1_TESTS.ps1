$ErrorActionPreference = "Stop"
$root = Resolve-Path (Join-Path $PSScriptRoot "..")
& "$root\.venv\Scripts\python.exe" -m pytest -q `
  tests/test_r13_20_1_result_cleanup.py `
  tests/test_r13_20_unified_investigation_search.py `
  tests/test_m021_qml_recursive_collection.py `
  tests/test_qml_desktop_bridge.py
