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

## AI assistant

There is no bundled/embedded local AI engine (it was removed — see
`arabicpy/ai_server.py` history). The AI Assistant panel works two ways:

- **Ollama**, if `ollama` is on PATH (`arabicpy/ide.py` shells out to
  `http://127.0.0.1:11434`)
- a **remote AI host**: another Al-Baa install running its background
  "AI Network" bridge (`arabicpy/ai_server.py`, `AlBaaAIHost.spec` /
  `launch_ai_server.py`), reachable over LAN or Tailscale

Don't reintroduce a bundled/offline model download flow unless asked.
