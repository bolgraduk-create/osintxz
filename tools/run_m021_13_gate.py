from __future__ import annotations
import subprocess
import sys

TESTS = [
    "tests/test_m021_13_open_web_warc_extraction_persistence_e2e.py",
    "tests/test_common_crawl_warc_content.py",
    "tests/test_open_web_content_hydration.py",
    "tests/test_common_crawl_raw_index.py",
    "tests/test_common_crawl_metadata_fallback.py",
    "tests/test_m021_12_service_container.py",
    "tests/test_m021_12_1_service_container.py",
]

def main():
    print("=" * 72)
    print("M021.13 OPEN-WEB WARC EXTRACTION/PERSISTENCE GATE")
    print("=" * 72)
    completed = subprocess.run(
        [sys.executable, "-m", "pytest", *TESTS, "-q"],
        check=False,
    )
    if completed.returncode != 0:
        print("\nM021.13 GATE: FAIL")
        return completed.returncode
    print("\nM021.13 GATE: PASS")
    print("WARC hydration: PASS")
    print("Unified extraction: PASS")
    print("Persistence integration: PASS")
    print("Idempotency: PASS")
    print("M021.12/M021.12.1 regression: PASS")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
