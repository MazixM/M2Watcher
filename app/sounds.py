"""
Dźwięki powiadomień.

Wcześniej aplikacja używała ``winsound.Beep`` — to sygnał „głośniczka systemowego”, który na
nowszych Windowsach bywa wyciszony albo w ogóle nie działa (np. na laptopach bez sterownika
beep lub przy słuchawkach), a błędy były po cichu ignorowane.

Teraz odtwarzamy zwykłe pliki WAV przez ``winsound.PlaySound``:

* działa na każdym urządzeniu audio, na którym słychać inne programy,
* M2Watcher pojawia się jako osobna aplikacja w mikserze głośności Windows,
* każde zdarzenie ma własny dźwięk (wbudowany albo własny plik .wav) i jest wspólna
  regulacja głośności w ustawieniach aplikacji.
"""
import array
import importlib
import io
import logging
import math
import platform
import shutil
import struct
import subprocess
import sys
import threading
import wave
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from config import app_dir

log = logging.getLogger(__name__)

IS_WINDOWS = platform.system() == "Windows"
# winsound istnieje tylko na Windowsie; Any — żeby analiza typów na innych systemach nie krzyczała
winsound: Any = importlib.import_module("winsound") if IS_WINDOWS else None

SAMPLE_RATE = 22050

BUILTIN_SOUNDS = {
    "alarm": "Alarm (trzy sygnały)",
    "syrena": "Syrena",
    "dzwonek": "Dzwonek",
    "ping": "Krótki sygnał",
}
NONE_SOUND = "none"
CUSTOM_SOUND = "custom"


def sound_choices() -> Dict[str, str]:
    """Wartości do listy wyboru dźwięku w ustawieniach."""
    choices = {f"builtin:{k}": v for k, v in BUILTIN_SOUNDS.items()}
    choices[CUSTOM_SOUND] = "Własny plik .wav…"
    choices[NONE_SOUND] = "Bez dźwięku"
    return choices


# ------------------------------------------------------------ generowanie WAV
def _tone(freq: float, seconds: float, volume: float = 1.0, fade: float = 0.01,
          decay: float = 0.0, freq_end: Optional[float] = None) -> list:
    n = int(SAMPLE_RATE * seconds)
    fade_n = max(1, int(SAMPLE_RATE * fade))
    out = []
    phase = 0.0
    for i in range(n):
        f = freq if freq_end is None else freq + (freq_end - freq) * i / n
        phase += 2 * math.pi * f / SAMPLE_RATE
        env = min(1.0, i / fade_n, (n - i) / fade_n)
        if decay:
            env *= math.exp(-decay * i / SAMPLE_RATE)
        # lekka druga harmoniczna — brzmi mniej „piskliwie” niż czysty sinus
        sample = 0.8 * math.sin(phase) + 0.2 * math.sin(2 * phase)
        out.append(sample * env * volume)
    return out


def _silence(seconds: float) -> list:
    return [0.0] * int(SAMPLE_RATE * seconds)


def builtin_samples(name: str) -> list:
    if name == "alarm":
        beep = _tone(880, 0.18)
        gap = _silence(0.09)
        return beep + gap + beep + gap + beep + _silence(0.6)
    if name == "syrena":
        return _tone(600, 0.45, freq_end=1200) + _tone(1200, 0.45, freq_end=600) + _silence(0.25)
    if name == "dzwonek":
        a = _tone(1319, 0.5, decay=6, fade=0.005)
        b = _tone(988, 0.9, decay=4, fade=0.005)
        return a[: int(SAMPLE_RATE * 0.22)] + b + _silence(0.4)
    if name == "ping":
        return _tone(1046, 0.15) + _silence(0.2)
    raise KeyError(name)


def samples_to_wav(samples: list, volume: float) -> bytes:
    volume = max(0.0, min(1.0, volume))
    peak = 32767 * 0.9 * volume
    data = array.array("h", (int(max(-1.0, min(1.0, s)) * peak) for s in samples))
    if sys.byteorder == "big":
        data.byteswap()
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(data.tobytes())
    return buf.getvalue()


def scale_wav(raw: bytes, volume: float) -> bytes:
    """Zmienia głośność pliku WAV 16-bit PCM. Inne formaty zwraca bez zmian."""
    try:
        with wave.open(io.BytesIO(raw), "rb") as r:
            params = r.getparams()
            frames = r.readframes(params.nframes)
    except (wave.Error, EOFError, struct.error):
        return raw
    if params.sampwidth != 2:
        return raw
    data = array.array("h")
    data.frombytes(frames)
    if sys.byteorder == "big":
        data.byteswap()
    v = max(0.0, min(1.0, volume))
    for i, s in enumerate(data):
        data[i] = int(s * v)
    if sys.byteorder == "big":
        data.byteswap()
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setparams(params)
        w.writeframes(data.tobytes())
    return buf.getvalue()


def validate_wav(path: str) -> Optional[str]:
    """Zwraca opis problemu z plikiem albo None, gdy plik da się odtworzyć."""
    p = Path(path)
    if not p.is_file():
        return "Plik nie istnieje."
    if p.suffix.lower() != ".wav":
        return "Obsługiwane są tylko pliki .wav (MP3 przekonwertuj np. w Audacity)."
    try:
        with wave.open(str(p), "rb") as r:
            if r.getnframes() == 0:
                return "Plik WAV jest pusty."
    except (wave.Error, EOFError) as e:
        return f"To nie jest poprawny plik WAV ({e})."
    return None


