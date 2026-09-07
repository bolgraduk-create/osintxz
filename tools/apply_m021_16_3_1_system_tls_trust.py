from __future__ import annotations

from pathlib import Path


TARGET = Path("app/osint/open_web/providers/live_web.py")


def main() -> int:
    if not TARGET.is_file():
        print(f"[FAIL] Missing {TARGET}")
        return 1

    original = TARGET.read_text(encoding="utf-8")
    text = original

    if "def _tls_context(" in text:
        print("[PASS] M021.16.3.1 already applied.")
        return 0

    import_anchor = """import ipaddress
import socket
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

import httpx
"""

    import_replacement = """import ipaddress
import socket
import ssl
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

import httpx

try:
    import truststore
except ImportError:
    truststore = None
"""

    if import_anchor not in text:
        print("[FAIL] Live Web import anchor not found.")
        return 1

    text = text.replace(
        import_anchor,
        import_replacement,
        1,
    )

    client_anchor = """            with httpx.Client(
                timeout=httpx.Timeout(float(timeout)),
                follow_redirects=False,
                transport=self.transport,
                headers={
"""

    client_replacement = """            with httpx.Client(
                timeout=httpx.Timeout(float(timeout)),
                follow_redirects=False,
                transport=self.transport,
                verify=self._tls_context(),
                headers={
"""

    if client_anchor not in text:
        print("[FAIL] httpx.Client anchor not found.")
        return 1

    text = text.replace(
        client_anchor,
        client_replacement,
        1,
    )

    method_anchor = """    @classmethod
    def _validate_public_url(cls, value: str) -> None:
"""

    method = """    @staticmethod
    def _tls_context() -> ssl.SSLContext:
        # Prefer the operating-system trust store on Windows so HTTPS trust
        # decisions match the machine/browser policy. TLS verification stays
        # enabled; this is deliberately not equivalent to verify=False.
        if truststore is not None:
            return truststore.SSLContext(
                ssl.PROTOCOL_TLS_CLIENT
            )

        context = ssl.create_default_context()
        context.check_hostname = True
        context.verify_mode = ssl.CERT_REQUIRED
        return context

"""

    if method_anchor not in text:
        print("[FAIL] validation method anchor not found.")
        return 1

    text = text.replace(
        method_anchor,
        method + method_anchor,
        1,
    )

    compile(text, str(TARGET), "exec")

    backup = TARGET.with_suffix(
        ".py.m021_16_3_1_backup"
    )
    if not backup.exists():
        backup.write_text(
            original,
            encoding="utf-8",
        )

    TARGET.write_text(
        text,
        encoding="utf-8",
    )

    print("[PASS] Live Web now prefers OS trust store via truststore.")
    print("[PASS] TLS certificate verification remains enabled.")
    print("[PASS] No verify=False fallback.")
    print("[PASS] Existing SSRF guards preserved.")
    print("[PASS] No database migration.")
    print(f"[INFO] Backup: {backup}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
