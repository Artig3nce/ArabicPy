"""Small, testable helpers used by the Windows release updater."""

from __future__ import annotations

import re


INSTALLER_PREFIX = "AlBaa-Setup-"
INSTALLER_SUFFIX = "-x64.exe"


def version_key(value: str) -> tuple[int, ...]:
    """Turn tags such as ``v1.2.3`` into a comparable numeric tuple."""
    match = re.search(r"\d+(?:\.\d+)*", str(value))
    return tuple(int(part) for part in match.group(0).split(".")) if match else ()


def is_newer_version(candidate: str, current: str) -> bool:
    candidate_key = version_key(candidate)
    current_key = version_key(current)
    width = max(len(candidate_key), len(current_key))
    if not candidate_key or not current_key:
        return False
    return candidate_key + (0,) * (width - len(candidate_key)) > current_key + (0,) * (width - len(current_key))


def installer_asset(release: dict) -> dict | None:
    """Return the supported Windows installer asset from a GitHub release."""
    for asset in release.get("assets", []):
        name = str(asset.get("name", ""))
        if name.startswith(INSTALLER_PREFIX) and name.endswith(INSTALLER_SUFFIX):
            return asset
    return None
