"""Custom themes + voice packs: storage, validation, zip/json import-export.
No Kivy imports here, so it can be tested anywhere."""
import io
import json
import os
import re
import shutil
import zipfile

from platform_util import data_dir

ROOT = os.path.join(data_dir(), "custom")
THEMES_DIR = os.path.join(ROOT, "themes")
VOICES_DIR = os.path.join(ROOT, "voices")
DRAFT_DIR = os.path.join(ROOT, "draft")
TMP_DIR = os.path.join(ROOT, "tmp_import")

ASSET_EXT = {".png", ".jpg", ".jpeg", ".gif", ".ttf", ".otf"}
MAX_ZIP_TOTAL = 60 * 1024 * 1024
MAX_FILE = 30 * 1024 * 1024
MAX_JSON = 256 * 1024

PRESETS = ("blue", "red", "green", "purple", "gold", "cyan", "pink")
FIT_MODES = ("cover", "contain", "fill")
FILE_KEYS = ("bg_photo", "bg_live", "core", "circle", "border", "font_title", "font_text")
BOOL_KEYS = ("show_core", "show_border", "show_clock", "show_title", "circle_spin")
NUM_RANGES = {            # key: (min, max)
    "bg_dim": (0.0, 0.9), "bg_live_opacity": (0.1, 1.0), "circle_opacity": (0.1, 1.0),
    "circle_scale": (0.5, 1.5), "text_scale": (0.7, 1.6), "anim_speed": (0.3, 3.0),
}

THEME_DEFAULTS = {
    "name": "My Theme", "accent": "3d7bff", "text_color": "ffffff",
    "bg_photo": "", "bg_live": "", "bg_live_opacity": 1.0, "bg_fit": "cover", "bg_dim": 0.3,
    "graphics": "blue", "core": "", "circle": "", "border": "",
    "show_core": True, "show_border": True, "circle_opacity": 1.0, "circle_spin": True,
    "font_title": "", "font_text": "", "title_text": "J.A.R.V.I.S",
    "show_clock": True, "show_title": True,
    "circle_scale": 1.0, "text_scale": 1.0, "anim_speed": 1.0,
}

VOICE_DEFAULTS = {"name": "My Voice", "voice": "", "language": "en-IN", "speed": 1.0,
                  "pitch": 1.0, "address": "sir", "greeting": "Good day {name}, Jarvis online."}

BUILTIN_VOICE_PACKS = {
    "Jarvis (default)": {"voice": "", "language": "en-IN", "speed": 1.0, "pitch": 1.0,
                         "address": "sir", "greeting": "Good day {name}, Jarvis online."},
    "Friday": {"voice": "", "language": "en-US", "speed": 1.05, "pitch": 1.25,
               "address": "boss", "greeting": "Hello {name}, Friday online. How can I help?"},
    "Deep Commander": {"voice": "", "language": "en-GB", "speed": 0.9, "pitch": 0.75,
                       "address": "commander", "greeting": "Systems ready, {name}. Awaiting your orders."},
    "Quick Assistant": {"voice": "", "language": "en-IN", "speed": 1.4, "pitch": 1.0,
                        "address": "boss", "greeting": "Ready when you are, {name}."},
}


class PackError(Exception):
    """Message is shown to the user as is."""


# ------------------------------------------------------------------ helpers
def slugify(name):
    return re.sub(r"[^a-z0-9]+", "-", str(name).lower()).strip("-")[:40] or "item"


def _hex(v, default):
    v = str(v or "").strip().lstrip("#")
    return v.lower() if re.fullmatch(r"[0-9a-fA-F]{6}", v) else default


def _num(v, lo, hi, default):
    try:
        return round(max(lo, min(hi, float(v))), 3)
    except (TypeError, ValueError):
        return default


def _bool(v, default):
    if isinstance(v, str):
        return v.strip().lower() in ("1", "true", "yes", "on")
    return default if v is None else bool(v)


