from pathlib import Path

def main() -> int:
    fusion=Path("app/osint/username_fusion.py").read_text(encoding="utf-8")
    p=Path("app/osint/finding_persistence.py").read_text(encoding="utf-8")
    checks=[("fusion policy","class UsernameProfileFusionPolicy" in fusion),("cap","CAP = 0.97" in fusion),("marker","M021.16.6.4.3A cross-source profile fusion" in p),("precompute","_build_username_profile_fusion" in p),("update confidence","self.entity_service.update_confidence" in p)]
    print("="*72); print("M021.16.6.4.3A CROSS-SOURCE CONFIDENCE AUDIT"); print("="*72)
    failed=False
    for label,ok in checks:
        print(f"[{'PASS' if ok else 'FAIL'}] {label}"); failed |= not ok
    print(f"\nRESULT: {'FAIL' if failed else 'PASS'}")
    return 1 if failed else 0

if __name__ == "__main__": raise SystemExit(main())
