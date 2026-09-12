from __future__ import annotations

import shutil
from pathlib import Path


PROJECT_ROOT = Path(
    __file__
).resolve().parents[2]


TOOLS_ROOT = (
    PROJECT_ROOT
    / "tools"
)


DISCOVERY_BIN_ROOT = (
    TOOLS_ROOT
    / "osint"
    / "bin"
)


MANAGED_TOOL_PATHS: dict[
    str,
    tuple[Path, ...],
] = {

    "phoneinfoga": (
        TOOLS_ROOT
        / "phoneinfoga"
        / "phoneinfoga.exe",
    ),

    "subfinder": (
        DISCOVERY_BIN_ROOT
        / "subfinder.exe",
    ),

    "dnsx": (
        DISCOVERY_BIN_ROOT
        / "dnsx.exe",
    ),

    "gau": (
        DISCOVERY_BIN_ROOT
        / "gau.exe",
    ),

    "waybackurls": (
        DISCOVERY_BIN_ROOT
        / "waybackurls.exe",
    ),

    "katana": (
        DISCOVERY_BIN_ROOT
        / "katana.exe",
    ),

    "assetfinder": (
        DISCOVERY_BIN_ROOT
        / "assetfinder.exe",
    ),

    "httpx": (
        DISCOVERY_BIN_ROOT
        / "httpx.exe",
    ),

}


def find_tool(
    name: str,
) -> str | None:
    """
    Resolve an OSINT executable.

    Resolution order:

    1. Managed application tool paths.
    2. System/user PATH.

    This allows the application to use bundled or
    automatically installed tools without requiring
    manual PATH configuration.
    """

    normalized_name = (
        str(name)
        .strip()
        .lower()
    )

    if not normalized_name:
        return None

    managed_candidates = (
        MANAGED_TOOL_PATHS.get(
            normalized_name,
            (),
        )
    )

    for candidate in (
        managed_candidates
    ):

        try:

            if (
                candidate.exists()
                and candidate.is_file()
            ):

                return str(
                    candidate
                )

        except OSError:
            continue

    return shutil.which(
        name
    )


def tool_available(
    name: str,
) -> bool:
    """
    Return whether an OSINT executable can be resolved.
    """

    return (
        find_tool(name)
        is not None
    )


def build_tool_command(
    name: str,
    *arguments: str,
) -> list[str]:
    """
    Build an executable command using the resolved
    managed or PATH-based executable.
    """

    executable = find_tool(
        name
    )

    if executable is None:

        raise FileNotFoundError(
            f"OSINT tool is not available: {name}"
        )

    return [
        executable,
        *[
            str(argument)
            for argument in arguments
        ],
    ]
