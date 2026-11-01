"""Import STEP files into a new Onshape document via the REST API.

Keys come from ONSHAPE_ACCESS_KEY / ONSHAPE_SECRET_KEY (process env, then the
Windows user registry so `setx` values work without restarting). Keys are never
printed.

Usage: python onshape_import_step.py "Doc name" file1.step [file2.step ...]
       python onshape_import_step.py --check
"""
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

BASE = "https://cad.onshape.com/api/v6"


def _key(name):
    v = os.environ.get(name)
    if not v and sys.platform == "win32":
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
                v = winreg.QueryValueEx(k, name)[0]
        except OSError:
            v = None
    return (v or "").strip().strip('"')


def _auth():
    a, s = _key("ONSHAPE_ACCESS_KEY"), _key("ONSHAPE_SECRET_KEY")
    if not a or not s:
        sys.exit("ONSHAPE_ACCESS_KEY / ONSHAPE_SECRET_KEY not found")
    return "Basic " + base64.b64encode(f"{a}:{s}".encode()).decode()


def call(method, path, body=None, headers=None, timeout=120):
    h = {"Authorization": _auth(), "Accept": "application/json"}
    data = None
    if isinstance(body, (dict, list)):
        data = json.dumps(body).encode()
        h["Content-Type"] = "application/json"
    elif isinstance(body, bytes):
        data = body
    h.update(headers or {})
    req = urllib.request.Request(BASE + path, data=data, headers=h, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        sys.exit(f"HTTP {e.code} on {method} {path}: {e.read()[:400].decode(errors='replace')}")


def multipart(fields, file_path):
    b = uuid.uuid4().hex
    out = []
    for k, v in fields.items():
        out.append(f'--{b}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode())
    p = Path(file_path)
    out.append(
        f'--{b}\r\nContent-Disposition: form-data; name="file"; filename="{p.name}"\r\n'
        f"Content-Type: application/octet-stream\r\n\r\n".encode()
    )
    out.append(p.read_bytes())
    out.append(f"\r\n--{b}--\r\n".encode())
    return b"".join(out), {"Content-Type": f"multipart/form-data; boundary={b}"}


def import_step(did, wid, path):
    body, hdr = multipart(
        {
            "formatName": "STEP",
            "flattenAssemblies": "false",
            "allowFaultyParts": "true",
            "importAppearances": "true",
            "yAxisIsUp": "false",
            "storeInDocument": "false",
            "encodedFilename": Path(path).name,
        },
        path,
    )
    t = call("POST", f"/translations/d/{did}/w/{wid}", body, hdr, timeout=600)
    tid = t["id"]
    print(f"  uploaded {Path(path).name}, translating ({tid})", flush=True)
    for _ in range(240):
        time.sleep(5)
        t = call("GET", f"/translations/{tid}")
        state = t.get("requestState")
        if state in ("DONE", "FAILED"):
            break
    print(f"  {Path(path).name}: {state} {t.get('failureReason') or ''}", flush=True)
    return t


def main():
    if sys.argv[1:] == ["--check"]:
        info = call("GET", "/users/sessioninfo")
        print("keys OK for", info.get("name") or info.get("email") or "user")
        return
    name, files = sys.argv[1], sys.argv[2:]
    doc = call("POST", "/documents", {"name": name, "isPublic": False})
    did, wid = doc["id"], doc["defaultWorkspace"]["id"]
    print(f"created document {did}", flush=True)
    results = [import_step(did, wid, f) for f in files]
    els = call("GET", f"/documents/d/{did}/w/{wid}/elements")
    parts = call("GET", f"/parts/d/{did}/w/{wid}")
    summary = {
        "url": f"https://cad.onshape.com/documents/{did}/w/{wid}",
        "translations": [r.get("requestState") for r in results],
        "elements": [(e["name"], e["elementType"]) for e in els],
        "part_count": len(parts),
    }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
