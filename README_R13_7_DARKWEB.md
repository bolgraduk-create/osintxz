# OSINTXZ — R13.7 Dark Web Intelligence

Adds a deliberately narrow public `.onion` observation layer over a local Tor
SOCKS proxy.

## Added

- Tor SOCKS HTTP transport (`socks5h`)
- strict Tor v3 `.onion` URL validation
- GET-only bounded page fetch
- no automatic redirects
- no cookies/login/authentication workflow
- no CAPTCHA bypass
- no binary/attachment downloads
- no direct-network fallback
- public-page indicator extraction:
  - email
  - domain
  - username
  - onion URL
  - clearnet URL
  - Bitcoin address
  - Ethereum address
- page SHA-256 and safe metadata
- Federation Catalog source `tor_public_onion_fetch`

The module does **not** store raw HTML or complete page text. URLs discovered on
a page are normalized without query strings/fragments before they become
indicators. Common credential-like assignments in page titles are redacted.

## Tor

The default proxy is:

```text
socks5h://127.0.0.1:9050
```

Override with:

```text
DARKWEB_TOR_SOCKS_PROXY=socks5h://127.0.0.1:9050
```

R13.7 intentionally permits only a local proxy in this first version.

## Dependency

Adds:

```text
socksio>=1.0.0,<2.0.0
```

HTTPX uses `socksio` for SOCKS proxy support. The installer installs it into the
active virtual environment when missing.

## Files

New:
- `app/darkweb_intelligence/__init__.py`
- `app/darkweb_intelligence/contracts.py`
- `app/darkweb_intelligence/tor_client.py`
- `app/darkweb_intelligence/extractor.py`
- `app/darkweb_intelligence/catalog.py`
- `app/darkweb_intelligence/service.py`
- `tests/test_darkweb_intelligence.py`

Patched:
- `app/core/config.py`
- `.env.example`
- `pyproject.toml`
- `app/core/service_container.py`

No database migration.