# ------------------------------------------------------------ odtwarzanie
class SoundPlayer:
    """Odtwarza dźwięki zdarzeń. Metody nie blokują (dźwięk gra w tle)."""

    def __init__(self, get_settings: Callable[[], Dict],
                 on_alarm_change: Optional[Callable[[bool], None]] = None,
                 cache_dir: Optional[Path] = None):
        self.get_settings = get_settings
        self.on_alarm_change = on_alarm_change
        self.cache_dir = Path(cache_dir) if cache_dir else app_dir() / "sounds_cache"
        self._lock = threading.Lock()
        self._alarm_active = False
        self._alarm_timer: Optional[threading.Timer] = None
        self._proc: Optional[subprocess.Popen] = None
        self._loop_stop = threading.Event()

    @property
    def alarm_active(self) -> bool:
        return self._alarm_active

    # --- API
    def play_event(self, event: str) -> bool:
        settings = self.get_settings()
        if not settings.get("enabled", True):
            return False
        ev = settings.get("events", {}).get(event, {})
        spec, custom = ev.get("sound", NONE_SOUND), ev.get("file", "")
        if spec == NONE_SOUND:
            return False
        # Ponowne zalogowanie to dobra wiadomość — gra raz i nie przerywa trwającego alarmu
        alarm = event != "reconnect" and settings.get("repeat_until_ack", True)
        if not alarm and self._alarm_active:
            return False
        return self._play(spec, custom, settings.get("volume", 80), loop=alarm,
                          max_seconds=settings.get("max_alarm_seconds", 300))

    def preview(self, spec: str, custom_file: str, volume: int) -> bool:
        """Odsłuchanie dźwięku w ustawieniach (zawsze raz)."""
        if spec == NONE_SOUND:
            return False
        return self._play(spec, custom_file, volume, loop=False)

    def stop(self) -> None:
        with self._lock:
            self._stop_locked()
        self._set_alarm(False)

    # --- wnętrze
    def _set_alarm(self, value: bool) -> None:
        if self._alarm_active == value:
            return
        self._alarm_active = value
        if self.on_alarm_change:
            try:
                self.on_alarm_change(value)
            except Exception:
                log.exception("Błąd callbacku alarmu")

    def _stop_locked(self) -> None:
        if self._alarm_timer:
            self._alarm_timer.cancel()
            self._alarm_timer = None
        self._loop_stop.set()
        if IS_WINDOWS:
            try:
                winsound.PlaySound(None, 0)  # None = zatrzymaj bieżący dźwięk
            except Exception:
                log.debug("PlaySound purge nie powiódł się", exc_info=True)
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()
        self._proc = None

    def resolve_file(self, spec: str, custom_file: str, volume: int) -> Path:
        """Przygotowuje plik WAV z uwzględnioną głośnością i zwraca ścieżkę do niego."""
        vol = max(0, min(100, int(volume)))
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        if spec.startswith("builtin:"):
            name = spec.split(":", 1)[1]
            target = self.cache_dir / f"{name}_{vol}.wav"
            if not target.exists():
                target.write_bytes(samples_to_wav(builtin_samples(name), vol / 100))
            return target
        if spec == CUSTOM_SOUND:
            problem = validate_wav(custom_file)
            if problem:
                raise ValueError(f"{custom_file}: {problem}")
            if vol == 100:
                return Path(custom_file)
            target = self.cache_dir / f"custom_{vol}.wav"
            target.write_bytes(scale_wav(Path(custom_file).read_bytes(), vol / 100))
            return target
        raise ValueError(f"Nieznany dźwięk: {spec}")

    def _play(self, spec: str, custom_file: str, volume: int, loop: bool,
              max_seconds: float = 0) -> bool:
        try:
            with self._lock:
                self._stop_locked()
                path = self.resolve_file(spec, custom_file, volume)
                self._loop_stop = threading.Event()
                self._start_backend(path, loop)
                if loop and max_seconds:
                    self._alarm_timer = threading.Timer(max_seconds, self._auto_stop)
                    self._alarm_timer.daemon = True
                    self._alarm_timer.start()
        except Exception:
            log.exception("Nie udało się odtworzyć dźwięku %s", spec)
            self._fallback_beep()
            return False
        self._set_alarm(loop)
        return True

    def _auto_stop(self) -> None:
        log.info("Alarm wyciszony automatycznie po czasie z ustawień")
        self.stop()

    def _start_backend(self, path: Path, loop: bool) -> None:
        if IS_WINDOWS:
            flags = winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT
            if loop:
                flags |= winsound.SND_LOOP
            winsound.PlaySound(str(path), flags)
            return
        # Linux/macOS — tylko na potrzeby uruchamiania z kodu źródłowego
        player = next((p for p in ("paplay", "aplay", "afplay") if shutil.which(p)), None)
        if not player:
            raise RuntimeError("Brak odtwarzacza audio (paplay/aplay/afplay)")
        stop = self._loop_stop

        def run():
            while not stop.is_set():
                self._proc = subprocess.Popen([player, str(path)], stdout=subprocess.DEVNULL,
                                              stderr=subprocess.DEVNULL)
                self._proc.wait()
                if not loop:
                    break

        threading.Thread(target=run, name="SoundLoop", daemon=True).start()

    @staticmethod
    def _fallback_beep() -> None:
        if IS_WINDOWS:
            try:
                winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
            except Exception:
                log.debug("MessageBeep nie powiódł się", exc_info=True)
