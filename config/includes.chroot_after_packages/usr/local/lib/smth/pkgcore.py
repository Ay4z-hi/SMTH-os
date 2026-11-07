"""SMTH package manager core: signed index, SHA-256 verified downloads, safe extraction, per-user installs. Flatpak backend for third-party apps."""
import hashlib, json, os, shutil, subprocess, tarfile, tempfile, urllib.parse, urllib.request
HOME = os.path.expanduser("~"); APPS = f"{HOME}/.local/share/smth-apps"; DESK = f"{HOME}/.local/share/applications"; DB = f"{APPS}/installed.json"
CONF, PUBKEY, DEFAULT_REPO = "/etc/smth/repo.conf", "/etc/smth/repo-pub.pem", "file:///usr/share/smth/repo/index.json"

def repo_url():
    try:
        for l in open(CONF):
            l = l.strip()
            if l and not l.startswith("#"): return l
    except OSError: pass
    return DEFAULT_REPO
def fetch(url): return urllib.request.urlopen(url, timeout=25).read()

def load_index():
    url = repo_url(); data = fetch(url); signed = False
    if os.path.exists(PUBKEY):                                   # a key is installed: signature is mandatory
        try: sig = fetch(url + ".sig")
        except Exception: raise ValueError("repository index is not signed")
        with tempfile.TemporaryDirectory() as t:
            open(f"{t}/i", "wb").write(data); open(f"{t}/s", "wb").write(sig)
            if subprocess.run(["openssl", "dgst", "-sha256", "-verify", PUBKEY, "-signature", f"{t}/s", f"{t}/i"], capture_output=True).returncode != 0:
                raise ValueError("bad repository signature")
        signed = True
    return json.loads(data), signed, url

def installed():
    try: return json.load(open(DB))
    except Exception: return {}
def _save(db): os.makedirs(APPS, exist_ok=True); json.dump(db, open(DB, "w"), indent=1)

def _safe(members):
    for m in members:
        n = os.path.normpath(m.name)
        if n.startswith(("/", "..")) or ".." in n.split(os.sep) or not (m.isfile() or m.isdir()):
            raise ValueError(f"unsafe path in package: {m.name}")
        yield m

def install(entry, base_url, progress=None):
    pid = entry["id"]; assert pid.replace("-", "").replace("_", "").isalnum(), "bad id"
    url = urllib.parse.urljoin(base_url, entry["url"]); data = fetch(url)
    if hashlib.sha256(data).hexdigest() != entry["sha256"].lower(): raise ValueError("checksum mismatch, download rejected")
    tmp = tempfile.mkdtemp(prefix="smthpkg-"); path = f"{tmp}/p.tgz"; open(path, "wb").write(data)
    try:
        with tarfile.open(path) as tf:
            tf.extractall(f"{tmp}/x", members=_safe(tf.getmembers()), filter="data")
        man = json.load(open(f"{tmp}/x/manifest.json"))
        if man.get("id") != pid: raise ValueError("manifest id does not match")
        dest = f"{APPS}/{pid}"; os.makedirs(APPS, exist_ok=True)
        if os.path.exists(dest): shutil.rmtree(dest)
        shutil.move(f"{tmp}/x", dest); os.makedirs(DESK, exist_ok=True)
        ex = os.path.normpath(os.path.join(dest, man["exec"]))
        if not ex.startswith(dest + os.sep): raise ValueError("exec escapes package")
        icon = os.path.join(dest, man["icon"]) if man.get("icon") else "application-x-executable"
        open(f"{DESK}/smthpkg-{pid}.desktop", "w").write(f"[Desktop Entry]\nType=Application\nName={man.get('name', pid)}\nExec={ex}\nIcon={icon}\nComment={man.get('description', '')}\nTerminal=false\nCategories={man.get('categories', 'Utility;')}\n")
        db = installed(); db[pid] = {"name": man.get("name", pid), "version": man.get("version", "?")}; _save(db)
    finally: shutil.rmtree(tmp, ignore_errors=True)

def remove(pid):
    shutil.rmtree(f"{APPS}/{pid}", ignore_errors=True)
    try: os.remove(f"{DESK}/smthpkg-{pid}.desktop")
    except OSError: pass
    db = installed(); db.pop(pid, None); _save(db)

# ---- Flatpak (Flathub) backend ----
def _fp(*a, t=900): return subprocess.run(["flatpak", *a], capture_output=True, text=True, timeout=t)
def fp_search(q):
    out = _fp("search", "--columns=application,name,description", q, t=60).stdout; rows = []
    for l in out.splitlines():
        p = l.split("\t")
        if len(p) >= 2 and "." in p[0]: rows.append((p[0], p[1], p[2] if len(p) > 2 else ""))
    return rows
def fp_install(app):
    _fp("remote-add", "--user", "--if-not-exists", "flathub", "https://dl.flathub.org/repo/flathub.flatpakrepo", t=60)
    r = _fp("install", "--user", "-y", "flathub", app)
    if r.returncode: raise ValueError(r.stderr.strip().splitlines()[-1] if r.stderr.strip() else "flatpak failed")
def fp_list():
    return [tuple(l.split("\t")[:2]) for l in _fp("list", "--user", "--app", "--columns=application,name", t=30).stdout.splitlines() if "\t" in l]
def fp_remove(app): _fp("uninstall", "--user", "-y", app)
