$ErrorActionPreference = "Stop"

python -m pytest -q `
  tests/test_r13_12_exposure_federation.py `
  tests/test_breach_intelligence_hibp.py `
  tests/test_darkweb_intelligence.py `
  tests/test_intelligence_source_federation.py `
  tests/test_remote_adapter_pack_1.py `
  tests/test_remote_adapter_pack_2.py `
  tests/test_remote_adapter_pack_3.py

if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
