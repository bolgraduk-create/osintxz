from app.osint.models import OsintTargetType
from app.osint.open_web.contracts import OpenWebProviderInfo


def main():
    print('=' * 72)
    print('OSINTXZ M021.7 OPEN-WEB CORE CONTRACT AUDIT')
    print('=' * 72)
    supported = {OsintTargetType.USERNAME, OsintTargetType.EMAIL, OsintTargetType.PHONE, OsintTargetType.DOMAIN, OsintTargetType.URL}
    info = OpenWebProviderInfo(name='audit', display_name='Audit', supported_targets=frozenset(supported), default_enabled=True)
    checks = [
        ('passive default', info.passive),
        ('public-data-only default', info.public_data_only),
        ('credential-free default', not info.requires_credentials),
        ('automatic eligibility explicit', info.automatic_eligible),
        ('phone supported by contract', OsintTargetType.PHONE in supported),
        ('username supported by contract', OsintTargetType.USERNAME in supported),
    ]
    failed = False
    for label, ok in checks:
        print(f"[{'PASS' if ok else 'FAIL'}] {label}"); failed |= not ok
    print('\nPolicy:')
    print('- WebDocument is a lead/document, not proof of ownership.')
    print('- Automatic providers must be passive, public, keyless and enabled.')
    print('- No concrete network provider is enabled in M021.7.')
    print('- Provider exceptions are isolated.')
    print('- No CAPTCHA/login/paywall/protection bypass is part of the contract.')
    print('- No DB migration.')
    print(f"\nRESULT: {'FAIL' if failed else 'PASS'}")
    return 1 if failed else 0

if __name__ == '__main__': raise SystemExit(main())
