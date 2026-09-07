from __future__ import annotations

import inspect

import app.database.session as session_module

from app.core.service_container import ServiceContainer
from app.osint.models import OsintTargetType
from app.osint.open_web.contracts import OpenWebQuery


print("=" * 80)
print("M021.16.3 LIVE WEB RUNTIME PROBE v2")
print("=" * 80)


def create_db_session():
    print("\n=== SESSION FACTORY ===")

    candidates = (
        "create_session",
        "SessionFactory",
        "get_session",
    )

    for name in candidates:
        value = getattr(
            session_module,
            name,
            None,
        )

        if value is None:
            continue

        print(
            f"{name}: "
            f"{type(value).__name__}"
        )

        try:
            print(
                " signature:",
                inspect.signature(value),
            )
        except Exception:
            pass

    create_session = getattr(
        session_module,
        "create_session",
        None,
    )

    if callable(create_session):
        try:
            session = create_session()
            print(
                "[PASS] session created via create_session()"
            )
            return session
        except Exception as exc:
            print(
                "[INFO] create_session() failed:",
                repr(exc),
            )

    factory = getattr(
        session_module,
        "SessionFactory",
        None,
    )

    if callable(factory):
        try:
            session = factory()
            print(
                "[PASS] session created via SessionFactory()"
            )
            return session
        except Exception as exc:
            print(
                "[INFO] SessionFactory() failed:",
                repr(exc),
            )

    raise RuntimeError(
        "Could not create database session."
    )


session = create_db_session()

try:
    print("\n=== SERVICE CONTAINER ===")

    container = ServiceContainer(
        session
    )

    print(
        "[PASS] ServiceContainer created"
    )


    print("\n=== REGISTERED PROVIDERS ===")

    for provider in (
        container
        .open_web_provider_registry
        .all()
    ):
        info = provider.info

        print(
            f"name={info.name} "
            f"enabled={info.default_enabled} "
            f"eligible={info.automatic_eligible} "
            f"targets="
            f"{[x.value for x in info.supported_targets]}"
        )


    query = OpenWebQuery(
        target_type=OsintTargetType.URL,
        value=(
            "https://www.uic.edu/"
            "about/contact-us/"
        ),
        limit=25,
        timeout=30,
    )


    print(
        "\n=== AUTOMATIC PROVIDERS FOR URL ==="
    )

    providers = (
        container
        .open_web_provider_registry
        .automatic_for(query)
    )

    for provider in providers:
        print(
            " -",
            provider.info.name,
        )


    print("\n=== LIVE WEB DIRECT ===")

    provider = getattr(
        container,
        "live_web_open_web_provider",
        None,
    )

    if provider is None:
        print(
            "[FAIL] "
            "live_web_open_web_provider "
            "missing from ServiceContainer"
        )
    else:
        result = provider.search(
            query
        )

        print(
            "provider:",
            result.provider,
        )
        print(
            "status:",
            result.status,
        )
        print(
            "error:",
            result.error,
        )
        print(
            "documents:",
            len(result.documents),
        )
        print(
            "metadata:",
            result.metadata,
        )

        for index, document in enumerate(
            result.documents,
            start=1,
        ):
            print()
            print(
                f"DOCUMENT {index}"
            )
            print(
                "url:",
                document.url,
            )
            print(
                "title:",
                document.title,
            )
            print(
                "content_type:",
                document.content_type,
            )
            print(
                "text_length:",
                len(
                    document.text or ""
                ),
            )
            print(
                "text_preview:"
            )
            print(
                (document.text or "")[
                    :1500
                ]
            )


    print("\n=== DISCOVERY SERVICE ===")

    discovery = (
        container
        .open_web_discovery_service
        .discover(query)
    )

    print(
        "provider results:",
        len(discovery.results),
    )
    print(
        "combined documents:",
        len(discovery.documents),
    )

    for result in discovery.results:
        print()
        print("RESULT")
        print(
            " provider:",
            result.provider,
        )
        print(
            " status:",
            result.status,
        )
        print(
            " error:",
            result.error,
        )
        print(
            " documents:",
            len(result.documents),
        )
        print(
            " metadata:",
            result.metadata,
        )

finally:
    try:
        session.close()
    except Exception:
        pass


print("\nPROBE COMPLETE")
