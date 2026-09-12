"""
OSINT Expansion 03 local discovery-runtime verification.
No network access.
"""

from __future__ import annotations

from pathlib import Path
import shutil
import subprocess


ROOT = Path(__file__).resolve().parents[1]
BIN = ROOT / "tools" / "osint" / "bin"

TOOLS = {
    "subfinder": "subfinder.exe",
    "dnsx": "dnsx.exe",
    "gau": "gau.exe",
    "waybackurls": "waybackurls.exe",
    "katana": "katana.exe",
    "assetfinder": "assetfinder.exe",
}


def main() -> int:
    failures: list[str] = []

    print("OSINT Expansion 03 — Local Runtime Verification")
    print("=" * 60)

    for name, executable in TOOLS.items():
        path = BIN / executable

        if not path.exists():
            print(f"FAILED {name:14} missing: {path}")
            failures.append(name)
            continue

        print(
            f"READY  {name:14} "
            f"{path.stat().st_size:>12} bytes "
            f"{path}"
        )

    print("")
    if failures:
        print("Missing:", ", ".join(failures))
        print("OSINT EXPANSION 03 VERIFY: FAIL")
        return 1

    print("OSINT EXPANSION 03 VERIFY: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
