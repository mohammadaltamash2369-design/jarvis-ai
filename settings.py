"""All user settings live in one JSON file in the app's private folder."""
import json
import os

from platform_util import data_dir

DEFAULTS = {
    "user_name": "Altamash",
    "address": "sir",
    "theme": "Jarvis Blue",
    "language": "en-IN",
    "voice": "",
    "voice_pack": "Jarvis (default)",
    "greeting": "Good day {name}, Jarvis online.",
    "speak_greeting": False,
    "speed": 1.0,
    "pitch": 1.0,
    "continuous": False,
    "prefer_offline": False,
    "gemini_key": "",
    "gemini_model": "gemini-2.5-flash",
    "news_key": "",
    "news_country": "in",
    "weather_key": "",
    "omdb_key": "",
    "email": "",
    "email_password": "",
    "smtp_host": "smtp.gmail.com",
    "smtp_port": 587,
}

_PATH = os.path.join(data_dir(), "jarvis_settings.json")
_data = None


def _load():
    global _data
    _data = dict(DEFAULTS)
    try:
        with open(_PATH, encoding="utf-8") as f:
            saved = json.load(f)
        _data.update({k: v for k, v in saved.items() if k in DEFAULTS})
    except (FileNotFoundError, json.JSONDecodeError):
        pass


def get(key):
    if _data is None:
        _load()
    return _data.get(key, DEFAULTS.get(key))


def set_many(values):
    if _data is None:
        _load()
    _data.update({k: v for k, v in values.items() if k in DEFAULTS})
    try:
        with open(_PATH, "w", encoding="utf-8") as f:
            json.dump(_data, f, indent=2)
    except OSError as e:
        print(f"[settings] could not save: {e}")
