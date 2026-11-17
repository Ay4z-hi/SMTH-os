# SMTH OS startup construction

Status: **implemented and unit-tested in the repository**. The GTK4 renderer has
not yet been executed on a booted image in this workspace; the QEMU boot job is
the first runtime check.

## Sequence

The ISO session starts the real desktop first (`labwc`, `smth-home`, Waybar and
the `smthd` helpers). `smth-startup` then opens a full-output layer-shell overlay
above it and draws the construction with GTK4/cairo:

1. **Logo** (0–1.4 s): black field, a short reveal/hold/fade of the SMTH mark,
   with a single red registration tick.
2. **Cursors** (0.9–8.6 s): seven independently moving cursors enter from the
   top and edges. Each follows its own path with a small per-cursor wobble and
   label (`ARCH`, `UI`, `LAYOUT`, `TYPE`, `SYNC`, …).
3. **Construction** (1.9–7.8 s): electric-blue, cyan, purple and red selection
   boxes are drawn progressively around the status bar, app grid, window,
   widgets, clock and dock. Panels, icons, window chrome and dock dots are wiped
   in under the boxes.
4. **Reveal** (7.8–8.6 s): construction outlines stop, the finished frame settles
   and the overlay fades out over the live interactive desktop. The overlay is
   keyboard/pointer-transparent to the real session after it closes.

Target duration is **9.6 s** (inside the requested 8–12 s). The final desktop is
the real running session, not a screenshot or video.

## Files

- `usr/local/lib/smth/startup_model.py` — pure Python timeline and
  resolution-independent layout. No GTK/cairo/Pillow import.
- `usr/local/lib/smth/startup.py` — GTK4/cairo layer-shell renderer.
- `usr/local/bin/smth-startup` — wrapper.
- `usr/local/bin/smth-settings` — *Accessibility → Startup animation* and
  *Preview animation*.
- `tools/test_startup.py` — timeline, bounds, cursor independence, selection
  boxes, construction items, resolutions and Reduced Motion.

## Disable and accessibility

Any of these skips the animation:

```sh
SMTH_NO_STARTUP_ANIMATION=1 smth-startup
# or add smth.no_startup_animation=1 to the kernel command line
# or Settings → Accessibility → Startup animation = off
```

The setting is stored at `~/.config/smth/startup-animation` (`0` / `off`
disables). *Reduce Motion* (`~/.config/smth/reduce-motion`) uses a 760 ms reveal
with no cursors or construction boxes. A click, key press or `timeout 15` also
ends the overlay, so a renderer failure cannot block the session.

## Logo replacement

Drop a PNG at `/usr/share/smth/startup-logo.png`. If it is absent, the renderer
tries `/usr/share/smth/logo.png`, then falls back to the dot-matrix `SMTH`
wordmark. The image is scaled to fit a 300 px box and is only shown during the
logo phase.

## Launcher adaptations

- **Windows**: `launchers/windows/smth_launcher.py` draws a 5.6 s Tk canvas
  construction over the live launcher, then fades it out. Click/Escape skips;
  `--no-animation`, `SMTH_NO_STARTUP_ANIMATION=1` or
  `%APPDATA%\SMTH\startup-animation` containing `0` disables it.
- **Android**: `MainActivity.kt` adds a 5.6 s `ConstructionView` over the built
  launcher. Tapping skips it, and the launcher skips it when the system animator
  scale is zero. The overlay is a real `View`, not a video, and does not replace
  the launcher.

## Verification limits

The local audit environment has no GTK4, cairo, QEMU or root. What is verified
here is the pure model and its tests, script syntax, wiring and CI YAML. The
renderer, layer-shell behaviour and fade on a real compositor remain to be
confirmed by the QEMU boot job and by hardware testing. Do not describe the
animation as visually verified until that evidence exists.
