from __future__ import annotations

from pathlib import Path

TARGET = Path("app/osint/open_web/extraction_bridge.py")


def main() -> int:
    if not TARGET.is_file():
        print(f"[FAIL] Missing {TARGET}")
        return 1

    original = TARGET.read_text(encoding="utf-8")
    text = original

    if "M021.16.3.2 quality gate" in text:
        print("[PASS] M021.16.3.2 already applied.")
        return 0

    text = text.replace(
        "from dataclasses import dataclass, field\nfrom typing import Iterable\n",
        "from dataclasses import dataclass, field\nfrom typing import Iterable\nfrom urllib.parse import urlsplit, urlunsplit\n",
        1,
    )

    text = text.replace(
        "from app.osint.open_web.contracts import OpenWebDocument, OpenWebQuery\n",
        "from app.models.entity import EntityType\nfrom app.osint.open_web.contracts import OpenWebDocument, OpenWebQuery\n",
        1,
    )

    old_extract = """        candidates, skipped_duplicates = self._deduplicate_candidates(
            raw_candidates
        )

        findings = [
"""
    new_extract = """        candidates, skipped_duplicates = self._deduplicate_candidates(
            raw_candidates
        )

        # M021.16.3.2 quality gate
        candidates, skipped_quality = self._filter_quality_candidates(
            candidates,
            document=document,
        )
        skipped_duplicates += skipped_quality

        findings = [
"""
    if old_extract not in text:
        print("[FAIL] extract_document anchor not found.")
        return 1
    text = text.replace(old_extract, new_extract, 1)

    old_builder = """    @staticmethod
    def _build_extraction_text(
        document: OpenWebDocument,
    ) -> str:
        \"\"\"Include the discovered page URL in the same unified extraction path.\"\"\"

        parts = [
            document.url.strip(),
            document.extraction_text.strip(),
        ]

        return "\\n".join(
            part
            for part in parts
            if part
        )
"""
    new_builder = """    @staticmethod
    def _build_extraction_text(
        document: OpenWebDocument,
    ) -> str:
        \"\"\"Extract page content only; document URL stays provenance metadata.\"\"\"

        return document.extraction_text.strip()
"""
    if old_builder not in text:
        print("[FAIL] _build_extraction_text anchor not found.")
        return 1
    text = text.replace(old_builder, new_builder, 1)

    helper_anchor = """    @staticmethod
    def _deduplicate_candidates(
"""
    helper = """    @classmethod
    def _filter_quality_candidates(
        cls,
        candidates: Iterable[ExtractionCandidate],
        *,
        document: OpenWebDocument,
    ) -> tuple[list[ExtractionCandidate], int]:
        accepted: list[ExtractionCandidate] = []
        skipped = 0
        document_url = cls._canonical_url(document.url)

        for candidate in candidates:
            if candidate.entity_type is EntityType.URL:
                candidate_url = cls._canonical_url(
                    candidate.normalized_value or candidate.value
                )
                if document_url and candidate_url == document_url:
                    skipped += 1
                    continue

            if candidate.entity_type is EntityType.PHONE:
                if not cls._plausible_open_web_phone(candidate.value):
                    skipped += 1
                    continue

            accepted.append(candidate)

        return accepted, skipped

    @staticmethod
    def _plausible_open_web_phone(value: str) -> bool:
        raw = value.strip()
        digits = "".join(ch for ch in raw if ch.isdigit())

        if len(digits) < 7 or len(digits) > 15:
            return False

        if raw.isdigit():
            return False

        has_plus = raw.startswith("+")
        has_phone_formatting = any(
            ch in raw
            for ch in (" ", "-", "(", ")")
        )

        if not has_plus and not has_phone_formatting:
            return False

        if len(digits) in {8, 14}:
            year_text = digits[:4]
            if year_text.isdigit():
                year = int(year_text)
                if 1900 <= year <= 2100:
                    return False

        return True

    @staticmethod
    def _canonical_url(value: str) -> str:
        raw = value.strip()
        if not raw:
            return ""

        try:
            parsed = urlsplit(raw)
        except ValueError:
            return raw.casefold().rstrip("/")

        scheme = parsed.scheme.casefold()
        host = (parsed.hostname or "").casefold().rstrip(".")
        if not host:
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
    if helper_anchor not in text:
        print("[FAIL] helper anchor not found.")
        return 1
    text = text.replace(helper_anchor, helper + helper_anchor, 1)

    compile(text, str(TARGET), "exec")

    backup = TARGET.with_suffix(".py.m021_16_3_2_backup")
    if not backup.exists():
        backup.write_text(original, encoding="utf-8")

    TARGET.write_text(text, encoding="utf-8")

    print("[PASS] Document URL removed from extraction text.")
    print("[PASS] Self-URL candidates filtered as provenance.")
    print("[PASS] Ambiguous bare numeric phone candidates rejected for Open-Web.")
    print("[PASS] UnifiedExtractionService unchanged.")
    print("[PASS] No database migration.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
