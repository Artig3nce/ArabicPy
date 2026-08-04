# الباء

الباء لغة برمجة عربية مع بيئة تطوير مكتبية، وتحوّل الكود العربي إلى Python.

## Android mode

Create a new Android file from **Android > مشروع Android جديد**. The first
supported Android syntax is:

The IDE generates a Kivy preview and can export `main.py` and
`buildozer.spec`. APK compilation uses **WSL2 + Buildozer** and is available
from **Android > إنشاء APK عبر WSL2**.

WSL2 and Buildozer must be installed separately before APK compilation. The
current machine does not have WSL installed, but project export works without
it.

## Al Baa Linux Builder

Builds the official, always-Ubuntu-based Al Baa Linux ISO. This is not a
generic distro-creation tool -- the OS name, base, and branding are fixed in
`arabicpy/albaa_linux.py`; every ISO it produces is Al Baa Linux.

Available from the **… > Al Baa Linux** menu:

- **Install Builder Tools** -- installs WSL2/Ubuntu if needed, then the
  `live-build` toolchain inside it.
- **Build Al Baa Linux ISO** -- runs `live-build` inside WSL2 and copies the
  finished ISO to `%LOCALAPPDATA%\AlBaa\linux_builder\output\`.

Like APK compilation, this requires WSL2 + Ubuntu, plus at least ~25 GB free
on the Windows drive and ~15 GB free inside WSL2 (checked before each build).
The v1 build produces a minimal XFCE desktop ISO; build channels
(dev/testing/stable) and in-app VM testing are planned but not yet built.
