# SMTH extension format (.smx)

Status: IMPLEMENTED IN SOURCE; BUILD/BOOT TEST UNTESTED.

An .smx is a ZIP container containing exactly manifest.json, manifest.sig and payload.squashfs. The manifest.sig is a detached RSA/SHA-256 signature over the exact manifest bytes. The payload is independently SHA-256 checked before signature acceptance.

The manifest has id, name, version, arch and sha256. Supported architecture values are all, amd64, arm64, or the host machine name. The public key is installed at /etc/smth/extensions.pub; without it, verification and installation fail closed.

The payload is mounted read-only under /opt/smth/extensions/ID with loop,ro,nodev,nosuid. Desktop files under usr/share/applications are linked into the SMTH application catalogue. A systemd service reactivates installed extensions at boot.

Commands:

    smthctl extension verify Browser.smx
    sudo smthctl extension install Browser.smx
    smthctl extension list
    sudo smthctl extension remove browser

Build/signing policy:
1. Build the extension filesystem independently from the core image.
2. Produce SquashFS with mksquashfs.
3. Create the manifest with the exact payload SHA-256.
4. Sign the manifest using the release signing key; never ship the private key in the ISO or repository.
5. Install the release public key at /etc/smth/extensions.pub.
6. Publish the .smx, detached signature inside the container, and checksums through a signed repository index.

This first implementation provides signature/hash verification, read-only mounting, boot activation, and removal. It does not yet provide dependency solving, automatic updates, rollback between extension versions, or a graphical extension browser.
