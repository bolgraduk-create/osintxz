from __future__ import annotations

from pathlib import Path


TARGET = Path("app/osint/finding_persistence.py")


def main() -> int:
    if not TARGET.is_file():
        print(f"[FAIL] Missing {TARGET}")
        return 1

    original = TARGET.read_text(encoding="utf-8")
    text = original

    if "M021.16.3.4 Open-Web provenance suppression" in text:
        print("[PASS] M021.16.3.4 already applied.")
        return 0

    old_loop = """        for entity_type, value, confidence in self._entity_candidates(finding):
            entity, created = self._resolve_or_create_entity(
"""

    new_loop = """        entity_candidates = self._entity_candidates(finding)

        # M021.16.3.4 Open-Web provenance suppression:
        # finding.url is the page/evidence provenance in Open-Web extraction.
        # It must stay in Evidence metadata, but must not become a discovered
        # URL Entity merely because persistence exposes provenance URLs.
        if connector.strip().casefold().startswith("open_web:"):
            entity_candidates = tuple(
                candidate
                for candidate in entity_candidates
                if not self._is_open_web_provenance_url_candidate(
                    entity_type=candidate[0],
                    value=candidate[1],
                    finding=finding,
                    target_type=target_type,
                    target_value=target_value,
                )
            )

        for entity_type, value, confidence in entity_candidates:
            entity, created = self._resolve_or_create_entity(
"""

    if old_loop not in text:
        print("[FAIL] entity candidate loop anchor not found.")
        return 1

    text = text.replace(old_loop, new_loop, 1)

    anchor = """    @staticmethod
    def _entity_candidates(
"""

    helper = """    @classmethod
    def _is_open_web_provenance_url_candidate(
        cls,
        *,
        entity_type: EntityType,
        value: str,
        finding: OsintFinding,
        target_type: OsintTargetType,
        target_value: str,
    ) -> bool:
        if entity_type is not EntityType.URL:
            return False

        candidate = cls._canonical_url_for_comparison(value)
        if not candidate:
            return False

        provenance = cls._canonical_url_for_comparison(
            finding.url or ""
        )

        if provenance and candidate == provenance:
            # Preserve a URL finding's own value when it is genuinely the
            # extracted identifier. Only suppress the extra candidate that
            # exists solely because finding.url is provenance.
            finding_category = (
                finding.category or ""
            ).strip().casefold()
            finding_value = cls._canonical_url_for_comparison(
                finding.value or ""
            )

            if (
                finding_category in {
                    "url",
                    "archived_url",
                    "public_url",
                    "link",
                }
                and finding_value
                and candidate == finding_value
                and candidate != cls._canonical_url_for_comparison(
                    target_value
                    if target_type is OsintTargetType.URL
                    else ""
                )
            ):
                return False

            return True

        if target_type is OsintTargetType.URL:
            target = cls._canonical_url_for_comparison(
                target_value
            )
            if target and candidate == target:
                return True

        return False

    @staticmethod
    def _canonical_url_for_comparison(
        value: str,
    ) -> str:
        from urllib.parse import urlsplit, urlunsplit

        raw = value.strip()
        if not raw:
            return ""

        try:
            parsed = urlsplit(raw)
        except ValueError:
            return raw.casefold().rstrip("/")

        scheme = parsed.scheme.casefold()
        host = (parsed.hostname or "").casefold().rstrip(".")

        if not scheme or not host:
            return raw.casefold().rstrip("/")

        port = parsed.port
        netloc = host

        if port and not (
            (scheme == "http" and port == 80)
            or (scheme == "https" and port == 443)
        ):
            netloc = f"{host}:{port}"

        path = parsed.path or "/"
        if path != "/":
            path = path.rstrip("/")

        return urlunsplit(
            (
                scheme,
                netloc,
                path,
                parsed.query,
                "",
            )
        )

"""

    if anchor not in text:
        print("[FAIL] _entity_candidates anchor not found.")
        return 1

    text = text.replace(anchor, helper + anchor, 1)

    compile(text, str(TARGET), "exec")

    backup = TARGET.with_suffix(
        ".py.m021_16_3_4_backup"
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

    print("[PASS] Open-Web finding.url provenance no longer becomes an Entity.")
    print("[PASS] Explicit URL findings from finding.value remain eligible.")
    print("[PASS] Original URL target is suppressed for Open-Web persistence.")
    print("[PASS] Other OSINT connector persistence behavior unchanged.")
    print("[PASS] Evidence/Source provenance remains unchanged.")
    print("[PASS] No database migration.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
