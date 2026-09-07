
from pathlib import Path

def main():
    text = Path("app/core/service_container.py").read_text(encoding="utf-8")
    recursive = text.find("self.osint_recursive_enrichment_service =")
    bridge = text.find("self.open_web_recursive_pivot_service =")
    checks = [
        ("recursive service exists", recursive >= 0),
        ("Open-Web bridge exists", bridge >= 0),
        ("recursive service created first", 0 <= recursive < bridge),
        ("one recursive service", text.count("self.osint_recursive_enrichment_service =") == 1),
        ("one Open-Web recursive bridge", text.count("self.open_web_recursive_pivot_service =") == 1),
        ("single OsintPipeline", text.count("self.osint_pipeline =") == 1),
    ]
    failed = False
    print("=" * 72)
    print("M021.14.1 COMPOSITION ORDER AUDIT")
    print("=" * 72)
    for label, ok in checks:
        print(f"[{'PASS' if ok else 'FAIL'}] {label}")
        failed |= not ok
    print(f"\nRESULT: {'FAIL' if failed else 'PASS'}")
    return 1 if failed else 0

if __name__ == "__main__":
    raise SystemExit(main())
