"""
Image EXIF extractor.

Reads complete image metadata through ExifTool.

The extractor prefers the bundled ExifTool executable
stored inside the project.

Resolution priority:

1. explicitly supplied executable path
2. bundled tools/exiftool/exiftool.exe
3. system PATH fallback

Responsible for:

- detecting ExifTool availability
- executing ExifTool in read-only mode
- requesting structured JSON output
- preserving complete raw metadata
- normalizing important investigation fields
- extracting GPS coordinates
- returning warnings without modifying the source file

Does NOT:

- modify original files
- write EXIF, XMP or IPTC metadata
- access the database
- commit transactions
- create entities or timeline events
"""

from __future__ import annotations

import json
import shutil
import subprocess

from pathlib import Path
from typing import Any

from app.core.config import (
    EXIFTOOL_EXECUTABLE,
)


class ImageExifExtractor:
    """
    Extract image metadata through ExifTool.
    """

    DEFAULT_TIMEOUT_SECONDS = 30

    PATH_EXECUTABLE_NAMES = (
        "exiftool",
        "exiftool.exe",
    )

    def __init__(
        self,
        *,
        executable_path: (
            str
            | Path
            | None
        ) = None,
        timeout_seconds: int = (
            DEFAULT_TIMEOUT_SECONDS
        ),
    ) -> None:

        self.executable_path = (
            self._resolve_executable(
                executable_path
            )
        )

        self.timeout_seconds = (
            self._validate_timeout(
                timeout_seconds
            )
        )

    # ==========================================================
    # Availability
    # ==========================================================

    def is_available(
        self,
    ) -> bool:
        """
        Return whether ExifTool is available.
        """

        return (
            self.executable_path
            is not None
            and self.executable_path.is_file()
        )

    def availability(
        self,
    ) -> dict[str, Any]:
        """
        Return detailed ExifTool availability information.
        """

        return {
            "available": (
                self.is_available()
            ),
            "executable": (
                str(
                    self.executable_path
                )
                if self.executable_path
                else None
            ),
            "bundled_executable": str(
                EXIFTOOL_EXECUTABLE
            ),
            "bundled_executable_exists": (
                EXIFTOOL_EXECUTABLE.is_file()
            ),
        }

    # ==========================================================
    # Extraction
    # ==========================================================

    def extract(
        self,
        path: str | Path,
    ) -> dict[str, Any]:
        """
        Extract complete and normalized image metadata.
        """

        image_path = (
            self._validate_image_path(
                path
            )
        )

        if not self.is_available():

            return {
                "status": "unavailable",
                "available": False,
                "executable": None,
                "normalized": {},
                "raw": {},
                "warnings": [
                    (
                        "Bundled ExifTool was not found at: "
                        f"{EXIFTOOL_EXECUTABLE}"
                    )
                ],
                "errors": [],
            }

        command = [
            str(
                self.executable_path
            ),
            "-json",
            "-G1",
            "-a",
            "-s",
            "-n",
            "-charset",
            "filename=UTF8",
            "--",
            str(
                image_path
            ),
        ]

        try:

            completed_process = (
                subprocess.run(
                    command,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=(
                        self.timeout_seconds
                    ),
                    check=False,
                    creationflags=(
                        subprocess.CREATE_NO_WINDOW
                        if hasattr(
                            subprocess,
                            "CREATE_NO_WINDOW",
                        )
                        else 0
                    ),
                )
            )

        except subprocess.TimeoutExpired as error:

            raise TimeoutError(
                (
                    "ExifTool metadata extraction "
                    "timed out after "
                    f"{self.timeout_seconds} seconds."
                )
            ) from error

        except OSError as error:

            raise RuntimeError(
                "Unable to execute bundled ExifTool: "
                f"{error}"
            ) from error

        standard_output = (
            completed_process.stdout
            or ""
        ).strip()

        standard_error = (
            completed_process.stderr
            or ""
        ).strip()

        if (
            completed_process.returncode
            != 0
            and not standard_output
        ):

            raise RuntimeError(
                (
                    "ExifTool failed with exit code "
                    f"{completed_process.returncode}: "
                    f"{standard_error or 'Unknown error'}"
                )
            )

        raw_metadata = (
            self._decode_output(
                standard_output
            )
        )

        warnings = self._extract_messages(
            raw_metadata,
            key_suffix="Warning",
        )

        errors = self._extract_messages(
            raw_metadata,
            key_suffix="Error",
        )

        if standard_error:

            warnings.append(
                standard_error
            )

        normalized_metadata = (
            self._normalize_metadata(
                raw_metadata
            )
        )

        return {
            "status": (
                "completed"
                if not errors
                else "completed_with_errors"
            ),
            "available": True,
            "executable": str(
                self.executable_path
            ),
            "normalized": (
                normalized_metadata
            ),
            "raw": raw_metadata,
            "warnings": (
                self._unique_strings(
                    warnings
                )
            ),
            "errors": (
                self._unique_strings(
                    errors
                )
            ),
        }

    # ==========================================================
    # Decoding
    # ==========================================================

    @staticmethod
    def _decode_output(
        output: str,
    ) -> dict[str, Any]:
        """
        Decode ExifTool JSON output.
        """

        if not output:

            return {}

        try:

            decoded = json.loads(
                output
            )

        except json.JSONDecodeError as error:

            raise ValueError(
                (
                    "ExifTool returned invalid "
                    "JSON output."
                )
            ) from error

        if not isinstance(
            decoded,
            list,
        ):

            raise ValueError(
                (
                    "ExifTool JSON output "
                    "must be a list."
                )
            )

        if not decoded:

            return {}

        first_item = decoded[0]

        if not isinstance(
            first_item,
            dict,
        ):

            raise ValueError(
                (
                    "ExifTool result must "
                    "contain an object."
                )
            )

        return first_item

    # ==========================================================
    # Normalization
    # ==========================================================

    def _normalize_metadata(
        self,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Normalize important investigation fields.
        """

        make = self._first_value(
            metadata,
            "EXIF:Make",
            "MakerNotes:Make",
            "QuickTime:Make",
        )

        model = self._first_value(
            metadata,
            "EXIF:Model",
            "MakerNotes:Model",
            "QuickTime:Model",
        )

        software = self._first_value(
            metadata,
            "EXIF:Software",
            "XMP:CreatorTool",
            "PNG:Software",
            "File:Software",
        )

        date_taken = self._first_value(
            metadata,
            "EXIF:DateTimeOriginal",
            "EXIF:CreateDate",
            "XMP:DateCreated",
            "QuickTime:CreateDate",
        )

        modify_date = self._first_value(
            metadata,
            "EXIF:ModifyDate",
            "File:FileModifyDate",
            "XMP:ModifyDate",
        )

        latitude = self._as_float(
            self._first_value(
                metadata,
                "EXIF:GPSLatitude",
                "Composite:GPSLatitude",
                "QuickTime:GPSLatitude",
            )
        )

        longitude = self._as_float(
            self._first_value(
                metadata,
                "EXIF:GPSLongitude",
                "Composite:GPSLongitude",
                "QuickTime:GPSLongitude",
            )
        )

        altitude = self._as_float(
            self._first_value(
                metadata,
                "EXIF:GPSAltitude",
                "Composite:GPSAltitude",
                "QuickTime:GPSAltitude",
            )
        )

        lens_model = self._first_value(
            metadata,
            "EXIF:LensModel",
            "Composite:LensID",
            "MakerNotes:LensType",
        )

        iso = self._first_value(
            metadata,
            "EXIF:ISO",
            "MakerNotes:ISO",
        )

        exposure_time = self._first_value(
            metadata,
            "EXIF:ExposureTime",
            "Composite:ShutterSpeed",
        )

        aperture = self._first_value(
            metadata,
            "EXIF:FNumber",
            "Composite:Aperture",
        )

        focal_length = self._first_value(
            metadata,
            "EXIF:FocalLength",
            "Composite:FocalLength35efl",
        )

        orientation = self._first_value(
            metadata,
            "EXIF:Orientation",
            "XMP:Orientation",
        )

        artist = self._first_value(
            metadata,
            "EXIF:Artist",
            "XMP:Creator",
            "IPTC:By-line",
        )

        copyright_value = self._first_value(
            metadata,
            "EXIF:Copyright",
            "XMP:Rights",
            "IPTC:CopyrightNotice",
        )

        description = self._first_value(
            metadata,
            "EXIF:ImageDescription",
            "XMP:Description",
            "IPTC:Caption-Abstract",
        )

        keywords = self._normalize_list(
            self._first_value(
                metadata,
                "XMP:Subject",
                "IPTC:Keywords",
            )
        )

        gps = {
            "latitude": latitude,
            "longitude": longitude,
            "altitude": altitude,
            "available": (
                latitude is not None
                and longitude is not None
            ),
        }

        return {
            "camera": {
                "make": make,
                "model": model,
                "lens_model": lens_model,
            },
            "software": software,
            "timestamps": {
                "date_taken": date_taken,
                "modify_date": modify_date,
            },
            "gps": gps,
            "capture": {
                "iso": iso,
                "exposure_time": (
                    exposure_time
                ),
                "aperture": aperture,
                "focal_length": (
                    focal_length
                ),
                "orientation": orientation,
            },
            "authorship": {
                "artist": artist,
                "copyright": (
                    copyright_value
                ),
            },
            "description": description,
            "keywords": keywords,
            "has_gps": gps["available"],
            "has_camera_information": bool(
                make
                or model
                or lens_model
            ),
            "editing_software_detected": bool(
                software
            ),
        }

    # ==========================================================
    # Metadata lookup
    # ==========================================================

    @staticmethod
    def _first_value(
        metadata: dict[str, Any],
        *keys: str,
    ) -> Any:
        """
        Return the first non-empty metadata value.
        """

        for key in keys:

            value = metadata.get(
                key
            )

            if value is None:

                continue

            if isinstance(
                value,
                str,
            ):

                normalized = (
                    value.strip()
                )

                if normalized:

                    return normalized

                continue

            return value

        return None

    @staticmethod
    def _extract_messages(
        metadata: dict[str, Any],
        *,
        key_suffix: str,
    ) -> list[str]:
        """
        Extract ExifTool warning or error fields.
        """

        messages: list[str] = []

        normalized_suffix = (
            key_suffix.casefold()
        )

        for key, value in metadata.items():

            key_name = str(
                key
            ).split(
                ":"
            )[-1].casefold()

            if key_name != normalized_suffix:

                continue

            if isinstance(
                value,
                list,
            ):

                messages.extend(
                    str(
                        item
                    )
                    for item in value
                    if item is not None
                )

            elif value is not None:

                messages.append(
                    str(
                        value
                    )
                )

        return messages

    # ==========================================================
    # Values
    # ==========================================================

    @staticmethod
    def _as_float(
        value: Any,
    ) -> float | None:
        """
        Convert a metadata value to float.
        """

        if value is None:

            return None

        try:

            return float(
                value
            )

        except (
            TypeError,
            ValueError,
        ):

            return None

    @staticmethod
    def _normalize_list(
        value: Any,
    ) -> list[str]:
        """
        Normalize metadata keyword values.
        """

        if value is None:

            return []

        if isinstance(
            value,
            list,
        ):

            return [
                str(
                    item
                ).strip()
                for item in value
                if str(
                    item
                ).strip()
            ]

        normalized = str(
            value
        ).strip()

        if not normalized:

            return []

        return [
            normalized
        ]

    @staticmethod
    def _unique_strings(
        values: list[str],
    ) -> list[str]:
        """
        Remove empty and duplicate messages.
        """

        result: list[str] = []

        seen: set[str] = set()

        for value in values:

            normalized = str(
                value
            ).strip()

            if (
                not normalized
                or normalized in seen
            ):

                continue

            seen.add(
                normalized
            )

            result.append(
                normalized
            )

        return result

    # ==========================================================
    # Executable resolution
    # ==========================================================

    @classmethod
    def _resolve_executable(
        cls,
        executable_path: (
            str
            | Path
            | None
        ),
    ) -> Path | None:
        """
        Resolve ExifTool executable.

        Priority:

        1. explicitly configured path
        2. bundled project executable
        3. system PATH fallback
        """

        if executable_path is not None:

            return cls._validate_executable_path(
                executable_path
            )

        if EXIFTOOL_EXECUTABLE.is_file():

            return (
                EXIFTOOL_EXECUTABLE
                .resolve()
            )

        for executable_name in (
            cls.PATH_EXECUTABLE_NAMES
        ):

            resolved = shutil.which(
                executable_name
            )

            if resolved:

                return Path(
                    resolved
                ).resolve()

        return None

    @staticmethod
    def _validate_executable_path(
        path: str | Path,
    ) -> Path:
        """
        Validate an explicitly configured executable.
        """

        candidate = Path(
            path
        ).expanduser()

        try:

            candidate = candidate.resolve(
                strict=True
            )

        except FileNotFoundError as error:

            raise FileNotFoundError(
                (
                    "Configured ExifTool executable "
                    f"does not exist: {candidate}"
                )
            ) from error

        if not candidate.is_file():

            raise ValueError(
                (
                    "Configured ExifTool path "
                    f"is not a file: {candidate}"
                )
            )

        return candidate

    # ==========================================================
    # Validation
    # ==========================================================

    @staticmethod
    def _validate_image_path(
        path: str | Path,
    ) -> Path:
        """
        Validate the source image path.
        """

        image_path = Path(
            path
        ).expanduser()

        try:

            image_path = image_path.resolve(
                strict=True
            )

        except FileNotFoundError as error:

            raise FileNotFoundError(
                (
                    "Image file does not exist: "
                    f"{image_path}"
                )
            ) from error

        if not image_path.is_file():

            raise ValueError(
                (
                    "Image path is not a file: "
                    f"{image_path}"
                )
            )

        return image_path

    @staticmethod
    def _validate_timeout(
        value: int,
    ) -> int:
        """
        Validate subprocess timeout.
        """

        try:

            timeout = int(
                value
            )

        except (
            TypeError,
            ValueError,
        ) as error:

            raise TypeError(
                (
                    "timeout_seconds must "
                    "be an integer."
                )
            ) from error

        if timeout <= 0:

            raise ValueError(
                (
                    "timeout_seconds must "
                    "be greater than zero."
                )
            )

        return timeout

    # ==========================================================
    # Information
    # ==========================================================

    def metadata(
        self,
    ) -> dict[str, Any]:
        """
        Return extractor information.
        """

        return {
            "type": "image_exif_extractor",
            "engine": "ExifTool",
            "available": self.is_available(),
            "executable": (
                str(
                    self.executable_path
                )
                if self.executable_path
                else None
            ),
            "bundled": (
                self.executable_path
                == EXIFTOOL_EXECUTABLE.resolve()
                if (
                    self.executable_path
                    and EXIFTOOL_EXECUTABLE.exists()
                )
                else False
            ),
            "timeout_seconds": (
                self.timeout_seconds
            ),
            "mode": "read_only",
            "capabilities": [
                "EXIF",
                "XMP",
                "IPTC",
                "MakerNotes",
                "GPS",
                "camera",
                "lens",
                "timestamps",
                "software",
                "authorship",
            ],
        }