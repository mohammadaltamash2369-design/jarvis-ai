"""Theme Studio: build your own theme (photo, live animation, colours, graphics, fonts).
It is a panel on the lower half of the screen so you can watch the live preview above it."""
import os
import re

from kivy.graphics import Color, Rectangle
from kivy.metrics import dp, sp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView

import filepicker
import imagetools
import packs
import settings
import themes
import uikit

NEW_THEME = "+ New theme"
FIT_LABELS = {"Fill screen (crop edges)": "cover", "Fit whole picture": "contain", "Stretch": "fill"}
GFX_LABELS = {"Blue": "blue", "Red": "red", "Green": "green", "Purple": "purple", "Gold": "gold",
              "Cyan": "cyan", "Pink": "pink", "My own images": "custom"}
TEXT_PALETTE = ["ffffff", "fff4e0", "e6fbff", "d6ffe3", "ffe0f0", "ffe27a"]

# slot -> (label, picker kind, allowed file kinds, saved base name)
SLOTS = {
    "bg_photo":   ("Background photo", "image", ("jpg", "png"), "bg_photo"),
    "bg_live":    ("Live animation (GIF)", "image", ("gif", "png", "jpg"), "bg_live"),
    "core":       ("Centre animation / image", "image", ("gif", "png", "jpg"), "core"),
    "circle":     ("Ring image (spins)", "image", ("png", "gif", "jpg"), "circle"),
    "border":     ("Frame image", "image", ("png", "gif", "jpg"), "border"),
    "font_title": ("Title font", "any", ("ttf", "otf"), "font_title"),
    "font_text":  ("Text font", "any", ("ttf", "otf"), "font_text"),
}
MAX_GIF = 15 * 1024 * 1024


