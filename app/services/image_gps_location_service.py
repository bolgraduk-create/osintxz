"""
Image GPS location service.

Creates or reuses investigation LOCATION entities
from GPS metadata stored on image evidence.

Responsibilities:

- load and validate IMAGE evidence
- parse evidence metadata_json
- extract GPS coordinates from supported metadata layouts
- validate latitude and longitude
- create or reuse LOCATION entity
- link source image evidence to LOCATION entity
- avoid duplicate EvidenceEntity links
- return normalized location data for future map UI

Does NOT:

- commit or rollback transactions
- interact with desktop widgets
- perform reverse geocoding
- render maps
- modify source image files
"""

from __future__ import annotations

import json

from typing import Any
from uuid import UUID

from app.models.entity import (
    Entity,
    EntityType,
)

from app.models.evidence import (
    Evidence,
    EvidenceType,
)

from app.services.entity_service import (
    EntityService,
)

from app.services.evidence_link_service import (
    EvidenceLinkService,
)

from app.services.evidence_service import (
    EvidenceService,
)


class ImageGpsLocationService:
    """
    Application service for creating investigation
    locations from image GPS metadata.
    """

    COORDINATE_PRECISION = 7

    def __init__(
        self,
        evidence_service: EvidenceService,
        entity_service: EntityService,
        evidence_link_service: EvidenceLinkService,
    ) -> None:

        self.evidence_service = (
            evidence_service
        )

        self.entity_service = (
            entity_service
        )

        self.evidence_link_service = (
            evidence_link_service
        )

    # ==========================================================
    # Public API
    # ==========================================================

    def create_from_image(
        self,
        evidence_id: str | UUID,
    ) -> dict[str, Any]:
        """
        Create or reuse LOCATION entity from GPS metadata
        of one IMAGE evidence record.
        """

        normalized_evidence_id = (
            self._normalize_uuid(
                evidence_id,
                field_name="evidence_id",
            )
        )

        evidence = self._require_image_evidence(
            normalized_evidence_id
        )

        metadata = self._parse_metadata(
            evidence.metadata_json
        )

        gps = self._extract_gps(
            metadata
        )

        latitude = self._normalize_latitude(
            gps.get(
                "latitude"
            )
        )

        longitude = self._normalize_longitude(
            gps.get(
                "longitude"
            )
        )

        altitude = self._normalize_optional_float(
            gps.get(
                "altitude"
            )
        )

        normalized_value = (
            self._build_normalized_value(
                latitude=latitude,
                longitude=longitude,
            )
        )

        display_value = (
            self._build_display_value(
                latitude=latitude,
                longitude=longitude,
            )
        )

        existing_entity = (
            self.entity_service
            .repository
            .find_in_case(
                case_id=evidence.case_id,
                entity_type=(
                    EntityType.LOCATION
                ),
                normalized_value=(
                    normalized_value
                ),
            )
        )

        created = False

        if existing_entity is None:

            entity = (
                self.entity_service
                .create_entity(
                    case_id=evidence.case_id,
                    entity_type=(
                        EntityType.LOCATION
                    ),
                    value=display_value,
                    normalized_value=(
                        normalized_value
                    ),
                    confidence=1.0,
                    metadata_json=(
                        self._build_location_metadata_json(
                            latitude=latitude,
                            longitude=longitude,
                            altitude=altitude,
                            evidence=evidence,
                        )
                    ),
                    description=(
                        self._build_description(
                            latitude=latitude,
                            longitude=longitude,
                            altitude=altitude,
                            evidence=evidence,
                        )
                    ),
                )
            )

            created = True

        else:

            entity = existing_entity

        link_created = (
            self._ensure_evidence_link(
                evidence=evidence,
                entity=entity,
            )
        )

        return {
            "case_id": str(
                evidence.case_id
            ),
            "evidence": (
                self._evidence_summary(
                    evidence
                )
            ),
            "location": (
                self._entity_summary(
                    entity
                )
            ),
            "gps": {
                "latitude": latitude,
                "longitude": longitude,
                "altitude": altitude,
            },
            "created": created,
            "link_created": (
                link_created
            ),
        }

    # ==========================================================
    # Evidence
    # ==========================================================

    def _require_image_evidence(
        self,
        evidence_id: UUID,
    ) -> Evidence:
        """
        Load and validate selected image evidence.
        """

        evidence = (
            self.evidence_service
            .get_evidence(
                evidence_id
            )
        )

        if evidence is None:

            raise LookupError(
                "Evidence was not found: "
                f"{evidence_id}"
            )

        if (
            evidence.evidence_type
            != EvidenceType.IMAGE
        ):

            raise ValueError(
                "GPS location creation requires "
                "IMAGE evidence."
            )

        if (
            getattr(
                evidence,
                "deleted_at",
                None,
            )
            is not None
        ):

            raise ValueError(
                "Deleted image evidence cannot "
                "be used to create a location."
            )

        return evidence

    # ==========================================================
    # GPS extraction
    # ==========================================================

    @classmethod
    def _extract_gps(
        cls,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Extract GPS data from all metadata layouts
        currently supported by PhotoWorkspaceView.
        """

        processing_metadata = metadata.get(
            "processing_metadata"
        )

        if not isinstance(
            processing_metadata,
            dict,
        ):

            processing_metadata = (
                metadata.get(
                    "processing"
                )
            )

            if isinstance(
                processing_metadata,
                dict,
            ):

                nested_metadata = (
                    processing_metadata.get(
                        "metadata"
                    )
                )

                if isinstance(
                    nested_metadata,
                    dict,
                ):

                    processing_metadata = (
                        nested_metadata
                    )

        if not isinstance(
            processing_metadata,
            dict,
        ):

            processing_metadata = {}

        exif_result = (
            processing_metadata.get(
                "exif"
            )
        )

        if not isinstance(
            exif_result,
            dict,
        ):

            exif_result = metadata.get(
                "exif"
            )

        if not isinstance(
            exif_result,
            dict,
        ):

            exif_result = {}

        normalized_exif = (
            exif_result.get(
                "normalized"
            )
        )

        if not isinstance(
            normalized_exif,
            dict,
        ):

            normalized_exif = {}

        gps = normalized_exif.get(
            "gps"
        )

        if not isinstance(
            gps,
            dict,
        ):

            gps = {}

        latitude = (
            gps.get(
                "latitude"
            )
        )

        if latitude is None:

            latitude = (
                processing_metadata.get(
                    "gps_latitude"
                )
            )

        longitude = (
            gps.get(
                "longitude"
            )
        )

        if longitude is None:

            longitude = (
                processing_metadata.get(
                    "gps_longitude"
                )
            )

        altitude = (
            gps.get(
                "altitude"
            )
        )

        if altitude is None:

            altitude = (
                processing_metadata.get(
                    "gps_altitude"
                )
            )

        if (
            latitude is None
            or longitude is None
        ):

            raise ValueError(
                "The selected image does not contain "
                "usable GPS coordinates."
            )

        return {
            "latitude": latitude,
            "longitude": longitude,
            "altitude": altitude,
        }

    # ==========================================================
    # Entity creation
    # ==========================================================

    @classmethod
    def _build_normalized_value(
        cls,
        *,
        latitude: float,
        longitude: float,
    ) -> str:
        """
        Build duplicate-detection value.
        """

        return (
            f"{latitude:.{cls.COORDINATE_PRECISION}f},"
            f"{longitude:.{cls.COORDINATE_PRECISION}f}"
        )

    @classmethod
    def _build_display_value(
        cls,
        *,
        latitude: float,
        longitude: float,
    ) -> str:
        """
        Build readable coordinate value.
        """

        return (
            f"{latitude:.{cls.COORDINATE_PRECISION}f}, "
            f"{longitude:.{cls.COORDINATE_PRECISION}f}"
        )

    @staticmethod
    def _build_location_metadata_json(
        *,
        latitude: float,
        longitude: float,
        altitude: float | None,
        evidence: Evidence,
    ) -> str:
        """
        Build metadata for LOCATION entity.
        """

        metadata = {
            "location": {
                "latitude": latitude,
                "longitude": longitude,
                "altitude": altitude,
            },
            "source": {
                "type": "photo_gps",
                "method": "exif",
                "evidence_id": str(
                    evidence.id
                ),
            },
            "map": {
                "marker_name": None,
                "marker_color": None,
                "marker_icon": None,
            },
        }

        return json.dumps(
            metadata,
            ensure_ascii=False,
            separators=(
                ",",
                ":",
            ),
            default=str,
        )

    @staticmethod
    def _build_description(
        *,
        latitude: float,
        longitude: float,
        altitude: float | None,
        evidence: Evidence,
    ) -> str:
        """
        Build provenance description.
        """

        altitude_text = (
            str(
                altitude
            )
            if altitude is not None
            else "Unavailable"
        )

        return (
            "Location created from image GPS metadata.\n\n"
            f"Latitude: {latitude}\n"
            f"Longitude: {longitude}\n"
            f"Altitude: {altitude_text}\n"
            f"Source evidence: {evidence.id}"
        )

    # ==========================================================
    # Evidence link
    # ==========================================================

    def _ensure_evidence_link(
        self,
        *,
        evidence: Evidence,
        entity: Entity,
    ) -> bool:
        """
        Ensure EvidenceEntity link exists.

        Returns True when a new link was created.
        """

        existing_links = (
            self.evidence_link_service
            .get_entities_for_evidence(
                evidence.id
            )
        )

        for link in existing_links:

            if (
                link.entity_id
                == entity.id
            ):

                return False

        self.evidence_link_service.link_evidence_to_entity(
            evidence_id=evidence.id,
            entity_id=entity.id,
        )

        return True

    # ==========================================================
    # Serialization
    # ==========================================================

    @staticmethod
    def _evidence_summary(
        evidence: Evidence,
    ) -> dict[str, Any]:

        return {
            "id": str(
                evidence.id
            ),
            "case_id": str(
                evidence.case_id
            ),
            "title": (
                evidence.title
            ),
            "file_path": (
                evidence.file_path
            ),
            "mime_type": (
                evidence.mime_type
            ),
        }

    @staticmethod
    def _entity_summary(
        entity: Entity,
    ) -> dict[str, Any]:

        return {
            "id": str(
                entity.id
            ),
            "case_id": str(
                entity.case_id
            ),
            "entity_type": (
                entity.entity_type.value
                if isinstance(
                    entity.entity_type,
                    EntityType,
                )
                else str(
                    entity.entity_type
                )
            ),
            "value": (
                entity.value
            ),
            "normalized_value": (
                entity.normalized_value
            ),
            "confidence": (
                entity.confidence
            ),
            "metadata_json": (
                entity.metadata_json
            ),
            "description": (
                entity.description
            ),
        }

    # ==========================================================
    # Metadata
    # ==========================================================

    @staticmethod
    def _parse_metadata(
        metadata_json: str | None,
    ) -> dict[str, Any]:
        """
        Safely parse Evidence.metadata_json.
        """

        if not metadata_json:

            return {}

        try:

            metadata = json.loads(
                metadata_json
            )

        except (
            TypeError,
            json.JSONDecodeError,
        ) as error:

            raise ValueError(
                "Evidence metadata_json contains "
                "invalid JSON."
            ) from error

        if not isinstance(
            metadata,
            dict,
        ):

            raise ValueError(
                "Evidence metadata_json must contain "
                "a JSON object."
            )

        return metadata

    # ==========================================================
    # Validation
    # ==========================================================

    @staticmethod
    def _normalize_latitude(
        value: Any,
    ) -> float:

        try:

            latitude = float(
                value
            )

        except (
            TypeError,
            ValueError,
        ) as error:

            raise ValueError(
                "GPS latitude is invalid."
            ) from error

        if not (
            -90.0
            <= latitude
            <= 90.0
        ):

            raise ValueError(
                "GPS latitude must be between "
                "-90 and 90 degrees."
            )

        return latitude

    @staticmethod
    def _normalize_longitude(
        value: Any,
    ) -> float:

        try:

            longitude = float(
                value
            )

        except (
            TypeError,
            ValueError,
        ) as error:

            raise ValueError(
                "GPS longitude is invalid."
            ) from error

        if not (
            -180.0
            <= longitude
            <= 180.0
        ):

            raise ValueError(
                "GPS longitude must be between "
                "-180 and 180 degrees."
            )

        return longitude

    @staticmethod
    def _normalize_optional_float(
        value: Any,
    ) -> float | None:

        if value is None:

            return None

        try:

            return float(
                value
            )

        except (
            TypeError,
            ValueError,
        ):

            return None

    @staticmethod
    def _normalize_uuid(
        value: str | UUID,
        *,
        field_name: str,
    ) -> UUID:

        if isinstance(
            value,
            UUID,
        ):

            return value

        try:

            return UUID(
                str(
                    value
                )
            )

        except (
            TypeError,
            ValueError,
            AttributeError,
        ) as error:

            raise ValueError(
                f"{field_name} must contain "
                "a valid UUID."
            ) from error

    @staticmethod
    def _normalize_marker_color(
        value: Any,
    ) -> str:
        """
        Validate hexadecimal marker color.
        """

        color = str(
            value
            or ""
        ).strip()

        if not color:

            return "#e072c4"

        if (
            len(color) == 7
            and color.startswith("#")
        ):

            hexadecimal = color[1:]

            try:

                int(
                    hexadecimal,
                    16,
                )

            except ValueError as error:

                raise ValueError(
                    "Marker color must be a valid "
                    "hexadecimal color."
                ) from error

            return color.lower()

        raise ValueError(
            "Marker color must use #RRGGBB format."
        )

    # ==========================================================
    # Information
    # ==========================================================

    def metadata(
        self,
    ) -> dict[str, Any]:

        return {
            "type": (
                "image_gps_location_service"
            ),
            "entity_type": (
                EntityType.LOCATION.value
            ),
            "source": (
                "image_exif_gps"
            ),
            "coordinate_precision": (
                self.COORDINATE_PRECISION
            ),
        }

    def update_location(
        self,
        location_id: str | UUID,
        *,
        marker_name: str,
        description: str,
        marker_color: str,
    ) -> dict[str, Any]:
        """
        Update user-editable properties of a LOCATION entity.

        GPS coordinates, source provenance and coordinate identity
        are preserved.
        """

        normalized_location_id = (
            self._normalize_uuid(
                location_id,
                field_name="location_id",
            )
        )

        entity = (
            self.entity_service
            .get_entity(
                normalized_location_id
            )
        )

        if entity is None:

            raise LookupError(
                "Location entity was not found: "
                f"{normalized_location_id}"
            )

        if (
            entity.entity_type
            != EntityType.LOCATION
        ):

            raise ValueError(
                "The selected entity is not a LOCATION."
            )

        metadata = self._parse_metadata(
            entity.metadata_json
        )

        map_metadata = metadata.get(
            "map"
        )

        if not isinstance(
            map_metadata,
            dict,
        ):

            map_metadata = {}

        normalized_marker_name = str(
            marker_name
            or ""
        ).strip()

        normalized_description = str(
            description
            or ""
        ).strip()

        normalized_marker_color = (
            self._normalize_marker_color(
                marker_color
            )
        )

        map_metadata["marker_name"] = (
            normalized_marker_name
            or None
        )

        map_metadata["marker_color"] = (
            normalized_marker_color
        )

        metadata["map"] = map_metadata

        updated_entity = (
            self.entity_service
            .update_entity(
                normalized_location_id,
                description=(
                    normalized_description
                ),
                metadata_json=(
                    json.dumps(
                        metadata,
                        ensure_ascii=False,
                        separators=(
                            ",",
                            ":",
                        ),
                        default=str,
                    )
                ),
            )
        )

        if updated_entity is None:

            raise RuntimeError(
                "Location entity could not be updated."
            )

        location_data = metadata.get(
            "location"
        )

        if not isinstance(
            location_data,
            dict,
        ):

            location_data = {}

        return {
            "location": (
                self._entity_summary(
                    updated_entity
                )
            ),
            "gps": {
                "latitude": (
                    location_data.get(
                        "latitude"
                    )
                ),
                "longitude": (
                    location_data.get(
                        "longitude"
                    )
                ),
                "altitude": (
                    location_data.get(
                        "altitude"
                    )
                ),
            },
            "map": {
                "marker_name": (
                    normalized_marker_name
                ),
                "marker_color": (
                    normalized_marker_color
                ),
            },
        }

    def get_location_photos(
        self,
        location_id: str | UUID,
    ) -> list[dict[str, Any]]:
        """
        Return IMAGE evidence linked to a LOCATION entity.

        The result is prepared for desktop UI consumption.
        """

        normalized_location_id = (
            self._normalize_uuid(
                location_id,
                field_name="location_id",
            )
        )

        entity = (
            self.entity_service
            .get_entity(
                normalized_location_id
            )
        )

        if entity is None:

            raise LookupError(
                "Location entity was not found: "
                f"{normalized_location_id}"
            )

        if (
            entity.entity_type
            != EntityType.LOCATION
        ):

            raise ValueError(
                "The selected entity is not a LOCATION."
            )

        photos = (
            self.evidence_link_service
            .get_image_evidence_for_entity(
                normalized_location_id
            )
        )

        metadata = self._parse_metadata(
            entity.metadata_json
        )

        source = metadata.get(
            "source"
        )

        if not isinstance(
            source,
            dict,
        ):

            source = {}

        primary_evidence_id = str(
            source.get(
                "evidence_id"
            )
            or ""
        ).strip()

        result: list[
            dict[str, Any]
        ] = []

        for evidence in photos:

            evidence_id = str(
                evidence.id
            )

            result.append(
                {
                    "id": evidence_id,
                    "case_id": str(
                        evidence.case_id
                    ),
                    "source_id": str(
                        evidence.source_id
                    ),
                    "title": (
                        evidence.title
                    ),
                    "description": (
                        evidence.description
                    ),
                    "file_path": (
                        evidence.file_path
                    ),
                    "mime_type": (
                        evidence.mime_type
                    ),
                    "sha256": (
                        evidence.sha256
                    ),
                    "created_at": (
                        evidence.created_at.isoformat()
                        if evidence.created_at
                        else None
                    ),
                    "is_primary": (
                        evidence_id
                        ==
                        primary_evidence_id
                    ),
                    "relationship": (
                        "gps_source"
                        if (
                            evidence_id
                            ==
                            primary_evidence_id
                        )
                        else "attached"
                    ),
                }
            )

        return result

    def attach_photo(
        self,
        location_id: str | UUID,
        evidence_id: str | UUID,
    ) -> dict[str, Any]:
        """
        Attach existing IMAGE evidence to LOCATION entity.
        """

        normalized_location_id = (
            self._normalize_uuid(
                location_id,
                field_name="location_id",
            )
        )

        normalized_evidence_id = (
            self._normalize_uuid(
                evidence_id,
                field_name="evidence_id",
            )
        )

        entity = (
            self.entity_service
            .get_entity(
                normalized_location_id
            )
        )

        if entity is None:

            raise LookupError(
                "Location entity was not found."
            )

        if (
            entity.entity_type
            != EntityType.LOCATION
        ):

            raise ValueError(
                "The selected entity is not a LOCATION."
            )

        evidence = self._require_image_evidence(
            normalized_evidence_id
        )

        if (
            evidence.case_id
            != entity.case_id
        ):

            raise ValueError(
                "Evidence and location must belong "
                "to the same investigation."
            )

        (
            link,
            created,
        ) = (
            self.evidence_link_service
            .ensure_link(
                evidence_id=(
                    normalized_evidence_id
                ),
                entity_id=(
                    normalized_location_id
                ),
            )
        )

        return {
            "location_id": str(
                normalized_location_id
            ),
            "evidence_id": str(
                normalized_evidence_id
            ),
            "link_id": str(
                link.id
            ),
            "created": created,
        }

    def detach_photo(
        self,
        location_id: str | UUID,
        evidence_id: str | UUID,
    ) -> bool:
        """
        Remove IMAGE evidence link from LOCATION.

        The original GPS source image cannot be detached.
        """

        normalized_location_id = (
            self._normalize_uuid(
                location_id,
                field_name="location_id",
            )
        )

        normalized_evidence_id = (
            self._normalize_uuid(
                evidence_id,
                field_name="evidence_id",
            )
        )

        entity = (
            self.entity_service
            .get_entity(
                normalized_location_id
            )
        )

        if entity is None:

            raise LookupError(
                "Location entity was not found."
            )

        if (
            entity.entity_type
            != EntityType.LOCATION
        ):

            raise ValueError(
                "The selected entity is not a LOCATION."
            )

        metadata = self._parse_metadata(
            entity.metadata_json
        )

        source = metadata.get(
            "source"
        )

        if not isinstance(
            source,
            dict,
        ):

            source = {}

        source_evidence_id = str(
            source.get(
                "evidence_id"
            )
            or ""
        ).strip()

        if (
            source_evidence_id
            ==
            str(
                normalized_evidence_id
            )
        ):

            raise ValueError(
                "The original GPS source image "
                "cannot be detached from this location."
            )

        return (
            self.evidence_link_service
            .unlink_evidence_from_entity(
                evidence_id=(
                    normalized_evidence_id
                ),
                entity_id=(
                    normalized_location_id
                ),
            )
        )