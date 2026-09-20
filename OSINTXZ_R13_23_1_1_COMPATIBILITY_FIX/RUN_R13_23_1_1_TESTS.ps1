$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) { $Python = "python" }
& $Python -m pytest -q `
  tests/test_r13_23_1_1_compatibility.py `
  tests/test_r13_23_1_person_card_mentions.py `
  tests/test_r13_23_person_card_v2.py `
  tests/test_r13_22_corroborating_mentions.py `
  tests/test_qml_desktop_bridge.py
