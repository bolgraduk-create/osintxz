param(
    [string]$ProjectRoot = "C:\osintxz"
)

$ErrorActionPreference = "Stop"
Set-Location $ProjectRoot

$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    $Python = "python"
}

& $Python -m pytest -q `
    tests/test_r13_13_leak_paste_source_pack.py `
    tests/test_r13_12_exposure_federation.py `
    tests/test_breach_intelligence_hibp.py `
    tests/test_darkweb_intelligence.py `
    tests/test_intelligence_source_federation.py `
    tests/test_remote_adapter_pack_1.py `
    tests/test_remote_adapter_pack_2.py `
    tests/test_remote_adapter_pack_3.py

exit $LASTEXITCODE
