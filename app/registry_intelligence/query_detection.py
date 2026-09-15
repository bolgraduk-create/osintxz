"""Conservative registry input detection, separate from OsintTargetType."""
import re

from app.registry_intelligence.contracts import (
    RegistryDomain,
    RegistryEntityKind,
    RegistryQuery,
    RegistryQueryKind,
)


_LEI_RE = re.compile(r"[A-Z0-9]{18}[0-9]{2}")
_COUNTRY_RE = re.compile(r"[A-Za-z]{2}")


def detect_registry_query(value: str) -> RegistryQuery | None:
    raw = (value or "").strip()
    if not raw:
        return None

    if raw.casefold().startswith("lei:"):
        lei = raw.split(":", 1)[1].strip().upper()
        if not _LEI_RE.fullmatch(lei):
            raise ValueError("LEI must contain 20 letters/digits and end in two digits.")
        return RegistryQuery(
            RegistryDomain.BUSINESS,
            RegistryQueryKind.LEI,
            lei,
            entity_kind=RegistryEntityKind.COMPANY,
        )

    if _LEI_RE.fullmatch(raw.upper()) and any(character.isalpha() for character in raw):
        return RegistryQuery(
            RegistryDomain.BUSINESS,
            RegistryQueryKind.LEI,
            raw.upper(),
            entity_kind=RegistryEntityKind.COMPANY,
        )

    if raw.casefold().startswith("reg:"):
        parts = raw.split(":", 2)
        if len(parts) != 3 or not _COUNTRY_RE.fullmatch(parts[1]):
            raise ValueError(
                "Use reg:COUNTRY:registration identifier, for example "
                "reg:CH:CHE-200.595.965."
            )
        return RegistryQuery(
            RegistryDomain.BUSINESS,
            RegistryQueryKind.REGISTRATION_ID,
            parts[2].strip(),
            country=parts[1].upper(),
            entity_kind=RegistryEntityKind.COMPANY,
        )

    if raw.casefold().startswith("edrpou:"):
        identifier = raw.split(":", 1)[1].strip()
        if not identifier:
            raise ValueError("EDRPOU identifier must not be empty.")
        return RegistryQuery(
            RegistryDomain.BUSINESS,
            RegistryQueryKind.REGISTRATION_ID,
            identifier,
            country="UA",
            sources=("ua_edr_business",),
            entity_kind=RegistryEntityKind.COMPANY,
        )

    if raw.casefold().startswith("tax:"):
        parts = raw.split(":", 2)
        if len(parts) == 3 and _COUNTRY_RE.fullmatch(parts[1]):
            country, identifier = parts[1].upper(), parts[2].strip()
        elif len(parts) == 2:
            country, identifier = None, parts[1].strip()
        else:
            raise ValueError("Use tax:IDENTIFIER or tax:COUNTRY:IDENTIFIER.")
        if not identifier:
            raise ValueError("Tax identifier must not be empty.")
        return RegistryQuery(
            RegistryDomain.BUSINESS,
            RegistryQueryKind.TAX_ID,
            identifier,
            country=country,
        )

    if raw.casefold().startswith("vat:"):
        parts = raw.split(":", 2)
        if len(parts) != 3 or not _COUNTRY_RE.fullmatch(parts[1]):
            raise ValueError("Use vat:COUNTRY:IDENTIFIER.")
        return RegistryQuery(
            RegistryDomain.BUSINESS,
            RegistryQueryKind.VAT_ID,
            parts[2].strip(),
            country=parts[1].upper(),
        )

    if raw.casefold().startswith("case:"):
        case_number = raw.split(":", 1)[1].strip()
        if not case_number:
            raise ValueError("Court case number must not be empty.")
        return RegistryQuery(
            RegistryDomain.COURT,
            RegistryQueryKind.CASE_NUMBER,
            case_number,
            entity_kind=RegistryEntityKind.COURT_CASE,
        )

    if raw.casefold().startswith("fop:"):
        name = raw.split(":", 1)[1].strip()
        if not name:
            raise ValueError("Sole-trader name must not be empty.")
        return RegistryQuery(
            RegistryDomain.BUSINESS,
            RegistryQueryKind.PERSON_NAME,
            name,
            country="UA",
            sources=("ua_edr_business",),
            entity_kind=RegistryEntityKind.SOLE_TRADER,
        )

    if raw.casefold().startswith("company:"):
        name = raw.split(":", 1)[1].strip()
        if not name:
            raise ValueError("Company name must not be empty.")
        return RegistryQuery(
            RegistryDomain.BUSINESS,
            RegistryQueryKind.NAME,
            name,
            entity_kind=RegistryEntityKind.COMPANY,
        )

    # Unformatted multiword names can be searched in business registries without
    # asserting that the input is a person or that any result is the same identity.
    if " " in raw and any(character.isalpha() for character in raw) and not any(
        character in raw for character in "@:/"
    ):
        return RegistryQuery(RegistryDomain.BUSINESS, RegistryQueryKind.NAME, raw)

    return None
