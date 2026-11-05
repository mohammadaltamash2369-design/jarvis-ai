"""All voice commands (online + offline ones)."""
import ast
import json
import operator
import os
import random
import re
import shutil
import subprocess
import sys
import threading
import urllib.parse
from datetime import datetime

import services
import settings
from platform_util import IS_ANDROID, android_activity, asset, data_dir, open_url
from textutil import humanize_seconds, parse_duration, words_to_digits

IS_WIN = sys.platform.startswith("win")
IS_MAC = sys.platform == "darwin"

JOKES = [
    "Why do programmers prefer dark mode? Because light attracts bugs.",
    "Why was the computer cold? It left its Windows open.",
    "There are only ten kinds of people: those who understand binary and those who don't.",
    "Why did the developer go broke? Because he used up all his cache.",
    "A SQL query walks into a bar, walks up to two tables and asks: can I join you?",
    "To understand recursion, you must first understand recursion.",
    "I would tell you a UDP joke, but you might not get it.",
]

ANDROID_PACKAGES = {
    "youtube": "com.google.android.youtube", "whatsapp": "com.whatsapp",
    "chrome": "com.android.chrome", "maps": "com.google.android.apps.maps",
    "gmail": "com.google.android.gm", "instagram": "com.instagram.android",
    "telegram": "org.telegram.messenger", "spotify": "com.spotify.music",
    "facebook": "com.facebook.katana", "photos": "com.google.android.apps.photos",
}
ANDROID_ACTIONS = {
    "camera": "android.media.action.STILL_IMAGE_CAMERA",
    "settings": "android.settings.SETTINGS",
    "phone": "android.intent.action.DIAL", "dialer": "android.intent.action.DIAL",
    "alarm": "android.intent.action.SHOW_ALARMS", "clock": "android.intent.action.SHOW_ALARMS",
}
SITES = {
    "youtube": "https://www.youtube.com", "google": "https://www.google.com",
    "gmail": "https://mail.google.com", "whatsapp": "https://web.whatsapp.com",
    "facebook": "https://www.facebook.com", "instagram": "https://www.instagram.com",
    "wikipedia": "https://www.wikipedia.org", "github": "https://github.com",
    "maps": "https://maps.google.com", "twitter": "https://x.com",
    "linkedin": "https://www.linkedin.com", "netflix": "https://www.netflix.com",
}


# ------------------------------------------------------------ safe calculator
_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
        ast.Div: operator.truediv, ast.Mod: operator.mod, ast.Pow: operator.pow}


def _safe_eval(expr):
    def ev(n):
        if isinstance(n, ast.Expression):
            return ev(n.body)
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)):
            return n.value
        if isinstance(n, ast.UnaryOp) and isinstance(n.op, (ast.USub, ast.UAdd)):
            v = ev(n.operand)
            return -v if isinstance(n.op, ast.USub) else v
        if isinstance(n, ast.BinOp) and type(n.op) in _OPS:
            l, r = ev(n.left), ev(n.right)
            if isinstance(n.op, ast.Pow) and abs(r) > 100:
                raise ValueError("exponent too large")
            return _OPS[type(n.op)](l, r)
        raise ValueError("unsupported expression")
    return ev(ast.parse(expr, mode="eval"))


_REPL = [("to the power of", "**"), ("multiplied by", "*"), ("divided by", "/"),
         ("modulo", "%"), ("times", "*"), ("into", "*"), ("over", "/"),
         ("plus", "+"), ("minus", "-"), ("mod", "%"), ("power", "**")]


def try_calculate(q):
    t = words_to_digits(q)
    for a, b in _REPL:
        t = t.replace(a, b)
    found = re.findall(r"[\d.+\-*/()% ]+", t)
    expr = max(found, key=len).strip() if found else ""
    if not re.search(r"\d", expr) or not re.search(r"[+\-*/%]", expr.lstrip("+-")):
        return None
    try:
        val = _safe_eval(expr)
    except Exception:
        return None
    if isinstance(val, float):
        val = int(val) if val.is_integer() else round(val, 6)
    return f"{expr.replace(' ', '')} equals {val}"


def _strip(q, words):
    pattern = r"\b(" + "|".join(re.escape(w) for w in words) + r")\b"
    return re.sub(r"\s+", " ", re.sub(pattern, " ", q)).strip()


