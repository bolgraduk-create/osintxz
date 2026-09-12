"""
OSINT Expansion 02 — Runtime Capability Audit

Purpose:
Measure whether each OSINT connector can actually execute on this machine,
instead of only measuring whether source files/classes exist.

Safety:
- no network requests
- no database writes
- no credentials are printed
- CLI smoke checks use local --version/--help only
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
import json
import os
import re
import shutil
import subprocess
import sys
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
CONNECTORS = ROOT / "app" / "osint" / "connectors"
OUT = ROOT / "storage" / "cache" / "osint_runtime_capability_audit"


CLI_REQUIREMENTS: dict[str, tuple[str, ...]] = {
    "amass_connector": ("amass",),
    "aquatone_connector": ("aquatone",),
    "assetfinder_connector": ("assetfinder",),
    "cloudenum_connector": ("cloudenum",),
    "dnsx_connector": ("dnsx",),
    "feroxbuster_connector": ("feroxbuster",),
    "ffuf_connector": ("ffuf",),
    "gau_connector": ("gau",),
    "gitleaks_connector": ("gitleaks",),
    "hakrawler_connector": ("hakrawler",),
    "httpx_connector": ("httpx",),
    "katana_connector": ("katana",),
    "maigret_connector": ("maigret",),
    "naabu_connector": ("naabu",),
    "nikto_connector": ("nikto",),
    "nmap_connector": ("nmap",),
    "nuclei_connector": ("nuclei",),
    "phoneinfoga_connector": ("phoneinfoga",),
    "s3scanner_connector": ("s3scanner", "s3scanner.exe"),
    "secretfinder_connector": ("secretfinder",),
    "sherlock_connector": ("sherlock",),
    "socialscan_connector": ("socialscan",),
    "spiderfoot_connector": ("spiderfoot", "spiderfoot.py"),
    "sslyze_connector": ("sslyze",),
    "subfinder_connector": ("subfinder",),
    "subjs_connector": ("subjs",),
    "testssl_connector": ("testssl", "testssl.sh"),
    "theharvester_connector": ("theHarvester", "theharvester"),
    "trufflehog_connector": ("trufflehog",),
    "waybackurls_connector": ("waybackurls",),
    "whatweb_connector": ("whatweb",),
}


PROJECT_TOOL_PATHS: dict[str, tuple[Path, ...]] = {
    "phoneinfoga": (
        ROOT / "tools" / "phoneinfoga" / "phoneinfoga.exe",
        ROOT / "tools" / "phoneinfoga" / "phoneinfoga",
    ),
    "exiftool": (
        ROOT / "tools" / "exiftool" / "exiftool.exe",
        ROOT / "tools" / "exiftool-13.59_64" / "exiftool.exe",
    ),
}


API_REQUIREMENTS: dict[str, tuple[str, ...]] = {
    "abuseipdb_connector": ("ABUSEIPDB_API_KEY",),
    "alienvault_otx_connector": ("ALIENVAULT_OTX_API_KEY", "OTX_API_KEY"),
    "greynoise_connector": ("GREYNOISE_API_KEY",),
    "haveibeenpwned_connector": ("HAVEIBEENPWNED_API_KEY",),
    "hybrid_analysis_connector": ("HYBRID_ANALYSIS_API_KEY",),
    "intelligencex_connector": ("INTELLIGENCEX_API_KEY",),
    "urlscan_connector": ("URLSCAN_API_KEY",),
    "virustotal_connector": ("VIRUSTOTAL_API_KEY",),
}


KNOWN_KEYLESS_HTTP = {
    "archivetoday_connector",
    "asnlookup_connector",
    "bgpview_connector",
    "commoncrawl_connector",
    "crtsh_connector",
    "gravatar_connector",
    "wappalyzer_connector",
}


PYTHON_PACKAGE_COMMANDS = {
    "holehe_connector": ("holehe",),
    "ghunt_connector": ("ghunt",),
}


HIGH_VALUE_MISSING_ORDER = (
    "subfinder",
    "dnsx",
    "gau",
    "waybackurls",
    "katana",
    "assetfinder",
    "amass",
    "whatweb",
    "sslyze",
    "gitleaks",
    "trufflehog",
    "naabu",
    "nmap",
    "ffuf",
    "feroxbuster",
    "nuclei",
)


@dataclass
class CommandProbe:
    command: str
    found: bool
    path: str | None
    smoke_ok: bool | None
    smoke_output: str | None


@dataclass
class ConnectorRuntime:
    connector: str
    path: str
    mode: str
    status: str
    required_commands: list[str]
    command_probes: list[CommandProbe]
    required_env_any_of: list[str]
    env_present: bool | None
    notes: list[str]


def read_env_keys() -> set[str]:
    keys: set[str] = set()

    for key, value in os.environ.items():
        if value:
            keys.add(key)

    env_file = ROOT / ".env"
    if env_file.exists():
        for raw in env_file.read_text(
            encoding="utf-8",
            errors="replace",
        ).splitlines():
            line = raw.strip()
            if (
                not line
                or line.startswith("#")
                or "=" not in line
            ):
                continue
            key, value = line.split("=", 1)
            if key.strip() and value.strip():
                keys.add(key.strip())

    return keys


def resolve_command(command: str) -> str | None:
    hit = shutil.which(command)
    if hit:
        return hit

    normalized = command.lower().removesuffix(".exe")

    for key, candidates in PROJECT_TOOL_PATHS.items():
        if normalized != key.lower():
            continue
        for candidate in candidates:
            if candidate.exists():
                return str(candidate)

    return None


def smoke_command(command: str, path: str) -> CommandProbe:
    attempts = (
        [path, "--version"],
        [path, "-version"],
        [path, "version"],
        [path, "--help"],
        [path, "-h"],
    )

    last_output = None

    for args in attempts:
        try:
            completed = subprocess.run(
                args,
                cwd=str(ROOT),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=4,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            last_output = f"{type(exc).__name__}: {exc}"
            continue

        output = (completed.stdout or "").strip()
        if output:
            output = output[:500]

        last_output = output or f"exit={completed.returncode}"

        # Help/version commands may legitimately return non-zero on some tools.
        if completed.returncode in (0, 1, 2) and output:
            return CommandProbe(
                command=command,
                found=True,
                path=path,
                smoke_ok=True,
                smoke_output=last_output,
            )

    return CommandProbe(
        command=command,
        found=True,
        path=path,
        smoke_ok=False,
        smoke_output=last_output,
    )


def connector_sources() -> list[Path]:
    if not CONNECTORS.exists():
        return []

    return sorted(
        path
        for path in CONNECTORS.glob("*_connector.py")
        if path.is_file()
    )


def classify_connector(
    path: Path,
    env_keys: set[str],
) -> ConnectorRuntime:
    name = path.stem
    rel = str(path.relative_to(ROOT)).replace("\\", "/")
    source = path.read_text(
        encoding="utf-8",
        errors="replace",
    )

    required_commands = list(
        CLI_REQUIREMENTS.get(name, ())
    )

    if not required_commands:
        required_commands = list(
            PYTHON_PACKAGE_COMMANDS.get(name, ())
        )

    required_env = list(
        API_REQUIREMENTS.get(name, ())
    )

    notes: list[str] = []
    probes: list[CommandProbe] = []

    if required_commands:
        for command in required_commands:
            resolved = resolve_command(command)
            if not resolved:
                probes.append(
                    CommandProbe(
                        command=command,
                        found=False,
                        path=None,
                        smoke_ok=None,
                        smoke_output=None,
                    )
                )
                continue

            probes.append(
                smoke_command(
                    command,
                    resolved,
                )
            )

        if any(
            probe.found and probe.smoke_ok
            for probe in probes
        ):
            status = "READY"
        elif any(probe.found for probe in probes):
            status = "PARTIAL"
            notes.append(
                "binary exists but local help/version smoke probe did not confirm execution"
            )
        else:
            status = "BLOCKED"
            notes.append(
                "required local CLI executable not found"
            )

        return ConnectorRuntime(
            connector=name,
            path=rel,
            mode="CLI",
            status=status,
            required_commands=required_commands,
            command_probes=probes,
            required_env_any_of=[],
            env_present=None,
            notes=notes,
        )

    if required_env:
        present = any(
            key in env_keys
            for key in required_env
        )

        return ConnectorRuntime(
            connector=name,
            path=rel,
            mode="API",
            status="READY" if present else "BLOCKED",
            required_commands=[],
            command_probes=[],
            required_env_any_of=required_env,
            env_present=present,
            notes=[] if present else [
                "required API/config key not present"
            ],
        )

    if name in KNOWN_KEYLESS_HTTP:
        return ConnectorRuntime(
            connector=name,
            path=rel,
            mode="HTTP_KEYLESS",
            status="READY",
            required_commands=[],
            command_probes=[],
            required_env_any_of=[],
            env_present=None,
            notes=[
                "source classified as keyless HTTP/public-source connector"
            ],
        )

    # Conservative static inference for unknown connectors.
    lower = source.lower()

    looks_http = any(
        token in lower
        for token in (
            "httpx.",
            "requests.",
            "asyncclient",
            "client.get(",
            "client.post(",
            "https://",
            "http://",
        )
    )

    if looks_http:
        return ConnectorRuntime(
            connector=name,
            path=rel,
            mode="HTTP_INFERRED",
            status="PARTIAL",
            required_commands=[],
            command_probes=[],
            required_env_any_of=[],
            env_present=None,
            notes=[
                "HTTP implementation detected, but key/runtime requirements are not explicitly mapped"
            ],
        )

    return ConnectorRuntime(
        connector=name,
        path=rel,
        mode="UNKNOWN",
        status="UNKNOWN",
        required_commands=[],
        command_probes=[],
        required_env_any_of=[],
        env_present=None,
        notes=[
            "runtime requirements could not be classified automatically"
        ],
    )


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)

    env_keys = read_env_keys()
    results = [
        classify_connector(path, env_keys)
        for path in connector_sources()
    ]

    counts = {
        state: sum(
            1
            for item in results
            if item.status == state
        )
        for state in (
            "READY",
            "PARTIAL",
            "BLOCKED",
            "UNKNOWN",
        )
    }

    missing_commands: set[str] = set()
    for item in results:
        for probe in item.command_probes:
            if not probe.found:
                missing_commands.add(
                    probe.command.lower().removesuffix(".exe")
                )

    prioritized_missing = [
        tool
        for tool in HIGH_VALUE_MISSING_ORDER
        if tool in missing_commands
    ]

    other_missing = sorted(
        missing_commands
        - set(prioritized_missing)
    )

    payload = {
        "audit_version": 2,
        "python": sys.version,
        "counts": counts,
        "connectors": [
            asdict(item)
            for item in results
        ],
        "missing_commands_priority": prioritized_missing,
        "missing_commands_other": other_missing,
        "notes": [
            "READY means runtime prerequisites were locally detectable; it does not guarantee a remote source will return data.",
            "No network requests were made.",
            "API key values are never printed.",
            "CLI smoke checks use local help/version commands only.",
        ],
    }

    json_path = OUT / "runtime_audit.json"
    json_path.write_text(
        json.dumps(
            payload,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    lines = [
        "# OSINT Runtime Capability Audit",
        "",
        "## Summary",
        "",
        f"- READY: {counts['READY']}",
        f"- PARTIAL: {counts['PARTIAL']}",
        f"- BLOCKED: {counts['BLOCKED']}",
        f"- UNKNOWN: {counts['UNKNOWN']}",
        "",
        "## Connector matrix",
        "",
        "| Connector | Mode | Status | Requirement |",
        "|---|---|---|---|",
    ]

    for item in results:
        requirement = "-"
        if item.required_commands:
            requirement = ", ".join(item.required_commands)
        elif item.required_env_any_of:
            requirement = " OR ".join(item.required_env_any_of)

        lines.append(
            f"| {item.connector} | {item.mode} | {item.status} | {requirement} |"
        )

    lines += [
        "",
        "## Highest-value missing free tools",
        "",
    ]

    if prioritized_missing:
        for index, tool in enumerate(
            prioritized_missing,
            start=1,
        ):
            lines.append(
                f"{index}. `{tool}`"
            )
    else:
        lines.append(
            "No high-value tools from the current priority set are missing."
        )

    if other_missing:
        lines += [
            "",
            "## Other missing commands",
            "",
        ]
        for tool in other_missing:
            lines.append(f"- `{tool}`")

    md_path = OUT / "runtime_audit.md"
    md_path.write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )

    print("OSINT Expansion 02 — Runtime Capability Audit")
    print("=" * 62)
    print(
        f"READY={counts['READY']}  "
        f"PARTIAL={counts['PARTIAL']}  "
        f"BLOCKED={counts['BLOCKED']}  "
        f"UNKNOWN={counts['UNKNOWN']}"
    )
    print("")
    print("Blocked connectors:")
    for item in results:
        if item.status == "BLOCKED":
            requirement = (
                ", ".join(item.required_commands)
                or " OR ".join(item.required_env_any_of)
                or "-"
            )
            print(
                f"  {item.connector:34} requirement={requirement}"
            )

    print("")
    print("Highest-value missing free tools:")
    if prioritized_missing:
        for tool in prioritized_missing:
            print(f"  {tool}")
    else:
        print("  none")

    if other_missing:
        print("")
        print("Other missing commands:")
        for tool in other_missing:
            print(f"  {tool}")

    print("")
    print(f"JSON: {json_path}")
    print(f"Markdown: {md_path}")
    print("")
    print("OSINT EXPANSION 02 RUNTIME AUDIT: PASS")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
