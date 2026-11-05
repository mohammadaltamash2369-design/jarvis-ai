"""Small widget factories shared by the Settings and Studio screens."""
import threading

from kivy.clock import Clock
from kivy.metrics import dp, sp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.slider import Slider
from kivy.uix.spinner import Spinner
from kivy.uix.switch import Switch
from kivy.uix.textinput import TextInput

import themes

PANEL = (0.08, 0.10, 0.20, 1)
SOFT = (0.8, 0.85, 1, 1)
PALETTE = ["3d7bff", "ff3b3b", "32e05a", "a64dff", "ffb02e", "2ee6e6",
           "ff4dc4", "ffffff", "ff8800", "00ffa3", "ff6f91", "c0c0c0"]


def _left(label):
    label.bind(size=lambda w, s: setattr(w, "text_size", s))
    return label


def header(text, accent):
    return _left(Label(text=f"[b]{text.upper()}[/b]", markup=True, color=accent, font_size=sp(14),
                       size_hint_y=None, height=dp(34), halign="left", valign="bottom"))


def caption(text, height=dp(22)):
    return _left(Label(text=text, font_size=sp(13), color=SOFT, size_hint_y=None,
                       height=height, halign="left", valign="middle"))


def field(caption_text, widget, height=dp(72)):
    box = BoxLayout(orientation="vertical", size_hint_y=None, height=height, spacing=dp(2))
    box.add_widget(caption(caption_text))
    box.add_widget(widget)
    return box


def text_input(value, hint, accent, password=False):
    return TextInput(text=str(value or ""), hint_text=hint, multiline=False, password=password,
                     font_size=sp(15), background_normal="", background_active="",
                     background_color=PANEL, foreground_color=(1, 1, 1, 1),
                     hint_text_color=(0.5, 0.55, 0.7, 1), cursor_color=accent,
                     padding=[dp(10), dp(12)])


def spinner(text, values):
    return Spinner(text=text, values=values, font_size=sp(15), background_normal="",
                   background_color=PANEL, color=(1, 1, 1, 1))


def slider(name, value, lo, hi, step, accent, fmt="{:.1f}x"):
    lbl = caption(f"{name}: {fmt.format(float(value))}")
    sl = Slider(min=lo, max=hi, step=step, value=float(value), size_hint_y=None, height=dp(40),
                value_track=True, value_track_color=accent)
    sl.bind(value=lambda inst, v: setattr(lbl, "text", f"{name}: {fmt.format(v)}"))
    return lbl, sl


def switch_row(caption_text, switch):
    row = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(8))
    row.add_widget(_left(Label(text=caption_text, font_size=sp(14), halign="left", valign="middle")))
    row.add_widget(switch)
    return row


def make_switch(active):
    return Switch(active=bool(active), size_hint_x=None, width=dp(90))


def button(text, callback, accent=None, height=dp(46)):
    color = (accent[0], accent[1], accent[2], 0.55) if accent else PANEL
    b = Button(text=text, font_size=sp(15), background_normal="", background_color=color,
               color=(1, 1, 1, 1), size_hint_y=None, height=height)
    b.bind(on_release=callback)
    return b


def status_label():
    return _left(Label(text="", font_size=sp(13), color=(1, 0.85, 0.4, 1), size_hint_y=None,
                       height=dp(30), halign="left", valign="middle"))


def palette(on_pick, colors=PALETTE, cols=6):
    rows = -(-len(colors) // cols)
    grid = GridLayout(cols=cols, spacing=dp(6), size_hint_y=None, height=rows * dp(38) + (rows - 1) * dp(6))
    for c in colors:
        b = Button(background_normal="", background_color=themes.rgba(c))
        b.bind(on_release=lambda inst, c=c: on_pick(c))
        grid.add_widget(b)
    return grid


def run_bg(work, done):
    """Run work() in a thread; done(result, error) is called on the Kivy main thread."""
    def target():
        try:
            res, err = work(), None
        except Exception as e:
            res, err = None, e
        Clock.schedule_once(lambda dt: done(res, err))
    threading.Thread(target=target, daemon=True).start()


def prompt_text(title, default, accent, on_ok):
    box = BoxLayout(orientation="vertical", padding=dp(10), spacing=dp(10))
    entry = text_input(default, "Name", accent)
    entry.size_hint_y = None
    entry.height = dp(46)
    box.add_widget(entry)
    row = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(10))
    popup = Popup(title=title, content=box, size_hint=(0.92, None), height=dp(190), auto_dismiss=True)

    def ok(*_):
        popup.dismiss()
        if entry.text.strip():
            on_ok(entry.text.strip())

    row.add_widget(button("Save", ok, accent))
    row.add_widget(button("Cancel", lambda *_: popup.dismiss()))
    box.add_widget(row)
    popup.open()


def confirm(title, message, accent, on_yes):
    box = BoxLayout(orientation="vertical", padding=dp(10), spacing=dp(10))
    box.add_widget(Label(text=message, font_size=sp(15), halign="center"))
    row = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(10))
    popup = Popup(title=title, content=box, size_hint=(0.9, None), height=dp(200))
    row.add_widget(button("Yes", lambda *_: (popup.dismiss(), on_yes()), accent))
    row.add_widget(button("No", lambda *_: popup.dismiss()))
    box.add_widget(row)
    popup.open()
