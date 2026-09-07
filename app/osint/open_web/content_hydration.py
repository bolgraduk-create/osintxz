"""Bounded Open-Web content hydration contracts and Common Crawl hydrator."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from app.osint.open_web.contracts import (
    OpenWebDocument,
)


class WarcContentClientProtocol(
    Protocol
):
    def fetch(
        self,
        *,
        filename: str,
        offset: int,
        length: int,
        timeout: int = 20,
    ):
        ...


@dataclass(slots=True)
class OpenWebHydrationBatchResult:
    documents: list[
        OpenWebDocument
    ] = field(
        default_factory=list
    )

    hydrated: int = 0
    skipped: int = 0
    failed: int = 0
    errors: list[str] = field(
        default_factory=list
    )


class CommonCrawlContentHydrator:
    """Hydrate a bounded number of Common Crawl index documents."""

    PROVIDER_NAME = (
        "common_crawl"
    )

    def __init__(
        self,
        client: WarcContentClientProtocol,
        *,
        max_documents: int = 3,
        timeout: int = 20,
    ) -> None:
        self.client = client
        self.max_documents = max(
            0,
            min(
                int(max_documents),
                10,
            ),
        )
        self.timeout = max(
            1,
            min(
                int(timeout),
                60,
            ),
        )

    def hydrate(
        self,
        documents: list[
            OpenWebDocument
        ],
    ) -> OpenWebHydrationBatchResult:
        result = (
            OpenWebHydrationBatchResult()
        )

        budget = (
            self.max_documents
        )

        for document in documents:
            if (
                document.provider
                != self.PROVIDER_NAME
            ):
                result.documents.append(
                    document
                )
                result.skipped += 1
                continue

            metadata = dict(
                document.metadata
            )

            filename = metadata.get(
                "warc_filename"
            )
            offset = metadata.get(
                "warc_offset"
            )
            length = metadata.get(
                "warc_length"
            )

            if (
                budget <= 0
                or not filename
                or offset in {
                    None,
                    "",
                }
                or length in {
                    None,
                    "",
                }
            ):
                result.documents.append(
                    document
                )
                result.skipped += 1
                continue

            try:
                content = (
                    self.client.fetch(
                        filename=str(
                            filename
                        ),
                        offset=int(
                            offset
                        ),
                        length=int(
                            length
                        ),
                        timeout=self.timeout,
                    )
                )
            except Exception as exc:
                result.documents.append(
                    document
                )
                result.failed += 1
                result.errors.append(
                    str(exc)
                    or exc.__class__.__name__
                )
                budget -= 1
                continue

            hydrated_metadata = (
                dict(metadata)
            )
            hydrated_metadata[
                "content_hydration"
            ] = {
                "status": "success",
                "source": (
                    "common_crawl_warc_range"
                ),
                **dict(
                    content.metadata
                ),
            }

            result.documents.append(
                OpenWebDocument(
                    url=document.url,
                    provider=document.provider,
                    title=document.title,
                    snippet=document.snippet,
                    text=(
                        content.text
                        or document.text
                    ),
                    captured_at=(
                        document.captured_at
                    ),
                    content_type=(
                        content.content_type
                        or document.content_type
                    ),
                    confidence=(
                        document.confidence
                    ),
                    reliability=(
                        document.reliability
                    ),
                    metadata=(
                        hydrated_metadata
                    ),
                )
            )

            result.hydrated += 1
            budget -= 1

        return result
