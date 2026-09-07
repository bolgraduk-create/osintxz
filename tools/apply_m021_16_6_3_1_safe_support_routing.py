from __future__ import annotations

from pathlib import Path

TARGET = Path("app/osint/pivot_router.py")


def main() -> int:
    if not TARGET.is_file():
        print(f"[FAIL] Missing {TARGET}")
        return 1

    original = TARGET.read_text(encoding="utf-8")

    marker = "M021.16.6.3.1 safe SUPPORT routing"
    if marker in original:
        print("[PASS] Patch already applied.")
        return 0

    text = original

    old_import = """from app.osint.capabilities import (
    ConnectorDisposition,
    DiscoveryGoal,
    OsintConnectorCapability,
    OSINT_CAPABILITY_CATALOG,
)
"""

    new_import = """from app.osint.capabilities import (
    ConnectorDisposition,
    DiscoveryGoal,
    NetworkMode,
    OsintConnectorCapability,
    OSINT_CAPABILITY_CATALOG,
)
"""

    if old_import not in text:
        print("[FAIL] capabilities import anchor not found.")
        return 1

    text = text.replace(old_import, new_import, 1)

    old_filter = """                    and not capability.requires_api_key
                    and capability.disposition in allowed_dispositions
"""

    new_filter = """                    and not capability.requires_api_key
                    and capability.disposition in allowed_dispositions
                    and self._network_mode_allowed_for_goal(
                        capability=capability,
                        goal=goal,
                    )
"""

    if old_filter not in text:
        print("[FAIL] connector eligibility anchor not found.")
        return 1

    text = text.replace(old_filter, new_filter, 1)

    old_method = """        if goal is DiscoveryGoal.ACCOUNT_DISCOVERY:
            # Account discovery must be driven by primary discovery engines.
            # SUPPORT tools may validate/enrich later, but must not widen the
            # core account-discovery route.
            return frozenset({ConnectorDisposition.CORE})

        return frozenset(
            {
                ConnectorDisposition.CORE,
                ConnectorDisposition.SUPPORT,
            }
        )

    def route_defaults(
"""

    new_method = """        if goal is DiscoveryGoal.ACCOUNT_DISCOVERY:
            # M021.16.6.3.1 safe SUPPORT routing
            #
            # SUPPORT account-discovery engines are allowed only when
            # the network-mode guard confirms they are passive.
            return frozenset(
                {
                    ConnectorDisposition.CORE,
                    ConnectorDisposition.SUPPORT,
                }
            )

        return frozenset(
            {
                ConnectorDisposition.CORE,
                ConnectorDisposition.SUPPORT,
            }
        )

    @staticmethod
    def _network_mode_allowed_for_goal(
        *,
        capability: OsintConnectorCapability,
        goal: DiscoveryGoal,
    ) -> bool:
        \"\"\"Keep automatic account discovery strictly passive.\"\"\"

        if goal is DiscoveryGoal.ACCOUNT_DISCOVERY:
            return capability.network_mode in {
                NetworkMode.PASSIVE,
                NetworkMode.PASSIVE_REMOTE,
            }

        # Preserve pre-existing routing behavior for all other goals.
        return True

    def route_defaults(
"""

    if old_method not in text:
        print("[FAIL] ACCOUNT_DISCOVERY disposition anchor not found.")
        return 1

    text = text.replace(old_method, new_method, 1)

    try:
        compile(text, str(TARGET), "exec")
    except Exception as exc:
        print(f"[FAIL] Patched source does not compile: {exc}")
        return 1

    backup = TARGET.with_suffix(".py.m021_16_6_3_1_backup")

    if not backup.exists():
        backup.write_text(original, encoding="utf-8")

    TARGET.write_text(text, encoding="utf-8")

    print("[PASS] ACCOUNT_DISCOVERY now accepts CORE + SUPPORT.")
    print("[PASS] ACCOUNT_DISCOVERY limited to PASSIVE/PASSIVE_REMOTE.")
    print("[PASS] CONDITIONAL/SEPARATE/REPLACE remain excluded.")
    print("[PASS] Credentialed connectors remain excluded.")
    print("[PASS] Other discovery goals preserve previous behavior.")
    print("[PASS] Pivot depth/budget/visited policy unchanged.")
    print("[PASS] No database migration.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
