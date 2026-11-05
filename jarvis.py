import threading
import time

from kivy.clock import Clock
from kivy.core.window import Window
from kivy.metrics import dp, sp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput

import imagetools
import settings
import speech
import themes
from commands import Assistant
from platform_util import IS_MOBILE, asset
from widgets import Dim, JarvisButton

try:  # desktop-only mic level meter (optional)
    import numpy as np
    import sounddevice as sd
except Exception:
    np = sd = None

STOP_WORDS = {"stop", "goodbye", "good bye", "bye", "that's all", "thats all", "thank you",
              "thanks", "cancel", "exit", "go to sleep"}


class Jarvis(FloatLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.volume_history = [0.0] * 7
        self.history_size = 140
        self._busy = threading.Lock()
        self._typed_waiter = None
        self._studio = None
        self.stream = None
        self.theme = None
        self.accent = "3d7bff"

        W = Window.width
        self._base_min = (0.45 if IS_MOBILE else 0.2) * W
        self._base_max = (0.85 if IS_MOBILE else 0.7) * W
        self.min_size, self.max_size = self._base_min, self._base_max
        self.gain = 1.5 if IS_MOBILE else 3
        Window.softinput_mode = "below_target"

        self._fs = {"time": sp(16 if IS_MOBILE else 24), "title": sp(26 if IS_MOBILE else 42),
                    "sub": sp(16 if IS_MOBILE else 24)}
        full = dict(size_hint=(1, 1), pos_hint={"x": 0, "y": 0})

        # layers, bottom -> top: photo, live animation, dimmer, frame, centre animation
        self.bg_photo = Image(fit_mode="cover", opacity=0, **full)
        self.bg_live = Image(fit_mode="cover", opacity=0, **full)
        self.dim = Dim(**full)
        self.border = Image(fit_mode="fill", **full)
        self.core = Image(size_hint=(None, None), pos_hint={"center_x": 0.5, "center_y": 0.5})
        self.circle = JarvisButton(fit_mode="contain", size_hint=(None, None),
                                   pos_hint={"center_x": 0.5, "center_y": 0.5})
        self.circle.bind(on_press=self.start_recording)
        for w in (self.bg_photo, self.bg_live, self.dim, self.border, self.core):
            self.add_widget(w)

        if IS_MOBILE:
            time_kw = dict(size=(dp(200), dp(40)), pos_hint={"center_x": 0.5, "top": 0.90})
        else:
            time_kw = dict(size=(300, 100), pos_hint={"x": 0.04, "top": 0.97})
        self.time_label = Label(text="", markup=True, size_hint=(None, None), **time_kw)
        self.add_widget(self.time_label)

        self.title_lbl = Label(markup=True, size_hint=(None, None),
                               size=(dp(300) if IS_MOBILE else 600, dp(50) if IS_MOBILE else 80),
                               pos_hint={"center_x": 0.5, "top": 0.97})
        self.add_widget(self.title_lbl)

        self.subtitles = Label(text="", size_hint=(0.9 if IS_MOBILE else 0.6, None),
                               height=dp(110 if IS_MOBILE else 120),
                               pos_hint={"center_x": 0.5, "y": 0.11}, halign="center", valign="middle")
        self.subtitles.bind(size=lambda w, s: setattr(w, "text_size", (s[0], None)))
        self.add_widget(self.subtitles)

        # bottom bar: typed commands + settings button
        bar = BoxLayout(orientation="horizontal", spacing=dp(8),
                        size_hint=(0.92 if IS_MOBILE else 0.6, None), height=dp(46),
                        pos_hint={"center_x": 0.5, "y": 0.03})
        self.text_in = TextInput(hint_text="Type a command, press Enter", multiline=False, font_size=sp(15),
                                 background_normal="", background_active="",
                                 background_color=(0, 0, 0, 0.55), foreground_color=(1, 1, 1, 1),
                                 padding=[dp(10), dp(12)])
        self.text_in.bind(on_text_validate=self._on_typed)
        self.settings_btn = Button(text="Settings", size_hint_x=0.3, font_size=sp(15),
                                   background_normal="", color=(1, 1, 1, 1))
        self.settings_btn.bind(on_release=self.open_settings)
        bar.add_widget(self.text_in)
        bar.add_widget(self.settings_btn)
        self.add_widget(bar)

        if not IS_MOBILE:
            self.left_vol = Label(font_size=22, markup=True, size_hint=(None, None), size=(220, 400),
                                  pos_hint={"x": 0.03, "center_y": 0.5})
            self.right_vol = Label(font_size=22, markup=True, size_hint=(None, None), size=(220, 400),
                                   pos_hint={"right": 0.97, "center_y": 0.5})
            self.add_widget(self.left_vol)
            self.add_widget(self.right_vol)
        self.add_widget(self.circle)

        self.assistant = Assistant(say=self.say, listen=self.listen, read_typed=self.read_typed)
        speech.set_volume_callback(self.push_volume)
        self.apply_theme(settings.get("theme"))
        self.subtitles.text = self.greeting_text() + "\nTap the circle and speak."

        Clock.schedule_interval(self.update_time, 1)
        Clock.schedule_interval(self.update_circle, 1 / 60)
        Clock.schedule_interval(self.circle.rotate_button, 1 / 60)
        Window.bind(on_key_down=self._on_key_down)

    # --------------------------------------------------------------- theme
    def apply_theme(self, name):
        try:
            self.apply_resolved(themes.resolve(name))
        except Exception as e:
            print(f"[theme] {name}: {e}")
            self.apply_resolved(themes.resolve(themes.DEFAULT_THEME))
            self.set_text("Theme load nahi ho saki, default laga di.")

    def _set_image(self, widget, path, opacity=1.0, fit=None):
        if path:
            widget.source = path
            widget.opacity = opacity
            if fit:
                widget.fit_mode = fit
        else:
            widget.source = ""
            widget.opacity = 0

    def apply_resolved(self, t):
        """Draw a resolved theme dict (from themes.resolve / themes.resolve_data)."""
        self.theme = t
        self.accent = t["accent"]
        speed = t["anim_speed"]
        self._set_image(self.bg_photo, t["bg_photo"], 1.0, t["bg_fit"])
        self._set_image(self.bg_live, t["bg_live"], t["bg_live_opacity"], t["bg_fit"])
        if t["bg_live"]:
            self.bg_live.anim_delay = max(0.02, imagetools.gif_frame_delay(t["bg_live"], 0.1) / speed)
        self.dim.set_alpha(t["bg_dim"])
        self._set_image(self.border, t["border"] if t["show_border"] else None)
        self._set_image(self.core, t["core"] if t["show_core"] else None)
        if t["show_core"] and t["core"]:
            self.core.anim_delay = max(0.02, imagetools.gif_frame_delay(t["core"], 0.2) / speed)
        self.circle.source = t["circle"]
        self.circle.opacity = t["circle_opacity"]
        self.circle.angle = 2 * speed if t["circle_spin"] else 0

        def font(path, fallback):
            return path if imagetools.font_ok(path) else fallback

        ts = t["text_scale"]
        self.title_lbl.font_name = font(t["font_title"], asset("static/dusri.ttf"))
        self.time_label.font_name = font(t["font_time"], asset("static/mw.ttf"))
        self.subtitles.font_name = font(t["font_sub"], asset("static/teesri.otf"))
        self.title_lbl.font_size = self._fs["title"] * ts
        self.time_label.font_size = self._fs["time"] * ts
        self.subtitles.font_size = self._fs["sub"] * ts
        if not IS_MOBILE:
            self.left_vol.font_name = self.right_vol.font_name = self.time_label.font_name

        cs = t["circle_scale"]
        self.min_size = self._base_min * cs
        self.max_size = min(self._base_max * cs, Window.width * 0.95)
        self.core.size = (self.min_size, self.min_size)
        self.circle.size = (self.min_size, self.min_size)

        a = self.accent
        self.title_lbl.text = f"[b][color={a}]{t['title_text']}[/color][/b]"
        self.title_lbl.opacity = 1 if t["show_title"] else 0
        self.time_label.opacity = 1 if t["show_clock"] else 0
        self.subtitles.color = themes.rgba(t["text_color"])
        self.settings_btn.background_color = themes.rgba(a, 0.45)
        self.text_in.cursor_color = themes.rgba(a)
        self.text_in.hint_text_color = themes.rgba(a, 0.7)
        self.update_time(0)

    # ------------------------------------------------------ screens / popups
    def open_settings(self, *args):
        from settings_ui import SettingsPopup
        SettingsPopup(self).open()

    def open_studio(self, edit_name=None):
        from studio_ui import StudioPanel
        if self._studio is not None:
            return
        self._studio = StudioPanel(self, edit_name)
        self.add_widget(self._studio)

    def close_studio(self):
        if self._studio is not None:
            self.remove_widget(self._studio)
            self._studio = None

    def on_settings_saved(self):
        self.assistant.refresh()
        self.set_text(f"Settings saved. {self.greeting_text()}")

    # ------------------------------------------------------------ greeting
    def greeting_text(self):
        text = settings.get("greeting") or "Good day {name}, Jarvis online."
        return text.replace("{name}", settings.get("user_name") or "friend")

    def startup(self, *args):
        """Called once after the app window is up."""
        if settings.get("speak_greeting") and self._busy.acquire(blocking=False):
            def run():
                try:
                    speech.speak(self.greeting_text())
                finally:
                    self._busy.release()
            threading.Thread(target=run, daemon=True).start()

    # ------------------------------------------------------------------ UI
    def set_text(self, text):
        Clock.schedule_once(lambda dt: setattr(self.subtitles, "text", text))

    def update_time(self, dt):
        self.time_label.text = f"[b][color={self.accent}]{time.strftime('TIME  %H:%M:%S')}[/color][/b]"

    def push_volume(self, v):
        self.volume_history.append(float(v))
        if len(self.volume_history) > self.history_size:
            self.volume_history.pop(0)

    def update_circle(self, dt):
        mean = sum(self.volume_history) / len(self.volume_history)
        size = max(self.min_size, min(self.max_size, self.min_size + mean * self.gain))
        self.circle.size = (size, size)
        if not IS_MOBILE:
            text = f"[b][color={self.accent}]" + "\n".join(f"{v:.2f}" for v in self.volume_history[-7:]) + "[/color][/b]"
            self.left_vol.text = text
            self.right_vol.text = text

    # ---------------------------------------------------- desktop mic meter
    def start_listening(self):
        if IS_MOBILE or sd is None or np is None:
            return
        try:
            def cb(indata, frames, t, status):
                self.push_volume(float(np.linalg.norm(indata) * 200))
            self.stream = sd.InputStream(callback=cb)
            self.stream.start()
        except Exception as e:
            print(f"[meter] {e}")

    def stop_listening(self):
        if self.stream:
            self.stream.stop()
            self.stream.close()

    # -------------------------------------------------- voice / typed input
    def _on_key_down(self, window, key, scancode, codepoint, modifier):
        if codepoint == "`" and not self.text_in.focus:
            self.start_recording()
            return True
        return False

    def start_recording(self, *args):
        self._start(None)

    def _on_typed(self, instance):
        text = instance.text.strip()
        instance.text = ""
        if not text:
            return
        waiter = self._typed_waiter
        if waiter is not None:           # an email address etc. was requested
            waiter["text"] = text
            waiter["event"].set()
            return
        self._start(text)

    def _start(self, typed):
        if not self._busy.acquire(blocking=False):
            return  # already listening / answering
        threading.Thread(target=self._worker, args=(typed,), daemon=True).start()

    def _worker(self, typed):
        try:
            first = True
            while True:
                if typed is not None:
                    query, typed = typed.lower(), None
                else:
                    self.set_text("Listening...")
                    query = speech.listen()
                if not query:
                    self.set_text("Sorry, I couldn't understand. Tap the circle and try again."
                                  if first else "Tap the circle to talk")
                    break
                first = False
                self.set_text(query)
                if query.strip(" .!?") in STOP_WORDS:
                    self.say("Okay, I'm here whenever you need me.")
                    break
                self.assistant.handle(query)
                if not settings.get("continuous"):
                    break
        except Exception as e:
            print(f"[worker] {e}")
            self.set_text(str(e))
        finally:
            self._busy.release()

    # used by Assistant (worker thread)
    def say(self, text):
        self.set_text(text)
        speech.speak(text)

    def listen(self):
        self.set_text("Listening...")
        return speech.listen()

    def read_typed(self, prompt, timeout=120):
        self.say(prompt)
        waiter = {"event": threading.Event(), "text": None}
        self._typed_waiter = waiter
        Clock.schedule_once(lambda dt: setattr(self.text_in, "focus", True))
        waiter["event"].wait(timeout)
        self._typed_waiter = None
        return waiter["text"]
