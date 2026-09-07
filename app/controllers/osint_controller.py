"""
OSINT workspace controller.

Responsible for:

- receiving OSINT workspace input
- converting UI data into application models
- validating basic input format
- calling the OSINT workspace application service
- returning UI-ready data

Does NOT:

- execute connectors directly
- contain OSINT business logic
- access database
- create or store domain entities
- contain widget logic
- call AI
"""

from __future__ import annotations

from collections.abc import Iterable
from collections.abc import Mapping
from datetime import date
from datetime import datetime
from typing import Any

from app.application.osint_workspace_service import (
    OsintWorkspaceService,
)

from app.osint.models import (
    OsintInvestigationRequest,
)


class OsintController:
    """
    Controller for the OSINT workspace.

    Converts values received from the interface into
    an OsintInvestigationRequest and delegates execution
    to OsintWorkspaceService.
    """

    def __init__(
        self,
        osint_service: OsintWorkspaceService,
    ) -> None:

        self.osint_service = osint_service

    # ==========================================================
    # Workspace
    # ==========================================================

    def get_workspace_state(
        self,
    ) -> dict[str, Any]:
        """
        Return the initial OSINT workspace state.
        """

        return (
            self.osint_service
            .get_workspace_state()
        )

    # ==========================================================
    # Investigation request
    # ==========================================================

    def create_request(
        self,
        form_data: Mapping[str, Any],
    ) -> OsintInvestigationRequest:
        """
        Convert UI form data into an investigation request.

        List fields may be passed as:

        - a Python list
        - a tuple or set
        - text separated by lines
        - text separated by commas
        - text separated by semicolons
        """

        return OsintInvestigationRequest(

            # Investigation context

            case_id=self._clean_optional_text(
                form_data.get(
                    "case_id"
                )
            ),

            title=self._clean_optional_text(
                form_data.get(
                    "title"
                )
            ),

            description=self._clean_optional_text(
                form_data.get(
                    "description"
                )
            ),

            # Person identity

            first_name=self._clean_optional_text(
                form_data.get(
                    "first_name"
                )
            ),

            middle_name=self._clean_optional_text(
                form_data.get(
                    "middle_name"
                )
            ),

            last_name=self._clean_optional_text(
                form_data.get(
                    "last_name"
                )
            ),

            birth_date=self._parse_date(
                form_data.get(
                    "birth_date"
                )
            ),

            # Online identities

            usernames=self._parse_list(
                form_data.get(
                    "usernames"
                )
            ),

            emails=self._parse_list(
                form_data.get(
                    "emails"
                )
            ),

            phones=self._parse_list(
                form_data.get(
                    "phones"
                )
            ),

            # Location

            country=self._clean_optional_text(
                form_data.get(
                    "country"
                )
            ),

            region=self._clean_optional_text(
                form_data.get(
                    "region"
                )
            ),

            city=self._clean_optional_text(
                form_data.get(
                    "city"
                )
            ),

            postal_code=self._clean_optional_text(
                form_data.get(
                    "postal_code"
                )
            ),

            address=self._clean_optional_text(
                form_data.get(
                    "address"
                )
            ),

            # Organizations

            organizations=self._parse_list(
                form_data.get(
                    "organizations"
                )
            ),

            # Network and web targets

            domains=self._parse_list(
                form_data.get(
                    "domains"
                )
            ),

            urls=self._parse_list(
                form_data.get(
                    "urls"
                )
            ),

            ip_addresses=self._parse_list(
                form_data.get(
                    "ip_addresses"
                )
            ),

            hashes=self._parse_list(
                form_data.get(
                    "hashes"
                )
            ),

            # Local artifacts

            file_paths=self._parse_list(
                form_data.get(
                    "file_paths"
                )
            ),

            image_paths=self._parse_list(
                form_data.get(
                    "image_paths"
                )
            ),

            # Additional context

            keywords=self._parse_list(
                form_data.get(
                    "keywords"
                )
            ),

            notes=self._clean_optional_text(
                form_data.get(
                    "notes"
                )
            ),
        )

    # ==========================================================
    # Preview
    # ==========================================================

    def preview_targets(
        self,
        form_data: Mapping[str, Any],
    ) -> dict[str, Any]:
        """
        Build investigation targets without running connectors.
        """

        request = self.create_request(
            form_data
        )

        targets = (
            self.osint_service
            .build_targets(
                request
            )
        )

        return {
            "request": (
                self._serialize_request(
                    request
                )
            ),
            "targets": targets,
            "target_count": len(
                targets
            ),
            "has_targets": bool(
                targets
            ),
        }

    def get_compatible_connectors(
        self,
        form_data: Mapping[str, Any],
    ) -> dict[str, Any]:
        """
        Return compatible connectors for generated targets.
        """

        request = self.create_request(
            form_data
        )

        targets = (
            self.osint_service
            .build_targets(
                request
            )
        )

        compatibility = (
            self.osint_service
            .get_compatible_connectors(
                request
            )
        )

        connector_names: set[str] = set()

        for item in compatibility:

            connectors = item.get(
                "connectors",
                [],
            )

            for connector_name in connectors:

                cleaned_name = (
                    self._clean_optional_text(
                        connector_name
                    )
                )

                if cleaned_name:

                    connector_names.add(
                        cleaned_name
                    )

        return {
            "request": (
                self._serialize_request(
                    request
                )
            ),
            "targets": targets,
            "target_count": len(
                targets
            ),
            "compatibility": compatibility,
            "compatible_connectors": sorted(
                connector_names,
                key=str.casefold,
            ),
            "compatible_connector_count": len(
                connector_names
            ),
            "has_targets": bool(
                targets
            ),
        }

    # ==========================================================
    # Execution
    # ==========================================================

    def run_investigation(
        self,
        form_data: Mapping[str, Any],
        selected_connectors: Iterable[str] | str | None = None,
        timeout: int = 300,
        use_cache: bool = True,
        save_raw_output: bool = False,
        include_metadata: bool = True,
        include_related: bool = True,
    ) -> dict[str, Any]:
        """
        Execute an OSINT investigation.

        When selected_connectors is None, all compatible
        connectors are executed.
        """

        request = self.create_request(
            form_data
        )

        targets = (
            self.osint_service
            .build_targets(
                request
            )
        )

        if not targets:

            raise ValueError(
                "OSINT investigation requires at least "
                "one non-empty target."
            )

        normalized_connectors = (
            self._normalize_selected_connectors(
                selected_connectors
            )
        )

        normalized_timeout = (
            self._normalize_timeout(
                timeout
            )
        )

        return (
            self.osint_service
            .run_investigation(
                request=request,
                selected_connectors=(
                    normalized_connectors
                ),
                timeout=normalized_timeout,
                use_cache=bool(
                    use_cache
                ),
                save_raw_output=bool(
                    save_raw_output
                ),
                include_metadata=bool(
                    include_metadata
                ),
                include_related=bool(
                    include_related
                ),
            )
        )

    # ==========================================================
    # Serialization
    # ==========================================================

    def _serialize_request(
        self,
        request: OsintInvestigationRequest,
    ) -> dict[str, Any]:
        """
        Serialize an investigation request for the UI.
        """

        return {
            "case_id": request.case_id,
            "title": request.title,
            "description": request.description,

            "first_name": request.first_name,
            "middle_name": request.middle_name,
            "last_name": request.last_name,

            "birth_date": (
                request.birth_date.isoformat()
                if request.birth_date is not None
                else None
            ),

            "usernames": list(
                request.usernames
            ),

            "emails": list(
                request.emails
            ),

            "phones": list(
                request.phones
            ),

            "country": request.country,
            "region": request.region,
            "city": request.city,
            "postal_code": request.postal_code,
            "address": request.address,

            "organizations": list(
                request.organizations
            ),

            "domains": list(
                request.domains
            ),

            "urls": list(
                request.urls
            ),

            "ip_addresses": list(
                request.ip_addresses
            ),

            "hashes": list(
                request.hashes
            ),

            "file_paths": list(
                request.file_paths
            ),

            "image_paths": list(
                request.image_paths
            ),

            "keywords": list(
                request.keywords
            ),

            "notes": request.notes,
        }

    # ==========================================================
    # Input helpers
    # ==========================================================

    def _clean_optional_text(
        self,
        value: Any,
    ) -> str | None:
        """
        Convert an optional UI value into clean text.
        """

        if value is None:
            return None

        cleaned_value = str(
            value
        ).strip()

        if not cleaned_value:
            return None

        return cleaned_value

    def _parse_list(
        self,
        value: Any,
    ) -> list[str]:
        """
        Convert a UI value into a clean unique text list.
        """

        if value is None:
            return []

        raw_values: list[Any] = []

        if isinstance(
            value,
            str,
        ):

            normalized_text = (
                value
                .replace(
                    "\r\n",
                    "\n",
                )
                .replace(
                    "\r",
                    "\n",
                )
                .replace(
                    ";",
                    "\n",
                )
                .replace(
                    ",",
                    "\n",
                )
            )

            raw_values.extend(
                normalized_text.split(
                    "\n"
                )
            )

        elif isinstance(
            value,
            Iterable,
        ):

            raw_values.extend(
                value
            )

        else:

            raw_values.append(
                value
            )

        result: list[str] = []

        seen: set[str] = set()

        for raw_value in raw_values:

            cleaned_value = (
                self._clean_optional_text(
                    raw_value
                )
            )

            if cleaned_value is None:
                continue

            normalized_value = (
                cleaned_value.casefold()
            )

            if normalized_value in seen:
                continue

            seen.add(
                normalized_value
            )

            result.append(
                cleaned_value
            )

        return result

    def _parse_date(
        self,
        value: Any,
    ) -> date | None:
        """
        Convert a UI date value into datetime.date.
        """

        if value is None:
            return None

        if isinstance(
            value,
            datetime,
        ):

            return value.date()

        if isinstance(
            value,
            date,
        ):

            return value

        cleaned_value = (
            self._clean_optional_text(
                value
            )
        )

        if cleaned_value is None:
            return None

        accepted_formats = (
            "%Y-%m-%d",
            "%d.%m.%Y",
            "%d/%m/%Y",
            "%m/%d/%Y",
        )

        for date_format in accepted_formats:

            try:

                return datetime.strptime(
                    cleaned_value,
                    date_format,
                ).date()

            except ValueError:
                continue

        raise ValueError(
            "Unsupported birth date format. "
            "Use YYYY-MM-DD or DD.MM.YYYY."
        )

    def _normalize_selected_connectors(
        self,
        connector_names: Iterable[str] | str | None,
    ) -> list[str] | None:
        """
        Normalize connector selection received from the UI.
        """

        if connector_names is None:
            return None

        names = self._parse_list(
            connector_names
        )

        return names

    def _normalize_timeout(
        self,
        timeout: Any,
    ) -> int:
        """
        Validate connector timeout.
        """

        try:

            normalized_timeout = int(
                timeout
            )

        except (
            TypeError,
            ValueError,
        ) as exc:

            raise ValueError(
                "OSINT timeout must be an integer."
            ) from exc

        if normalized_timeout < 1:

            raise ValueError(
                "OSINT timeout must be greater than zero."
            )

        return normalized_timeout