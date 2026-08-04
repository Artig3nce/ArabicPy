from arabicpy.updater import installer_asset, is_newer_version, version_key


def test_version_tags_are_compared_numerically():
    assert version_key("v1.12.3") == (1, 12, 3)
    assert is_newer_version("v0.1.1", "0.1.0")
    assert not is_newer_version("v0.1", "0.1.0")
    assert not is_newer_version("not-a-version", "0.1.0")


def test_only_x64_installer_asset_is_selected():
    release = {
        "assets": [
            {"name": "source.zip"},
            {"name": "AlBaa-Setup-0.2.0-x64.exe", "browser_download_url": "https://example.test/setup.exe"},
        ]
    }
    assert installer_asset(release)["name"] == "AlBaa-Setup-0.2.0-x64.exe"
