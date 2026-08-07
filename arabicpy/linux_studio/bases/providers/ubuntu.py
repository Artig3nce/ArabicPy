"""UbuntuBaseProvider -- the only BaseProvider implementation today.

Ubuntu Desktop's exact ISO filename changes across an LTS series' point
releases (24.04, 24.04.1, 24.04.2, ...), so the filename is resolved at
download time from the release's own published SHA256SUMS rather than
hardcoded -- `find_desktop_amd64_entry` does that resolution.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

from .base import BaseProvider, BaseRecord, ReleaseInfo
from .. import iso_manager

KNOWN_RELEASES = [
    ReleaseInfo("22.04", "jammy", "Ubuntu 22.04 LTS", True, "https://releases.ubuntu.com/22.04/"),
    ReleaseInfo("24.04", "noble", "Ubuntu 24.04 LTS", True, "https://releases.ubuntu.com/24.04/"),
    ReleaseInfo("24.10", "oracular", "Ubuntu 24.10", False, "https://releases.ubuntu.com/24.10/"),
    ReleaseInfo("25.04", "plucky", "Ubuntu 25.04", False, "https://releases.ubuntu.com/25.04/"),
]


def _now() -> str:
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


class UbuntuBaseProvider(BaseProvider):
    family = "ubuntu"

    def list_known_releases(self) -> list[ReleaseInfo]:
        return list(KNOWN_RELEASES)

    def _resolve_iso(self, release: ReleaseInfo):
        sums_text = iso_manager.fetch_text(release.directory_url + "SHA256SUMS")
        entry = iso_manager.find_desktop_amd64_entry(iso_manager.parse_sha256sums(sums_text))
        if entry is None:
            raise ValueError(f"No desktop amd64 ISO found in {release.directory_url}SHA256SUMS")
        filename, expected_sha256 = entry
        return release.directory_url + filename, expected_sha256

    def download(
        self,
        release: ReleaseInfo,
        destination: Path,
        *,
        on_progress: Optional[Callable[[int, int], None]] = None,
    ) -> BaseRecord:
        iso_url, expected_sha256 = self._resolve_iso(release)
        iso_manager.download_with_resume(iso_url, destination, on_progress=on_progress)
        verified = iso_manager.sha256_file(destination) == expected_sha256
        return BaseRecord(
            family=self.family,
            version=release.version,
            codename=release.codename,
            source="downloaded",
            sha256=expected_sha256,
            verified=verified,
            downloaded_at=_now(),
            iso_path=str(destination),
        )

    def verify(self, iso_path: Path, release: ReleaseInfo) -> bool:
        _, expected_sha256 = self._resolve_iso(release)
        return iso_manager.sha256_file(iso_path) == expected_sha256

    def import_existing_iso(self, iso_path: Path) -> BaseRecord:
        """Register an ISO the user already has. Verified against a known
        release's SHA256SUMS when one matches; otherwise accepted as
        unverified rather than rejected outright."""
        actual_sha256 = iso_manager.sha256_file(iso_path)
        for release in KNOWN_RELEASES:
            try:
                if self.verify(iso_path, release):
                    return BaseRecord(
                        family=self.family,
                        version=release.version,
                        codename=release.codename,
                        source="imported-iso",
                        sha256=actual_sha256,
                        verified=True,
                        downloaded_at=_now(),
                        iso_path=str(iso_path),
                    )
            except (OSError, ValueError):
                continue
        return BaseRecord(
            family=self.family,
            version="unknown",
            codename="unknown",
            source="imported-iso",
            sha256=actual_sha256,
            verified=False,
            downloaded_at=_now(),
            iso_path=str(iso_path),
        )

    def import_existing_rootfs(self, rootfs_path: Path) -> BaseRecord:
        """Register an already-extracted filesystem. No ISO, so no checksum
        is possible -- always "Imported", never "Verified"."""
        return BaseRecord(
            family=self.family,
            version="unknown",
            codename="unknown",
            source="imported-rootfs",
            verified=False,
            downloaded_at=_now(),
            rootfs_path=str(rootfs_path),
        )
