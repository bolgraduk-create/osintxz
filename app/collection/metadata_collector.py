"""
Metadata collector.

Collects technical metadata
about source files.
"""

from __future__ import annotations


import hashlib


from pathlib import Path


from datetime import datetime, timezone


from app.collection.base import (
    BaseCollector,
)


from app.collection.models import (
    CollectedData,
)



class MetadataCollector(
    BaseCollector
):
    """
    Collector for technical metadata.
    """



    def collect(
        self,
        source: str | Path,
    ) -> CollectedData:
        """
        Collect file metadata.
        """

        path = Path(
            source
        )


        if not path.exists():

            raise FileNotFoundError(
                path
            )


        if not path.is_file():

            raise ValueError(
                "Source is not a file"
            )



        metadata = {

            "filename":
                path.name,


            "extension":
                path.suffix.lower(),


            "size":
                path.stat().st_size,


            "sha256":
                self._hash_file(
                    path
                ),


            "collected_at":
                datetime.now(
                    timezone.utc
                ).isoformat(),

        }



        return CollectedData(

            source="metadata",

            content=None,

            metadata=metadata,

        )



    def _hash_file(
        self,
        path: Path,
    ) -> str:
        """
        Calculate SHA-256 hash.
        """

        sha256 = hashlib.sha256()



        with path.open(
            "rb"
        ) as file:

            while chunk := file.read(
                8192
            ):

                sha256.update(
                    chunk
                )



        return sha256.hexdigest()