import config  # noqa: F401  (must be first: sets Kivy window options)

from kivy.app import App

import speech
from jarvis import Jarvis


class JarvisApp(App):
    title = "Jarvis AI"

    def build(self):
        speech.init()
        self.jarvis = Jarvis()
        self.jarvis.start_listening()
        return self.jarvis

    def on_start(self):
        from kivy.clock import Clock
        Clock.schedule_once(self.jarvis.startup, 1.5)

    def on_pause(self):
        return True  # keep running when the phone app goes to background

    def on_stop(self):
        self.jarvis.stop_listening()


if __name__ == "__main__":
    JarvisApp().run()
