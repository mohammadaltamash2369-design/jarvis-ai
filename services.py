"""Online helpers: IP, news, weather, wikipedia, movies, email, Gemini."""
import re
import smtplib
import urllib.parse
from email.message import EmailMessage

import settings
from netutil import get_json, post_json


def find_my_ip():
    return get_json("https://api64.ipify.org", {"format": "json"})["ip"]


def wikipedia_summary(topic, sentences=2):
    r = get_json("https://en.wikipedia.org/w/api.php", {
        "action": "query", "list": "search", "srsearch": topic, "format": "json", "srlimit": 1})
    hits = r.get("query", {}).get("search", [])
    if not hits:
        return None
    title = hits[0]["title"]
    s = get_json("https://en.wikipedia.org/api/rest_v1/page/summary/"
                 + urllib.parse.quote(title.replace(" ", "_"), safe=""))
    parts = re.split(r"(?<=[.!?])\s+", (s.get("extract") or "").strip())
    return " ".join(parts[:sentences]) or None


def get_news(limit=6):
    key = settings.get("news_key")
    if not key:
        raise ValueError("no_key")
    r = get_json("https://newsapi.org/v2/top-headlines", {
        "country": settings.get("news_country") or "in", "category": "general", "apiKey": key})
    if r.get("status") != "ok":
        raise ValueError(r.get("message", "news error"))
    return [a["title"].rsplit(" - ", 1)[0] for a in r.get("articles", []) if a.get("title")][:limit]


def weather_forecast(city):
    key = settings.get("weather_key")
    if not key:
        raise ValueError("no_key")
    r = get_json("https://api.openweathermap.org/data/2.5/weather",
                 {"q": city, "appid": key, "units": "metric"})
    if str(r.get("cod")) != "200":
        raise ValueError(r.get("message", "weather error"))
    return r["weather"][0]["main"], f'{r["main"]["temp"]}°C', f'{r["main"]["feels_like"]}°C'


def movie_info(title):
    key = settings.get("omdb_key")
    if not key:
        raise ValueError("no_key")
    r = get_json("https://www.omdbapi.com/", {"t": title, "apikey": key, "plot": "short"})
    if r.get("Response") != "True":
        return None
    return r


def send_email(to, subject, message):
    addr, pwd = settings.get("email"), settings.get("email_password")
    if not addr or not pwd:
        raise ValueError("no_key")
    mail = EmailMessage()
    mail["To"], mail["Subject"], mail["From"] = to, subject, addr
    mail.set_content(message)
    with smtplib.SMTP(settings.get("smtp_host"), int(settings.get("smtp_port")), timeout=20) as s:
        s.starttls()
        s.login(addr, pwd.replace(" ", ""))
        s.send_message(mail)


# ------------------------------------------------------------------ Gemini
_history = []


def ask_gemini(prompt):
    key = settings.get("gemini_key")
    if not key:
        return "Please add your Gemini API key in Settings first."
    system = (f"You are Jarvis, a concise voice assistant for {settings.get('user_name')}. "
              "Reply in plain text only (no markdown, no lists, no emojis), in at most three short "
              "sentences. Reply in the same language the user speaks.")
    contents = _history[-8:] + [{"role": "user", "parts": [{"text": prompt}]}]
    try:
        r = post_json(
            f"https://generativelanguage.googleapis.com/v1beta/models/{settings.get('gemini_model')}:generateContent",
            {"systemInstruction": {"parts": [{"text": system}]}, "contents": contents},
            headers={"x-goog-api-key": key})
        if "error" in r:
            print(f"[gemini] {r['error']}")
            return "Gemini returned an error. Please check your API key in Settings."
        text = r["candidates"][0]["content"]["parts"][0]["text"]
        text = re.sub(r"[*#`_]", "", text).strip()
        _history.extend([{"role": "user", "parts": [{"text": prompt}]},
                         {"role": "model", "parts": [{"text": text}]}])
        del _history[:-12]
        return text or "I'm sorry, I couldn't process that request."
    except Exception as e:
        print(f"[gemini] {e}")
        return "I couldn't reach Gemini. Please check your internet connection."
