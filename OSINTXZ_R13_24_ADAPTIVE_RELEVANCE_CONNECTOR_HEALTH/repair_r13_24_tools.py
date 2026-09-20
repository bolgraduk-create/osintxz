from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path
import shutil
import subprocess
import sys

TOOLS = (
    ("Sherlock", "sherlock", "sherlock_project", "sherlock-project"),
    ("Maigret", "maigret", "maigret", "maigret"),
    ("User Scanner", "user-scanner", "user_scanner", "user-scanner"),
)


def project_python(root: Path) -> Path:
    candidate = root / ".venv" / "Scripts" / "python.exe"
    return candidate if candidate.is_file() else Path(sys.executable)


def module_exists(py: Path, module: str) -> bool:
    code = f"import importlib.util; raise SystemExit(0 if importlib.util.find_spec({module!r}) else 1)"
    return subprocess.run([str(py), "-c", code], cwd=py.parent, check=False).returncode == 0


def exe_exists(root: Path, name: str) -> bool:
    scripts = root / ".venv" / "Scripts"
    return any((scripts / candidate).is_file() for candidate in (name, name + ".exe")) or shutil.which(name) is not None


def main() -> int:
    parser = argparse.ArgumentParser(description="Diagnose/repair R13.24 local OSINT tools")
    parser.add_argument("root")
    parser.add_argument("--install-missing", action="store_true")
    parser.add_argument("--upgrade", action="store_true")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    py = project_python(root)
    print("Python:", py)
    failed = 0
    for label, exe, module, package in TOOLS:
        available = exe_exists(root, exe) or module_exists(py, module)
        print(f"{label}: {'READY' if available else 'MISSING'}")
        if (not available and args.install_missing) or args.upgrade:
            cmd = [str(py), "-m", "pip", "install"]
            if args.upgrade:
                cmd.append("--upgrade")
            cmd.append(package)
            print("Running:", " ".join(cmd))
            rc = subprocess.run(cmd, cwd=root, check=False).returncode
            if rc != 0:
                failed += 1
                print(f"{label}: install/upgrade FAILED")
            else:
                ready = exe_exists(root, exe) or module_exists(py, module)
                print(f"{label}: {'READY' if ready else 'INSTALLED BUT NOT DETECTED'}")
                failed += 0 if ready else 1
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
