"""Speech in/out.
Android : system SpeechRecognizer + system TextToSpeech (voices, speed, pitch)
Desktop : SpeechRecognition (Google) + pyttsx3
API     : init(), listen(), speak(text, overrides=None), list_voices(lang), open_voice_settings()
"""
import threading
import time

import settings
from platform_util import IS_ANDROID
from textutil import words_to_digits

_volume_cb = None


def set_volume_callback(fn):
    global _volume_cb
    _volume_cb = fn


def _cfg(key, ov=None):
    return (ov or {}).get(key, settings.get(key))


# ================================================================ ANDROID
if IS_ANDROID:
    from android.runnable import run_on_ui_thread  # type: ignore
    from jnius import PythonJavaClass, autoclass, java_method  # type: ignore

    _activity = autoclass("org.kivy.android.PythonActivity").mActivity
    _Intent = autoclass("android.content.Intent")
    _RecognizerIntent = autoclass("android.speech.RecognizerIntent")
    _SpeechRecognizer = autoclass("android.speech.SpeechRecognizer")
    _TextToSpeech = autoclass("android.speech.tts.TextToSpeech")
    _Locale = autoclass("java.util.Locale")

    _ERRORS = {
        1: "Network timeout - check your internet", 2: "No internet connection",
        3: "Audio error", 4: "Speech service error", 5: "Speech client error",
        6: "I didn't hear anything", 7: "I couldn't understand that",
        8: "Speech service is busy, try again", 9: "Microphone permission is missing",
    }
    _QUIET = (6, 7)   # not real errors, just "nothing recognised"

    class _Listener(PythonJavaClass):
        __javainterfaces__ = ["android/speech/RecognitionListener"]
        __javacontext__ = "app"

        def __init__(self, owner):
            super().__init__()
            self.owner = owner

        @java_method("(Landroid/os/Bundle;)V")
        def onReadyForSpeech(self, params):
            pass

        @java_method("()V")
        def onBeginningOfSpeech(self):
            pass

        @java_method("(F)V")
        def onRmsChanged(self, rms):
            if _volume_cb:
                _volume_cb(max(0.0, float(rms)) * 12)

        @java_method("([B)V")
        def onBufferReceived(self, buf):
            pass

        @java_method("()V")
        def onEndOfSpeech(self):
            pass

        @java_method("(I)V")
        def onError(self, error):
            self.owner._err_code = int(error)
            self.owner._done.set()

        @java_method("(Landroid/os/Bundle;)V")
        def onResults(self, results):
            try:
                matches = results.getStringArrayList(_SpeechRecognizer.RESULTS_RECOGNITION)
                if matches is not None and matches.size() > 0:
                    self.owner._text = str(matches.get(0)).lower()
            except Exception as e:
                print(f"[stt] result error: {e}")
            self.owner._done.set()

        @java_method("(Landroid/os/Bundle;)V")
        def onPartialResults(self, partial):
            pass

        @java_method("(ILandroid/os/Bundle;)V")
        def onEvent(self, event_type, params):
            pass

    class _TtsInit(PythonJavaClass):
        __javainterfaces__ = ["android/speech/tts/TextToSpeech$OnInitListener"]
        __javacontext__ = "app"

        def __init__(self, ready):
            super().__init__()
            self.ready = ready

        @java_method("(I)V")
        def onInit(self, status):
            self.ready.set()

    class _AndroidSpeech:
        def __init__(self):
            self._done = threading.Event()
            self._text = None
            self._err_code = None
            self._rec = None
            self._listener = _Listener(self)
            self._tts_ready = threading.Event()
            self._tts_init = _TtsInit(self._tts_ready)
            self._tts = None
            self._voice_objs = None

        def init(self):
            try:
                from android.permissions import Permission, request_permissions  # type: ignore
                request_permissions([Permission.RECORD_AUDIO])
            except Exception as e:
                print(f"[perm] {e}")
            self._create_tts()

        @run_on_ui_thread
        def _create_tts(self):
            try:
                self._tts = _TextToSpeech(_activity, self._tts_init)
            except Exception as e:
                print(f"[tts] create failed: {e}")

        # ------------------------------------------------------- listening
        @run_on_ui_thread
        def _start(self):
            try:
                self._rec = _SpeechRecognizer.createSpeechRecognizer(_activity)
                self._rec.setRecognitionListener(self._listener)
                intent = _Intent(_RecognizerIntent.ACTION_RECOGNIZE_SPEECH)
                intent.putExtra(_RecognizerIntent.EXTRA_LANGUAGE_MODEL,
                                _RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
                intent.putExtra(_RecognizerIntent.EXTRA_LANGUAGE, str(settings.get("language")))
                if settings.get("prefer_offline"):
                    intent.putExtra(_RecognizerIntent.EXTRA_PREFER_OFFLINE, True)
                self._rec.startListening(intent)
            except Exception as e:
                print(f"[stt] start failed: {e}")
                self._err_code = 5
                self._done.set()

        @run_on_ui_thread
        def _destroy(self):
            try:
                if self._rec is not None:
                    self._rec.destroy()
            except Exception:
                pass
            self._rec = None

        def listen(self, timeout=15):
            self._done.clear()
            self._text, self._err_code = None, None
            self._start()
            if not self._done.wait(timeout):
                self._err_code = 6
            self._destroy()
            if self._text:
                return words_to_digits(self._text)
            if self._err_code is not None and self._err_code not in _QUIET:
                raise RuntimeError(_ERRORS.get(self._err_code, f"Speech error {self._err_code}"))
            return None

        # -------------------------------------------------------- speaking
        def _ensure_voices(self):
            if self._voice_objs:
                return self._voice_objs
            objs = {}
            try:
                voices = self._tts.getVoices()
                if voices is not None:
                    it = voices.iterator()
                    while it.hasNext():
                        v = it.next()
                        objs[str(v.getName())] = v
            except Exception as e:
                print(f"[tts] voices: {e}")
            self._voice_objs = objs or None
            return objs

        def list_voices(self, lang=None):
            """[(voice_name, label), ...] filtered by language prefix when possible."""
            if not self._tts_ready.wait(3) or self._tts is None:
                return []
            rows = []
            for name, v in self._ensure_voices().items():
                try:
                    loc = str(v.getLocale().toString())
                    net = bool(v.isNetworkConnectionRequired())
                except Exception:
                    loc, net = "?", False
                rows.append((loc, name, net))
            if lang:
                want = lang.replace("-", "_").split("_")[0].lower()
                same = [r for r in rows if r[0].lower().startswith(want)]
                rows = same or rows
            rows.sort()
            return [(name, f"{loc} - {name}{' (online)' if net else ''}") for loc, name, net in rows]

        def speak(self, text, overrides=None):
            if not text or not self._tts_ready.wait(5) or self._tts is None:
                return
            try:
                self._tts.setSpeechRate(float(_cfg("speed", overrides)))
                self._tts.setPitch(float(_cfg("pitch", overrides)))
                voice = _cfg("voice", overrides)
                obj = self._ensure_voices().get(voice) if voice else None
                if obj is not None:
                    self._tts.setVoice(obj)
                else:
                    self._tts.setLanguage(_Locale.forLanguageTag(str(_cfg("language", overrides))))
                self._tts.speak(text, _TextToSpeech.QUEUE_FLUSH, None, "jarvis")
                time.sleep(0.4)
                while self._tts.isSpeaking():
                    time.sleep(0.1)
            except Exception as e:
                print(f"[tts] speak failed: {e}")

        def open_voice_settings(self):
            for action in ("com.android.settings.TTS_SETTINGS",
                           "android.speech.tts.engine.INSTALL_TTS_DATA",
                           "android.settings.SETTINGS"):
                try:
                    _activity.startActivity(_Intent(action))
                    return True
                except Exception:
                    continue
            return False

    _impl = _AndroidSpeech()

# ================================================================= DESKTOP
else:
    class _DesktopSpeech:
        def init(self):
            pass

        def listen(self, timeout=8, phrase_limit=15):
            import speech_recognition as sr
            r = sr.Recognizer()
            try:
                with sr.Microphone() as source:
                    r.adjust_for_ambient_noise(source, duration=0.4)
                    audio = r.listen(source, timeout=timeout, phrase_time_limit=phrase_limit)
            except sr.WaitTimeoutError:
                return None
            try:
                text = r.recognize_google(audio, language=str(settings.get("language")))
            except sr.UnknownValueError:
                return None
            except sr.RequestError as e:
                raise RuntimeError(f"Speech service error: {e}")
            return words_to_digits(text.lower())

        def list_voices(self, lang=None):
            try:
                import pyttsx3
                return [(v.id, v.name) for v in pyttsx3.init().getProperty("voices")]
            except Exception as e:
                print(f"[tts] voices: {e}")
                return []

        def speak(self, text, overrides=None):
            if not text:
                return
            try:
                import pyttsx3
                engine = pyttsx3.init()
                engine.setProperty("rate", int(190 * float(_cfg("speed", overrides))))
                voice = _cfg("voice", overrides)
                if voice:
                    engine.setProperty("voice", voice)
                engine.say(text)
                engine.runAndWait()
            except Exception as e:
                print(f"[tts] {e}")

        def open_voice_settings(self):
            return False

    _impl = _DesktopSpeech()


def init():
    _impl.init()


def listen():
    return _impl.listen()


def speak(text, overrides=None):
    _impl.speak(text, overrides)


def list_voices(lang=None):
    return _impl.list_voices(lang)


def open_voice_settings():
    return _impl.open_voice_settings()
