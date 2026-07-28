"""
File collector.

Collects data from local files.

Supports text files in v1.0.
"""

from __future__ import annotations


from pathlib import Path


from app.collection.base import (
    BaseCollector,
)


from app.collection.models import (
    CollectedData,
)



class FileCollector(
    BaseCollector
):
    """
    Collector for local files.
    """



    def collect(
        self,
        source: str | Path,
    ) -> CollectedData:
        """
        Read file and return normalized data.
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



        content = (
            path.read_text(
                encoding="utf-8"
            )
        )


        metadata = {

            "filename":
                path.name,


            "extension":
                path.suffix,


            "size":
                path.stat().st_size,


            "path":
                str(path),

        }



        return CollectedData(

            source="file",

            content=content,

            metadata=metadata,

        )