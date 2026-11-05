"""Pick a file from the phone (Android system picker) / PC (file chooser), and save a file.
All callbacks run on the Kivy main thread.
    pick(kind, callback, max_bytes)   callback(data|None, name|None, error|None)
    save_as(filename, data, mime, callback)   callback(ok, message)
"""
import os
import threading

from kivy.clock import Clock

from platform_util import IS_ANDROID

_PICK, _SAVE = 7101, 7102
_pending = {"pick": None, "save": None, "max": 25 * 1024 * 1024, "data": b""}


def _main(fn):
    Clock.schedule_once(lambda dt: fn())


# ------------------------------------------------------------------- Android
if IS_ANDROID:
    from android import activity as _events  # type: ignore
    from jnius import autoclass  # type: ignore

    _act = autoclass("org.kivy.android.PythonActivity").mActivity
    _Intent = autoclass("android.content.Intent")

    def _display_name(uri):
        try:
            cursor = _act.getContentResolver().query(uri, None, None, None, None)
            if cursor is not None:
                try:
                    if cursor.moveToFirst():
                        idx = cursor.getColumnIndex("_display_name")
                        if idx >= 0:
                            return str(cursor.getString(idx))
                finally:
                    cursor.close()
        except Exception:
            pass
        return None

    def _read_uri(uri, cb, limit):
        try:
            name = _display_name(uri)
            pfd = _act.getContentResolver().openFileDescriptor(uri, "r")
            fd = pfd.detachFd()                       # hand the descriptor to Python
            with os.fdopen(fd, "rb") as f:
                data = f.read(limit + 1)
            if len(data) > limit:
                _main(lambda: cb(None, name, f"File bahut badi hai (limit {limit // (1024 * 1024)} MB)."))
            else:
                _main(lambda: cb(data, name, None))
        except Exception as e:
            print(f"[picker] {e}")
            _main(lambda: cb(None, None, "File padhi nahi ja saki."))

    def _write_uri(uri, data, cb):
        try:
            pfd = _act.getContentResolver().openFileDescriptor(uri, "wt")
            fd = pfd.detachFd()
            with os.fdopen(fd, "wb") as f:
                f.write(data)
            _main(lambda: cb(True, "Saved"))
        except Exception as e:
            print(f"[save] {e}")
            _main(lambda: cb(False, "Save nahi ho saka."))

    def _on_result(request_code, result_code, intent):
        if request_code == _PICK:
            cb, _pending["pick"] = _pending["pick"], None
            if cb is None:
                return
            if result_code != -1 or intent is None or intent.getData() is None:
                _main(lambda: cb(None, None, None))      # user cancelled
                return
            threading.Thread(target=_read_uri, args=(intent.getData(), cb, _pending["max"]), daemon=True).start()
        elif request_code == _SAVE:
            cb, _pending["save"] = _pending["save"], None
            if cb is None:
                return
            if result_code != -1 or intent is None or intent.getData() is None:
                _main(lambda: cb(False, "Cancelled"))
                return
            threading.Thread(target=_write_uri, args=(intent.getData(), _pending["data"], cb), daemon=True).start()

    _events.bind(on_activity_result=_on_result)

    def pick(kind, callback, max_bytes=25 * 1024 * 1024):
        _pending["pick"], _pending["max"] = callback, max_bytes
        intent = _Intent("android.intent.action.OPEN_DOCUMENT")
        intent.addCategory("android.intent.category.OPENABLE")
        intent.setType("image/*" if kind == "image" else "*/*")
        _act.startActivityForResult(intent, _PICK)

    def save_as(filename, data, mime, callback):
        _pending["save"], _pending["data"] = callback, data
        intent = _Intent("android.intent.action.CREATE_DOCUMENT")
        intent.addCategory("android.intent.category.OPENABLE")
        intent.setType(mime)
        intent.putExtra("android.intent.extra.TITLE", filename)
        _act.startActivityForResult(intent, _SAVE)

# ------------------------------------------------------------------- Desktop
else:
    def pick(kind, callback, max_bytes=25 * 1024 * 1024):
        from kivy.uix.boxlayout import BoxLayout
        from kivy.uix.button import Button
        from kivy.uix.filechooser import FileChooserListView
        from kivy.uix.popup import Popup

        filters = ["*.png", "*.jpg", "*.jpeg", "*.gif", "*.PNG", "*.JPG", "*.JPEG", "*.GIF"] if kind == "image" else []
        chooser = FileChooserListView(path=os.path.expanduser("~"), filters=filters)
        box = BoxLayout(orientation="vertical")
        box.add_widget(chooser)
        row = BoxLayout(size_hint_y=None, height=48)
        popup = Popup(title="Choose a file", content=box, size_hint=(0.95, 0.9))

        def done(*_):
            popup.dismiss()
            if not chooser.selection:
                callback(None, None, None)
                return
            path = chooser.selection[0]
            try:
                if os.path.getsize(path) > max_bytes:
                    callback(None, os.path.basename(path), f"File bahut badi hai (limit {max_bytes // (1024 * 1024)} MB).")
                    return
                with open(path, "rb") as f:
                    callback(f.read(), os.path.basename(path), None)
            except OSError:
                callback(None, None, "File padhi nahi ja saki.")

        ok = Button(text="Select")
        ok.bind(on_release=done)
        cancel = Button(text="Cancel")
        cancel.bind(on_release=lambda *_: (popup.dismiss(), callback(None, None, None)))
        row.add_widget(ok)
        row.add_widget(cancel)
        box.add_widget(row)
        popup.open()

    def save_as(filename, data, mime, callback):
        folder = os.path.join(os.path.expanduser("~"), "Downloads")
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, filename)
        try:
            with open(path, "wb") as f:
                f.write(data)
            callback(True, path)
        except OSError as e:
            callback(False, str(e))
