import json

from arabicpy.os_builder import OSBuilderProject, OSBuilderProjectStore


def test_os_builder_project_round_trip(tmp_path):
    path = tmp_path / "custom.albaa-os.json"
    project = OSBuilderProject(
        distribution_name="My Ubuntu",
        logo_path="branding/logo.png",
        accent_color="#123456",
        applications={"python": True, "vscode": False},
        additional_packages=["curl", "htop"],
    )
    OSBuilderProjectStore.save(path, project)
    loaded = OSBuilderProjectStore.load(path)
    assert loaded.distribution_name == "My Ubuntu"
    assert loaded.logo_path == "branding/logo.png"
    assert loaded.accent_color == "#123456"
    assert loaded.applications["python"] is True
    assert loaded.applications["vscode"] is False
    assert loaded.additional_packages == ["curl", "htop"]
    assert json.loads(path.read_text(encoding="utf-8"))["format_version"] == 1


def test_os_builder_defaults_do_not_enable_optional_vscode():
    project = OSBuilderProject()
    assert project.applications["al_baa_ide"] is True
    assert project.applications["vscode"] is False
