"""Al Baa Linux Builder -- generates the build scripts and branding files for
the official, Ubuntu-based Al Baa Linux ISO.

This is deliberately not a generic distro-creation toolkit: every constant
below is fixed. No function in this module accepts a name, base-OS, or
branding argument, so every ISO this module can ever describe is the same
Al Baa Linux, the way every Windows build is the same Windows.
"""
import os

DISTRO_NAME = "Al Baa Linux"
DISTRO_ID = "albaa"
DISTRO_VERSION = "1.0"
DISTRO_PRETTY = f"{DISTRO_NAME} {DISTRO_VERSION} (Noble)"
DISTRO_HOSTNAME = "albaa-linux"

# Pinned, not "latest" -- live-build's mirror/suite selection needs a fixed
# codename for a reproducible build.
UBUNTU_CODENAME = "noble"

ISO_VOLUME_ID = "ALBAA_LINUX"
ISO_FILENAME = f"AlBaaLinux-{DISTRO_VERSION}-amd64.iso"

BUILD_DIR = "/opt/albaa-linux-builder/build"

# A short, curated list -- XFCE rather than the full ubuntu-desktop meta
# package, so the "the desktop experience is always Al Baa" identity holds
# from the very first ISO without inflating build time/size.
DEFAULT_PACKAGE_LIST = [
    "task-xfce-desktop",
    "lightdm",
    "network-manager",
    "network-manager-gnome",
    "firefox",
    "pcmanfm",
    "xfce4-terminal",
]

BUILDER_TOOL_PACKAGES = [
    "live-build",
    "xorriso",
    "squashfs-tools",
    "isolinux",
    "syslinux-efi",
    "grub-pc-bin",
    "grub-efi-amd64-bin",
    "mtools",
    "dosfstools",
]


def builder_tools_install_script():
    """Bash script that installs the live-build toolchain system-wide in WSL2."""
    packages = " ".join(BUILDER_TOOL_PACKAGES)
    return (
        "set -e\n"
        "apt-get update\n"
        f"apt-get install -y {packages}\n"
        f"mkdir -p {BUILD_DIR}\n"
    )


def branding_files():
    """Text files written under config/includes.chroot/ so the built system
    reports Al Baa Linux, not Ubuntu, once it boots."""
    os_release = (
        f'NAME="{DISTRO_NAME}"\n'
        f'PRETTY_NAME="{DISTRO_PRETTY}"\n'
        f'ID={DISTRO_ID}\n'
        f'ID_LIKE=ubuntu debian\n'
        f'VERSION="{DISTRO_VERSION}"\n'
        f'VERSION_ID="{DISTRO_VERSION}"\n'
        f'HOME_URL="https://albaa.dev/"\n'
    )
    lsb_release = (
        f"DISTRIB_ID={DISTRO_ID}\n"
        f"DISTRIB_RELEASE={DISTRO_VERSION}\n"
        f'DISTRIB_DESCRIPTION="{DISTRO_PRETTY}"\n'
    )
    lightdm_greeter = (
        "[greeter]\n"
        "background=/usr/share/backgrounds/albaa-wallpaper.png\n"
        f"default-user-image=/usr/share/backgrounds/albaa-wallpaper.png\n"
    )
    return {
        "etc/os-release": os_release,
        "etc/hostname": f"{DISTRO_HOSTNAME}\n",
        "etc/lsb-release": lsb_release,
        "etc/lightdm/lightdm-gtk-greeter.conf": lightdm_greeter,
    }


def package_list_file():
    """Contents of config/package-lists/albaa.list.chroot."""
    return "\n".join(DEFAULT_PACKAGE_LIST) + "\n"


def lb_config_script():
    """The `lb config` invocation. Codename and image type are the only
    "shape" decisions; everything else uses live-build's own defaults."""
    return (
        "lb config "
        f"--distribution {UBUNTU_CODENAME} "
        '--archive-areas "main restricted universe multiverse" '
        "--binary-images iso-hybrid "
        f'--bootappend-live "boot=live components hostname={DISTRO_HOSTNAME}"'
    )


def lb_build_script(output_iso_path, wallpaper_base64=""):
    """Full bash pipeline: configure, drop in branding + package list, build,
    then copy the finished ISO out to the Windows-visible output path."""
    lines = [
        "set -e",
        f"mkdir -p {BUILD_DIR}",
        f"cd {BUILD_DIR}",
        lb_config_script(),
        "mkdir -p config/includes.chroot/usr/share/backgrounds",
        "mkdir -p config/includes.chroot/etc/lightdm",
    ]
    for relative_path, content in branding_files().items():
        target = f"config/includes.chroot/{relative_path}"
        directory = os.path.dirname(target)
        if directory:
            lines.append(f"mkdir -p {directory}")
        lines.append(f"cat > {target} <<'ALBAA_EOF'\n{content}ALBAA_EOF")
    if wallpaper_base64:
        lines.append(
            "base64 -d <<'ALBAA_WALLPAPER' > "
            "config/includes.chroot/usr/share/backgrounds/albaa-wallpaper.png\n"
            f"{wallpaper_base64}\nALBAA_WALLPAPER"
        )
    lines.append(f"mkdir -p config/package-lists")
    lines.append(f"cat > config/package-lists/albaa.list.chroot <<'ALBAA_EOF'\n{package_list_file()}ALBAA_EOF")
    lines.append("lb build 2>&1 | tee build.log")
    lines.append(f'ISO_PATH=$(ls -1 *.iso | head -n 1)')
    lines.append('if [ -z "$ISO_PATH" ]; then echo "ALBAA_BUILD_FAILED_NO_ISO"; exit 1; fi')
    lines.append(f'mkdir -p "$(dirname "{output_iso_path}")"')
    lines.append(f'cp "$ISO_PATH" "{output_iso_path}"')
    return "\n".join(lines) + "\n"


def export_linux_builder_workspace(directory):
    """Write the generated live-build config tree to `directory` for
    inspection, without touching WSL2. Mirrors export_android_project()."""
    os.makedirs(directory, exist_ok=True)
    package_lists_dir = os.path.join(directory, "config", "package-lists")
    os.makedirs(package_lists_dir, exist_ok=True)
    with open(
        os.path.join(package_lists_dir, "albaa.list.chroot"), "w", encoding="utf-8", newline="\n"
    ) as file:
        file.write(package_list_file())

    includes_root = os.path.join(directory, "config", "includes.chroot")
    for relative_path, content in branding_files().items():
        target_path = os.path.join(includes_root, *relative_path.split("/"))
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        with open(target_path, "w", encoding="utf-8", newline="\n") as file:
            file.write(content)

    with open(os.path.join(directory, "lb_config.sh"), "w", encoding="utf-8", newline="\n") as file:
        file.write(lb_config_script() + "\n")

    return directory
