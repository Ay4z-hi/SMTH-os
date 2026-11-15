#!/usr/bin/env python3
"""Build a signed SMTH .smx extension from extensions/ID/packages.txt."""
import argparse, hashlib, json, os, pathlib, shutil, subprocess, tempfile, zipfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
EXT = ROOT / "extensions"

def call(args):
    subprocess.run(args, check=True)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("extension")
    ap.add_argument("--arch", choices=("amd64", "arm64"), required=True)
    ap.add_argument("--private-key", required=True)
    ap.add_argument("--out", default="out/extensions")
    args = ap.parse_args()
    if os.geteuid() != 0:
        raise SystemExit("run as root so debootstrap can create the extension rootfs")
    source = EXT / args.extension
    packages_file = source / "packages.txt"
    meta_file = source / "manifest.json"
    if not packages_file.is_file() or not meta_file.is_file():
        raise SystemExit(f"unknown extension: {args.extension}")
    packages = [x.strip() for x in packages_file.read_text().splitlines() if x.strip() and not x.startswith("#")]
    if not packages:
        raise SystemExit("extension package list is empty")
    meta = json.loads(meta_file.read_text())
    with tempfile.TemporaryDirectory(prefix="smth-ext-") as td:
        root = pathlib.Path(td) / "root"
        call(["debootstrap", "--arch=" + args.arch, "--variant=minbase", "--include=" + ",".join(packages), "trixie", str(root), "https://deb.debian.org/debian"])
        payload = pathlib.Path(td) / "payload.squashfs"
        call(["mksquashfs", str(root), str(payload), "-noappend", "-comp", "zstd", "-b", "1M"])
        digest = hashlib.sha256(payload.read_bytes()).hexdigest()
        manifest = {"id": args.extension, "name": meta["name"], "version": meta["version"], "arch": args.arch, "sha256": digest}
        manifest_path = pathlib.Path(td) / "manifest.json"
        sig_path = pathlib.Path(td) / "manifest.sig"
        manifest_path.write_text(json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n")
        call(["openssl", "dgst", "-sha256", "-sign", args.private_key, "-out", str(sig_path), str(manifest_path)])
        out = pathlib.Path(args.out); out.mkdir(parents=True, exist_ok=True)
        target = out / f"{args.extension}-{args.arch}.smx"
        with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_STORED) as z:
            z.write(manifest_path, "manifest.json")
            z.write(sig_path, "manifest.sig")
            z.write(payload, "payload.squashfs")
        print(target)

if __name__ == "__main__":
    main()
