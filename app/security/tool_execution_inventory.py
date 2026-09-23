"""Approved executable inventory for third-party OSINT CLI tools.

R14.2b centralizes the executable names that ToolRunner is permitted to start.
The inventory is intentionally explicit. Adding a new CLI connector requires an
inventory update and a regression test before the executable can run.
"""

from __future__ import annotations

from pathlib import Path


APPROVED_OSINT_EXECUTABLES: frozenset[str] = frozenset(
    {
        "amass",
        "aquatone",
        "assetfinder",
        "cloudenum",
        "dnsx",
        "feroxbuster",
        "ffuf",
        "gau",
        "ghunt",
        "gitdorker",
        "gitleaks",
        "hakrawler",
        "holehe",
        "httpx",
        "katana",
        "maigret",
        "naabu",
        "nikto",
        "nmap",
        "nuclei",
        "phoneinfoga",
        "s3scanner",
        "secretfinder",
        "sherlock",
        "socialscan",
        "spiderfoot",
        "sslyze",
        "subfinder",
        "subjs",
        "testssl",
        "theharvester",
        "trufflehog",
        "user-scanner",
        "user_scanner",
        "wappalyzer",
        "waybackurls",
        "whatweb",
    }
)


def canonical_executable_name(value: str | Path) -> str:
    """Return the case-insensitive inventory name for one executable path."""

    name = Path(str(value)).name.strip().casefold()

    for suffix in (".exe", ".cmd", ".bat", ".com", ".py", ".sh"):
        if name.endswith(suffix):
            name = name[: -len(suffix)]
            break

    return name


def is_approved_osint_executable(value: str | Path) -> bool:
    """Return whether an executable belongs to the approved OSINT inventory."""

    return canonical_executable_name(value) in APPROVED_OSINT_EXECUTABLES


__all__ = [
    "APPROVED_OSINT_EXECUTABLES",
    "canonical_executable_name",
    "is_approved_osint_executable",
]
