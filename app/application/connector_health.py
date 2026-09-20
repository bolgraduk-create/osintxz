"""Connector/provider health classification for the unified search UI."""
from __future__ import annotations

from collections import Counter
import re
from typing import Any, Iterable


def annotate_provider_health(rows: Iterable[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, int]]:
    out: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()
    for raw in rows:
        row = dict(raw)
        state, label, action, retryable = classify_provider_health(row)
        row["healthState"] = state
        row["healthLabel"] = label
        row["healthAction"] = action
        row["retryable"] = retryable
        counts[state] += 1
        out.append(row)
    summary = {
        "ready": counts["ready"],
        "partial": counts["partial"],
        "timeout": counts["timeout"],
        "notInstalled": counts["not_installed"],
        "notConfigured": counts["not_configured"],
        "authOrPolicy": counts["auth_or_policy"],
        "rateLimited": counts["rate_limited"],
        "endpointError": counts["endpoint_error"],
        "temporarilyUnavailable": counts["temporarily_unavailable"],
        "guarded": counts["guarded"],
        "broken": counts["broken"],
    }
    summary["issues"] = sum(v for k, v in counts.items() if k not in {"ready", "guarded"})
    return out, summary


def classify_provider_health(row: dict[str, Any]) -> tuple[str, str, str, bool]:
    status = str(row.get("status") or "").strip().casefold()
    detail = " ".join(str(row.get(key) or "") for key in ("detail", "error", "source")).casefold()

    if status in {"success", "completed", "finding", "remote", "registry"}:
        return "ready", "READY", "", False
    if status == "guarded":
        return "guarded", "EXPLICIT ONLY", "Run explicitly when scope/policy permits.", False
    if status in {"not_configured"} or "api key" in detail or "not configured" in detail:
        return "not_configured", "NOT CONFIGURED", "Configure the required credential or endpoint.", False
    if status in {"not_available"} or "not installed" in detail or "executable not found" in detail:
        return "not_installed", "NOT INSTALLED", "Install/repair the local tool in the project .venv.", False
    if "timeout" in detail or "timed out" in detail:
        return "timeout", "TIMEOUT", "Retry with the bounded fast-pass; partial findings are retained when available.", True
    if re.search(r"http\s*429\b", detail) or "rate limit" in detail:
        return "rate_limited", "RATE LIMITED", "Retry later and respect provider backoff.", True
    if re.search(r"http\s*(401|403)\b", detail):
        return "auth_or_policy", "AUTH / POLICY", "Check client identification, credentials, or provider access policy.", True
    if re.search(r"http\s*404\b", detail):
        return "endpoint_error", "ENDPOINT / QUERY", "Verify provider endpoint/query compatibility.", True
    if re.search(r"http\s*5\d\d\b", detail) or any(x in detail for x in ("connection", "network", "temporarily unavailable")):
        return "temporarily_unavailable", "TEMPORARY FAILURE", "Retry later; provider failure is isolated.", True
    if status == "partial":
        return "partial", "PARTIAL", "Partial findings are usable; retry for broader coverage.", True
    if status in {"failed", "error"}:
        return "broken", "FAILED", "Inspect the provider error and repair/update the connector if persistent.", True
    return "partial", (status or "UNKNOWN").replace("_", " ").upper(), "Review provider status.", False
