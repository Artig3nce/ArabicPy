"""Base-image provider extension point (architecture plan v4, section 8) --
the same registry-of-implementations shape as `DistroModule`/`DistroBackend`
(see `arabicpy/linux_studio/modules/registry.py` and
`arabicpy/linux_studio/backends/registry.py`). v1 ships exactly one
implementation, `UbuntuBaseProvider`; a second distro family's provider
implements the same methods against its own image format (Fedora's
Kickstart/Kiwi tooling, Arch's bootstrap tarballs, ...) without the Base
Manager UI, the project schema, or the Upgrade Wizard changing.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional


@dataclass(frozen=True)
class ReleaseInfo:
    """One known release this provider can fetch -- not yet installed."""

    version: str
    codename: str
    display_name: str
    lts: bool
    directory_url: str


@dataclass
class BaseRecord:
    """One installed base image, as tracked by `cache.py`'s manifest."""

    family: str
    version: str
    codename: str
    source: str
    sha256: str = ""
    verified: bool = False
    downloaded_at: str = ""
    iso_path: str = ""
    rootfs_path: str = ""


class BaseProvider(ABC):
    family: str = ""

    @abstractmethod
    def list_known_releases(self) -> list[ReleaseInfo]:
        """Known releases for this family -- a bundled static list until the
        live release feed (architecture plan v4, section 5) replaces/
        supplements it."""

    @abstractmethod
    def download(
        self,
        release: ReleaseInfo,
        destination: Path,
        *,
        on_progress: Optional[Callable[[int, int], None]] = None,
    ) -> BaseRecord:
        """Download and verify `release`'s ISO to `destination`; return the
        resulting BaseRecord."""

    @abstractmethod
    def verify(self, iso_path: Path, release: ReleaseInfo) -> bool:
        """Check `iso_path`'s SHA256 against the release's published sum."""

    def import_existing_iso(self, iso_path: Path) -> BaseRecord:
        raise NotImplementedError

    def import_existing_rootfs(self, rootfs_path: Path) -> BaseRecord:
        raise NotImplementedError
