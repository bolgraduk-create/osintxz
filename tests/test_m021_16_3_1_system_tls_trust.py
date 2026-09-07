from __future__ import annotations

import ast
import ssl
from pathlib import Path

from app.osint.open_web.providers.live_web import (
    LiveWebOpenWebProvider,
)


def test_tls_context_keeps_verification_enabled():
    context = LiveWebOpenWebProvider._tls_context()

    assert isinstance(
        context,
        ssl.SSLContext,
    )

    assert (
        context.verify_mode
        == ssl.CERT_REQUIRED
    )


def test_live_web_source_never_disables_tls_verification():
    path = Path(
        "app/osint/open_web/providers/live_web.py"
    )

    text = path.read_text(
        encoding="utf-8",
    )

    tree = ast.parse(text)

    httpx_client_calls = []

    for node in ast.walk(tree):
        if not isinstance(
            node,
            ast.Call,
        ):
            continue

        func = node.func

        is_httpx_client = (
            isinstance(
                func,
                ast.Attribute,
            )
            and func.attr == "Client"
            and isinstance(
                func.value,
                ast.Name,
            )
            and func.value.id == "httpx"
        )

        if is_httpx_client:
            httpx_client_calls.append(
                node
            )

    assert httpx_client_calls

    found_tls_context = False

    for call in httpx_client_calls:
        for keyword in call.keywords:
            if keyword.arg != "verify":
                continue

            if (
                isinstance(
                    keyword.value,
                    ast.Constant,
                )
                and keyword.value.value
                is False
            ):
                raise AssertionError(
                    "httpx.Client uses "
                    "verify=False"
                )

            if isinstance(
                keyword.value,
                ast.Call,
            ):
                func = keyword.value.func

                if (
                    isinstance(
                        func,
                        ast.Attribute,
                    )
                    and func.attr
                    == "_tls_context"
                ):
                    found_tls_context = True

    assert found_tls_context