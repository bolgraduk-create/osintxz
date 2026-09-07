from __future__ import annotations

import traceback

import app.database.session as session_module

from app.core.service_container import ServiceContainer
from app.osint.models import OsintTargetType
from app.osint.open_web.contracts import OpenWebQuery


print("=" * 88)
print("M021.16.5.2A GDELT LIVE DIAGNOSTIC")
print("=" * 88)

session = session_module.create_session()

try:
    container = ServiceContainer(session)

    provider = getattr(
        container,
        "gdelt_exact_email_open_web_provider",
        None,
    )

    print("\n=== PROVIDER ===")
    print(
        "exists:",
        provider is not None,
    )

    if provider is None:
        raise RuntimeError(
            "GDELT provider is not present "
            "in ServiceContainer."
        )

    print(
        "name:",
        provider.info.name,
    )
    print(
        "automatic eligible:",
        provider.info.automatic_eligible,
    )

    query = OpenWebQuery(
        target_type=OsintTargetType.EMAIL,
        value="bolgraduk@gmail.com",
        limit=5,
        timeout=30,
    )


    print("\n=== RAW GDELT CANDIDATE SEARCH ===")

    try:
        articles = provider._search_candidates(
            email=query.value,
            limit=5,
            timeout=30,
        )

        print(
            "candidate count:",
            len(articles),
        )

        for index, article in enumerate(
            articles,
            start=1,
        ):
            print()
            print(
                f"CANDIDATE {index}"
            )
            print(
                "url:",
                article.get("url"),
            )
            print(
                "title:",
                article.get("title"),
            )
            print(
                "domain:",
                article.get("domain"),
            )

    except Exception as exc:
        print(
            "[RAW SEARCH FAILED]"
        )
        print(
            "type:",
            type(exc).__name__,
        )
        print(
            "repr:",
            repr(exc),
        )
        print(
            "str:",
            str(exc),
        )

        print()
        print("TRACEBACK:")
        traceback.print_exc()


    print("\n=== PROVIDER SEARCH ===")

    try:
        result = provider.search(
            query
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
                "text length:",
                len(
                    document.text or ""
                ),
            )
            print(
                "exact verified:",
                document.metadata.get(
                    "exact_email_verified"
                ),
            )

    except Exception as exc:
        print(
            "[PROVIDER SEARCH CRASHED]"
        )
        print(
            "type:",
            type(exc).__name__,
        )
        print(
            "repr:",
            repr(exc),
        )
        print(
            "str:",
            str(exc),
        )
        traceback.print_exc()


finally:
    session.close()


print()
print("DIAGNOSTIC COMPLETE")
