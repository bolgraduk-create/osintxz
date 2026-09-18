# OSINTXZ — R13.6 Breach Intelligence: HIBP

Adds the first real Breach Intelligence provider on top of R13.5.

## What is added

### Email breach lookup

Uses HIBP API v3:

- email -> list of known breaches
- breach name/domain/date
- exposed data classes
- verified/fabricated/sensitive/spam-list metadata
- `password_exposed=True` when the breach data classes include passwords

The actual password is never returned by HIBP account lookup and OSINTXZ does
not create a password value from breach metadata.

Email lookup requires the existing OSINTXZ setting:

```text
HAVEIBEENPWNED_API_KEY=
```

No API key is bundled.

HIBP account lookup is registered in the Federation catalog as subscription /
contract-backed and is not an automatic source by default.

### Pwned Passwords

Adds safe password-exposure checking using the HIBP k-anonymity range API.

Flow:

1. password is received transiently by `check_password()`;
2. SHA-1 is computed locally;
3. only the first 5 hash characters are sent to Pwned Passwords;
4. returned suffixes are compared locally;
5. OSINTXZ returns only:
   - `password_exposed`
   - `occurrence_count`

OSINTXZ result stores neither the plaintext password nor its full SHA-1 hash.

Pwned Passwords is free and needs no API key.

## Source catalog

R13.6 registers two separate capabilities:

- `hibp_breached_account`
- `hibp_pwned_passwords`

This distinction is important because their access/cost models are different.

## Files

New:
- `app/breach_intelligence/__init__.py`
- `app/breach_intelligence/contracts.py`
- `app/breach_intelligence/hibp_client.py`
- `app/breach_intelligence/catalog.py`
- `app/breach_intelligence/service.py`
- `tests/test_breach_intelligence_hibp.py`

Patched:
- `app/core/service_container.py`

No database migration and no new dependency.

## Install

With the project virtualenv active:

```powershell
python .\install_breach_intelligence_r13_6.py C:\osintxz --run-tests
```
