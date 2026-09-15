"""Conservative registry input detection, separate from OsintTargetType."""
import re

from app.registry_intelligence.contracts import RegistryDomain, RegistryQuery, RegistryQueryKind


def detect_registry_query(value: str) -> RegistryQuery | None:
    raw = (value or "").strip()
    if raw.casefold().startswith("lei:"):
        lei = raw.split(":", 1)[1].strip().upper()
        if not re.fullmatch(r"[A-Z0-9]{18}[0-9]{2}", lei):
            raise ValueError("LEI must contain 20 letters/digits and end in two digits.")
        return RegistryQuery(RegistryDomain.BUSINESS, RegistryQueryKind.LEI, lei)
    if re.fullmatch(r"[A-Z0-9]{18}[0-9]{2}", raw.upper()) and any(c.isalpha() for c in raw):
        return RegistryQuery(RegistryDomain.BUSINESS, RegistryQueryKind.LEI, raw.upper())
    if raw.casefold().startswith("reg:"):
        parts = raw.split(":", 2)
        if len(parts) != 3 or not re.fullmatch(r"[A-Za-z]{2}", parts[1]):
            raise ValueError("Use reg:COUNTRY:registration identifier, for example reg:CH:CHE-200.595.965.")
        return RegistryQuery(RegistryDomain.BUSINESS, RegistryQueryKind.REGISTRATION_ID,
                             parts[2].strip(), country=parts[1].upper())
    if raw.casefold().startswith("company:"):
        return RegistryQuery(RegistryDomain.BUSINESS, RegistryQueryKind.NAME, raw.split(":", 1)[1].strip())
    # Unformatted multiword names can be searched in business registries without
    # asserting that the input is a person or that any result is the same identity.
    if " " in raw and any(c.isalpha() for c in raw) and not any(c in raw for c in "@:/"):
        return RegistryQuery(RegistryDomain.BUSINESS, RegistryQueryKind.NAME, raw)
    return None
