"""
OSINT Expansion 01 — Free Maximum Coverage Audit

Read-only project audit. No network requests and no database writes.

Outputs are written under storage/cache/osint_free_maximum_audit/, which is
expected to be ignored by Git.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
import json
import os
import re
import shutil
import sys
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app"
OUT = ROOT / "storage" / "cache" / "osint_free_maximum_audit"


TARGETS = (
    "username",
    "email",
    "phone",
    "domain",
    "ip",
    "url",
    "person",
    "company",
    "document",
    "location",
)


TARGET_HINTS = {
    "username": (
        "sherlock", "maigret", "whatsmyname", "user_scanner",
        "socialscan", "username",
    ),
    "email": (
        "holehe", "gravatar", "ghunt", "email",
        "haveibeenpwned", "hibp", "gdelt_exact_email",
        "brave_exact_email",
    ),
    "phone": (
        "phoneinfoga", "local_phone", "phone_intelligence",
        "gdelt_phone_exact", "searxng_phone_exact",
        "targeted_phone_public_sources", "phone",
    ),
    "domain": (
        "crtsh", "commoncrawl", "common_crawl", "subfinder", "amass",
        "assetfinder", "dnsx", "httpx", "wayback", "gau",
        "theharvester", "domain",
    ),
    "ip": (
        "bgpview", "asnlookup", "abuseipdb", "greynoise",
        "urlscan", "ip", "asn",
    ),
    "url": (
        "commoncrawl", "common_crawl", "archive", "wayback",
        "urlscan", "gau", "url", "open_web",
    ),
    "person": (
        "person", "identity", "entity_resolution", "username_fusion",
        "open_web", "registry",
    ),
    "company": (
        "company", "organization", "registry", "gleif", "lei",
    ),
    "document": (
        "document", "public_document", "warc", "pdf",
        "metadata", "exif",
    ),
    "location": (
        "location", "gps", "geo", "map",
    ),
}


TOOL_CANDIDATES = {
    "phoneinfoga": (
        ROOT / "tools" / "phoneinfoga" / "phoneinfoga.exe",
        ROOT / "tools" / "phoneinfoga" / "phoneinfoga",
    ),
    "exiftool": (
        ROOT / "tools" / "exiftool" / "exiftool.exe",
        ROOT / "tools" / "exiftool-13.59_64" / "exiftool.exe",
    ),
    "sherlock": (),
    "maigret": (),
    "socialscan": (),
    "holehe": (),
    "subfinder": (),
    "amass": (),
    "assetfinder": (),
    "dnsx": (),
    "httpx": (),
    "naabu": (),
    "nmap": (),
    "nuclei": (),
    "ffuf": (),
    "feroxbuster": (),
    "katana": (),
    "gau": (),
    "waybackurls": (),
    "whatweb": (),
    "sslyze": (),
    "gitleaks": (),
    "trufflehog": (),
}


@dataclass
class Component:
    path: str
    kind: str
    name: str


@dataclass
class TargetCoverage:
    target: str
    source_components: int
    routing: bool
    persistence: bool
    recursion: bool
    content_extraction: bool
    tests: int
    installed_tools: int
    score: int
    grade: str
    gaps: list[str]
    matching_components: list[str]


def iter_text_files(base: Path) -> Iterable[Path]:
    if not base.exists():
        return
    for path in base.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in {".py", ".md", ".yml", ".yaml", ".toml"}:
            continue
        if "__pycache__" in path.parts:
            continue
        yield path


def safe_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="replace")


def collect_components() -> list[Component]:
    result: list[Component] = []

    roots = (
        ("connector", APP / "osint" / "connectors"),
        ("open_web_provider", APP / "osint" / "open_web" / "providers"),
        ("registry_provider", APP / "registry_intelligence" / "providers"),
        ("open_web_infrastructure", APP / "infrastructure" / "open_web"),
        ("registry_infrastructure", APP / "infrastructure" / "registries"),
    )

    for kind, base in roots:
        if not base.exists():
            continue
        for path in base.glob("*.py"):
            if path.name == "__init__.py":
                continue
            result.append(
                Component(
                    path=str(path.relative_to(ROOT)).replace("\\", "/"),
                    kind=kind,
                    name=path.stem,
                )
            )

    return sorted(result, key=lambda item: (item.kind, item.name))


def project_corpus() -> dict[str, str]:
    corpus: dict[str, str] = {}
    for path in iter_text_files(APP):
        rel = str(path.relative_to(ROOT)).replace("\\", "/")
        corpus[rel] = safe_text(path)
    return corpus


def test_corpus() -> dict[str, str]:
    base = ROOT / "tests"
    corpus: dict[str, str] = {}
    for path in iter_text_files(base):
        rel = str(path.relative_to(ROOT)).replace("\\", "/")
        corpus[rel] = safe_text(path)
    return corpus


def has_any(corpus: dict[str, str], patterns: Iterable[str]) -> bool:
    joined = "\n".join(corpus.values()).lower()
    return any(pattern.lower() in joined for pattern in patterns)


def matching_paths(
    corpus: dict[str, str],
    patterns: Iterable[str],
) -> list[str]:
    pats = tuple(pattern.lower() for pattern in patterns)
    found = []
    for path, text in corpus.items():
        haystack = (path + "\n" + text).lower()
        if any(pat in haystack for pat in pats):
            found.append(path)
    return sorted(found)


def tool_state() -> dict[str, dict[str, object]]:
    state: dict[str, dict[str, object]] = {}

    for tool, local_candidates in TOOL_CANDIDATES.items():
        found_path = shutil.which(tool)

        if found_path:
            state[tool] = {
                "installed": True,
                "path": found_path,
                "source": "PATH",
            }
            continue

        local_hit = None
        for candidate in local_candidates:
            if candidate.exists():
                local_hit = str(candidate)
                break

        state[tool] = {
            "installed": bool(local_hit),
            "path": local_hit,
            "source": "project_tools" if local_hit else None,
        }

    return state


def env_capabilities() -> dict[str, bool]:
    env_file = ROOT / ".env"
    keys: set[str] = set()

    if env_file.exists():
        for raw_line in safe_text(env_file).splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key = line.split("=", 1)[0].strip()
            if key:
                keys.add(key)

    interesting = (
        "OPENAI_API_KEY",
        "VIRUSTOTAL_API_KEY",
        "ABUSEIPDB_API_KEY",
        "GREYNOISE_API_KEY",
        "HAVEIBEENPWNED_API_KEY",
        "INTELLIGENCEX_API_KEY",
        "BRAVE_API_KEY",
        "SEARXNG_URL",
    )

    return {key: key in keys for key in interesting}


def grade(score: int) -> str:
    if score >= 85:
        return "A"
    if score >= 70:
        return "B"
    if score >= 55:
        return "C"
    if score >= 40:
        return "D"
    return "E"


def build_target_coverage(
    target: str,
    corpus: dict[str, str],
    tests: dict[str, str],
    components: list[Component],
    tools: dict[str, dict[str, object]],
) -> TargetCoverage:
    hints = TARGET_HINTS[target]

    component_matches = [
        item.path
        for item in components
        if any(
            hint in (item.name + " " + item.path).lower()
            for hint in hints
        )
    ]

    related_paths = matching_paths(corpus, hints)
    related_tests = matching_paths(tests, hints)

    routing = any(
        token in "\n".join(
            corpus.get(path, "")
            for path in related_paths
        ).lower()
        for token in (
            "pivot_router",
            "capability",
            "supported",
            "supports(",
            "target_type",
            "registry",
            "route",
        )
    )

    persistence = any(
        token in "\n".join(
            corpus.get(path, "")
            for path in related_paths
        ).lower()
        for token in (
            "finding_persistence",
            "persist",
            "repository",
            "evidence",
            "source_type",
        )
    )

    recursion = any(
        token in "\n".join(
            corpus.get(path, "")
            for path in related_paths
        ).lower()
        for token in (
            "recursive",
            "pivot",
            "max_depth",
            "max_pivots",
        )
    )

    content_extraction = any(
        token in "\n".join(
            corpus.get(path, "")
            for path in related_paths
        ).lower()
        for token in (
            "extraction",
            "extract",
            "hydrate",
            "content_hydration",
            "public_document",
            "warc",
            "metadata",
        )
    )

    installed_tools = 0
    for tool_name, info in tools.items():
        if not info["installed"]:
            continue
        if any(hint in tool_name.lower() for hint in hints):
            installed_tools += 1

    # Heuristic score: measures architectural coverage, not OSINT truth/quality.
    score = 0
    score += min(30, len(component_matches) * 5)
    score += 15 if routing else 0
    score += 15 if persistence else 0
    score += 15 if recursion else 0
    score += 15 if content_extraction else 0
    score += min(8, len(related_tests) * 2)
    score += min(2, installed_tools * 2)
    score = min(100, score)

    gaps: list[str] = []
    if len(component_matches) < 2:
        gaps.append("few dedicated source/provider components")
    if not routing:
        gaps.append("routing/capability path not clearly detected")
    if not persistence:
        gaps.append("persistence/provenance path not clearly detected")
    if not recursion:
        gaps.append("recursive pivot path not clearly detected")
    if not content_extraction:
        gaps.append("content extraction/hydration not clearly detected")
    if len(related_tests) < 2:
        gaps.append("weak target-specific automated test coverage")

    return TargetCoverage(
        target=target,
        source_components=len(component_matches),
        routing=routing,
        persistence=persistence,
        recursion=recursion,
        content_extraction=content_extraction,
        tests=len(related_tests),
        installed_tools=installed_tools,
        score=score,
        grade=grade(score),
        gaps=gaps,
        matching_components=component_matches[:40],
    )


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)

    components = collect_components()
    corpus = project_corpus()
    tests = test_corpus()
    tools = tool_state()
    env = env_capabilities()

    coverage = [
        build_target_coverage(
            target,
            corpus,
            tests,
            components,
            tools,
        )
        for target in TARGETS
    ]

    weakest = sorted(
        coverage,
        key=lambda item: (
            item.score,
            item.source_components,
            item.tests,
        ),
    )

    payload = {
        "audit_version": 1,
        "project_root": str(ROOT),
        "python": sys.version,
        "component_count": len(components),
        "components": [asdict(item) for item in components],
        "tool_state": tools,
        "env_key_presence": env,
        "coverage": [asdict(item) for item in coverage],
        "priority_order": [
            item.target
            for item in weakest
        ],
        "notes": [
            "Scores are architecture/coverage heuristics, not guarantees of live-source quality.",
            "No network requests were made.",
            "No API-key values are read or printed; only key presence is reported.",
        ],
    }

    json_path = OUT / "audit.json"
    json_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    rows = []
    for item in sorted(coverage, key=lambda value: value.score):
        rows.append(
            "| {target} | {score} | {grade} | {sources} | {tests} | {routing} | "
            "{persist} | {recursion} | {extract} |".format(
                target=item.target,
                score=item.score,
                grade=item.grade,
                sources=item.source_components,
                tests=item.tests,
                routing="yes" if item.routing else "no",
                persist="yes" if item.persistence else "no",
                recursion="yes" if item.recursion else "no",
                extract="yes" if item.content_extraction else "no",
            )
        )

    md = [
        "# OSINT Free Maximum — Coverage Audit",
        "",
        "This report is a static/runtime-local architecture audit.",
        "It does not make network requests.",
        "",
        "## Coverage matrix",
        "",
        "| Target | Score | Grade | Components | Tests | Routing | Persistence | Recursion | Extraction |",
        "|---|---:|:---:|---:|---:|:---:|:---:|:---:|:---:|",
        *rows,
        "",
        "## Priority order",
        "",
    ]

    for index, item in enumerate(weakest, start=1):
        md.append(
            f"{index}. **{item.target}** — {item.score}/100 ({item.grade})"
        )
        if item.gaps:
            for gap in item.gaps:
                md.append(f"   - {gap}")

    md += [
        "",
        "## Installed local/external tools",
        "",
    ]

    for name, info in sorted(tools.items()):
        state = "installed" if info["installed"] else "missing"
        source = info["source"] or "-"
        path = info["path"] or "-"
        md.append(
            f"- **{name}**: {state}; source={source}; path={path}"
        )

    md += [
        "",
        "## API/config key presence",
        "",
        "Only presence is reported; values are never printed.",
        "",
    ]

    for key, present in env.items():
        md.append(
            f"- `{key}`: {'present' if present else 'absent'}"
        )

    md_path = OUT / "audit.md"
    md_path.write_text(
        "\n".join(md) + "\n",
        encoding="utf-8",
    )

    print("OSINT Expansion 01 — Free Maximum Coverage Audit")
    print("=" * 60)
    print(f"Components discovered: {len(components)}")
    print("")
    print("Coverage, weakest first:")
    for item in weakest:
        print(
            f"  {item.target:10} {item.score:3}/100 "
            f"grade={item.grade} components={item.source_components} "
            f"tests={item.tests}"
        )

    print("")
    print("Priority order:")
    print("  " + " -> ".join(item.target for item in weakest))
    print("")
    print(f"JSON: {json_path}")
    print(f"Markdown: {md_path}")
    print("")
    print("OSINT EXPANSION 01 AUDIT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
