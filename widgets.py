from kivy.graphics import Color, PopMatrix, PushMatrix, Rectangle, Rotate
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.image import Image
from kivy.uix.widget import Widget


class JarvisButton(ButtonBehavior, Image):
    """Tappable circle image that can keep spinning (angle = degrees per frame)."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.angle = 2
        with self.canvas.before:
            PushMatrix()
            self._rotation = Rotate(angle=0, origin=self.center)
        with self.canvas.after:
            PopMatrix()

    def rotate_button(self, *_):
        self._rotation.angle += self.angle
        self._rotation.origin = self.center


class Dim(Widget):
    """Black overlay with adjustable opacity (keeps text readable over photos)."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        with self.canvas:
            self._color = Color(0, 0, 0, 0)
            self._rect = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._update, size=self._update)

    def _update(self, *_):
        self._rect.pos = self.pos
        self._rect.size = self.size

    def set_alpha(self, alpha):
        self._color.a = float(alpha)
