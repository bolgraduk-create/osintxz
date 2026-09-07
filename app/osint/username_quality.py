from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from urllib.parse import urlsplit, urlunsplit


class UsernameFindingKind(str, Enum):
    PUBLIC_PROFILE = "public_profile"
    SERVICE_ENDPOINT = "service_endpoint"
    REGISTRATION_SIGNAL = "registration_signal"
    IDENTIFIER = "identifier"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class UsernameFindingClassification:
    kind: UsernameFindingKind
    canonical_profile_url: str | None = None
    platform: str | None = None
    reason: str | None = None


class UsernameFindingQuality:
    """Pure username-result quality rules; no DB/network access."""

    _SERVICE_ENDPOINT_HOSTS = {
        "account.proton.me",
        "accounts.google.com",
        "login.microsoftonline.com",
        "account.microsoft.com",
        "appleid.apple.com",
        "idmsa.apple.com",
    }

    _SERVICE_ENDPOINT_PATH_PREFIXES = (
        "/login",
        "/signin",
        "/sign-in",
        "/signup",
        "/sign-up",
        "/register",
        "/password",
        "/forgot",
        "/recover",
        "/recovery",
        "/reset",
    )

    @classmethod
    def classify(
        cls,
        *,
        category: str,
        value: str,
        url: str | None,
        target_username: str,
        metadata: dict | None = None,
    ) -> UsernameFindingClassification:
        category_cf = (category or "").strip().casefold()
        value_s = (value or "").strip()
        target = (target_username or "").strip()
        metadata = metadata or {}

        candidate_url = (url or "").strip()
        if not candidate_url and category_cf in {"url", "public_url", "link"}:
            candidate_url = value_s

        if candidate_url:
            canonical = cls.canonicalize_url(candidate_url)

            if cls.is_service_endpoint(canonical):
                return UsernameFindingClassification(
                    kind=UsernameFindingKind.SERVICE_ENDPOINT,
                    platform=cls.platform_for_url(canonical),
                    reason="generic_service_or_login_endpoint",
                )

            if cls.is_public_profile_url(
                canonical,
                target_username=target,
                metadata=metadata,
            ):
                return UsernameFindingClassification(
                    kind=UsernameFindingKind.PUBLIC_PROFILE,
                    canonical_profile_url=canonical,
                    platform=cls.platform_for_url(canonical),
                    reason="profile_shaped_url",
                )

        if category_cf == "username":
            return UsernameFindingClassification(
                kind=UsernameFindingKind.IDENTIFIER,
                reason="explicit_username_identifier",
            )

        if category_cf == "account":
            return UsernameFindingClassification(
                kind=UsernameFindingKind.REGISTRATION_SIGNAL,
                platform=cls.platform_for_url(candidate_url),
                reason="account_presence_without_verified_profile_url",
            )

        return UsernameFindingClassification(
            kind=UsernameFindingKind.UNKNOWN,
            reason="no_username_quality_rule_matched",
        )

    @classmethod
    def canonicalize_url(cls, value: str) -> str:
        raw = (value or "").strip()
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

        return urlunsplit((scheme, netloc, path, parsed.query, ""))

    @classmethod
    def is_service_endpoint(cls, value: str) -> bool:
        canonical = cls.canonicalize_url(value)
        if not canonical:
            return False

        try:
            parsed = urlsplit(canonical)
        except ValueError:
            return False

        host = (parsed.hostname or "").casefold()
        path = (parsed.path or "/").casefold()

        if host in cls._SERVICE_ENDPOINT_HOSTS:
            return True
        if path == "/":
            return True

        return any(
            path == prefix or path.startswith(prefix + "/")
            for prefix in cls._SERVICE_ENDPOINT_PATH_PREFIXES
        )

    @classmethod
    def is_public_profile_url(
        cls,
        value: str,
        *,
        target_username: str,
        metadata: dict | None = None,
    ) -> bool:
        canonical = cls.canonicalize_url(value)
        if not canonical or cls.is_service_endpoint(canonical):
            return False

        try:
            parsed = urlsplit(canonical)
        except ValueError:
            return False

        host = (parsed.hostname or "").casefold()
        path = parsed.path or "/"
        path_cf = path.casefold()
        username = (target_username or "").strip().casefold()

        if not username:
            return False

        checks = (
            host in {"t.me", "telegram.me"}
            and path_cf.strip("/") == username,

            host in {"tiktok.com", "www.tiktok.com"}
            and path_cf.strip("/") == f"@{username}",

            host in {"snapchat.com", "www.snapchat.com"}
            and path_cf.strip("/") == f"@{username}",

            host in {"fragment.com", "www.fragment.com"}
            and path_cf.strip("/") == f"username/{username}",

            host in {"github.com", "www.github.com"}
            and path_cf.strip("/") == username,

            host in {"reddit.com", "www.reddit.com"}
            and path_cf.strip("/") in {f"u/{username}", f"user/{username}"},
        )

        if any(checks):
            return True

        if host in {"roblox.com", "www.roblox.com"}:
            parts = [part for part in path_cf.split("/") if part]
            if len(parts) >= 2 and parts[0] == "users" and parts[1].isdigit():
                return True

        segments = [part.casefold() for part in path.split("/") if part]
        return username in segments or f"@{username}" in segments

    @staticmethod
    def platform_for_url(value: str) -> str | None:
        canonical = UsernameFindingQuality.canonicalize_url(value)
        if not canonical:
            return None

        try:
            host = (urlsplit(canonical).hostname or "").casefold()
        except ValueError:
            return None

        if host.startswith("www."):
            host = host[4:]

        aliases = {
            "t.me": "telegram",
            "telegram.me": "telegram",
            "twitter.com": "x",
            "x.com": "x",
        }

        return aliases.get(host, host or None)
