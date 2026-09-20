$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) { $Python = "python" }
& $Python -m pytest -q `
  tests/test_r13_22_corroborating_mentions.py `
  tests/test_r13_21_4_strict_url_candidate_quality.py `
  tests/test_r13_21_3_account_identity_url_fix.py `
  tests/test_r13_21_2_strict_identity_persistence.py `
  tests/test_r13_21_1_contextual_relevance.py `
  tests/test_r13_21_identity_resolution.py `
  tests/test_r13_20_2_person_name_relevance.py `
  tests/test_r13_20_1_result_cleanup.py
