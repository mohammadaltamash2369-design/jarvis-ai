import os
import webbrowser

IS_ANDROID = "ANDROID_ARGUMENT" in os.environ or "ANDROID_PRIVATE" in os.environ
IS_MOBILE = IS_ANDROID
HERE = os.path.dirname(os.path.abspath(__file__))


def data_dir():
    """Writable folder (settings, notes)."""
    if IS_ANDROID and os.environ.get("ANDROID_PRIVATE"):
        return os.environ["ANDROID_PRIVATE"]
    return HERE


def asset(rel_path):
    """Absolute path of a bundled file, e.g. asset('static/mw.ttf')."""
    return os.path.join(HERE, *rel_path.split("/"))


def android_activity():
    from jnius import autoclass
    return autoclass("org.kivy.android.PythonActivity").mActivity


def open_url(url):
    """Open a web page / app link on phone or desktop."""
    if IS_ANDROID:
        from jnius import autoclass
        Intent = autoclass("android.content.Intent")
        Uri = autoclass("android.net.Uri")
        android_activity().startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url)))
    else:
        webbrowser.open(url)
