# Jarvis AI (online edition) - Android + desktop

Kivy voice assistant. Tap the circle and speak, or type a command.

## Make it yours (no rebuild needed)
* **Settings -> Open Studio**: build your own theme - background photo, live GIF animation,
  colours, your own centre/ring/frame images, fonts, clock/title, sizes, animation speed.
  The top half of the screen shows a live preview while you edit.
* **Voice packs**: voice + speed + pitch + language + how Jarvis addresses you + greeting.
  Save your own, they work with every theme. Export/import as a small .json file.
* **Import / export**: themes are `.jarvistheme.zip` files, voice packs are `.voicepack.json`.
  Try the files in `sample-packs/` (Settings -> Import theme zip / voice pack file).
* Build a theme on a PC: zip a `theme.json` + your images (see THEME_PACK_FORMAT below).

### THEME_PACK_FORMAT (theme.json, all keys optional)
```
{ "name": "My Theme", "accent": "ff8800", "text_color": "ffffff",
  "bg_photo": "photo.jpg", "bg_live": "rain.gif", "bg_live_opacity": 1.0,
  "bg_fit": "cover | contain | fill", "bg_dim": 0.3,
  "graphics": "blue|red|green|purple|gold|cyan|pink|custom",
  "core": "centre.gif", "circle": "ring.png", "border": "frame.png",
  "show_core": true, "show_border": true, "circle_opacity": 1.0, "circle_spin": true,
  "font_title": "title.ttf", "font_text": "text.ttf", "title_text": "J.A.R.V.I.S",
  "show_clock": true, "show_title": true,
  "circle_scale": 1.0, "text_scale": 1.0, "anim_speed": 1.0 }
```
Files go next to theme.json in the zip (png, jpg, gif, ttf, otf only; max 60 MB total).
Live animation = animated GIF (convert MP4 to GIF on any free site; keep it under 15 MB).

## Phone
Build the APK with the included GitHub workflow (`.github/workflows/build.yml`) or
`buildozer android debug` on Linux/WSL. Full Hinglish step-by-step guide: see the
"Jarvis AI - Phone Setup Guide" document shared in the chat.

PC test run: `pip install -r requirements-desktop.txt` then `python main.py`

Voice commands: time, date, open <app>, timer, notes, calculate, weather, news, ip address,
wikipedia, youtube, google, send email, movie, jokes, coin, dice - anything else goes to Gemini.