# ------------------------------------------------------------ system actions
def _launch_first(cmds):
    for cmd in cmds:
        if shutil.which(cmd[0]):
            subprocess.Popen(cmd)
            return True
    return False


def open_terminal():
    if IS_WIN:
        subprocess.Popen("start cmd", shell=True)
        return True
    if IS_MAC:
        subprocess.Popen(["open", "-a", "Terminal"])
        return True
    return _launch_first([["x-terminal-emulator"], ["gnome-terminal"], ["konsole"], ["xterm"]])


def open_text_editor():
    if IS_WIN:
        subprocess.Popen(["notepad.exe"])
        return True
    if IS_MAC:
        subprocess.Popen(["open", "-a", "TextEdit"])
        return True
    return _launch_first([["gedit"], ["kate"], ["mousepad"]])


def open_camera_desktop():
    if IS_WIN:
        subprocess.Popen("start microsoft.windows.camera:", shell=True)
        return True
    if IS_MAC:
        subprocess.Popen(["open", "-a", "Photo Booth"])
        return True
    return _launch_first([["cheese"]])


def open_path(path):
    if IS_WIN:
        os.startfile(path)
    elif IS_MAC:
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path])


def android_open_package(package):
    try:
        act = android_activity()
        intent = act.getPackageManager().getLaunchIntentForPackage(package)
        if intent is None:
            return False
        act.startActivity(intent)
        return True
    except Exception as e:
        print(f"[android open] {e}")
        return False


def android_open_action(action):
    try:
        from jnius import autoclass
        android_activity().startActivity(autoclass("android.content.Intent")(action))
        return True
    except Exception as e:
        print(f"[android action] {e}")
        return False


def android_set_timer(seconds):
    try:
        from jnius import autoclass
        AlarmClock = autoclass("android.provider.AlarmClock")
        intent = autoclass("android.content.Intent")(AlarmClock.ACTION_SET_TIMER)
        intent.putExtra(AlarmClock.EXTRA_LENGTH, int(seconds))
        intent.putExtra(AlarmClock.EXTRA_MESSAGE, "Jarvis timer")
        intent.putExtra(AlarmClock.EXTRA_SKIP_UI, True)
        android_activity().startActivity(intent)
        return True
    except Exception as e:
        print(f"[android timer] {e}")
        return False


def load_custom_apps():
    """apps.json: name -> desktop path (or Android package name)."""
    try:
        with open(asset("apps.json"), encoding="utf-8") as f:
            return {k.lower(): v for k, v in json.load(f).items() if not k.startswith("_")}
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _notes_path():
    return os.path.join(data_dir(), "jarvis_notes.txt")


