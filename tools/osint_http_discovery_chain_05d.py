
"""
OSINT Expansion 05D — Controlled HTTP Discovery Chain Integration

Live production-wrapper chain:

    example.com
        ↓
    Subfinder + Assetfinder
        ↓
    bounded host candidates
        ↓
    DNSX
        ↓
    HTTPX
        ↓
    GAU + Waybackurls
        ↓
    Katana

Safety:
- benign public target: example.com
- ConnectorRequest.limit = 3
- bounded per-connector timeouts
- no DB writes
- no persistence
- no recursive enrichment
- no vulnerability scanners
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import enum
import json
from pathlib import Path
from typing import Any

from app.osint.connectors.assetfinder_connector import AssetfinderConnector
from app.osint.connectors.dnsx_connector import DNSXConnector
from app.osint.connectors.gau_connector import GauConnector
from app.osint.connectors.httpx_connector import HTTPXConnector
from app.osint.connectors.katana_connector import KatanaConnector
from app.osint.connectors.subfinder_connector import SubfinderConnector
from app.osint.connectors.waybackurls_connector import WaybackurlsConnector
from app.osint.models import (
    ConnectorRequest,
    OsintTarget,
    OsintTargetType,
)
from app.osint.result import OsintResult


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "storage" / "cache" / "osint_expansion_05d"

SEED_DOMAIN = "example.com"
RESULT_LIMIT = 3

TIMEOUTS = {
    "subfinder": 20,
    "assetfinder": 12,
    "dnsx": 12,
    "httpx": 15,
    "gau": 15,
    "waybackurls": 15,
    "katana": 15,
}


@dataclass(slots=True)
class StageRecord:
    stage: str
    connector: str
    target_type: str
    target: str
    status: str
    findings: int
    limit_honored: bool
    error: str | None
    values: list[str]
    metadata: dict[str, Any]


def status_value(result: OsintResult) -> str:
    value = result.status
    if isinstance(value, enum.Enum):
        return str(value.value)
    return str(value)


def finding_value(finding: Any) -> str:
    for attr in ("url", "value"):
        value = getattr(finding, attr, None)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return repr(finding)[:300]


def run_connector(
    *,
    stage: str,
    connector: Any,
    target_type: OsintTargetType,
    target: str,
    timeout: int,
) -> tuple[StageRecord, OsintResult]:

    request = ConnectorRequest(
        target=OsintTarget(
            target_type=target_type,
            value=target,
        ),
        timeout=timeout,
        include_related=True,
        include_metadata=True,
        limit=RESULT_LIMIT,
    )

    result = connector.execute(request)

    values = [
        finding_value(item)
        for item in result.findings[:RESULT_LIMIT]
    ]

    record = StageRecord(
        stage=stage,
        connector=connector.name,
        target_type=target_type.value,
        target=target,
        status=status_value(result),
        findings=result.total_findings,
        limit_honored=(
            result.total_findings <= RESULT_LIMIT
        ),
        error=result.error,
        values=values,
        metadata=dict(result.metadata or {}),
    )

    return record, result


def normalize_host(value: str) -> str | None:
    text = value.strip().lower().rstrip(".")

    if "://" in text:
        try:
            from urllib.parse import urlsplit
            parsed = urlsplit(text)
            text = (parsed.hostname or "").lower().rstrip(".")
        except Exception:
            return None

    if not text:
        return None

    if text == SEED_DOMAIN:
        return text

    if text.endswith("." + SEED_DOMAIN):
        return text

    return None


def normalize_url(value: str) -> str | None:
    text = value.strip()

    if text.startswith("http://") or text.startswith("https://"):
        return text

    return None


def add_unique(
    collection: list[str],
    value: str | None,
    *,
    limit: int,
) -> None:
    if not value:
        return
    if value in collection:
        return
    if len(collection) >= limit:
        return
    collection.append(value)


def print_record(record: StageRecord) -> None:
    print(
        f"{record.stage:14} "
        f"{record.connector:12} "
        f"status={record.status:12} "
        f"findings={record.findings:<3} "
        f"limit_ok={record.limit_honored} "
        f"target={record.target}",
        flush=True,
    )

    if record.error:
        short_error = (
            record.error
            .replace("\r", " ")
            .replace("\n", " ")
        )
        print(
            f"  error: {short_error[:220]}",
            flush=True,
        )

    for value in record.values[:3]:
        print(
            f"  -> {value[:220]}",
            flush=True,
        )


def main() -> int:
    OUT.mkdir(
        parents=True,
        exist_ok=True,
    )

    print(
        "OSINT Expansion 05D — Controlled HTTP Discovery Chain",
        flush=True,
    )
    print(
        "=" * 72,
        flush=True,
    )
    print(
        f"Seed: {SEED_DOMAIN}",
        flush=True,
    )
    print(
        f"Per-stage result limit: {RESULT_LIMIT}",
        flush=True,
    )
    print("", flush=True)

    records: list[StageRecord] = []

    # ------------------------------------------------------------------
    # 1. Passive subdomain discovery
    # ------------------------------------------------------------------

    host_candidates: list[str] = [
        SEED_DOMAIN,
    ]

    for connector_name, connector in (
        ("subfinder", SubfinderConnector()),
        ("assetfinder", AssetfinderConnector()),
    ):
        record, result = run_connector(
            stage="discovery",
            connector=connector,
            target_type=OsintTargetType.DOMAIN,
            target=SEED_DOMAIN,
            timeout=TIMEOUTS[connector_name],
        )
        records.append(record)
        print_record(record)

        for finding in result.findings:
            add_unique(
                host_candidates,
                normalize_host(
                    finding_value(finding)
                ),
                limit=RESULT_LIMIT,
            )

    print("", flush=True)
    print(
        "Host candidates: "
        + ", ".join(host_candidates),
        flush=True,
    )
    print("", flush=True)

    # ------------------------------------------------------------------
    # 2. DNS resolution for bounded host candidates
    # ------------------------------------------------------------------

    dnsx = DNSXConnector()

    for host in host_candidates:
        record, _ = run_connector(
            stage="dns",
            connector=dnsx,
            target_type=OsintTargetType.DOMAIN,
            target=host,
            timeout=TIMEOUTS["dnsx"],
        )
        records.append(record)
        print_record(record)

    print("", flush=True)

    # ------------------------------------------------------------------
    # 3. HTTP probing
    # ------------------------------------------------------------------

    httpx = HTTPXConnector()
    live_urls: list[str] = []

    for host in host_candidates:
        record, result = run_connector(
            stage="http",
            connector=httpx,
            target_type=OsintTargetType.DOMAIN,
            target=host,
            timeout=TIMEOUTS["httpx"],
        )
        records.append(record)
        print_record(record)

        for finding in result.findings:
            add_unique(
                live_urls,
                normalize_url(
                    finding_value(finding)
                ),
                limit=RESULT_LIMIT,
            )

    if not live_urls:
        # Keep the archive/crawl stages testable even if HTTPX has a transient
        # network failure; this fallback is the original benign seed URL.
        live_urls.append(
            "https://example.com"
        )

    print("", flush=True)
    print(
        "Live URL candidates: "
        + ", ".join(live_urls),
        flush=True,
    )
    print("", flush=True)

    # ------------------------------------------------------------------
    # 4. Archive/history discovery on the original domain
    # ------------------------------------------------------------------

    for connector_name, connector in (
        ("gau", GauConnector()),
        ("waybackurls", WaybackurlsConnector()),
    ):
        record, _ = run_connector(
            stage="archive",
            connector=connector,
            target_type=OsintTargetType.DOMAIN,
            target=SEED_DOMAIN,
            timeout=TIMEOUTS[connector_name],
        )
        records.append(record)
        print_record(record)

    print("", flush=True)

    # ------------------------------------------------------------------
    # 5. Controlled crawl of one live URL
    # ------------------------------------------------------------------

    katana = KatanaConnector()

    record, _ = run_connector(
        stage="crawl",
        connector=katana,
        target_type=OsintTargetType.URL,
        target=live_urls[0],
        timeout=TIMEOUTS["katana"],
    )
    records.append(record)
    print_record(record)

    # ------------------------------------------------------------------
    # Summary / assertions
    # ------------------------------------------------------------------

    violations = [
        record
        for record in records
        if not record.limit_honored
    ]

    successful_or_partial = [
        record
        for record in records
        if record.status in {
            "success",
            "partial",
        }
    ]

    stage_names = {
        record.stage
        for record in successful_or_partial
    }

    required_stages = {
        "discovery",
        "dns",
        "http",
        "archive",
        "crawl",
    }

    missing_working_stages = sorted(
        required_stages - stage_names
    )

    report = {
        "gate_version": 1,
        "seed_domain": SEED_DOMAIN,
        "result_limit": RESULT_LIMIT,
        "host_candidates": host_candidates,
        "live_urls": live_urls,
        "records": [
            asdict(record)
            for record in records
        ],
        "limit_violations": [
            record.connector
            for record in violations
        ],
        "working_stages": sorted(stage_names),
        "missing_working_stages": missing_working_stages,
        "notes": [
            "This gate uses production connector wrappers.",
            "No DB writes or persistence are performed.",
            "No vulnerability scanner is invoked.",
            "A failed individual connector does not invalidate another connector in the same stage.",
        ],
    }

    report_path = (
        OUT
        / "http_discovery_chain.json"
    )

    report_path.write_text(
        json.dumps(
            report,
            indent=2,
            ensure_ascii=False,
            default=str,
        ),
        encoding="utf-8",
    )

    print("", flush=True)
    print("SUMMARY", flush=True)
    print("-" * 72, flush=True)
    print(
        f"records={len(records)} "
        f"limit_violations={len(violations)}",
        flush=True,
    )
    print(
        "working_stages="
        + ",".join(sorted(stage_names)),
        flush=True,
    )

    if missing_working_stages:
        print(
            "missing_working_stages="
            + ",".join(missing_working_stages),
            flush=True,
        )

    print(
        f"JSON: {report_path}",
        flush=True,
    )
    print("", flush=True)

    if violations:
        print(
            "OSINT EXPANSION 05D HTTP DISCOVERY CHAIN: FAIL",
            flush=True,
        )
        print(
            "Reason: result limit violation.",
            flush=True,
        )
        return 1

    if missing_working_stages:
        print(
            "OSINT EXPANSION 05D HTTP DISCOVERY CHAIN: PARTIAL",
            flush=True,
        )
        return 0

    print(
        "OSINT EXPANSION 05D HTTP DISCOVERY CHAIN: PASS",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
