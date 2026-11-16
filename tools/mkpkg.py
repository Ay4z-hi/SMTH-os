#!/usr/bin/env python3
"""mkpkg.py DIR OUT.smthpkg  : tar.gz a package dir (needs manifest.json). Then add sha256 to index.json."""
import hashlib, sys, tarfile
d, out = sys.argv[1], sys.argv[2]
with tarfile.open(out, "w:gz") as t: t.add(d, arcname=".")
print("sha256", hashlib.sha256(open(out, "rb").read()).hexdigest())
