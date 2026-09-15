OSINTXZ — OSINT Result Center v1

Files replaced:
- app/interface/desktop/bridges/desktop_bridge.py
- app/interface/desktop/qml/pages/Osint.qml

Architectural intent:
- Production Run Collection uses the existing InvestigationTargetEnrichmentService.
- Existing persistence remains authoritative: Source -> Evidence -> Entity -> EvidenceEntity.
- No database model/migration/pipeline changes.
- Last-run Result Center state is session-only; persisted Evidence/Entities remain in PostgreSQL.
- Existing lightweight/test containers retain the old osint_controller fallback.
- Execution is still synchronous in v1. Move it to a scoped worker/session only after this result/persistence contract is verified.

Recommended apply flow from C:\\osintxz:
1. git status
2. git switch -c osint-result-center-v1
3. Copy the two replacement files into the same paths, OR run:
   git apply --check <path-to>/osint_result_center_v1.patch
   git apply <path-to>/osint_result_center_v1.patch
4. python -m pytest tests/test_qml_desktop_bridge.py -q
5. python -m pytest -q
6. Run the desktop app and test against a safe target in a selected investigation.

Do not commit until runtime verification is complete.
