"""Explicit opt-in probe: python -m pytest tools/check_registry_live_runtime.py -q -s.

Reads GLEIF's own public LEI record, creates no production DB data and performs
no retry/rate-limit bypass. This file is outside default testpaths.
"""
import json
from pathlib import Path

from app.infrastructure.registries.gleif_client import GleifRegistryHttpClient
from app.registry_intelligence.providers.gleif import GleifRegistryProvider
from app.registry_intelligence.query_detection import detect_registry_query
from app.registry_intelligence.contracts import RegistryResultStatus


def test_gleif_live_public_foundation_record():
    result = GleifRegistryProvider(client=GleifRegistryHttpClient()).search(
        detect_registry_query("506700GE1G29325QX363"))
    report = {"provider": result.provider, "status": result.status.value,
              "error": result.error, "metadata": result.metadata,
              "records": [{"lei": r.lei, "name": r.display_name, "source_url": r.source_url}
                          for r in result.records]}
    Path("docs/osint_stabilization/registry_live_probe.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=True))
    assert result.status is RegistryResultStatus.SUCCESS
    assert len(result.records) == 1
    assert result.records[0].lei == "506700GE1G29325QX363"
