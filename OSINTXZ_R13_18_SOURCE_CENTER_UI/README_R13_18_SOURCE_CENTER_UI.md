# OSINTXZ — R13.18 Source Center & Federated Search UI

## What this package adds

R13.18 makes the already-installed R13.9–R13.17 intelligence federation visible and searchable from the authoritative QML desktop UI.

### New `Sources` workspace

The desktop now has a dedicated **Sources** page that inventories:

- classic OSINT connectors;
- Open-Web providers;
- Registry providers;
- R13 Remote/Federation adapters;
- catalog-only/manual-assisted sources that are known but do not have an executable remote adapter yet.

For every source the UI shows its subsystem, runtime/configuration state, capabilities, country scope, access mode and implementation status.

### Federated search in the UI

The page can run `RemoteSourceAdapterService` through a background `QThread` worker.

Two execution modes are available:

1. **All safe compatible sources** — leaves `RemoteSourceQuery.sources` empty. The existing adapter registry therefore runs only adapters whose `automatic_enabled` policy permits automatic execution.
2. **Explicit selected Federation source** — runs one selected adapter. Sources requiring `VERIFIED_SCOPE` are blocked until the user explicitly confirms verified/authorized scope.

Provider failures are isolated by the existing Federation service and are shown alongside successful providers.

### Secret handling

R13.18 does not persist remote search results. The existing Federation sanitizer remains the primary boundary, and the QML transport snapshot adds a second defensive redaction of password/token/cookie/secret/private-key/session-like fields. The UI explicitly reports that raw secret values are not stored.

## What this package deliberately does not change

- no database migration;
- no bulk dataset downloads;
- no rewrite of `DesktopBridge`;
- no change to recursive OSINT collection;
- no change to Registry Intelligence persistence or legal guardrails;
- no automatic execution of verified-scope/contract-sensitive/Tor sources;
- no automatic identity merge from name-only results.

Classic OSINT and Registry providers are shown in the Source Center and remain searchable through their existing dedicated workflows. The next UI step can broaden the Registry page beyond its current explicit Ukrainian modes while preserving its legal-data safety model.

## Files added

- `app/intelligence_sources/source_center.py`
- `app/interface/desktop/workers/federated_source_search_worker.py`
- `app/interface/desktop/bridges/source_center_bridge.py`
- `app/interface/desktop/qml/pages/Sources.qml`
- `tests/test_r13_18_source_center_ui.py`

## Existing files patched

- `app/interface/desktop/bridges/__init__.py`
- `app/interface/desktop/workers/__init__.py`
- `app/interface/desktop/desktop_app.py`
- `app/interface/desktop/qml/Main.qml`
- `app/interface/desktop/qml/components/Sidebar.qml`

## Test command

```powershell
python .\OSINTXZ_R13_18_SOURCE_CENTER_UI\install_r13_18_source_center_ui.py C:\osintxz --run-tests
```

The installer backs up every patched existing file before making changes.
