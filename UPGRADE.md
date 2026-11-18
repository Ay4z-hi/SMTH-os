# Upgrading and maintaining SMTH OS

The old "v5/v6 pack" workflow (upload a ZIP, let a GitHub Action overwrite the
tree) is retired. It mangled paths and left the shell's helper commands outside
`usr/local/bin`. The repository is now the single source of truth, and
`.github/workflows/ci.yml` checks the result on every push.

## Change the palette

`tools/palette.json` is the only palette source. For a global accent swap:

```sh
python3 tools/recolor.py "#701b35" "#f2c6d2"   # new A, new B
python3 tools/gen_tokens.py
python3 tools/test_palette.py
```

AHIAN colours (`AHIAN_A`, `AHIAN_B`) are edited directly in `palette.json`,
because they are not a global swap target; regenerate artwork afterwards.

## Typography

Doto, DotGothic16 and Space Mono live in
`config/includes.chroot_after_packages/usr/share/fonts/truetype/smth/` with their
OFL licences. Do not reintroduce `fonts-inter` or `fonts-jetbrains-mono`.

## Before pushing

```sh
cd core && cargo test --workspace && cargo clippy --workspace --all-targets -- -D warnings
cd .. && python3 tools/check_wiring.py && python3 tools/test_palette.py
python3 tools/estimate_iso.py --arch amd64 --check-names
```

## Lock password in the live image

The live user password is `live`; the lock screen is `swaylock` (PAM password).
PIN/pattern lock is not implemented yet — see `README.md` "Known gaps".
