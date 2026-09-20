$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
& "$ProjectRoot\.venv\Scripts\python.exe" -m pytest -q `
  tests/test_r13_18_source_center_ui.py `
  tests/test_r13_17_low_footprint_remote_pack_2.py `
  tests/test_r13_16_low_footprint_remote_pack.py `
  tests/test_r13_15_free_public_data_pack.py `
  tests/test_r13_14_darkweb_discovery_indexing.py `
  tests/test_r13_13_leak_paste_source_pack.py `
  tests/test_r13_12_exposure_federation.py `
  tests/test_m021_qml_recursive_collection.py `
  tests/test_m022_registry_ui.py `
  tests/test_qml_desktop_bridge.py
