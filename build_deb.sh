#!/usr/bin/env bash
# Builds dist/deb/albaa_<version>_amd64.deb from the current checkout.
# Run on Linux (or WSL) with python3, PyInstaller, PySide6, and dpkg-deb
# available. Mirrors build_exe.ps1 + AlBaaInstaller.iss for the Windows build.
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$project_root"

# Icon generation instantiates a headless QApplication; force the offscreen
# platform plugin so this also works on a display-less CI runner.
export QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-offscreen}"

version="$(python3 -c "import re; print(re.search(r'__version__ = \"([^\"]+)\"', open('arabicpy/version.py').read()).group(1))")"
package_name="albaa"
arch="amd64"
stage_dir="dist/deb/${package_name}_${version}_${arch}"

echo "Building ${package_name} ${version} for Debian/Ubuntu (${arch})..."

python3 assets/generate_icon.py

rm -rf dist/albaa "$stage_dir"
python3 -m PyInstaller --noconfirm --clean AlBaaLinux.spec

mkdir -p \
    "$stage_dir/DEBIAN" \
    "$stage_dir/usr/lib/albaa" \
    "$stage_dir/usr/bin" \
    "$stage_dir/usr/share/applications" \
    "$stage_dir/usr/share/icons/hicolor/256x256/apps"

cp -r dist/albaa/. "$stage_dir/usr/lib/albaa/"

cat > "$stage_dir/usr/bin/albaa" <<'LAUNCHER'
#!/bin/sh
exec /usr/lib/albaa/albaa "$@"
LAUNCHER
chmod 0755 "$stage_dir/usr/bin/albaa"

cp packaging/linux/albaa.desktop "$stage_dir/usr/share/applications/albaa.desktop"
cp assets/albaa.png "$stage_dir/usr/share/icons/hicolor/256x256/apps/albaa.png"

sed "s/^Version: .*/Version: ${version}/" packaging/linux/control > "$stage_dir/DEBIAN/control"

dpkg-deb --build --root-owner-group "$stage_dir" "dist/deb/${package_name}_${version}_${arch}.deb"

echo "Built: dist/deb/${package_name}_${version}_${arch}.deb"
