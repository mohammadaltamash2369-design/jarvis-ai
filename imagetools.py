"""Image/font helpers: GIF speed, photo downscale (+EXIF rotation), font validation."""
import os

from platform_util import IS_ANDROID

_font_cache = {}


def gif_frame_delay(path, default=0.1):
    """Seconds per frame stored in the GIF (so the animation plays at its real speed)."""
    try:
        with open(path, "rb") as f:
            head = f.read(65536)
        i = head.find(b"\x21\xf9\x04")
        if i >= 0 and i + 6 <= len(head):
            cs = head[i + 4] | (head[i + 5] << 8)
            if cs > 0:
                return max(0.02, cs / 100.0)
    except OSError:
        pass
    return default


def prepare_photo(src, dst, max_dim=2048):
    """Write a screen-sized, correctly rotated JPEG copy of a photo. True on success."""
    try:
        if IS_ANDROID:
            return _prepare_android(src, dst, max_dim)
        return _prepare_pil(src, dst, max_dim)
    except Exception as e:
        print(f"[photo] could not resize: {e}")
        return False


def _prepare_android(src, dst, max_dim):
    from jnius import autoclass
    BitmapFactory = autoclass("android.graphics.BitmapFactory")
    Options = autoclass("android.graphics.BitmapFactory$Options")
    Bitmap = autoclass("android.graphics.Bitmap")
    CompressFormat = autoclass("android.graphics.Bitmap$CompressFormat")
    Matrix = autoclass("android.graphics.Matrix")
    ExifInterface = autoclass("android.media.ExifInterface")
    FileOutputStream = autoclass("java.io.FileOutputStream")

    bounds = Options()
    bounds.inJustDecodeBounds = True
    BitmapFactory.decodeFile(src, bounds)
    w, h = int(bounds.outWidth), int(bounds.outHeight)
    if w <= 0 or h <= 0:
        return False
    sample = 1
    while max(w, h) / sample > max_dim * 2:
        sample *= 2
    opts = Options()
    opts.inSampleSize = sample
    bmp = BitmapFactory.decodeFile(src, opts)
    if bmp is None:
        return False
    try:
        orient = int(ExifInterface(src).getAttributeInt("Orientation", 1))
    except Exception:
        orient = 1
    deg = {6: 90, 3: 180, 8: 270}.get(orient, 0)
    scale = min(1.0, max_dim / float(max(bmp.getWidth(), bmp.getHeight())))
    if deg or scale < 1.0:
        m = Matrix()
        if scale < 1.0:
            m.postScale(scale, scale)
        if deg:
            m.postRotate(float(deg))
        bmp = Bitmap.createBitmap(bmp, 0, 0, bmp.getWidth(), bmp.getHeight(), m, True)
    out = FileOutputStream(dst)
    bmp.compress(CompressFormat.JPEG, 88, out)
    out.flush()
    out.close()
    return True


def _prepare_pil(src, dst, max_dim):
    from PIL import Image, ImageOps
    im = ImageOps.exif_transpose(Image.open(src)).convert("RGB")
    im.thumbnail((max_dim, max_dim))
    im.save(dst, "JPEG", quality=88)
    return True


def font_ok(path):
    """True if Kivy can really render text with this font file (cached)."""
    if not path:
        return False
    key = (path, os.path.getmtime(path) if os.path.exists(path) else 0)
    if key not in _font_cache:
        try:
            from kivy.core.text import Label as CoreLabel
            CoreLabel(text="Aa", font_name=path).refresh()
            _font_cache[key] = True
        except Exception as e:
            print(f"[font] {path}: {e}")
            _font_cache[key] = False
    return _font_cache[key]
