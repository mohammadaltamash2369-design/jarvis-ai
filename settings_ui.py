import re
import threading

from kivy.metrics import dp, sp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.modalview import ModalView
from kivy.uix.scrollview import ScrollView

import filepicker
import packs
import settings
import speech
import themes
import uikit
from platform_util import IS_ANDROID

LANGS = {"English (India)": "en-IN", "English (US)": "en-US",
         "English (UK)": "en-GB", "Hindi": "hi-IN"}
DEFAULT_VOICE = "Default voice for this language"


class SettingsPopup(ModalView):
    def __init__(self, jarvis, **kwargs):
        super().__init__(size_hint=(0.96, 0.93), auto_dismiss=True, background="",
                         background_color=(0.02, 0.03, 0.08, 0.98), **kwargs)
        self.jarvis = jarvis
        self.saved = False
        self.accent = themes.rgba(jarvis.accent)
        self.langs = dict(LANGS)
        self.voice_map = {}
        a = self.accent

        root = BoxLayout(orientation="vertical", padding=dp(10), spacing=dp(6))
        root.add_widget(Label(text="[b]SETTINGS[/b]", markup=True, color=a, font_size=sp(20),
                              size_hint_y=None, height=dp(34)))
        self.status = uikit.status_label()
        root.add_widget(self.status)
        scroll = ScrollView(do_scroll_x=False)
        grid = GridLayout(cols=1, spacing=dp(8), size_hint_y=None, padding=[0, 0, dp(4), dp(10)])
        grid.bind(minimum_height=grid.setter("height"))

        # ---- profile
        grid.add_widget(uikit.header("Profile", a))
        self.name_in = uikit.text_input(settings.get("user_name"), "Your name", a)
        grid.add_widget(uikit.field("Your name", self.name_in))

        # ---- look
        grid.add_widget(uikit.header("Look - themes", a))
        names = themes.all_names()
        cur_theme = settings.get("theme") if settings.get("theme") in names else themes.DEFAULT_THEME
        self.theme_sp = uikit.spinner(cur_theme, names)
        self.theme_sp.bind(text=lambda inst, val: self.jarvis.apply_theme(val))       # live preview
        grid.add_widget(uikit.field("Theme (changes instantly)", self.theme_sp))
        grid.add_widget(uikit.button("Open Studio - make my own theme", self._open_studio, a))
        grid.add_widget(uikit.button("Export this theme (share as zip)", self._export_theme))
        grid.add_widget(uikit.button("Import theme zip / voice pack file", self._import))

        # ---- voice pack
        grid.add_widget(uikit.header("Voice pack", a))
        pack_names = packs.voice_pack_names()
        cur_pack = settings.get("voice_pack") if settings.get("voice_pack") in pack_names else pack_names[0]
        self.pack_sp = uikit.spinner(cur_pack, pack_names)
        self.pack_sp.bind(text=lambda inst, val: self._load_pack(val))
        grid.add_widget(uikit.field("Voice pack (works with every theme)", self.pack_sp))

        cur_lang = next((k for k, v in self.langs.items() if v == settings.get("language")), None)
        if cur_lang is None:
            cur_lang = self._lang_label(settings.get("language"))
        self.lang_sp = uikit.spinner(cur_lang, list(self.langs))
        self.lang_sp.bind(text=lambda *args: self._reload_voices())
        grid.add_widget(uikit.field("Language (listening + speaking)", self.lang_sp))
        self.voice_sp = uikit.spinner(DEFAULT_VOICE, [DEFAULT_VOICE])
        grid.add_widget(uikit.field("Voice", self.voice_sp))
        self.speed_lbl, self.speed = uikit.slider("Speed", settings.get("speed"), 0.5, 2.0, 0.1, a)
        self.pitch_lbl, self.pitch = uikit.slider("Pitch", settings.get("pitch"), 0.5, 2.0, 0.1, a)
        for w in (self.speed_lbl, self.speed, self.pitch_lbl, self.pitch):
            grid.add_widget(w)
        self.addr_in = uikit.text_input(settings.get("address"), "sir", a)
        grid.add_widget(uikit.field("Jarvis calls you (sir, boss, bhai...)", self.addr_in))
        self.greet_in = uikit.text_input(settings.get("greeting"), "Good day {name}, Jarvis online.", a)
        grid.add_widget(uikit.field("Greeting line ({name} = your name)", self.greet_in))
        self.greet_sw = uikit.make_switch(settings.get("speak_greeting"))
        grid.add_widget(uikit.switch_row("Speak the greeting when the app starts", self.greet_sw))
        grid.add_widget(uikit.button("Test voice", self._test_voice))
        grid.add_widget(uikit.button("Save current voice as my voice pack", self._save_pack, a))
        grid.add_widget(uikit.button("Delete this voice pack", self._delete_pack))
        grid.add_widget(uikit.button("Export this voice pack", self._export_pack))
        if IS_ANDROID:
            grid.add_widget(uikit.button("Get more voices (phone settings)",
                                         lambda *args: speech.open_voice_settings()))

        # ---- behaviour
        grid.add_widget(uikit.header("Behaviour", a))
        self.cont_sw = uikit.make_switch(settings.get("continuous"))
        grid.add_widget(uikit.switch_row("Keep listening after each answer", self.cont_sw))
        self.off_sw = uikit.make_switch(settings.get("prefer_offline"))
        if IS_ANDROID:
            grid.add_widget(uikit.switch_row("Prefer offline speech recognition", self.off_sw))

        # ---- keys
        grid.add_widget(uikit.header("API keys (stored only on this device)", a))
        self.gem_key = uikit.text_input(settings.get("gemini_key"), "Gemini API key", a, password=True)
        grid.add_widget(uikit.field("Gemini API key (AI answers)", self.gem_key))
        self.gem_model = uikit.text_input(settings.get("gemini_model"), "gemini-2.5-flash", a)
        grid.add_widget(uikit.field("Gemini model", self.gem_model))
        self.news_key = uikit.text_input(settings.get("news_key"), "NewsAPI key", a, password=True)
        grid.add_widget(uikit.field("News API key (newsapi.org)", self.news_key))
        self.news_cc = uikit.text_input(settings.get("news_country"), "in", a)
        grid.add_widget(uikit.field("News country code (in, us, gb...)", self.news_cc))
        self.weather_key = uikit.text_input(settings.get("weather_key"), "OpenWeather key", a, password=True)
        grid.add_widget(uikit.field("Weather API key (openweathermap.org)", self.weather_key))
        self.omdb_key = uikit.text_input(settings.get("omdb_key"), "OMDb key", a, password=True)
        grid.add_widget(uikit.field("Movie API key (omdbapi.com)", self.omdb_key))
        self.email_in = uikit.text_input(settings.get("email"), "you@gmail.com", a)
        grid.add_widget(uikit.field("Your email (to send mails)", self.email_in))
        self.email_pw = uikit.text_input(settings.get("email_password"), "16-letter app password", a, password=True)
        grid.add_widget(uikit.field("Email APP password (not your normal password)", self.email_pw))

        scroll.add_widget(grid)
        root.add_widget(scroll)
        row = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(10))
        row.add_widget(uikit.button("Save", self._save, a))
        row.add_widget(uikit.button("Cancel", lambda *args: self.dismiss()))
        root.add_widget(row)
        self.add_widget(root)

        self.bind(on_dismiss=self._on_dismiss)
        self._reload_voices(wanted=settings.get("voice"))

    # ----------------------------------------------------------- helpers
    def _say(self, text):
        self.status.text = text

    def _lang_label(self, code):
        for label, c in self.langs.items():
            if c == code:
                return label
        label = f"Other ({code})"
        self.langs[label] = code
        return label

    # ------------------------------------------------------------- voices
    def _reload_voices(self, wanted=None):
        code = self.langs.get(self.lang_sp.text, "en-IN")
        current = wanted if wanted is not None else self.voice_map.get(self.voice_sp.text, "")
        self.voice_map = {label: name for name, label in speech.list_voices(code)}
        self.voice_sp.values = [DEFAULT_VOICE] + list(self.voice_map)
        self.voice_sp.text = next((lbl for lbl, n in self.voice_map.items() if n == current), DEFAULT_VOICE)

    def _overrides(self):
        return {"language": self.langs.get(self.lang_sp.text, "en-IN"),
                "voice": self.voice_map.get(self.voice_sp.text, ""),
                "speed": round(self.speed.value, 1), "pitch": round(self.pitch.value, 1)}

    def _test_voice(self, *args):
        name = self.name_in.text.strip() or "there"
        threading.Thread(target=speech.speak, daemon=True,
                         args=(f"Hello {name}. This is how I sound.", self._overrides())).start()

    # --------------------------------------------------------- voice packs
    def _load_pack(self, name):
        p = packs.get_voice_pack(name)
        if not p:
            return
        self.lang_sp.text = self._lang_label(p["language"])      # reloads the voice list
        self.lang_sp.values = list(self.langs)
        self._reload_voices(wanted=p["voice"])
        self.speed.value = p["speed"]
        self.pitch.value = p["pitch"]
        self.addr_in.text = p["address"]
        self.greet_in.text = p["greeting"]
        self._say(f"Voice pack loaded: {name}. Save dabao to keep it.")

    def _pack_values(self, name):
        v = self._overrides()
        v.update({"name": name, "address": self.addr_in.text.strip() or "sir",
                  "greeting": self.greet_in.text})
        return v

    def _save_pack(self, *args):
        current = self.pack_sp.text
        default = "My Voice" if packs.is_builtin_voice(current) else current
        uikit.prompt_text("Name this voice pack", default, self.accent, self._do_save_pack)

    def _do_save_pack(self, name):
        saved = packs.save_voice_pack(self._pack_values(name))
        self.pack_sp.values = packs.voice_pack_names()
        self.pack_sp.text = saved
        self._say(f"Voice pack saved: {saved}")

    def _delete_pack(self, *args):
        name = self.pack_sp.text
        if packs.is_builtin_voice(name):
            self._say("Built-in voice pack delete nahi ho sakta.")
            return
        packs.delete_voice_pack(name)
        self.pack_sp.values = packs.voice_pack_names()
        self.pack_sp.text = packs.voice_pack_names()[0]
        self._say(f"Deleted voice pack: {name}")

    def _export_pack(self, *args):
        name = self.pack_sp.text
        try:
            data = packs.export_voice_pack(name)
        except packs.PackError as e:
            self._say(str(e))
            return
        filepicker.save_as(f"{packs.slugify(name)}.voicepack.json", data, "application/json",
                           lambda ok, msg: self._say("Voice pack exported." if ok else msg))

    # ------------------------------------------------------- theme tools
    def _export_theme(self, *args):
        found = packs.find_custom_theme(self.theme_sp.text)
        if not found:
            self._say("Built-in theme export nahi hoti. Studio mein apni theme banao.")
            return
        data = packs.zip_theme_folder(found[1], found[0])
        filepicker.save_as(f"{packs.slugify(found[0]['name'])}.jarvistheme.zip", data, "application/zip",
                           lambda ok, msg: self._say("Theme exported." if ok else msg))

    def _import(self, *args):
        filepicker.pick("any", self._on_import, max_bytes=packs.MAX_ZIP_TOTAL)

    def _on_import(self, data, name, err):
        if err:
            self._say(err)
            return
        if not data:
            return
        kind = packs.sniff(data)
        if kind == "zip":
            uikit.run_bg(lambda: packs.install_theme_zip(data, themes.BUILTIN_NAMES), self._theme_imported)
        elif kind == "json":
            uikit.run_bg(lambda: packs.install_voice_json(data), self._voice_imported)
        else:
            self._say("Ye theme zip ya voice pack json nahi lagti.")

    def _theme_imported(self, name, err):
        if err:
            self._say(str(err) if isinstance(err, packs.PackError) else "Import fail ho gaya.")
            return
        self.theme_sp.values = themes.all_names()
        self.theme_sp.text = name                      # applies it live
        self._say(f"Theme imported: {name}. Save dabao to keep it.")

    def _voice_imported(self, name, err):
        if err:
            self._say(str(err) if isinstance(err, packs.PackError) else "Import fail ho gaya.")
            return
        self.pack_sp.values = packs.voice_pack_names()
        self.pack_sp.text = name
        self._say(f"Voice pack imported: {name}")

    def _open_studio(self, *args):
        self._save(close=False)
        self.dismiss()
        custom = packs.find_custom_theme(self.theme_sp.text)
        self.jarvis.open_studio(edit_name=self.theme_sp.text if custom else None)

    # --------------------------------------------------------- save / close
    def _save(self, *args, close=True):
        values = self._overrides()
        pack = self.pack_sp.text if self.pack_sp.text in packs.voice_pack_names() else ""
        values.update({
            "user_name": self.name_in.text.strip() or "Altamash",
            "theme": self.theme_sp.text,
            "voice_pack": pack,
            "address": self.addr_in.text.strip() or "sir",
            "greeting": self.greet_in.text,
            "speak_greeting": bool(self.greet_sw.active),
            "continuous": bool(self.cont_sw.active),
            "prefer_offline": bool(self.off_sw.active),
            "gemini_key": self.gem_key.text.strip(),
            "gemini_model": self.gem_model.text.strip() or "gemini-2.5-flash",
            "news_key": self.news_key.text.strip(),
            "news_country": re.sub(r"[^a-z]", "", self.news_cc.text.lower())[:2] or "in",
            "weather_key": self.weather_key.text.strip(),
            "omdb_key": self.omdb_key.text.strip(),
            "email": self.email_in.text.strip(),
            "email_password": self.email_pw.text.strip(),
        })
        settings.set_many(values)
        self.saved = True
        self.jarvis.on_settings_saved()
        if close:
            self.dismiss()

    def _on_dismiss(self, *args):
        if not self.saved:   # undo the live theme preview
            self.jarvis.apply_theme(settings.get("theme"))
