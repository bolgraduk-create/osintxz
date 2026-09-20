param(
    [string]$ProjectRoot = "C:\osintxz"
)

Set-Location $ProjectRoot
python -m pytest -q `
  tests/test_r13_19_full_registry_ui.py `
  tests/test_r13_18_source_center_ui.py `
  tests/test_m022_registry_ui.py `
  tests/test_m022_1_registry_core_router.py `
  tests/test_registry_search_ui.py `
  tests/test_registry_companies_house.py `
  tests/test_registry_courtlistener.py `
  tests/test_registry_opencorporates.py `
  tests/test_registry_poland_krs.py `
  tests/test_registry_recap_pacer.py `
  tests/test_registry_vies.py `
  tests/test_registry_persistence_integration.py
