"""Tiny HTTP helpers using only the standard library (keeps the Android build simple)."""
import json
import os
import ssl
import urllib.error
import urllib.parse
import urllib.request


def _context():
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        ctx = ssl.create_default_context()
        if os.path.isdir("/system/etc/security/cacerts"):
            try:
                ctx.load_verify_locations(capath="/system/etc/security/cacerts")
            except Exception:
                pass
        return ctx


def _send(req, timeout):
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_context()) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:   # APIs often explain the error in JSON
        try:
            return json.loads(e.read().decode("utf-8"))
        except Exception:
            raise


def get_json(url, params=None, headers=None, timeout=12):
    if params:
        url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "JarvisAI/1.0", **(headers or {})})
    return _send(req, timeout)


def post_json(url, payload, headers=None, timeout=30):
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=body, method="POST",
        headers={"Content-Type": "application/json", "User-Agent": "JarvisAI/1.0", **(headers or {})})
    return _send(req, timeout)
