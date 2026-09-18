# OSINTXZ — R11 RECAP / PACER Safety Patch

Adds search of federal PACER dockets already present in the free RECAP archive through CourtListener API v4, while hard-blocking any paid PACER fetch.

## Scope

- CourtListener search `type=d` (federal docket metadata, no nested filing payloads)
- `COURT/LEGAL + CASE_NUMBER`
- `COURT/LEGAL + NAME`
- country `US`
- exact normalized post-filter for case numbers

The provider reuses `COURTLISTENER_API_TOKEN` from R10.

## PACER safety boundary

CourtListener's `/api/rest/v4/recap-fetch/` can purchase PACER data with a user's PACER credentials. R11 intentionally does not call that endpoint. `PacerPaidFetchGuard` rejects paid access before network I/O, even if a caller supplies an explicit confirmation or budget.

No PACER username/password is added or stored.

## Legal safeguards

Every result is a sensitive `COURT_CASE` aggregator record and includes:

- `identity_confirmed=False`
- `legal_outcome_inferred=False`
- `pacer_recap=True`
- `recap_archive_only=True`
- `paid_pacer_fetch_performed=False`

A docket hit is not proof of identity, guilt, liability, or conviction.

## Install

```powershell
python .\install_recap_pacer_r11_patch.py C:\osintxz --run-tests
```

New files:
- `app/infrastructure/registries/recap_client.py`
- `app/registry_intelligence/providers/recap.py`
- `tests/test_registry_recap_pacer.py`

Patched:
- `app/core/service_container.py`

No DB migration and no new dependency.
