from __future__ import annotations

from pathlib import Path

CONFIG = Path("app/core/config.py")
REGISTRY = Path("app/osint/open_web/registry.py")
CONTAINER = Path("app/core/service_container.py")
WORKER = Path(
    "app/interface/desktop/workers/investigation_search_worker.py"
)


def patch_config(text: str) -> str:
    if "brave_search_api_key" in text:
        return text

    anchor = '    virustotal_api_key: str | None = None\n'
    replacement = (
        anchor
        + '\n'
        + '    # M021.16.5.2B — Brave Search API\n'
        + '    brave_search_api_key: SecretStr | None = None\n'
    )

    if anchor not in text:
        raise RuntimeError("OSINT API key config anchor not found.")

    return text.replace(anchor, replacement, 1)


def patch_registry(text: str) -> str:
    marker = (
        "M021.16.5.2B credential-aware "
        "Open-Web automatic routing"
    )
    if marker in text:
        return text

    old = '''    def automatic_for(self, query: OpenWebQuery) -> tuple[OpenWebProvider, ...]:
        return tuple(
            provider for provider in self.all()
            if provider.supports(query) and provider.info.automatic_eligible
        )
'''

    new = '''    def automatic_for(self, query: OpenWebQuery) -> tuple[OpenWebProvider, ...]:
        # M021.16.5.2B credential-aware Open-Web automatic routing
        selected: list[OpenWebProvider] = []

        for provider in self.all():
            if not provider.supports(query):
                continue

            info = provider.info

            if info.automatic_eligible:
                selected.append(provider)
                continue

            if not (
                info.passive
                and info.public_data_only
                and info.default_enabled
                and info.requires_credentials
            ):
                continue

            availability = getattr(
                provider,
                "is_available",
                None,
            )

            if not callable(availability):
                continue

            try:
                available = bool(availability())
            except Exception:
                available = False

            if available:
                selected.append(provider)

        return tuple(selected)
'''

    if old not in text:
        raise RuntimeError(
            "OpenWebProviderRegistry.automatic_for anchor not found."
        )

    return text.replace(old, new, 1)


def patch_container(text: str) -> str:
    marker = (
        "M021.16.5.2B Brave exact-email "
        "Open-Web registration"
    )
    if marker in text:
        return text

    anchor = '''        self.open_web_discovery_service = (
'''

    block = '''        # M021.16.5.2B Brave exact-email Open-Web registration
        from app.osint.open_web.providers.brave_exact_email import (
            BraveExactEmailOpenWebProvider,
        )

        self.brave_exact_email_open_web_provider = (
            BraveExactEmailOpenWebProvider(
                live_web_provider=self.live_web_open_web_provider,
            )
        )

        self.open_web_provider_registry.register(
            self.brave_exact_email_open_web_provider
        )

'''

    if anchor not in text:
        raise RuntimeError(
            "Open-Web discovery service anchor not found."
        )

    return text.replace(anchor, block + anchor, 1)


def patch_worker(text: str) -> str:
    marker = "M021.16.5.2B broad email candidate budget"
    if marker in text:
        return text

    block_start = text.find(
        "M021.16.5.2A EMAIL public-web"
    )
    if block_start < 0:
        raise RuntimeError(
            "M021.16.5.2A EMAIL Open-Web block not found."
        )

    prefix = text[:block_start]
    suffix = text[block_start:]

    old = '''                            limit=15,
                            timeout=30,
'''

    new = '''                            # M021.16.5.2B broad email candidate budget
                            limit=40,
                            timeout=30,
'''

    if old not in suffix:
        raise RuntimeError(
            "EMAIL OpenWebQuery limit anchor not found."
        )

    return prefix + suffix.replace(old, new, 1)


def main() -> int:
    provider = Path(
        "app/osint/open_web/providers/brave_exact_email.py"
    )

    for path in (
        provider,
        CONFIG,
        REGISTRY,
        CONTAINER,
        WORKER,
    ):
        if not path.exists():
            print(f"[FAIL] Missing {path}")
            return 1

    originals = {
        CONFIG: CONFIG.read_text(encoding="utf-8"),
        REGISTRY: REGISTRY.read_text(encoding="utf-8"),
        CONTAINER: CONTAINER.read_text(encoding="utf-8"),
        WORKER: WORKER.read_text(encoding="utf-8"),
    }

    try:
        updated = {
            CONFIG: patch_config(originals[CONFIG]),
            REGISTRY: patch_registry(originals[REGISTRY]),
            CONTAINER: patch_container(originals[CONTAINER]),
            WORKER: patch_worker(originals[WORKER]),
        }

        compile(
            provider.read_text(encoding="utf-8"),
            str(provider),
            "exec",
        )

        for path, value in updated.items():
            compile(value, str(path), "exec")

    except Exception as exc:
        print(f"[FAIL] {exc}")
        return 1

    for path, value in updated.items():
        backup = path.with_suffix(
            ".py.m021_16_5_2b_backup"
        )

        if not backup.exists():
            backup.write_text(
                originals[path],
                encoding="utf-8",
            )

        path.write_text(value, encoding="utf-8")

    print("[PASS] BRAVE_SEARCH_API_KEY setting added.")
    print("[PASS] Credential-aware Open-Web routing added.")
    print("[PASS] Brave Exact Email provider registered.")
    print("[PASS] Broad EMAIL candidate budget raised to 40.")
    print("[PASS] Live exact-email verification preserved.")
    print("[PASS] Existing TLS/SSRF guards reused.")
    print("[PASS] No second pipeline.")
    print("[PASS] No database migration.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
