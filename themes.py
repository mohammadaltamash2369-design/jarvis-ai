"""Built-in themes + custom themes (from packs.py), resolved to absolute file paths."""
import os

import packs
from platform_util import asset

PRESET_DIRS = {
    "blue": "static", "red": "static/themes/red", "green": "static/themes/green",
    "purple": "static/themes/purple", "gold": "static/themes/gold",
    "cyan": "static/themes/cyan", "pink": "static/themes/pink",
}
PRESET_ACCENT = {
    "blue": "3d7bff", "red": "ff3b3b", "green": "32e05a", "purple": "a64dff",
    "gold": "ffb02e", "cyan": "2ee6e6", "pink": "ff4dc4",
}
_BUILTIN_PRESETS = {
    "Jarvis Blue": "blue", "Iron Man Red": "red", "Matrix Green": "green", "Royal Purple": "purple",
    "Solar Gold": "gold", "Ice Cyan": "cyan", "Hot Pink": "pink",
}
BUILTIN_NAMES = list(_BUILTIN_PRESETS)
DEFAULT_THEME = "Jarvis Blue"


def _builtin_data(name):
    preset = _BUILTIN_PRESETS[name]
    return {"name": name, "graphics": preset, "accent": PRESET_ACCENT[preset], "bg_dim": 0.0}


def all_names():
    return BUILTIN_NAMES + [n for n in packs.custom_theme_names() if n not in BUILTIN_NAMES]


def is_builtin(name):
    return name in _BUILTIN_PRESETS


def resolve(name):
    if name in _BUILTIN_PRESETS:
        return resolve_data(_builtin_data(name), None)
    found = packs.find_custom_theme(name)
    if found:
        return resolve_data(found[0], found[1])
    return resolve_data(_builtin_data(DEFAULT_THEME), None)


def resolve_data(raw, folder):
    """Theme dict with absolute paths ready for the UI."""
    d = packs.clean_theme(raw, folder)

    def mine(key):
        return os.path.join(folder, d[key]) if folder and d[key] else None

    custom = d["graphics"] == "custom"
    base = PRESET_DIRS.get(d["graphics"], PRESET_DIRS["blue"])
    out = dict(d)
    out["bg_photo"], out["bg_live"] = mine("bg_photo"), mine("bg_live")
    out["core"] = (mine("core") if custom else None) or asset(base + "/jarvis.gif")
    out["circle"] = (mine("circle") if custom else None) or asset(base + "/circle.png")
    out["border"] = (mine("border") if custom else None) or asset(base + "/border.eps.png")
    out["font_title"] = mine("font_title") or asset("static/dusri.ttf")
    out["font_time"] = mine("font_text") or asset("static/mw.ttf")
    out["font_sub"] = mine("font_text") or asset("static/teesri.otf")
    return out


def rgba(hex_color, alpha=1.0):
    h = hex_color.lstrip("#")
    return (int(h[0:2], 16) / 255, int(h[2:4], 16) / 255, int(h[4:6], 16) / 255, alpha)