class StudioPanel(BoxLayout):
    def __init__(self, jarvis, edit_name=None, **kwargs):
        super().__init__(orientation="vertical", size_hint=(1, 0.54), pos_hint={"x": 0, "y": 0},
                         padding=dp(8), spacing=dp(6), **kwargs)
        self.jarvis = jarvis
        self.accent = themes.rgba(jarvis.accent)
        self._ready = False
        self.slot_labels = {}
        self.editing = edit_name if edit_name and packs.find_custom_theme(edit_name) else None
        self.draft_dir, self.draft = packs.new_draft(self.editing)

        with self.canvas.before:
            Color(0.02, 0.03, 0.08, 0.96)
            self._bg = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._sync_bg, size=self._sync_bg)

        self._build()
        self._load_widgets()
        self._ready = True
        self._changed()

    def _sync_bg(self, *args):
        self._bg.pos, self._bg.size = self.pos, self.size

    # ------------------------------------------------------------- layout
    def _build(self):
        a = self.accent
        top = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(8))
        top.add_widget(Label(text="[b]THEME STUDIO[/b]", markup=True, color=a, font_size=sp(17)))
        top.add_widget(uikit.button("Close", self._close, height=dp(40)))
        self.add_widget(top)
        self.status = uikit.status_label()
        self.status.height = dp(22)
        self.add_widget(self.status)

        scroll = ScrollView(do_scroll_x=False)
        g = GridLayout(cols=1, spacing=dp(8), size_hint_y=None, padding=[0, 0, dp(4), dp(10)])
        g.bind(minimum_height=g.setter("height"))

        g.add_widget(uikit.header("Theme", a))
        self.edit_sp = uikit.spinner(self.editing or NEW_THEME, [NEW_THEME] + packs.custom_theme_names())
        self.edit_sp.bind(text=self._switch_draft)
        g.add_widget(uikit.field("Edit which theme?", self.edit_sp))
        self.name_in = uikit.text_input("", "My Theme", a)
        self.name_in.bind(text=self._changed)
        g.add_widget(uikit.field("Theme name", self.name_in))

        g.add_widget(uikit.header("Background", a))
        self._slot_row(g, "bg_photo")
        self._slot_row(g, "bg_live")
        self.live_op_lbl, self.live_op = uikit.slider("Animation opacity", 1.0, 0.1, 1.0, 0.05, a, "{:.2f}")
        self.dim_lbl, self.dim = uikit.slider("Darken background", 0.3, 0.0, 0.9, 0.05, a, "{:.2f}")
        self.fit_sp = uikit.spinner(list(FIT_LABELS)[0], list(FIT_LABELS))
        for w in (self.live_op_lbl, self.live_op, self.dim_lbl, self.dim):
            g.add_widget(w)
        g.add_widget(uikit.field("Picture fit", self.fit_sp))

        g.add_widget(uikit.header("Colours", a))
        g.add_widget(uikit.caption("Main colour (buttons, clock, title)"))
        g.add_widget(uikit.palette(self._set_accent))
        self.accent_in = uikit.text_input("3d7bff", "hex like ff8800", a)
        g.add_widget(uikit.field("Main colour hex", self.accent_in, dp(72)))
        g.add_widget(uikit.button("Open colour picker", lambda *args: self._color_picker("accent")))
        g.add_widget(uikit.caption("Text colour"))
        g.add_widget(uikit.palette(self._set_text_color, TEXT_PALETTE))
        self.text_color_in = uikit.text_input("ffffff", "hex like ffffff", a)
        g.add_widget(uikit.field("Text colour hex", self.text_color_in, dp(72)))

        g.add_widget(uikit.header("Jarvis graphics", a))
        self.gfx_sp = uikit.spinner("Blue", list(GFX_LABELS))
        g.add_widget(uikit.field("Style", self.gfx_sp))
        for slot in ("core", "circle", "border"):
            self._slot_row(g, slot)
        self.core_sw = uikit.make_switch(True)
        self.border_sw = uikit.make_switch(True)
        self.spin_sw = uikit.make_switch(True)
        g.add_widget(uikit.switch_row("Show centre animation", self.core_sw))
        g.add_widget(uikit.switch_row("Show frame", self.border_sw))
        g.add_widget(uikit.switch_row("Spin the ring", self.spin_sw))
        self.circ_op_lbl, self.circ_op = uikit.slider("Ring opacity", 1.0, 0.1, 1.0, 0.05, a, "{:.2f}")
        g.add_widget(self.circ_op_lbl)
        g.add_widget(self.circ_op)

        g.add_widget(uikit.header("Layout", a))
        self.clock_sw = uikit.make_switch(True)
        self.title_sw = uikit.make_switch(True)
        g.add_widget(uikit.switch_row("Show clock", self.clock_sw))
        g.add_widget(uikit.switch_row("Show title", self.title_sw))
        self.title_in = uikit.text_input("J.A.R.V.I.S", "Title text", a)
        g.add_widget(uikit.field("Title text", self.title_in))
        self.scale_lbl, self.scale = uikit.slider("Ring size", 1.0, 0.5, 1.5, 0.05, a, "{:.2f}x")
        self.text_lbl, self.text_scale = uikit.slider("Text size", 1.0, 0.7, 1.6, 0.05, a, "{:.2f}x")
        self.speed_lbl, self.speed = uikit.slider("Animation speed", 1.0, 0.3, 3.0, 0.1, a)
        for w in (self.scale_lbl, self.scale, self.text_lbl, self.text_scale, self.speed_lbl, self.speed):
            g.add_widget(w)

        g.add_widget(uikit.header("Fonts (optional .ttf / .otf)", a))
        self._slot_row(g, "font_title")
        self._slot_row(g, "font_text")

        for w in (self.accent_in, self.text_color_in, self.title_in):
            w.bind(text=self._changed)
        for w in (self.live_op, self.dim, self.circ_op, self.scale, self.text_scale, self.speed):
            w.bind(value=self._changed)
        for w in (self.core_sw, self.border_sw, self.spin_sw, self.clock_sw, self.title_sw):
            w.bind(active=self._changed)
        for w in (self.fit_sp, self.gfx_sp):
            w.bind(text=self._changed)

        scroll.add_widget(g)
        self.add_widget(scroll)

        bottom = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(8))
        bottom.add_widget(uikit.button("Save theme", self._save, a))
        bottom.add_widget(uikit.button("Export zip", self._export))
        if self.editing:
            bottom.add_widget(uikit.button("Delete", self._delete))
        self.add_widget(bottom)

    def _slot_row(self, grid, slot):
        label, _, _, _ = SLOTS[slot]
        lbl = uikit.caption("")
        self.slot_labels[slot] = lbl
        row = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(8))
        row.add_widget(uikit.button(f"Pick: {label}", lambda *args, s=slot: self._pick(s), self.accent))
        row.add_widget(uikit.button("Remove", lambda *args, s=slot: self._remove(s), height=dp(46)))
        row.children[0].size_hint_x = 0.3
        grid.add_widget(lbl)
        grid.add_widget(row)

    # ---------------------------------------------------- widgets <-> draft
    def _load_widgets(self):
        d = self.draft
        was, self._ready = self._ready, False
        self.name_in.text = d["name"] if self.editing else ""
        self.accent_in.text = d["accent"]
        self.text_color_in.text = d["text_color"]
        self.live_op.value = d["bg_live_opacity"]
        self.dim.value = d["bg_dim"]
        self.fit_sp.text = next(k for k, v in FIT_LABELS.items() if v == d["bg_fit"])
        self.gfx_sp.text = next(k for k, v in GFX_LABELS.items() if v == d["graphics"])
        self.core_sw.active, self.border_sw.active = d["show_core"], d["show_border"]
        self.spin_sw.active = d["circle_spin"]
        self.circ_op.value = d["circle_opacity"]
        self.clock_sw.active, self.title_sw.active = d["show_clock"], d["show_title"]
        self.title_in.text = d["title_text"]
        self.scale.value, self.text_scale.value, self.speed.value = d["circle_scale"], d["text_scale"], d["anim_speed"]
        self._refresh_status()
        self._ready = was

    def _collect(self):
        d = self.draft
        d["name"] = self.name_in.text.strip() or "My Theme"
        if re.fullmatch(r"#?[0-9a-fA-F]{6}", self.accent_in.text.strip()):
            d["accent"] = self.accent_in.text.strip().lstrip("#").lower()
        if re.fullmatch(r"#?[0-9a-fA-F]{6}", self.text_color_in.text.strip()):
            d["text_color"] = self.text_color_in.text.strip().lstrip("#").lower()
        d["bg_live_opacity"] = round(self.live_op.value, 2)
        d["bg_dim"] = round(self.dim.value, 2)
        d["bg_fit"] = FIT_LABELS.get(self.fit_sp.text, "cover")
        d["graphics"] = GFX_LABELS.get(self.gfx_sp.text, "blue")
        d["show_core"], d["show_border"] = bool(self.core_sw.active), bool(self.border_sw.active)
        d["circle_spin"] = bool(self.spin_sw.active)
        d["circle_opacity"] = round(self.circ_op.value, 2)
        d["show_clock"], d["show_title"] = bool(self.clock_sw.active), bool(self.title_sw.active)
        d["title_text"] = self.title_in.text[:24]
        d["circle_scale"], d["text_scale"] = round(self.scale.value, 2), round(self.text_scale.value, 2)
        d["anim_speed"] = round(self.speed.value, 1)

    def _changed(self, *args):
        if not self._ready:
            return
        self._collect()
        try:
            self.jarvis.apply_resolved(themes.resolve_data(self.draft, self.draft_dir))
        except Exception as e:
            print(f"[studio] preview failed: {e}")
            self._say("Preview nahi ban saka, kuch setting galat hai.")

    def _refresh_status(self):
        for slot, lbl in self.slot_labels.items():
            lbl.text = f"{SLOTS[slot][0]}: {self.draft.get(slot) or 'none'}"

    def _say(self, text):
        self.status.text = text

    def _switch_draft(self, inst, value):
        if not self._ready:
            return
        self.editing = None if value == NEW_THEME else value
        self.draft_dir, self.draft = packs.new_draft(self.editing)
        self._ready = False
        self._load_widgets()
        self._ready = True
        self._changed()

    # -------------------------------------------------------------- colours
    def _set_accent(self, hex_color):
        self.accent_in.text = hex_color

    def _set_text_color(self, hex_color):
        self.text_color_in.text = hex_color

    def _color_picker(self, which):
        try:
            from kivy.uix.colorpicker import ColorPicker
        except Exception:
            self._say("Colour picker is device par nahi chal raha, hex ya palette use karo.")
            return
        start = self.accent_in.text if which == "accent" else self.text_color_in.text
        picker = ColorPicker(color=themes.rgba(start) if re.fullmatch(r"[0-9a-fA-F]{6}", start) else (1, 1, 1, 1))
        box = BoxLayout(orientation="vertical", spacing=dp(8))
        box.add_widget(picker)
        popup = Popup(title="Pick a colour", content=box, size_hint=(0.96, 0.85))

        def ok(*args):
            r, g, b = [int(round(c * 255)) for c in picker.color[:3]]
            hex_color = f"{r:02x}{g:02x}{b:02x}"
            if which == "accent":
                self._set_accent(hex_color)
            else:
                self._set_text_color(hex_color)
            popup.dismiss()

        row = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(8))
        row.add_widget(uikit.button("Use this colour", ok, self.accent))
        row.add_widget(uikit.button("Cancel", lambda *args: popup.dismiss()))
        box.add_widget(row)
        popup.open()

    # ------------------------------------------------------ picking files
    def _pick(self, slot):
        label, kind, _, _ = SLOTS[slot]
        limit = 10 * 1024 * 1024 if kind == "any" else 25 * 1024 * 1024
        self._say(f"{label}: file chuno...")
        filepicker.pick(kind, lambda data, name, err: self._picked(slot, data, err), limit)

    def _picked(self, slot, data, err):
        if err:
            self._say(err)
            return
        if not data:
            self._say("")
            return
        kind = packs.sniff(data)
        label, _, allowed, base = SLOTS[slot]
        if slot == "bg_photo" and kind == "gif":          # friendly: a GIF belongs in the animation slot
            slot, kind = "bg_live", "gif"
            label, _, allowed, base = SLOTS[slot]
            self._say("GIF mila, isse live animation mein laga raha hoon.")
        if kind not in allowed:
            self._say(f"{label} ke liye {'/'.join(allowed).upper()} file chuno.")
            return
        if kind == "gif" and len(data) > MAX_GIF:
            self._say("GIF 15 MB se chhoti chuno (phone slow ho jayega).")
            return
        folder = self.draft_dir

        def work():
            ext = kind
            payload = data
            if slot == "bg_photo":
                src = os.path.join(folder, "_incoming." + kind)
                dst = os.path.join(folder, "_resized.jpg")
                with open(src, "wb") as f:
                    f.write(data)
                if imagetools.prepare_photo(src, dst):
                    with open(dst, "rb") as f:
                        payload, ext = f.read(), "jpg"
                for tmp in (src, dst):
                    if os.path.exists(tmp):
                        os.remove(tmp)
            return packs.save_asset(folder, base, payload, ext)

        self._say("Processing...")
        uikit.run_bg(work, lambda fname, e: self._stored(slot, fname, e))

    def _stored(self, slot, fname, err):
        if err:
            print(f"[studio] {err}")
            self._say("File save nahi ho saki.")
            return
        if slot in ("font_title", "font_text") and not imagetools.font_ok(os.path.join(self.draft_dir, fname)):
            packs.remove_asset(self.draft_dir, fname)
            self._say("Ye font chal nahi raha, doosra chuno.")
            return
        self.draft[slot] = fname
        if slot in ("core", "circle", "border"):
            self.gfx_sp.text = "My own images"
        self._refresh_status()
        self._say("Added.")
        self._changed()

    def _remove(self, slot):
        packs.remove_asset(self.draft_dir, self.draft.get(slot))
        self.draft[slot] = ""
        self._refresh_status()
        self._changed()

    # -------------------------------------------------- save / close / etc.
    def _save(self, *args):
        self._collect()
        try:
            name = packs.save_theme(self.draft_dir, self.draft, themes.BUILTIN_NAMES, old_name=self.editing)
        except Exception as e:
            print(f"[studio] save failed: {e}")
            self._say("Theme save nahi ho saki.")
            return
        settings.set_many({"theme": name})
        packs.discard_draft()
        self.jarvis.close_studio()
        self.jarvis.apply_theme(name)
        self.jarvis.set_text(f"Theme saved: {name}")

    def _close(self, *args):
        packs.discard_draft()
        self.jarvis.close_studio()
        self.jarvis.apply_theme(settings.get("theme"))

    def _delete(self, *args):
        uikit.confirm("Delete theme", f"Delete '{self.editing}' for good?", self.accent, self._do_delete)

    def _do_delete(self):
        name = self.editing
        packs.delete_theme(name)
        if settings.get("theme") == name:
            settings.set_many({"theme": themes.DEFAULT_THEME})
        packs.discard_draft()
        self.jarvis.close_studio()
        self.jarvis.apply_theme(settings.get("theme"))
        self.jarvis.set_text(f"Deleted theme: {name}")

    def _export(self, *args):
        self._collect()
        data = packs.zip_theme_folder(self.draft_dir, self.draft)
        filepicker.save_as(f"{packs.slugify(self.draft['name'])}.jarvistheme.zip", data, "application/zip",
                           lambda ok, msg: self._say("Exported zip." if ok else msg))
