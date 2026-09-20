$ErrorActionPreference = "Stop"
$root = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $root
python -m pytest -q `
  tests/test_r13_20_unified_investigation_search.py `
  tests/test_r13_19_full_registry_ui.py `
  tests/test_r13_18_source_center_ui.py `
  tests/test_r13_17_low_footprint_remote_pack_2.py `
  tests/test_r13_16_low_footprint_remote_pack.py `
  tests/test_r13_15_free_public_data_pack.py `
  tests/test_m021_qml_recursive_collection.py `
  tests/test_m022_registry_ui.py `
  tests/test_registry_search_ui.py `
  tests/test_qml_desktop_bridge.py
