"""
Konfiguracja aplikacji M2Watcher.

Plik konfiguracyjny: ``%USERPROFILE%\\.m2watcher\\config.json``.
Katalog można nadpisać zmienną środowiskową ``M2WATCHER_HOME`` (przydatne w testach).
"""
import copy
import json
import logging
import os
import socket
import threading
from pathlib import Path
from typing import Any, Dict, Optional

log = logging.getLogger(__name__)

CONFIG_VERSION = 2


def app_dir() -> Path:
    """Katalog danych aplikacji (konfiguracja, logi, kolejka powiadomień)."""
    override = os.environ.get("M2WATCHER_HOME")
    return Path(override) if override else Path.home() / ".m2watcher"


CONFIG_DIR = app_dir()
CONFIG_FILE = CONFIG_DIR / "config.json"

# Zdarzenia, dla których można ustawić dźwięk i powiadomienie Discord
EVENTS = ("logout", "closed", "reconnect")
EVENT_LABELS = {
    "logout": "Wylogowanie",
    "closed": "Zamknięcie klienta",
    "reconnect": "Ponowne zalogowanie",
}


def default_device_name() -> str:
    try:
        return socket.gethostname() or "Mój komputer"
    except Exception:
        return "Mój komputer"


DEFAULT_CONFIG: Dict[str, Any] = {
    "config_version": CONFIG_VERSION,
    # False dopóki użytkownik nie przejdzie kreatora pierwszego uruchomienia
    "setup_completed": False,
    "device_name": "",
    # Nazwy plików klienta gry (serwery prywatne często mają własną nazwę .exe)
    "process_names": ["metin2client.exe"],
    "check_interval": 2.0,
    "logout_grace_seconds": 5.0,
    "debug": False,
    "start_minimized": False,
    "discord": {
        # "webhook" (zalecane), "bot" albo "none"
        "method": "none",
        "webhook_url": "",
        "bot_token": "",
        "channel_id": "",
        "user_id": "",
        "mention_user": True,
        "notify_events": {"logout": True, "closed": True, "reconnect": True},
    },
    "sounds": {
        "enabled": True,
        "volume": 80,
        # Powtarzaj dźwięk, dopóki użytkownik nie kliknie „Zatrzymaj alarm”
        "repeat_until_ack": True,
        # Po tylu sekundach alarm wycisza się sam (0 = nigdy)
        "max_alarm_seconds": 300,
        "events": {
            "logout": {"sound": "builtin:alarm", "file": ""},
            "closed": {"sound": "builtin:syrena", "file": ""},
            "reconnect": {"sound": "builtin:dzwonek", "file": ""},
        },
    },
    # Moduł optymalizacji wielu klientów (optimizer.py) — opcjonalny, domyślnie wyłączony
    "optimization": {
        "enabled": False,
        # Ustawienia dla wszystkich klientów; wybrane klienty mogą mieć własne (w oknie aplikacji)
        "default": {
            "fps_limit": 0,                   # 0 = bez limitu, 5–59 = limit FPS
            "fps_background_only": True,      # limit tylko dla klientów, których okno nie jest aktywne
            "cores_mode": "none",             # "none" | "list" | "spread"
            "cores": [],                      # pula rdzeni logicznych (pusta = wszystkie)
            "background_priority": "normal",  # "normal" | "below_normal" | "idle"
        },
    },
}


def deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """Zwraca kopię ``base`` z nadpisanymi wartościami z ``override`` (rekurencyjnie)."""
    result = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def migrate(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Przenosi ustawienia ze starego formatu (v1) do bieżącego."""
    data = copy.deepcopy(raw)
    if data.get("config_version", 1) >= CONFIG_VERSION:
        return data

    discord = data.get("discord", {}) or {}
    if "method" not in discord:
        token = str(discord.get("bot_token", "") or "")
        placeholder = token.startswith("YOUR_")
        if discord.get("enabled") and token and not placeholder:
            discord["method"] = "bot"
        else:
            discord["method"] = "none"
    for key in ("bot_token", "guild_id", "user_id", "channel_id"):
        if str(discord.get(key, "")).startswith("YOUR_"):
            discord[key] = ""
    discord.pop("enabled", None)
    discord.pop("guild_id", None)
    data["discord"] = discord

    sounds = data.get("sounds", {}) or {}
    if "sound_enabled" in data:
        sounds.setdefault("enabled", bool(data.pop("sound_enabled")))
    if "sound_wait_for_input" in data:
        sounds.setdefault("repeat_until_ack", bool(data.pop("sound_wait_for_input")))
    data["sounds"] = sounds
    # Te opcje nigdy realnie nie działały (liczniki I/O procesu nie zawierają ruchu sieciowego),
    # wykrywanie opiera się na liczbie połączeń TCP — patrz m2watcher.py
    for obsolete in ("show_status", "network_check_samples", "network_threshold"):
        data.pop(obsolete, None)

    # Stara konfiguracja istniała, więc użytkownik już coś ustawiał —
    # mimo to pokazujemy kreator, żeby uzupełnił nazwę urządzenia.
    data["setup_completed"] = False
    data["config_version"] = CONFIG_VERSION
    return data


class Config:
    """Konfiguracja z zapisem do pliku JSON. Bezpieczna dla wielu wątków."""

    def __init__(self, path: Optional[Path] = None):
        self.path = Path(path) if path else app_dir() / "config.json"
        self._lock = threading.RLock()
        self._config: Dict[str, Any] = copy.deepcopy(DEFAULT_CONFIG)
        self.load_error: str = ""
        self._load()

    # ------------------------------------------------------------------ I/O
    def _load(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._config["device_name"] = default_device_name()
            return  # zapis dopiero po kreatorze

        try:
            with open(self.path, "r", encoding="utf-8-sig") as f:
                loaded = json.load(f)
            if not isinstance(loaded, dict):
                raise ValueError("plik konfiguracyjny nie zawiera obiektu JSON")
        except Exception as e:
            # Uszkodzony plik: zachowaj kopię i zacznij od domyślnych ustawień
            self.load_error = f"Nie udało się wczytać konfiguracji ({e}). Utworzono kopię zapasową."
            log.exception("Błąd wczytywania konfiguracji %s", self.path)
            try:
                backup = self.path.with_suffix(".broken.json")
                self.path.replace(backup)
            except OSError:
                log.exception("Nie udało się zrobić kopii uszkodzonej konfiguracji")
            self._config["device_name"] = default_device_name()
            return

        migrated = migrate(loaded)
        self._config = deep_merge(DEFAULT_CONFIG, migrated)
        if not self._config.get("device_name"):
            self._config["device_name"] = default_device_name()
        if migrated != loaded:
            log.info("Zmigrowano konfigurację do wersji %s", CONFIG_VERSION)
            self.save()

    def save(self) -> None:
        """Zapisuje atomowo (plik tymczasowy + rename), żeby nie uszkodzić konfiguracji."""
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self._config, f, indent=2, ensure_ascii=False)
            os.replace(tmp, self.path)

    # Zgodność ze starszym API
    save_config = save

    # ------------------------------------------------------------- dostęp
    @property
    def is_first_run(self) -> bool:
        return not self.get("setup_completed", False)

    def as_dict(self) -> Dict[str, Any]:
        with self._lock:
            return copy.deepcopy(self._config)

    def replace(self, data: Dict[str, Any]) -> None:
        """Podmienia całą konfigurację (np. po zapisaniu okna ustawień) i zapisuje."""
        with self._lock:
            self._config = deep_merge(DEFAULT_CONFIG, data)
            self.save()

    def get(self, key: str, default: Any = None) -> Any:
        with self._lock:
            value: Any = self._config
            for k in key.split("."):
                if isinstance(value, dict) and k in value:
                    value = value[k]
                else:
                    return default
            return copy.deepcopy(value)

    def set(self, key: str, value: Any, save: bool = True) -> None:
        with self._lock:
            keys = key.split(".")
            node = self._config
            for k in keys[:-1]:
                node = node.setdefault(k, {})
            node[keys[-1]] = value
            if save:
                self.save()
