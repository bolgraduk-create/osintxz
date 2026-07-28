"""
Hash service.

Calculates file hashes
for investigation artifacts.
"""

from __future__ import annotations

import hashlib

from pathlib import Path



class HashService:
    """
    Service for file hashing.
    """



    def calculate_md5(
        self,
        file_path: str,
    ) -> str:
        """
        Calculate MD5 hash.
        """

        return self._calculate_hash(
            file_path,
            "md5",
        )



    def calculate_sha256(
        self,
        file_path: str,
    ) -> str:
        """
        Calculate SHA256 hash.
        """

        return self._calculate_hash(
            file_path,
            "sha256",
        )



    def calculate_file_size(
        self,
        file_path: str,
    ) -> int:
        """
        Return file size in bytes.
        """

        return Path(
            file_path
        ).stat().st_size



    def _calculate_hash(
        self,
        file_path: str,
        algorithm: str,
    ) -> str:
        """
        Internal hash calculation.
        """

        hasher = hashlib.new(
            algorithm
        )


        with open(
            file_path,
            "rb",
        ) as file:


            for chunk in iter(
                lambda: file.read(4096),
                b"",
            ):

                hasher.update(
                    chunk
                )


        return hasher.hexdigest()