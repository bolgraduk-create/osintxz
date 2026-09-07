from __future__ import annotations
import subprocess
import sys

TESTS = [
    "tests/test_m021_15_target_detection.py",
    "tests/test_m021_15_ui_wiring.py",
    "tests/test_m021_14_1_composition_order.py",
    "tests/test_m021_14_open_web_recursive_pivots.py",
    "tests/test_m021_13_open_web_warc_extraction_persistence_e2e.py",
]

def main():
    print("=" * 72)
    print("M021.15 INVESTIGATION SEARCH UI GATE")
    print("=" * 72)
    completed = subprocess.run(
        [sys.executable, "-m", "pytest", *TESTS, "-q"],
        check=False,
    )
    if completed.returncode != 0:
        print("\nM021.15 GATE: FAIL")
        return completed.returncode
    print("\nM021.15 GATE: PASS")
    print("Target detection: PASS")
    print("Desktop wiring: PASS")
    print("Composition-order regression: PASS")
    print("Recursive pivot regression: PASS")
    print("WARC persistence regression: PASS")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
