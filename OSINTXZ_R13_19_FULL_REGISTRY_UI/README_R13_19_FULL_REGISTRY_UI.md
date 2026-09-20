# OSINTXZ R13.19 — Full Registry Search UI

## What this archive changes

R13.19 turns the existing Registry Intelligence backend into a provider-aware desktop workflow.

- Replaces the old four-mode Registry page with a dynamic Registry Center.
- Reads the live `RegistryProviderRegistry`; provider names/capabilities are not hardcoded in QML.
- Supports domain, query kind, optional ISO country and optional explicit provider selection.
- `AUTO` executes every compatible provider that is eligible under the existing access policy.
- Explicit provider selection may execute a configured public API/PUBLIC_AUTOMATED provider even when it is not default-enabled.
- Explicit selection **does not** bypass missing credentials, MANUAL_ASSISTED sources or RESTRICTED sources.
- Preserves candidate-only identity handling and sensitive legal-data warnings.
- Keeps court/case matches separate from any conclusion about identity, guilt, liability or conviction.
- Keeps provider failure isolation and existing Registry persistence into Source/Evidence/Entity.
- No database migration and no bulk dataset download.

## Runtime sources

The page uses whatever providers are actually registered by `ServiceContainer`, including the current GLEIF, VIES, OpenCorporates, CourtListener, RECAP, Companies House, Poland KRS and remote Ukraine EDR/EDRSR providers when configured/available.

## Install

```powershell
cd C:\osintxz
python .\OSINTXZ_R13_19_FULL_REGISTRY_UI\install_r13_19_full_registry_ui.py C:\osintxz --run-tests
```

The installer creates a backup under `storage/patch_backups/r13_19_*` before replacing or patching files.
