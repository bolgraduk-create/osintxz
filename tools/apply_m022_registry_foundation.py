from pathlib import Path
import shutil

TARGET = Path("app/core/service_container.py")

def main() -> int:
    if not TARGET.exists():
        print(f"[FAIL] Missing: {TARGET}")
        return 1
    original = TARGET.read_text(encoding="utf-8")
    if "# M022 Registry Intelligence" in original:
        print("[PASS] Already wired.")
        return 0
    imports = "\nfrom app.application.registry_intelligence_service import RegistryIntelligenceService\nfrom app.infrastructure.registries.gleif_client import GleifRegistryHttpClient\nfrom app.registry_intelligence.providers.gleif import GleifRegistryProvider\nfrom app.registry_intelligence.registry import RegistryProviderRegistry\n"
    anchor = "from __future__ import annotations\n"
    if anchor not in original:
        print("[FAIL] import anchor not found.")
        return 1
    text = original.replace(anchor, anchor + imports, 1)
    init_anchor = "        # ==================================================\n        # Open-Web Discovery / Enrichment\n"
    init = "        # ==================================================\n        # M022 Registry Intelligence\n        # ==================================================\n\n        self.registry_provider_registry = RegistryProviderRegistry()\n        self.gleif_registry_http_client = GleifRegistryHttpClient()\n        self.gleif_registry_provider = GleifRegistryProvider(\n            client=self.gleif_registry_http_client\n        )\n        self.registry_provider_registry.register(\n            self.gleif_registry_provider\n        )\n        self.registry_intelligence_service = RegistryIntelligenceService(\n            registry=self.registry_provider_registry\n        )\n\n"
    if init_anchor not in text:
        print("[FAIL] Open-Web init anchor not found.")
        return 1
    text = text.replace(init_anchor, init + init_anchor, 1)
    try:
        compile(text, str(TARGET), "exec")
    except Exception as exc:
        print("[FAIL] compile:", exc)
        return 1
    backup = TARGET.with_suffix(TARGET.suffix + ".m022_backup")
    if not backup.exists():
        shutil.copy2(TARGET, backup)
    TARGET.write_text(text, encoding="utf-8")
    print("[PASS] Registry contracts/service/provider registry/GLEIF wired.")
    print("[PASS] No database migration.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