def sniff(data):
    """Detect the real file type from its first bytes."""
    head = data[:16]
    if head[:6] in (b"GIF87a", b"GIF89a"):
        return "gif"
    if head[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if head[:3] == b"\xff\xd8\xff":
        return "jpg"
    if head[:4] in (b"PK\x03\x04", b"PK\x05\x06"):
        return "zip"
    if head[:4] == b"OTTO":
        return "otf"
    if head[:4] in (b"\x00\x01\x00\x00", b"true", b"ttcf"):
        return "ttf"
    if head[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    if data.lstrip(b"\xef\xbb\xbf \t\r\n")[:1] in (b"{", b"["):
        return "json"
    return None


def _write_json(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)


# -------------------------------------------------------------------- themes
def clean_theme(raw, folder=None):
    """Whitelist + clamp every field. Never trusts imported JSON."""
    d = dict(THEME_DEFAULTS)
    if not isinstance(raw, dict):
        return d
    d["name"] = str(raw.get("name") or d["name"]).strip()[:32] or d["name"]
    d["accent"] = _hex(raw.get("accent"), d["accent"])
    d["text_color"] = _hex(raw.get("text_color"), d["text_color"])
    d["bg_fit"] = raw.get("bg_fit") if raw.get("bg_fit") in FIT_MODES else "cover"
    d["graphics"] = raw.get("graphics") if raw.get("graphics") in PRESETS + ("custom",) else "blue"
    for k, (lo, hi) in NUM_RANGES.items():
        d[k] = _num(raw.get(k), lo, hi, d[k])
    for k in BOOL_KEYS:
        d[k] = _bool(raw.get(k), d[k])
    d["title_text"] = str(raw.get("title_text", d["title_text"]))[:24]
    for k in FILE_KEYS:
        fname = os.path.basename(str(raw.get(k) or ""))
        ext = os.path.splitext(fname)[1].lower()
        ok = bool(fname) and ext in ASSET_EXT
        if ok and folder is not None and not os.path.isfile(os.path.join(folder, fname)):
            ok = False
        d[k] = fname if ok else ""
    return d


def _iter_custom():
    if not os.path.isdir(THEMES_DIR):
        return
    for entry in sorted(os.listdir(THEMES_DIR)):
        folder = os.path.join(THEMES_DIR, entry)
        tj = os.path.join(folder, "theme.json")
        if not os.path.isfile(tj):
            continue
        try:
            with open(tj, encoding="utf-8") as f:
                raw = json.load(f)
        except Exception:
            continue
        yield clean_theme(raw, folder), folder


def custom_theme_names():
    return [d["name"] for d, _ in _iter_custom()]


def find_custom_theme(name):
    for d, folder in _iter_custom():
        if d["name"] == name:
            return d, folder
    return None


def new_draft(from_name=None):
    """Fresh working folder for the Studio. Returns (folder, data)."""
    if os.path.isdir(DRAFT_DIR):
        shutil.rmtree(DRAFT_DIR)
    found = find_custom_theme(from_name) if from_name else None
    if found:
        data, folder = found
        shutil.copytree(folder, DRAFT_DIR)
        return DRAFT_DIR, data
    os.makedirs(DRAFT_DIR)
    return DRAFT_DIR, clean_theme({})


def discard_draft():
    shutil.rmtree(DRAFT_DIR, ignore_errors=True)


def save_asset(folder, base, data, ext):
    """Store picked bytes as <base>.<ext>, replacing any older <base>.* file."""
    os.makedirs(folder, exist_ok=True)
    for f in os.listdir(folder):
        if f.startswith(base + "."):
            os.remove(os.path.join(folder, f))
    fname = f"{base}.{ext}"
    with open(os.path.join(folder, fname), "wb") as f:
        f.write(data)
    return fname


def remove_asset(folder, fname):
    if fname:
        try:
            os.remove(os.path.join(folder, os.path.basename(fname)))
        except OSError:
            pass


def save_theme(draft_dir, data, builtin_names, old_name=None):
    d = clean_theme(data, draft_dir)
    name = d["name"]
    if name.lower() in [b.lower() for b in builtin_names]:
        name += " (custom)"
    d["name"] = name
    os.makedirs(THEMES_DIR, exist_ok=True)
    dest = os.path.join(THEMES_DIR, slugify(name))
    old = find_custom_theme(old_name) if old_name else None
    if os.path.exists(dest):
        shutil.rmtree(dest)
    shutil.copytree(draft_dir, dest)
    _write_json(os.path.join(dest, "theme.json"), d)
    if old and os.path.abspath(old[1]) != os.path.abspath(dest) and os.path.isdir(old[1]):
        shutil.rmtree(old[1])
    return name


def delete_theme(name):
    found = find_custom_theme(name)
    if found:
        shutil.rmtree(found[1], ignore_errors=True)
        return True
    return False


def zip_theme_folder(folder, data):
    """Bytes of a shareable .zip: theme.json + only the files the theme uses."""
    d = clean_theme(data, folder)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("theme.json", json.dumps(d, indent=2, ensure_ascii=False))
        for k in FILE_KEYS:
            if d[k]:
                zf.write(os.path.join(folder, d[k]), d[k])
    return buf.getvalue()


def install_theme_zip(data, builtin_names=()):
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        raise PackError("Ye valid zip file nahi hai.")
    infos = [i for i in zf.infolist() if not i.is_dir()]
    if sum(i.file_size for i in infos) > MAX_ZIP_TOTAL:
        raise PackError("Zip bahut badi hai (60 MB se kam honi chahiye).")
    cands = [i for i in infos if os.path.basename(i.filename.replace("\\", "/")).lower() == "theme.json"]
    if not cands:
        raise PackError("Zip ke andar theme.json nahi mila.")
    tj = min(cands, key=lambda i: i.filename.count("/"))
    if tj.file_size > MAX_JSON:
        raise PackError("theme.json bahut badi hai.")
    base = os.path.dirname(tj.filename.replace("\\", "/"))
    try:
        raw = json.loads(zf.read(tj).decode("utf-8-sig"))
    except Exception:
        raise PackError("theme.json padhi nahi ja saki (JSON galat hai).")

    shutil.rmtree(TMP_DIR, ignore_errors=True)
    os.makedirs(TMP_DIR)
    try:
        for i in infos:
            name = i.filename.replace("\\", "/")
            if name.startswith("/") or ".." in name.split("/"):
                continue
            if base and not name.startswith(base + "/"):
                continue
            rel = name[len(base) + 1:] if base else name
            ext = os.path.splitext(rel)[1].lower()
            if "/" in rel or ext not in ASSET_EXT or i.file_size > MAX_FILE:
                continue
            with open(os.path.join(TMP_DIR, rel), "wb") as f:
                f.write(zf.read(i))
        d = clean_theme(raw, TMP_DIR)
        name = d["name"]
        if name.lower() in [b.lower() for b in builtin_names]:
            name += " (imported)"
        d["name"] = name
        os.makedirs(THEMES_DIR, exist_ok=True)
        dest = os.path.join(THEMES_DIR, slugify(name))
        shutil.rmtree(dest, ignore_errors=True)
        shutil.move(TMP_DIR, dest)
        _write_json(os.path.join(dest, "theme.json"), d)
        return name
    finally:
        shutil.rmtree(TMP_DIR, ignore_errors=True)


# --------------------------------------------------------------- voice packs
def clean_voice(raw):
    d = dict(VOICE_DEFAULTS)
    if not isinstance(raw, dict):
        return d
    d["name"] = str(raw.get("name") or d["name"]).strip()[:32] or d["name"]
    d["voice"] = str(raw.get("voice") or "")[:200]
    lang = str(raw.get("language") or "")
    d["language"] = lang if re.fullmatch(r"[a-z]{2,3}(-[A-Za-z0-9]{2,8})?", lang) else d["language"]
    d["speed"] = _num(raw.get("speed"), 0.5, 2.0, 1.0)
    d["pitch"] = _num(raw.get("pitch"), 0.5, 2.0, 1.0)
    d["address"] = str(raw.get("address") or d["address"]).strip()[:24] or d["address"]
    d["greeting"] = str(raw.get("greeting") if raw.get("greeting") is not None else d["greeting"])[:160]
    return d


def _custom_voice_files():
    if not os.path.isdir(VOICES_DIR):
        return []
    return [os.path.join(VOICES_DIR, f) for f in sorted(os.listdir(VOICES_DIR)) if f.endswith(".json")]


def _custom_voice_packs():
    out = {}
    for path in _custom_voice_files():
        try:
            with open(path, encoding="utf-8") as f:
                d = clean_voice(json.load(f))
            out[d["name"]] = d
        except Exception:
            continue
    return out


def voice_pack_names():
    return list(BUILTIN_VOICE_PACKS) + sorted(_custom_voice_packs())


def is_builtin_voice(name):
    return name in BUILTIN_VOICE_PACKS


def get_voice_pack(name):
    if name in BUILTIN_VOICE_PACKS:
        return clean_voice({"name": name, **BUILTIN_VOICE_PACKS[name]})
    return _custom_voice_packs().get(name)


def save_voice_pack(raw):
    d = clean_voice(raw)
    if d["name"] in BUILTIN_VOICE_PACKS:
        d["name"] += " (custom)"
    os.makedirs(VOICES_DIR, exist_ok=True)
    _write_json(os.path.join(VOICES_DIR, slugify(d["name"]) + ".json"), {"type": "voice_pack", **d})
    return d["name"]


def delete_voice_pack(name):
    if name in BUILTIN_VOICE_PACKS:
        return False
    for path in _custom_voice_files():
        try:
            with open(path, encoding="utf-8") as f:
                if clean_voice(json.load(f))["name"] == name:
                    os.remove(path)
                    return True
        except Exception:
            continue
    return False


def export_voice_pack(name):
    d = get_voice_pack(name)
    if not d:
        raise PackError("Ye voice pack nahi mila.")
    return json.dumps({"type": "voice_pack", **d}, indent=2, ensure_ascii=False).encode("utf-8")


def install_voice_json(data):
    if len(data) > MAX_JSON:
        raise PackError("Ye file bahut badi hai.")
    try:
        raw = json.loads(data.decode("utf-8-sig"))
    except Exception:
        raise PackError("JSON file padhi nahi ja saki.")
    if not isinstance(raw, dict) or not ({"speed", "pitch", "voice", "greeting", "address"} & raw.keys()):
        raise PackError("Ye voice pack file nahi lagti.")
    return save_voice_pack(raw)
