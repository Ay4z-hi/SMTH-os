# SMTH launchers

The Android launcher is a native Android HOME app (minSdk 26). Install the APK, open it, and select SMTH Launcher as the default Home app. It provides a searchable app grid, date/time, and a strict black/orange/blue visual style. Apps that are not installed on the phone show a clear message.

The Windows launcher is a standalone desktop shell/window built with Tkinter. It opens Windows system apps and settings through their normal launch targets. It does not replace Windows Explorer or claim to be a bootable OS.

Release builds are produced by GitHub Actions:
- Android: unsigned universal APK (sign locally before Play Store distribution).
- Windows: portable PyInstaller EXE.

These are companion launchers, not the full Linux SMTH OS ISO.
