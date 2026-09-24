"""Read-only presentation payloads for QML Media and Map workspaces.

This module adapts already persisted investigation data for the desktop UI.
It deliberately performs no writes, analysis execution, entity creation,
evidence creation, commits, deletes, reverse geocoding, or network access.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime
import json
from pathlib import Path
from typing import Any
from uuid import UUID

from PySide6.QtCore import QUrl

from app.models.entity import EntityType


MEDIA_TYPES = {"image", "video", "audio"}
WORKSPACE_LIMIT = 300


def _metadata(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if not value:
        return {}
    try:
        decoded = json.loads(str(value))
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return decoded if isinstance(decoded, dict) else {}


def _processing(metadata: dict[str, Any]) -> dict[str, Any]:
    direct = metadata.get("processing_metadata")
    if isinstance(direct, dict):
        return dict(direct)

    wrapper = metadata.get("processing")
    if isinstance(wrapper, dict):
        nested = wrapper.get("metadata")
        if isinstance(nested, dict):
            return dict(nested)

    return {}


def _date_text(value: Any) -> str:
    if not value:
        return ""
    text = str(value)
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).strftime("%b %d, %Y")
    except ValueError:
        return text[:16]


def _local_file_url(*values: Any) -> str:
    for value in values:
        text = str(value or "").strip()
        if not text:
            continue
        try:
            path = Path(text).expanduser()
        except (TypeError, ValueError):
            continue
        if not path.is_file():
            continue
        try:
            path = path.resolve()
        except OSError:
            pass
        return QUrl.fromLocalFile(str(path)).toString()
    return ""


def _safe_coordinate(value: Any, minimum: float, maximum: float) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if minimum <= number <= maximum else None


def extract_gps(metadata: dict[str, Any]) -> dict[str, Any]:
    processing = _processing(metadata)

    exif = processing.get("exif")
    if not isinstance(exif, dict):
        exif = metadata.get("exif")
    if not isinstance(exif, dict):
        exif = {}

    normalized = exif.get("normalized")
    if not isinstance(normalized, dict):
        normalized = {}

    gps = normalized.get("gps")
    if not isinstance(gps, dict):
        gps = {}

    latitude = gps.get("latitude")
    if latitude is None:
        latitude = processing.get("gps_latitude", metadata.get("gps_latitude"))

    longitude = gps.get("longitude")
    if longitude is None:
        longitude = processing.get("gps_longitude", metadata.get("gps_longitude"))

    altitude = gps.get("altitude")
    if altitude is None:
        altitude = processing.get("gps_altitude", metadata.get("gps_altitude"))

    lat = _safe_coordinate(latitude, -90.0, 90.0)
    lon = _safe_coordinate(longitude, -180.0, 180.0)
    if lat is None or lon is None:
        return {
            "available": False,
            "latitude": None,
            "longitude": None,
            "altitude": None,
        }

    try:
        alt = float(altitude) if altitude is not None else None
    except (TypeError, ValueError):
        alt = None

    return {
        "available": True,
        "latitude": lat,
        "longitude": lon,
        "altitude": alt,
    }


def _result_data(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    data = value.get("data")
    return dict(data) if isinstance(data, dict) else dict(value)


def _case_evidence(container: Any, case_id: str, limit: int = WORKSPACE_LIMIT) -> list[Any]:
    if not case_id:
        return []

    service = getattr(container, "evidence_service", None)
    if service is None:
        return []

    try:
        case_uuid = UUID(case_id)
    except (TypeError, ValueError, AttributeError):
        return []

    try:
        return list(
            service.get_page(
                limit=max(1, int(limit)),
                offset=0,
                case_id=case_uuid,
            )
            or []
        )
    except TypeError:
        getter = getattr(service, "get_case_evidence", None)
        if not callable(getter):
            return []
        try:
            return list(getter(case_uuid) or [])[:limit]
        except Exception:
            return []
    except Exception:
        return []


def _media_record(evidence: Any) -> dict[str, Any]:
    metadata = _metadata(getattr(evidence, "metadata_json", None))
    processing = _processing(metadata)
    evidence_type = str(
        getattr(
            getattr(evidence, "evidence_type", None),
            "value",
            getattr(evidence, "evidence_type", ""),
        )
        or ""
    ).strip().lower()
    file_path = str(getattr(evidence, "file_path", "") or "")

    preview = processing.get("preview")
    preview_path = ""
    if isinstance(preview, dict):
        preview_path = str(preview.get("preview_path") or preview.get("path") or "")

    thumbnail = processing.get("thumbnail")
    thumbnail_path = ""
    if isinstance(thumbnail, dict):
        thumbnail_path = str(thumbnail.get("thumbnail_path") or thumbnail.get("path") or "")

    preview_url = _local_file_url(
        preview_path,
        processing.get("preview_path"),
        metadata.get("preview_path"),
        thumbnail_path,
        processing.get("thumbnail_path"),
        metadata.get("thumbnail_path"),
        file_path if evidence_type == "image" else "",
    )

    image_analysis = metadata.get("image_analysis")
    if not isinstance(image_analysis, dict):
        image_analysis = {}

    ocr_data = _result_data(image_analysis.get("ocr"))
    face_data = _result_data(image_analysis.get("faces"))

    ocr_text = str(
        ocr_data.get("text")
        or processing.get("ocr_text")
        or metadata.get("ocr_text")
        or ""
    ).strip()

    transcript = str(
        processing.get("transcript_text")
        or metadata.get("transcript_text")
        or ""
    ).strip()

    transcription = processing.get("transcription")
    if not transcript and isinstance(transcription, dict):
        transcription_data = transcription.get("data")
        if isinstance(transcription_data, dict):
            transcript = str(transcription_data.get("text") or "").strip()

    try:
        face_count = int(face_data.get("count", 0) or 0)
    except (TypeError, ValueError):
        face_count = 0

    gps = extract_gps(metadata)

    camera = " ".join(
        part
        for part in (
            str(processing.get("camera_make") or metadata.get("camera_make") or "").strip(),
            str(processing.get("camera_model") or metadata.get("camera_model") or "").strip(),
        )
        if part
    )
    date_taken = str(
        processing.get("date_taken")
        or metadata.get("date_taken")
        or ""
    ).strip()

    return {
        "id": str(getattr(evidence, "id", "") or ""),
        "type": evidence_type,
        "title": str(getattr(evidence, "title", "") or "Untitled media"),
        "detail": str(
            getattr(evidence, "description", "")
            or getattr(evidence, "value", "")
            or ""
        ),
        "mimeType": str(getattr(evidence, "mime_type", "") or ""),
        "filePath": file_path,
        "previewUrl": preview_url,
        "date": _date_text(getattr(evidence, "created_at", None)),
        "dateTaken": date_taken,
        "sha256": str(getattr(evidence, "sha256", "") or ""),
        "gps": gps,
        "camera": camera,
        "ocrText": ocr_text[:4000],
        "faceCount": face_count,
        "transcript": transcript[:6000],
        "hasAnalysis": bool(
            ocr_text
            or transcript
            or face_count > 0
            or gps.get("available")
            or image_analysis
        ),
    }


def build_media_workspace_payload(
    container: Any,
    *,
    case_id: str,
    case_title: str,
) -> dict[str, Any]:
    items: list[dict[str, Any]] = []

    for evidence in _case_evidence(container, case_id):
        evidence_type = str(
            getattr(
                getattr(evidence, "evidence_type", None),
                "value",
                getattr(evidence, "evidence_type", ""),
            )
            or ""
        ).strip().lower()

        if evidence_type in MEDIA_TYPES:
            items.append(_media_record(evidence))

    counts = Counter(item.get("type", "") for item in items)

    return {
        "hasCase": bool(case_id),
        "caseId": case_id,
        "caseTitle": case_title,
        "items": items,
        "counts": {
            "all": len(items),
            "image": int(counts.get("image", 0)),
            "video": int(counts.get("video", 0)),
            "audio": int(counts.get("audio", 0)),
            "analyzed": sum(1 for item in items if item.get("hasAnalysis")),
            "gps": sum(1 for item in items if (item.get("gps") or {}).get("available")),
        },
        "limit": WORKSPACE_LIMIT,
    }


def _entity_type_value(entity: Any) -> str:
    return str(
        getattr(
            getattr(entity, "entity_type", None),
            "value",
            getattr(entity, "entity_type", ""),
        )
        or ""
    ).strip().lower()


def _case_locations(container: Any, case_id: str, limit: int = WORKSPACE_LIMIT) -> list[Any]:
    if not case_id:
        return []

    service = getattr(container, "entity_service", None)
    if service is None:
        return []

    try:
        case_uuid = UUID(case_id)
    except (TypeError, ValueError, AttributeError):
        return []

    entity_types = (EntityType.LOCATION, EntityType.ADDRESS)

    try:
        return list(
            service.get_page(
                limit=max(1, int(limit)),
                offset=0,
                case_id=case_uuid,
                entity_types=entity_types,
            )
            or []
        )
    except TypeError as exc:
        message = str(exc)
        if "entity_types" not in message or "unexpected keyword argument" not in message:
            return []

        getter = getattr(service, "get_case_entities", None)
        if not callable(getter):
            return []

        try:
            allowed = {item.value for item in entity_types}
            return [
                row
                for row in list(getter(case_uuid) or [])
                if _entity_type_value(row) in allowed
            ][:limit]
        except Exception:
            return []
    except Exception:
        return []


def _location_coordinates(entity: Any, metadata: dict[str, Any]) -> dict[str, Any]:
    location = metadata.get("location")
    if not isinstance(location, dict):
        location = {}

    latitude = location.get("latitude")
    longitude = location.get("longitude")
    altitude = location.get("altitude")

    if latitude is None or longitude is None:
        parts = [
            part.strip()
            for part in str(getattr(entity, "value", "") or "").split(",")
        ]
        if len(parts) >= 2:
            if latitude is None:
                latitude = parts[0]
            if longitude is None:
                longitude = parts[1]

    lat = _safe_coordinate(latitude, -90.0, 90.0)
    lon = _safe_coordinate(longitude, -180.0, 180.0)

    try:
        alt = float(altitude) if altitude is not None else None
    except (TypeError, ValueError):
        alt = None

    return {
        "available": lat is not None and lon is not None,
        "latitude": lat,
        "longitude": lon,
        "altitude": alt,
    }


def _location_source(metadata: dict[str, Any]) -> str:
    source = metadata.get("source")
    if isinstance(source, str) and source.strip():
        return source.strip()
    if isinstance(source, dict):
        source_type = str(source.get("type") or "").strip().replace("_", " ")
        method = str(source.get("method") or "").strip().replace("_", " ")
        parts = [part for part in (source_type, method) if part]
        if parts:
            return " · ".join(parts)
    return "Stored location"


def build_map_workspace_payload(
    container: Any,
    *,
    case_id: str,
    case_title: str,
) -> dict[str, Any]:
    markers: list[dict[str, Any]] = []
    unmapped: list[dict[str, Any]] = []
    seen: set[str] = set()

    for entity in _case_locations(container, case_id):
        metadata = _metadata(getattr(entity, "metadata_json", None))
        coordinates = _location_coordinates(entity, metadata)
        entity_type = _entity_type_value(entity) or "location"

        map_metadata = metadata.get("map")
        if not isinstance(map_metadata, dict):
            map_metadata = {}

        row = {
            "id": str(getattr(entity, "id", "") or ""),
            "kind": "location",
            "entityType": entity_type,
            "title": str(
                map_metadata.get("marker_name")
                or getattr(entity, "value", "")
                or "Location"
            ),
            "detail": str(
                getattr(entity, "description", "")
                or entity_type.replace("_", " ").title()
            ),
            "latitude": coordinates.get("latitude"),
            "longitude": coordinates.get("longitude"),
            "altitude": coordinates.get("altitude"),
            "source": _location_source(metadata),
        }

        if coordinates.get("available"):
            key = "location:" + row["id"]
            if key not in seen:
                seen.add(key)
                markers.append(row)
        else:
            unmapped.append(row)

    media = build_media_workspace_payload(
        container,
        case_id=case_id,
        case_title=case_title,
    )

    for item in media.get("items", []):
        if not isinstance(item, dict):
            continue
        gps = item.get("gps")
        if not isinstance(gps, dict) or not gps.get("available"):
            continue

        key = "photo:" + str(item.get("id") or "")
        if key in seen:
            continue
        seen.add(key)

        markers.append(
            {
                "id": str(item.get("id") or ""),
                "kind": "photo",
                "entityType": "image",
                "title": str(item.get("title") or "GPS photo"),
                "detail": str(
                    item.get("dateTaken")
                    or item.get("date")
                    or "Image GPS metadata"
                ),
                "latitude": gps.get("latitude"),
                "longitude": gps.get("longitude"),
                "altitude": gps.get("altitude"),
                "source": "Photo GPS",
                "previewUrl": str(item.get("previewUrl") or ""),
                "evidenceId": str(item.get("id") or ""),
            }
        )

    return {
        "hasCase": bool(case_id),
        "caseId": case_id,
        "caseTitle": case_title,
        "markers": markers,
        "unmapped": unmapped,
        "counts": {
            "mapped": len(markers),
            "locations": sum(1 for marker in markers if marker.get("kind") == "location"),
            "photoGps": sum(1 for marker in markers if marker.get("kind") == "photo"),
            "unmapped": len(unmapped),
        },
        "baseLayer": "local_schematic",
        "satelliteAvailable": False,
    }
