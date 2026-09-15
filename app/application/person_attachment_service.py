"""Manual attachments for PERSON entities.

This service records analyst-supplied material as ordinary investigation
Source/Evidence data and links it to an existing PERSON entity.  It deliberately
does not create identity relationships or mark manually supplied identifiers as
verified.

Database transaction ownership remains with the caller.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import mimetypes
from pathlib import Path
import re
import shutil
from typing import Any
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4

from app.core.config import DATA_DIR
from app.models.entity import EntityType
from app.models.evidence import EvidenceType
from app.models.source import SourceType


@dataclass(slots=True)
class PersonAttachmentResult:
    evidence_id: str
    source_id: str
    attachment_kind: str
    related_entity_id: str = ""
    managed_path: str = ""
    duplicate: bool = False


class PersonAttachmentService:
    """Create explicit analyst-supplied attachments for a PERSON entity."""

    MAX_PHOTO_BYTES = 25 * 1024 * 1024
    MAX_FILE_BYTES = 100 * 1024 * 1024
    MANAGED_DIR = Path(DATA_DIR) / "person_attachments"

    TEXT_KINDS: dict[str, tuple[EvidenceType, EntityType | None]] = {
        "link": (EvidenceType.LINK, EntityType.URL),
        "email": (EvidenceType.EMAIL, EntityType.EMAIL),
        "phone": (EvidenceType.PHONE, EntityType.PHONE),
        "username": (EvidenceType.USERNAME, EntityType.USERNAME),
        "note": (EvidenceType.OTHER, None),
    }

    def __init__(
        self,
        *,
        source_service: Any,
        evidence_service: Any,
        entity_service: Any,
        evidence_link_service: Any,
    ) -> None:
        self.source_service = source_service
        self.evidence_service = evidence_service
        self.entity_service = entity_service
        self.evidence_link_service = evidence_link_service

    def add(
        self,
        *,
        person: Any,
        kind: str,
        title: str = "",
        value: str = "",
        description: str = "",
    ) -> PersonAttachmentResult:
        self._validate_person(person)
        normalized_kind = str(kind or "").strip().lower()
        if normalized_kind in {"photo", "file"}:
            return self._add_file(
                person=person,
                kind=normalized_kind,
                title=title,
                source_value=value,
                description=description,
            )
        if normalized_kind not in self.TEXT_KINDS:
            raise ValueError("Unsupported person attachment type.")
        return self._add_text(
            person=person,
            kind=normalized_kind,
            title=title,
            value=value,
            description=description,
        )

    @classmethod
    def managed_file_path(cls, value: str) -> Path | None:
        """Return a resolved managed attachment path or None for external paths."""
        return cls._validated_managed_path(value)

    def cleanup_managed_file(self, managed_path: str) -> None:
        """Best-effort cleanup if the caller's transaction fails to commit."""
        path = self._validated_managed_path(managed_path)
        if path is None:
            return
        try:
            path.unlink(missing_ok=True)
        except OSError:
            return
        self._remove_empty_parents(path.parent)

    # ------------------------------------------------------------------
    # Text/manual identifiers
    # ------------------------------------------------------------------

    def _add_text(
        self,
        *,
        person: Any,
        kind: str,
        title: str,
        value: str,
        description: str,
    ) -> PersonAttachmentResult:
        normalized_value = self._normalize_text_value(kind, value)
        if self._has_duplicate(person, kind=kind, value=normalized_value):
            return PersonAttachmentResult(
                evidence_id="",
                source_id="",
                attachment_kind=kind,
                duplicate=True,
            )

        evidence_type, entity_type = self.TEXT_KINDS[kind]
        attachment_id = uuid4().hex
        case_id = getattr(person, "case_id")
        person_id = getattr(person, "id")

        source_type = SourceType.WEBSITE if kind == "link" else SourceType.OTHER
        source_path = (
            normalized_value
            if kind == "link"
            else f"manual://person/{person_id}/{attachment_id}"
        )
        display_title = self._title_for(kind, title, normalized_value)
        metadata = self._metadata(
            kind=kind,
            person_id=str(person_id),
            value=normalized_value,
            original_path="",
            managed_path="",
            sha256_value="",
        )
        if kind == "link":
            metadata["url"] = normalized_value

        source = self.source_service.create_source(
            case_id=case_id,
            name=f"Manual · {display_title}"[:255],
            source_type=source_type,
            path=source_path,
            description=(
                "Analyst-supplied person attachment. This is a manual assertion, "
                "not independently verified identity evidence."
            ),
        )
        evidence = self.evidence_service.create_evidence(
            case_id=case_id,
            source_id=source.id,
            evidence_type=evidence_type,
            title=display_title[:255],
            value=normalized_value[:1024],
            description=(description.strip() or "Manually attached to person card.")[:4000],
        )
        evidence.metadata_json = json.dumps(
            metadata,
            ensure_ascii=False,
            sort_keys=True,
        )
        self._flush_evidence()
        self.evidence_link_service.ensure_link(
            evidence_id=evidence.id,
            entity_id=person_id,
        )

        related_entity_id = ""
        if entity_type is not None:
            related, _ = self.entity_service.resolve_or_create_entity(
                case_id=case_id,
                entity_type=entity_type,
                value=normalized_value,
                confidence=1.0,
                metadata_json=json.dumps(
                    {
                        "workflow": "manual_person_attachment",
                        "attachment_kind": kind,
                        "association_basis": "manual_user_assertion",
                        "identity_verified": False,
                        **({"url": normalized_value} if kind == "link" else {}),
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                ),
                description=(
                    "Identifier manually attached to a person card; association is "
                    "user-supplied and not independently verified."
                ),
            )
            related_entity_id = str(related.id)
            self.evidence_link_service.ensure_link(
                evidence_id=evidence.id,
                entity_id=related.id,
            )

        return PersonAttachmentResult(
            evidence_id=str(evidence.id),
            source_id=str(source.id),
            attachment_kind=kind,
            related_entity_id=related_entity_id,
        )

    # ------------------------------------------------------------------
    # Managed local files
    # ------------------------------------------------------------------

    def _add_file(
        self,
        *,
        person: Any,
        kind: str,
        title: str,
        source_value: str,
        description: str,
    ) -> PersonAttachmentResult:
        source_path = Path(str(source_value or "").strip()).expanduser()
        if not source_path.is_file():
            raise ValueError("Selected attachment file does not exist.")

        size = source_path.stat().st_size
        maximum = self.MAX_PHOTO_BYTES if kind == "photo" else self.MAX_FILE_BYTES
        if size <= 0:
            raise ValueError("Selected attachment file is empty.")
        if size > maximum:
            limit_mb = maximum // (1024 * 1024)
            raise ValueError(f"Attachment exceeds the {limit_mb} MB limit.")

        mime_type = mimetypes.guess_type(source_path.name)[0] or "application/octet-stream"
        if kind == "photo" and not mime_type.startswith("image/"):
            raise ValueError("Photo attachments must be image files.")

        digest = self._file_sha256(source_path)
        if self._has_duplicate(person, kind=kind, sha256_value=digest):
            return PersonAttachmentResult(
                evidence_id="",
                source_id="",
                attachment_kind=kind,
                duplicate=True,
            )

        case_id = getattr(person, "case_id")
        person_id = getattr(person, "id")
        destination_dir = self.MANAGED_DIR / str(case_id) / str(person_id)
        destination_dir.mkdir(parents=True, exist_ok=True)
        safe_name = self._safe_filename(source_path.name)
        destination = destination_dir / f"{uuid4().hex}_{safe_name}"

        try:
            shutil.copy2(source_path, destination)
            copied_digest = self._file_sha256(destination)
            if copied_digest != digest:
                raise OSError("Attachment checksum mismatch after copy.")

            evidence_type = EvidenceType.IMAGE if kind == "photo" else EvidenceType.DOCUMENT
            source_type = SourceType.IMAGE if kind == "photo" else SourceType.FILE
            display_title = self._title_for(kind, title, source_path.name)
            metadata = self._metadata(
                kind=kind,
                person_id=str(person_id),
                value=source_path.name,
                original_path=str(source_path),
                managed_path=str(destination),
                sha256_value=digest,
            )

            source = self.source_service.create_source(
                case_id=case_id,
                name=f"Manual · {display_title}"[:255],
                source_type=source_type,
                path=str(destination),
                description=(
                    "Managed copy of a file manually attached to a person card."
                ),
            )
            evidence = self.evidence_service.create_evidence(
                case_id=case_id,
                source_id=source.id,
                evidence_type=evidence_type,
                title=display_title[:255],
                value=source_path.name[:1024],
                file_path=str(destination),
                mime_type=mime_type[:128],
                description=(description.strip() or "Manually attached to person card.")[:4000],
            )
            evidence.sha256 = digest
            evidence.metadata_json = json.dumps(
                metadata,
                ensure_ascii=False,
                sort_keys=True,
            )
            self._flush_evidence()
            self.evidence_link_service.ensure_link(
                evidence_id=evidence.id,
                entity_id=person_id,
            )
        except Exception:
            destination.unlink(missing_ok=True)
            self._remove_empty_parents(destination.parent)
            raise

        return PersonAttachmentResult(
            evidence_id=str(evidence.id),
            source_id=str(source.id),
            attachment_kind=kind,
            managed_path=str(destination),
        )

    # ------------------------------------------------------------------
    # Validation / helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_person(person: Any) -> None:
        if person is None:
            raise ValueError("Person entity is unavailable.")
        entity_type = getattr(
            getattr(person, "entity_type", None),
            "value",
            getattr(person, "entity_type", None),
        )
        if str(entity_type) != EntityType.PERSON.value:
            raise ValueError("Attachments can only be added to PERSON entities.")
        if not getattr(person, "id", None) or not getattr(person, "case_id", None):
            raise ValueError("Person entity is missing investigation identity.")

    @classmethod
    def _normalize_text_value(cls, kind: str, value: str) -> str:
        text = str(value or "").strip()
        if not text:
            raise ValueError("Attachment value is required.")
        if kind == "link":
            parsed = urlsplit(text)
            if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
                raise ValueError("Link must be an explicit http:// or https:// URL.")
            text = urlunsplit(
                (parsed.scheme.lower(), parsed.netloc, parsed.path, parsed.query, "")
            )
        elif kind == "email":
            text = text.casefold()
            if len(text) > 254 or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", text):
                raise ValueError("Enter a valid email address.")
        elif kind == "phone":
            if sum(ch.isdigit() for ch in text) < 5:
                raise ValueError("Enter a valid phone number.")
        elif kind == "username":
            if len(text) > 512:
                raise ValueError("Username is too long.")
        elif kind == "note":
            if len(text) > 1000:
                raise ValueError("Manual note is limited to 1000 characters.")
        return text

    def _has_duplicate(
        self,
        person: Any,
        *,
        kind: str,
        value: str = "",
        sha256_value: str = "",
    ) -> bool:
        evidence_rows = self.evidence_link_service.get_evidence_objects_for_entity(
            getattr(person, "id")
        ) or []
        target_value = str(value or "").strip().casefold()
        target_sha = str(sha256_value or "").strip().lower()
        for evidence in evidence_rows:
            metadata = self._json_dict(getattr(evidence, "metadata_json", None))
            if metadata.get("workflow") != "manual_person_attachment":
                continue
            if str(metadata.get("attachment_kind") or "").strip().lower() != kind:
                continue
            if target_sha and str(getattr(evidence, "sha256", "") or "").lower() == target_sha:
                return True
            if target_value and str(getattr(evidence, "value", "") or "").strip().casefold() == target_value:
                return True
        return False

    @staticmethod
    def _metadata(
        *,
        kind: str,
        person_id: str,
        value: str,
        original_path: str,
        managed_path: str,
        sha256_value: str,
    ) -> dict[str, Any]:
        return {
            "workflow": "manual_person_attachment",
            "attachment_kind": kind,
            "person_entity_id": person_id,
            "association_basis": "manual_user_assertion",
            "identity_verified": False,
            "value": value,
            "original_path": original_path,
            "managed_path": managed_path,
            "sha256": sha256_value,
        }

    @staticmethod
    def _title_for(kind: str, title: str, fallback: str) -> str:
        explicit = str(title or "").strip()
        if explicit:
            return explicit[:255]
        label = {
            "link": "Profile / page",
            "photo": "Person photo",
            "file": "Person file",
            "email": "Email address",
            "phone": "Phone number",
            "username": "Username / account",
            "note": "Analyst note",
        }.get(kind, "Person attachment")
        fallback_text = str(fallback or "").strip()
        return f"{label} · {fallback_text}"[:255] if fallback_text else label

    def _flush_evidence(self) -> None:
        repository = getattr(self.evidence_service, "repository", None)
        session = getattr(repository, "session", None)
        if session is not None:
            session.flush()

    @staticmethod
    def _file_sha256(path: Path) -> str:
        digest = sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _safe_filename(value: str) -> str:
        name = Path(str(value or "attachment")).name
        cleaned = re.sub(r"[^A-Za-z0-9._ -]+", "_", name).strip(" .")
        return (cleaned or "attachment")[:160]

    @classmethod
    def _validated_managed_path(cls, value: str) -> Path | None:
        text = str(value or "").strip()
        if not text:
            return None
        try:
            root = cls.MANAGED_DIR.resolve()
            path = Path(text).resolve()
            path.relative_to(root)
        except (OSError, ValueError):
            return None
        return path

    @classmethod
    def _remove_empty_parents(cls, path: Path) -> None:
        root = cls.MANAGED_DIR.resolve()
        current = path
        while current != root:
            try:
                current.rmdir()
            except OSError:
                return
            current = current.parent

    @staticmethod
    def _json_dict(value: Any) -> dict[str, Any]:
        if isinstance(value, dict):
            return dict(value)
        if not value:
            return {}
        try:
            parsed = json.loads(str(value))
        except (TypeError, ValueError, json.JSONDecodeError):
            return {}
        return parsed if isinstance(parsed, dict) else {}
