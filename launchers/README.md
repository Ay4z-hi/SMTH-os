# SMTH launchers

Companion launchers for the SMTH OS identity. They are not the bootable ISO.

## Android (`launchers/android`)

A native HOME app (`os.smth.launcher`, minSdk 26, targetSdk 35).

* Enumerates installed launcher apps from `PackageManager` on every resume — no
  hard-coded package list and no "App not installed" grid.
* Searchable app grid rebuilt on each query (no invisible holes), 4/5/6 columns by
  screen width, long-press for app info.
* Dock shows four real, tappable shortcuts for the preferred apps that are
  actually installed; it is empty-safe rather than decorative.
* Battery + live clock header, dot-field background drawn at runtime, SMTH icon
  and black theme (no white flash), pointer icons suppressed so no mouse cursor
  ever appears.
* Bundled Space Mono / Doto fonts in `res/font` (OFL, licences in `licenses/`).

Verification: `gradle assembleDebug` was run locally (JDK 17.0.21, Android SDK 35,
Gradle 8.9) — BUILD SUCCESSFUL, APK 894,010 bytes, sha256
`fe2a87fd1397f56280193363ff58109fad80c1fc04c559a59d7a74bac92315a2`. Checks that
passed: `unzip -t`, `classes.dex`/`classes2.dex`/`classes3.dex`, bundled
`res/font`, `aapt dump badging` package `os.smth.launcher` + launchable activity
`os.smth.launcher.MainActivity`, `apksigner verify` (debug key).

**Not verified: install and launch.** This environment has no emulator, no
KVM group access and no system image. `.github/workflows/launchers.yml` performs
the install + launch check on an API 35 emulator with a process-liveness
assertion; treat the app as compile-verified, not runtime-verified, until that run
exists.

## Windows (`launchers/windows`)

A standalone Tkinter shell in the SMTH visual language.

* Real targets with fallbacks; protocol handlers use `os.startfile`
  (`webbrowser.open("ms-settings:")` silently fails on Windows).
* Failures are reported in an in-window status line instead of a raw traceback.
* Responsive app grid, Escape closes, Ctrl+F focuses search, bundled fonts are
  registered process-locally with `AddFontResourceExW`.
* Battery percentage via `GetSystemPowerStatus`; shutdown asks for confirmation
  and reports errors.

Verification (CI): PyInstaller build, size sanity check, and a smoke test that
launches the EXE and requires the process to stay alive for 8 seconds. A GUI is
not visually inspected in CI.
