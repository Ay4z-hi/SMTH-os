# SMTH OS implementation status

This file distinguishes implemented source from tested behaviour. Source code is not proof that a feature works on a booted ISO.

| Phase | Scope | Status |
|---|---|---|
| P0 | Palette contract, generated tokens/assets, AHIAN palette/motion, build checks | Source committed; CI/build pending |
| P1 | Desktop shell: labwc, Waybar layouts, launcher, keyboard shortcuts, adaptive layout | Existing implementation present; end-to-end UX untested |
| P2 | Core apps: Settings, Files, Calculator, Store, Terminal, media tools | Existing apps present; app-level tests incomplete |
| P3 | Extension architecture and signed .smx lifecycle | CLI/service source added; integration test untested |
| P4 | Live/installer/persistence/recovery boot journey | Live, persistence, toram, safe-graphics and recovery menu entries added; installer still missing |
| P5 | Security: signatures, least privilege, firewall, sandbox policy, encrypted install | Signed extension verification and nftables default-deny inbound policy added; sandbox/LUKS/A-B update security missing |
| P6 | Performance budgets and automated measurements | 450 MiB ISO gate added; runtime metrics still unmeasured |
| P7 | Full acceptance journeys, accessibility, AHIAN polish | Partial; not acceptance-tested |

## Current visual rules

- tools/palette.json is the only palette source.
- Black #000000, A #FF7A00, B #2F6BFF, and white foreground only.
- No gradients, blur, glows, shadows, acrylic, or translucent surfaces.
- Wallpapers and generated marks must pass python3 tools/test_palette.py.
- Inter and JetBrains Mono are the specified UI fonts; fallback fonts do not count as completion.
- Reduce Motion must disable decorative animation.

## Required before completion

- Complete the latest native amd64/arm64 builds and boot both ISOs in QEMU.
- Implement and test installer, persistence, safe graphics and recovery menu paths.
- Separate core and extension images in live-build output.
- Add nftables default-deny rules, application sandbox policy, LUKS installation, signed A/B updates and rollback.
- Measure RAM, boot time, app launch time, idle CPU and image size on a documented 2GB VM.
- Run acceptance journeys and record evidence.
