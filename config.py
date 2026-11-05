"""Import this BEFORE anything that touches kivy.core.window."""
import os

from kivy.config import Config

from platform_util import IS_MOBILE

if not IS_MOBILE:
    if os.environ.get("FULLSCREEN", "0") == "1":
        Config.set("graphics", "fullscreen", "auto")
    else:
        Config.set("graphics", "fullscreen", "0")
        Config.set("graphics", "width", "1280")
        Config.set("graphics", "height", "720")

TITLE_TEXT = "J.A.R.V.I.S"
