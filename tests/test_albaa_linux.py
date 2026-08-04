import inspect

from arabicpy import albaa_linux
from arabicpy.albaa_linux import (
    DISTRO_ID,
    DISTRO_NAME,
    UBUNTU_CODENAME,
    branding_files,
    builder_tools_install_script,
    export_linux_builder_workspace,
    lb_build_script,
    lb_config_script,
    package_list_file,
)


def test_no_function_accepts_a_branding_override():
    """The whole point of this module: nobody can point it at a different
    name/base-OS/branding, so every ISO it can describe is Al Baa Linux."""
    banned_params = {"name", "distro", "distro_name", "base", "branding", "id"}
    for _, function in inspect.getmembers(albaa_linux, inspect.isfunction):
        params = set(inspect.signature(function).parameters)
        assert not (params & banned_params), f"{function.__name__} accepts a branding override: {params}"


def test_os_release_reports_albaa_not_ubuntu():
    files = branding_files()
    os_release = files["etc/os-release"]
    assert f'NAME="{DISTRO_NAME}"' in os_release
    assert f"ID={DISTRO_ID}" in os_release
    assert "NAME=Ubuntu" not in os_release
    assert 'NAME="Ubuntu"' not in os_release


def test_hostname_and_lsb_release_are_branded():
    files = branding_files()
    assert files["etc/hostname"].strip() == "albaa-linux"
    assert DISTRO_ID in files["etc/lsb-release"]


def test_package_list_includes_a_desktop_environment():
    packages = package_list_file()
    assert "task-xfce-desktop" in packages
    assert "lightdm" in packages


def test_lb_config_pins_the_ubuntu_codename():
    assert f"--distribution {UBUNTU_CODENAME}" in lb_config_script()
    assert UBUNTU_CODENAME == "noble"


def test_builder_tools_install_script_installs_live_build():
    script = builder_tools_install_script()
    assert "live-build" in script
    assert "xorriso" in script


def test_lb_build_script_writes_branding_and_copies_the_iso_out():
    script = lb_build_script("/mnt/c/Users/test/AppData/Local/AlBaa/linux_builder/output/AlBaaLinux-1.0-amd64.iso")
    assert "lb build" in script
    assert "os-release" in script
    assert "cp \"$ISO_PATH\"" in script
    assert "/mnt/c/Users/test/AppData/Local/AlBaa/linux_builder/output/AlBaaLinux-1.0-amd64.iso" in script


def test_export_linux_builder_workspace_writes_expected_files(tmp_path):
    export_linux_builder_workspace(str(tmp_path))

    os_release_path = tmp_path / "config" / "includes.chroot" / "etc" / "os-release"
    package_list_path = tmp_path / "config" / "package-lists" / "albaa.list.chroot"

    assert os_release_path.is_file()
    assert package_list_path.is_file()
    assert f'NAME="{DISTRO_NAME}"' in os_release_path.read_text(encoding="utf-8")
    assert "task-xfce-desktop" in package_list_path.read_text(encoding="utf-8")