# ------------------------------------------------------------------ assistant
class Assistant:
    """say(text) speaks (blocking) | listen() -> text or None | read_typed(prompt) -> text or None"""

    def __init__(self, say, listen, read_typed):
        self.say = say
        self.listen = listen
        self.read_typed = read_typed
        self.refresh()

    def refresh(self):
        self.a = settings.get("address") or "sir"
        self.custom_apps = load_custom_apps()

    def ask(self, prompt):
        self.say(prompt)
        return self.listen()

    def handle(self, query):
        try:
            self._route(query.strip(), words_to_digits(query.lower().strip()))
        except ValueError as e:
            print(f"[command] {e}")
            self.say("Sorry, that didn't work. Please check your keys in Settings.")
        except OSError as e:
            print(f"[network] {e}")
            self.say("I couldn't connect to the internet.")
        except Exception as e:
            print(f"[command error] {e}")
            self.say(f"Sorry {self.a}, something went wrong with that request.")

    def _svc_error(self, e, name):
        if str(e) == "no_key":
            self.say(f"Please add your {name} details in Settings first.")
        else:
            print(f"[{name}] {e}")
            self.say(f"The {name} service said: {e}")

    # ------------------------------------------------------------- routing
    def _route(self, raw, q):
        a = self.a
        for name, target in self.custom_apps.items():
            if f"open {name}" in q or f"launch {name}" in q:
                self.say(f"Opening {name} for you {a}")
                if IS_ANDROID:
                    if not android_open_package(target):
                        self.say(f"I couldn't open {name}.")
                else:
                    open_path(target)
                return

        words = q.split()
        if "how are you" in q:
            self.say(f"I am absolutely fine {a}. What about you?")
        elif q in ("help", "what can you do") or "what can you do" in q:
            self.say("I can tell the time and date, open apps, set timers, take notes, calculate, "
                     "read news and weather, search wikipedia, google and youtube, send email, "
                     "tell jokes, and answer questions using Gemini.")
        elif "timer" in q or "remind me in" in q:
            self.timer_flow(q)
        elif re.search(r"\b(read|show)( my)? notes\b|\bmy notes\b", q):
            self.read_notes()
        elif re.search(r"\b(clear|delete)( my)? notes\b", q):
            self.clear_notes()
        elif re.search(r"\b(take a note|make a note|note that|note down|remember that)\b", q):
            self.take_note(q)
        elif q.startswith(("open ", "launch ", "start ")):
            self.open_flow(q.split(" ", 1)[1].strip())
        elif "weather" in q or "temperature" in q:
            self.weather_flow(q)
        elif "news" in q or "headlines" in q:
            self.news_flow()
        elif "time" in words or "what time" in q:
            self.say("It is " + datetime.now().strftime("%I:%M %p").lstrip("0"))
        elif re.search(r"\b(date|what day|which day)\b", q) or q in ("today", "what is today"):
            self.say("Today is " + datetime.now().strftime("%A, %d %B %Y"))
        elif "ip address" in q:
            self.say(f"Your IP address is {services.find_my_ip()}")
        elif re.search(r"\b(send|write)\b.*\bemail\b", q):
            self.email_flow()
        elif "movie" in q or "film" in q.split():
            self.movie_flow(q)
        elif "wikipedia" in q or "wiki" in words:
            self.wiki_flow(q)
        elif "youtube" in q:
            topic = _strip(q, ["play", "on", "in", "youtube", "search", "for", "video", "videos", "the", "please"])
            topic = topic or self.ask("What do you want to play on youtube?")
            if topic:
                self.say(f"Searching {topic} on youtube")
                open_url("https://www.youtube.com/results?search_query=" + urllib.parse.quote_plus(topic))
            else:
                self.say("I didn't catch that.")
        elif "google" in q or q.startswith("search "):
            topic = _strip(q, ["search", "on", "in", "google", "for", "about", "the", "please"])
            topic = topic or self.ask("What do you want to search on google?")
            if topic:
                self.say(f"Searching {topic} on google")
                open_url("https://www.google.com/search?q=" + urllib.parse.quote_plus(topic))
            else:
                self.say("I didn't catch that.")
        elif "joke" in q or "make me laugh" in q:
            self.say(random.choice(JOKES))
        elif "flip a coin" in q or "toss a coin" in q or "coin toss" in q:
            self.say("It's " + random.choice(["heads", "tails"]))
        elif "roll a dice" in q or "roll a die" in q or "roll dice" in q:
            self.say(f"You rolled a {random.randint(1, 6)}")
        else:
            result = try_calculate(q) if re.search(r"calculate|what is|what's|how much|\d", q) else None
            self.say(result or services.ask_gemini(raw))

    # --------------------------------------------------------------- flows
    def open_flow(self, name):
        name = re.sub(r"^(the|my)\s+", "", name)
        if IS_ANDROID:
            for key, action in ANDROID_ACTIONS.items():
                if key in name:
                    self.say(f"Opening {key}")
                    if not android_open_action(action):
                        self.say("I couldn't open that.")
                    return
            for key, pkg in ANDROID_PACKAGES.items():
                if key in name:
                    self.say(f"Opening {key}")
                    if not android_open_package(pkg):
                        if key in SITES:
                            open_url(SITES[key])
                        else:
                            self.say(f"{key} doesn't seem to be installed.")
                    return
        else:
            if "terminal" in name or "command prompt" in name:
                self.say("Opening terminal") if open_terminal() else self.say("I couldn't find a terminal.")
                return
            if "notepad" in name or "editor" in name:
                self.say("Opening the editor") if open_text_editor() else self.say("I couldn't find an editor.")
                return
            if "camera" in name:
                self.say("Opening camera") if open_camera_desktop() else self.say("I couldn't find a camera app.")
                return
        for key, url in SITES.items():
            if key in name:
                self.say(f"Opening {key}")
                open_url(url)
                return
        self.say(f"I don't know how to open {name}. You can add it to apps dot json.")

    def weather_flow(self, q):
        m = re.search(r"weather (?:in|of|at|for|like in)\s+([a-z .'-]+)", q)
        city = m.group(1).strip() if m else None
        city = city or self.ask("Tell me the name of your city")
        if not city:
            self.say("I didn't catch the city name.")
            return
        try:
            weather, temp, feels = services.weather_forecast(city)
        except ValueError as e:
            return self._svc_error(e, "weather")
        self.say(f"In {city} the temperature is {temp}, but it feels like {feels}. "
                 f"The weather report says {weather}.")

    def news_flow(self):
        try:
            headlines = services.get_news()
        except ValueError as e:
            return self._svc_error(e, "news")
        if not headlines:
            self.say("I couldn't find any headlines right now.")
            return
        self.say(f"Here are the latest headlines, {self.a}. " + ". ".join(headlines))

    def wiki_flow(self, q):
        topic = _strip(q, ["search", "look", "up", "tell", "me", "about", "on", "in", "for",
                           "from", "wikipedia", "wiki", "the", "please"])
        topic = topic or self.ask("What do you want to search on wikipedia?")
        if not topic:
            self.say("I didn't catch that.")
            return
        summary = services.wikipedia_summary(topic)
        self.say(f"According to wikipedia, {summary}" if summary else f"I found nothing about {topic}.")

    def movie_flow(self, q):
        title = _strip(q, ["tell", "me", "about", "the", "movie", "film", "named", "called", "search", "for", "please"])
        title = title or self.ask("Please tell me the movie name")
        if not title:
            self.say("I didn't catch that.")
            return
        try:
            m = services.movie_info(title)
        except ValueError as e:
            return self._svc_error(e, "OMDb movie")
        if not m:
            self.say("I couldn't find that movie.")
            return
        self.say(f"{m.get('Title')} was released in {m.get('Year')} and has an IMDb rating of "
                 f"{m.get('imdbRating')}. Cast: {m.get('Actors')}. Plot: {m.get('Plot')}")

    def email_flow(self):
        if not settings.get("email") or not settings.get("email_password"):
            self.say("Please add your email and app password in Settings first.")
            return
        to = self.read_typed("Type the receiver's email address in the box below.")
        if not to:
            self.say("I didn't get an email address.")
            return
        subject = self.ask("What should be the subject?")
        message = self.ask("What is the message?")
        if not subject or not message:
            self.say("I didn't catch that, email cancelled.")
            return
        try:
            services.send_email(to.strip(), subject.capitalize(), message.capitalize())
            self.say(f"I have sent the email {self.a}")
        except Exception as e:
            print(f"[email] {e}")
            self.say("The email could not be sent. Please check your email settings.")

    def timer_flow(self, q):
        secs = parse_duration(q)
        if secs <= 0:
            answer = self.ask("For how long?")
            secs = parse_duration(words_to_digits(answer or ""))
        if secs <= 0:
            self.say("I couldn't understand the duration.")
            return
        if IS_ANDROID and android_set_timer(secs):
            self.say(f"Timer set for {humanize_seconds(secs)}")
            return
        t = threading.Timer(secs, lambda: self.say(f"Time is up {self.a}"))
        t.daemon = True
        t.start()
        self.say(f"Timer set for {humanize_seconds(secs)}")

    def take_note(self, q):
        m = re.search(r"(?:take a note|make a note|note that|note down|remember that)\s*(.*)", q)
        text = (m.group(1) if m else "").strip() or self.ask("What should I note down?")
        if not text:
            self.say("I didn't catch that.")
            return
        with open(_notes_path(), "a", encoding="utf-8") as f:
            f.write(f"{datetime.now():%Y-%m-%d %H:%M} - {text}\n")
        self.say(f"Noted {self.a}.")

    def read_notes(self):
        try:
            with open(_notes_path(), encoding="utf-8") as f:
                lines = [l.strip().split(" - ", 1)[-1] for l in f if l.strip()]
        except FileNotFoundError:
            lines = []
        self.say("Your notes are. " + ". ".join(lines[-5:]) if lines else "You have no notes yet.")

    def clear_notes(self):
        try:
            os.remove(_notes_path())
        except FileNotFoundError:
            pass
        self.say("All notes deleted.")
