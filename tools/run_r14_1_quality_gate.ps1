$ErrorActionPreference = "Stop"

function Invoke-Checked {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name,

        [Parameter(Mandatory = $true)]
        [scriptblock]$Command
    )

    Write-Host ""
    Write-Host "=== $Name ===" -ForegroundColor Cyan
    & $Command

    if ($LASTEXITCODE -ne 0) {
        throw "$Name failed with exit code $LASTEXITCODE."
    }
}

Write-Host "OSINTXZ R14.1 Production Foundation Gate" -ForegroundColor Green

Invoke-Checked -Name "Compile Python sources" -Command {
    python -m compileall -q app tests tools
}

Invoke-Checked -Name "Check Alembic heads" -Command {
    python -m alembic heads
}

Invoke-Checked -Name "Upgrade database to Alembic head" -Command {
    python -m alembic upgrade head
}

Invoke-Checked -Name "Show current Alembic revision" -Command {
    python -m alembic current
}

$RegressionTests = @(
    "tests/test_bootstrap_architecture_contract.py",
    "tests/test_final_stabilization_contract.py",
    "tests/test_golden_investigation_fixture.py",
    "tests/test_r13_26b_search_quality_benchmark.py",
    "tests/test_m024a_evidence_confidence_integration.py",
    "tests/test_m024b_evidence_confidence_propagation.py",
    "tests/test_m024c_confidence_ui.py",
    "tests/test_m025a_evidence_explainability.py",
    "tests/test_m025b_unified_explainability.py",
    "tests/test_m025c_unified_why_ui.py"
)

Invoke-Checked -Name "Architecture and intelligence regression gate" -Command {
    python -m pytest -q @RegressionTests
}

Invoke-Checked -Name "Search quality benchmark gate" -Command {
    python tools/run_r13_26b_search_quality_benchmark.py
}

Write-Host ""
Write-Host "R14.1 QUALITY GATE: PASS" -ForegroundColor Green
