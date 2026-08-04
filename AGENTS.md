# Agent notes for ArabicPy / Al-Baa

## Release packaging

Every push to `main` (see `.github/workflows/release.yml`) builds **both**:

- a Windows installer (`windows-installer` job: PyInstaller via `AlBaaIDE.spec`
  + `build_exe.ps1`, then `AlBaaInstaller.iss` with Inno Setup)
- a Debian package (`linux-deb` job, which `needs: windows-installer`):
  PyInstaller via `AlBaaLinux.spec` + `build_deb.sh`, packaged with
  `packaging/linux/control` and `packaging/linux/albaa.desktop`

Both artifacts are uploaded to the same GitHub Release. **Keep the `.deb`
build working on every release** — if you change anything that affects
packaging (the app entry point `launch_ide.py`, `arabicpy/version.py`,
app dependencies, `assets/`, or the PyInstaller setup), update
`AlBaaLinux.spec` / `build_deb.sh` / `packaging/linux/*` alongside the
Windows equivalents so `linux-deb` doesn't silently break or fall out of
sync. Don't remove or skip the `linux-deb` job without being asked.

Note: the `.deb` does not bundle the embedded llama.cpp AI engine (that's
Windows-only, via `prepare_embedded_ai.ps1` / `AlBaaAIHost.spec`). On
Linux, AI features fall back to a system-installed `llama-server`,
Ollama, or a remote AI host reachable over the network
(`arabicpy/embedded_ai.py`).
