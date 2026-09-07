"""
OSINT target builder.

Converts one structured investigation request
into independent OSINT targets.

Responsibilities:

- build targets from investigation form data
- combine person identity fields
- combine location fields
- remove empty and duplicate targets
- attach shared investigation context

Does NOT:

- execute connectors
- select connectors
- store results
- access database
- call AI
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date
from typing import Any

from app.osint.models import (
    OsintInvestigationRequest,
    OsintTarget,
    OsintTargetType,
)


class OsintTargetBuilder:
    """
    Builds OSINT targets from a structured request.

    One investigation request may produce many targets:

    - person
    - usernames
    - emails
    - phones
    - locations
    - organizations
    - domains
    - URLs
    - IP addresses
    - hashes
    - files
    - images
    """

    def build(
        self,
        request: OsintInvestigationRequest,
    ) -> list[OsintTarget]:
        """
        Convert an investigation request into targets.
        """

        targets: list[OsintTarget] = []

        shared_description = (
            self._build_shared_description(
                request
            )
        )

        person_target = self._build_person_target(
            request=request,
            shared_description=shared_description,
        )

        if person_target is not None:
            targets.append(
                person_target
            )

        location_target = self._build_location_target(
            request=request,
            shared_description=shared_description,
        )

        if location_target is not None:
            targets.append(
                location_target
            )

        targets.extend(
            self._build_list_targets(
                values=request.usernames,
                target_type=OsintTargetType.USERNAME,
                label="Username",
                case_id=request.case_id,
                shared_description=shared_description,
            )
        )

        targets.extend(
            self._build_list_targets(
                values=request.emails,
                target_type=OsintTargetType.EMAIL,
                label="Email address",
                case_id=request.case_id,
                shared_description=shared_description,
            )
        )

        targets.extend(
            self._build_list_targets(
                values=request.phones,
                target_type=OsintTargetType.PHONE,
                label="Phone number",
                case_id=request.case_id,
                shared_description=shared_description,
            )
        )

        targets.extend(
            self._build_list_targets(
                values=request.organizations,
                target_type=OsintTargetType.ORGANIZATION,
                label="Organization",
                case_id=request.case_id,
                shared_description=shared_description,
            )
        )

        targets.extend(
            self._build_list_targets(
                values=request.domains,
                target_type=OsintTargetType.DOMAIN,
                label="Domain",
                case_id=request.case_id,
                shared_description=shared_description,
            )
        )

        targets.extend(
            self._build_list_targets(
                values=request.urls,
                target_type=OsintTargetType.URL,
                label="URL",
                case_id=request.case_id,
                shared_description=shared_description,
            )
        )

        targets.extend(
            self._build_list_targets(
                values=request.ip_addresses,
                target_type=OsintTargetType.IP,
                label="IP address",
                case_id=request.case_id,
                shared_description=shared_description,
            )
        )

        targets.extend(
            self._build_list_targets(
                values=request.hashes,
                target_type=OsintTargetType.HASH,
                label="File hash",
                case_id=request.case_id,
                shared_description=shared_description,
            )
        )

        targets.extend(
            self._build_list_targets(
                values=request.file_paths,
                target_type=OsintTargetType.FILE,
                label="File",
                case_id=request.case_id,
                shared_description=shared_description,
            )
        )

        targets.extend(
            self._build_list_targets(
                values=request.image_paths,
                target_type=OsintTargetType.IMAGE,
                label="Image",
                case_id=request.case_id,
                shared_description=shared_description,
            )
        )

        return self._remove_duplicates(
            targets
        )

    def build_grouped(
        self,
        request: OsintInvestigationRequest,
    ) -> dict[OsintTargetType, list[OsintTarget]]:
        """
        Build targets grouped by target type.
        """

        grouped: dict[
            OsintTargetType,
            list[OsintTarget],
        ] = {}

        for target in self.build(
            request
        ):

            grouped.setdefault(
                target.target_type,
                [],
            ).append(
                target
            )

        return grouped

    def _build_person_target(
        self,
        request: OsintInvestigationRequest,
        shared_description: str | None,
    ) -> OsintTarget | None:
        """
        Build a person target from name fields.
        """

        name_parts = self._clean_values(
            [
                request.first_name,
                request.middle_name,
                request.last_name,
            ]
        )

        if not name_parts:
            return None

        full_name = " ".join(
            name_parts
        )

        description_parts: list[str] = []

        if shared_description:
            description_parts.append(
                shared_description
            )

        if request.birth_date is not None:

            description_parts.append(
                (
                    "Birth date: "
                    f"{self._format_date(request.birth_date)}"
                )
            )

        description = self._join_description_parts(
            description_parts
        )

        return OsintTarget(
            target_type=OsintTargetType.PERSON,
            value=full_name,
            label="Person",
            description=description,
            case_id=request.case_id,
        )

    def _build_location_target(
        self,
        request: OsintInvestigationRequest,
        shared_description: str | None,
    ) -> OsintTarget | None:
        """
        Build one location target from address fields.
        """

        location_parts = self._clean_values(
            [
                request.address,
                request.city,
                request.region,
                request.postal_code,
                request.country,
            ]
        )

        if not location_parts:
            return None

        location = ", ".join(
            location_parts
        )

        return OsintTarget(
            target_type=OsintTargetType.LOCATION,
            value=location,
            label="Location",
            description=shared_description,
            case_id=request.case_id,
        )

    def _build_list_targets(
        self,
        values: Iterable[Any],
        target_type: OsintTargetType,
        label: str,
        case_id: str | None,
        shared_description: str | None,
    ) -> list[OsintTarget]:
        """
        Build targets from a collection of values.
        """

        targets: list[OsintTarget] = []

        for value in self._clean_values(
            values
        ):

            targets.append(
                OsintTarget(
                    target_type=target_type,
                    value=value,
                    label=label,
                    description=shared_description,
                    case_id=case_id,
                )
            )

        return targets

    def _build_shared_description(
        self,
        request: OsintInvestigationRequest,
    ) -> str | None:
        """
        Build shared contextual description.
        """

        parts: list[str] = []

        title = self._clean_value(
            request.title
        )

        if title:
            parts.append(
                f"Investigation: {title}"
            )

        description = self._clean_value(
            request.description
        )

        if description:
            parts.append(
                description
            )

        keywords = self._clean_values(
            request.keywords
        )

        if keywords:

            parts.append(
                (
                    "Keywords: "
                    + ", ".join(
                        keywords
                    )
                )
            )

        notes = self._clean_value(
            request.notes
        )

        if notes:
            parts.append(
                f"Notes: {notes}"
            )

        return self._join_description_parts(
            parts
        )

    def _remove_duplicates(
        self,
        targets: list[OsintTarget],
    ) -> list[OsintTarget]:
        """
        Remove duplicate targets while preserving order.
        """

        unique_targets: list[OsintTarget] = []

        seen: set[
            tuple[OsintTargetType, str]
        ] = set()

        for target in targets:

            normalized_value = (
                target.value
                .strip()
                .casefold()
            )

            key = (
                target.target_type,
                normalized_value,
            )

            if key in seen:
                continue

            seen.add(
                key
            )

            unique_targets.append(
                target
            )

        return unique_targets

    def _clean_values(
        self,
        values: Iterable[Any],
    ) -> list[str]:
        """
        Clean a collection of optional values.
        """

        cleaned_values: list[str] = []

        for value in values:

            cleaned_value = self._clean_value(
                value
            )

            if cleaned_value:
                cleaned_values.append(
                    cleaned_value
                )

        return cleaned_values

    def _clean_value(
        self,
        value: Any,
    ) -> str | None:
        """
        Convert an optional value to clean text.
        """

        if value is None:
            return None

        cleaned_value = str(
            value
        ).strip()

        if not cleaned_value:
            return None

        return cleaned_value

    def _join_description_parts(
        self,
        parts: Iterable[str],
    ) -> str | None:
        """
        Join description parts.
        """

        cleaned_parts = self._clean_values(
            parts
        )

        if not cleaned_parts:
            return None

        return "\n".join(
            cleaned_parts
        )

    def _format_date(
        self,
        value: date,
    ) -> str:
        """
        Format a date for target metadata.
        """

        return value.isoformat()