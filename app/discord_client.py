"""
Wysyłanie powiadomień na Discord przez REST API.

Dlaczego nie ``discord.py``: gateway (WebSocket) bota po dłuższym braku internetu potrafił
się nie podnieść, a powiadomienie, którego nie udało się wysłać, przepadało. Tutaj:

* każde powiadomienie trafia najpierw do trwałej kolejki na dysku (``outbox.json``),
* osobny wątek wysyła je po kolei i przy błędzie sieci ponawia z rosnącym odstępem
  (5 s → 10 s → … → 60 s), aż internet wróci — także po restarcie aplikacji,
* opóźnione powiadomienie dostaje dopisek, o której zdarzenie faktycznie wykryto.

Obsługiwane są dwie metody:

* ``webhook`` — wklejasz jeden adres URL z ustawień kanału (najprostsze),
* ``bot`` — token bota + ID kanału albo ID użytkownika (wiadomość prywatna).
"""
import json
import logging
import os
import re
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

import requests

from config import app_dir

log = logging.getLogger(__name__)

API_BASE = "https://discord.com/api/v10"
USER_AGENT = "DiscordBot (https://github.com/MazixM/M2Watcher, 2.0)"
WEBHOOK_RE = re.compile(
    r"^https://(?:(?:ptb|canary)\.)?discord(?:app)?\.com/api/(?:v\d+/)?webhooks/\d+/[\w-]+/?$"
)
SNOWFLAKE_RE = re.compile(r"^\d{15,21}$")

MAX_QUEUE = 200
BACKOFF_STEPS = (5, 10, 20, 40, 60)
CONFIG_ERROR_RETRY = 60
DELAY_NOTE_AFTER = 60  # sekund — od tylu dopisujemy informację o opóźnieniu

STATE_DISABLED = "disabled"
STATE_OK = "ok"
STATE_SENDING = "sending"
STATE_OFFLINE = "offline"
STATE_CONFIG_ERROR = "config_error"


class RetryableError(Exception):
    """Błąd przejściowy (brak sieci, 5xx, limit) — spróbuj ponownie później."""

    def __init__(self, message: str, retry_after: Optional[float] = None):
        super().__init__(message)
        self.retry_after = retry_after


class ConfigError(Exception):
    """Błąd konfiguracji (zły token/URL, brak uprawnień) — trzeba poprawić ustawienia."""


class PayloadError(Exception):
    """Discord odrzucił treść wiadomości — ponawianie nic nie da."""


@dataclass
class Notification:
    event: str
    title: str
    description: str
    color: int
    device: str
    fields: List[Tuple[str, str]] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    attempts: int = 0

    @classmethod
    def from_dict(cls, data: Dict) -> "Notification":
        data = dict(data)
        data["fields"] = [tuple(f) for f in data.get("fields", [])]
        known = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        return cls(**known)


def validate_webhook_url(url: str) -> bool:
    return bool(WEBHOOK_RE.match((url or "").strip()))


def validate_snowflake(value: str) -> bool:
    return bool(SNOWFLAKE_RE.match((value or "").strip()))


def validate_settings(discord_cfg: Dict) -> List[str]:
    """Zwraca listę problemów z ustawieniami Discorda (pusta = OK)."""
    problems = []
    method = discord_cfg.get("method", "none")
    user_id = (discord_cfg.get("user_id") or "").strip()
    if user_id and not validate_snowflake(user_id):
        problems.append("ID użytkownika powinno składać się z 15–21 cyfr.")
    if method == "webhook":
        if not validate_webhook_url(discord_cfg.get("webhook_url", "")):
            problems.append(
                "Adres webhooka powinien wyglądać tak: https://discord.com/api/webhooks/123…/abc…"
            )
    elif method == "bot":
        if not (discord_cfg.get("bot_token") or "").strip():
            problems.append("Podaj token bota.")
        channel = (discord_cfg.get("channel_id") or "").strip()
        if channel and not validate_snowflake(channel):
            problems.append("ID kanału powinno składać się z 15–21 cyfr.")
        if not channel and not user_id:
            problems.append("Podaj ID kanału albo ID użytkownika (wtedy bot wyśle wiadomość prywatną).")
    return problems


# ---------------------------------------------------------------- kolejka
class Outbox:
    """Trwała kolejka FIFO zapisywana w pliku JSON."""

    def __init__(self, path: Optional[Path] = None):
        self.path = Path(path) if path else app_dir() / "outbox.json"
        self._lock = threading.Lock()
        self._items: List[Notification] = []
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            self._items = [Notification.from_dict(item) for item in raw]
            if self._items:
                log.info("Wczytano %d niewysłanych powiadomień z kolejki", len(self._items))
        except Exception:
            log.exception("Uszkodzona kolejka powiadomień %s — zaczynam od pustej", self.path)
            self._items = []

    def _save(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps([asdict(i) for i in self._items], ensure_ascii=False), encoding="utf-8")
            os.replace(tmp, self.path)
        except OSError:
            log.exception("Nie udało się zapisać kolejki powiadomień")

    def put(self, item: Notification) -> None:
        with self._lock:
            self._items.append(item)
            if len(self._items) > MAX_QUEUE:
                dropped = len(self._items) - MAX_QUEUE
                self._items = self._items[dropped:]
                log.warning("Kolejka pełna — usunięto %d najstarszych powiadomień", dropped)
            self._save()

    def peek(self) -> Optional[Notification]:
        with self._lock:
            return self._items[0] if self._items else None

    def remove(self, item_id: str) -> None:
        with self._lock:
            self._items = [i for i in self._items if i.id != item_id]
            self._save()

    def touch(self, item: Notification) -> None:
        """Zapisuje zmieniony licznik prób elementu (element jest współdzielony z kolejką)."""
        with self._lock:
            self._save()

    def clear(self) -> None:
        with self._lock:
            self._items = []
            self._save()

    def __len__(self) -> int:
        with self._lock:
            return len(self._items)


# ---------------------------------------------------------------- transport
def build_payload(item: Notification, discord_cfg: Dict, now: Optional[float] = None) -> Dict:
    now = time.time() if now is None else now
    detected = datetime.fromtimestamp(item.created_at)
    fields = [{"name": "🖥️ Urządzenie", "value": item.device or "?", "inline": True},
              {"name": "🕒 Wykryto", "value": detected.strftime("%H:%M:%S (%d.%m)"), "inline": True}]
    fields += [{"name": n, "value": v or "—", "inline": False} for n, v in item.fields]

    footer = "M2Watcher"
    delay = now - item.created_at
    if delay >= DELAY_NOTE_AFTER:
        minutes = int(delay // 60)
        footer = f"M2Watcher • wysłano z opóźnieniem {minutes} min (brak połączenia z Discordem)"

    embed = {
        "title": item.title[:256],
        "description": item.description[:4000],
        "color": item.color,
        "fields": fields[:25],
        "footer": {"text": footer},
        "timestamp": datetime.fromtimestamp(item.created_at, tz=timezone.utc).isoformat(),
    }
    payload: Dict = {"embeds": [embed], "allowed_mentions": {"parse": []}}
    user_id = (discord_cfg.get("user_id") or "").strip()
    if discord_cfg.get("mention_user", True) and validate_snowflake(user_id):
        payload["content"] = f"<@{user_id}>"
        payload["allowed_mentions"] = {"users": [user_id]}
    return payload


class DiscordTransport:
    """Pojedyncze wywołania HTTP do Discorda (bez ponawiania)."""

    def __init__(self, session: Optional[requests.Session] = None, timeout=(5, 15)):
        self.session = session or requests.Session()
        self.session.headers["User-Agent"] = USER_AGENT
        self.timeout = timeout
        self._dm_channels: Dict[Tuple[str, str], str] = {}

    def send(self, payload: Dict, discord_cfg: Dict) -> None:
        method = discord_cfg.get("method", "none")
        if method == "webhook":
            url = discord_cfg.get("webhook_url", "").strip().rstrip("/")
            body = dict(payload, username="M2Watcher")
            self._request("POST", url, params={"wait": "true"}, json=body)
        elif method == "bot":
            token = discord_cfg.get("bot_token", "").strip()
            channel_id = self._bot_channel(discord_cfg, token)
            self._request("POST", f"{API_BASE}/channels/{channel_id}/messages", json=payload, token=token)
        else:
            raise ConfigError("Powiadomienia Discord są wyłączone.")

    def _bot_channel(self, discord_cfg: Dict, token: str) -> str:
        channel_id = (discord_cfg.get("channel_id") or "").strip()
        if channel_id:
            return channel_id
        user_id = (discord_cfg.get("user_id") or "").strip()
        if not user_id:
            raise ConfigError("Brak ID kanału i ID użytkownika.")
        key = (token, user_id)
        if key not in self._dm_channels:
            data = self._request("POST", f"{API_BASE}/users/@me/channels",
                                 json={"recipient_id": user_id}, token=token)
            self._dm_channels[key] = str(data["id"])
        return self._dm_channels[key]

    def _request(self, method: str, url: str, token: str = "", **kwargs) -> Dict:
        headers = {"Authorization": f"Bot {token}"} if token else {}
        try:
            resp = self.session.request(method, url, headers=headers, timeout=self.timeout, **kwargs)
        except (requests.ConnectionError, requests.Timeout) as e:
            raise RetryableError(f"Brak połączenia z Discordem: {e.__class__.__name__}") from e
        except requests.RequestException as e:
            raise RetryableError(f"Błąd sieci: {e}") from e

        if resp.status_code == 429:
            retry_after = None
            try:
                retry_after = float(resp.json().get("retry_after"))
            except Exception:
                try:
                    retry_after = float(resp.headers.get("Retry-After", 5))
                except (TypeError, ValueError):
                    retry_after = 5.0
            raise RetryableError("Limit zapytań Discorda (429)", retry_after=retry_after)
        if resp.status_code >= 500:
            raise RetryableError(f"Discord chwilowo niedostępny (HTTP {resp.status_code})")
        code = None
        if resp.status_code >= 400:
            try:
                code = resp.json().get("code")
            except Exception:
                code = None
        if code == 40001:
            raise ConfigError("Ten bot nigdy nie połączył się z Discordem (wymóg Discorda dla nowych botów) — "
                              "użyj metody Webhook")
        if resp.status_code in (401, 403, 404):
            hint = {
                401: "nieprawidłowy token bota",
                403: "bot nie ma uprawnień do kanału lub nie może pisać do Ciebie prywatnie",
                404: "nie znaleziono webhooka/kanału — sprawdź adres lub ID",
            }[resp.status_code]
            raise ConfigError(f"HTTP {resp.status_code}: {hint}")
        if resp.status_code >= 400:
            raise PayloadError(f"HTTP {resp.status_code}: {resp.text[:300]}")
        if resp.status_code == 204 or not resp.content:
            return {}
        try:
            return resp.json()
        except ValueError:
            return {}


# ---------------------------------------------------------------- wysyłka w tle
@dataclass
class SenderStatus:
    state: str = STATE_DISABLED
    pending: int = 0
    last_error: str = ""
    last_success: Optional[float] = None
    next_retry_in: float = 0.0


class DiscordSender:
    """Wątek w tle opróżniający kolejkę. Nigdy nie blokuje monitora."""

    def __init__(self, get_settings: Callable[[], Dict], outbox: Optional[Outbox] = None,
                 transport: Optional[DiscordTransport] = None,
                 on_status: Optional[Callable[[SenderStatus], None]] = None):
        self.get_settings = get_settings
        self.outbox = outbox if outbox is not None else Outbox()
        self.transport = transport if transport is not None else DiscordTransport()
        self.on_status = on_status
        self.status = SenderStatus(pending=len(self.outbox))
        self._wake = threading.Event()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._failures = 0

    # --- API publiczne
    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="DiscordSender", daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 2.0) -> None:
        self._stop.set()
        self._wake.set()
        if self._thread:
            self._thread.join(timeout)

    def enqueue(self, item: Notification) -> None:
        if not self.enabled:
            return
        self.outbox.put(item)
        log.info("Powiadomienie w kolejce: %s (%s)", item.title, item.id[:8])
        self._publish(pending=len(self.outbox))
        self._wake.set()

    def settings_changed(self) -> None:
        """Wywołaj po zapisaniu ustawień — ponowi wysyłkę od razu."""
        self._failures = 0
        self._transport_reset()
        if not self.enabled:
            self._publish(state=STATE_DISABLED)
        self._wake.set()

    def retry_now(self) -> None:
        self._failures = 0
        self._wake.set()

    @property
    def enabled(self) -> bool:
        return self.get_settings().get("method", "none") in ("webhook", "bot")

    def send_test(self, device: str, settings: Optional[Dict] = None) -> Tuple[bool, str]:
        """Wysyła wiadomość testową od razu (synchronicznie). Do użycia z wątku GUI w tle."""
        cfg = settings if settings is not None else self.get_settings()
        problems = validate_settings(cfg)
        if cfg.get("method", "none") == "none":
            return False, "Wybierz sposób wysyłania (webhook albo bot)."
        if problems:
            return False, "\n".join(problems)
        item = Notification(
            event="test", title=f"✅ Test M2Watcher — {device}",
            description="Powiadomienia działają. Tak będą wyglądały alerty z tego komputera.",
            color=0x3BA55D, device=device,
        )
        try:
            DiscordTransport().send(build_payload(item, cfg), cfg)
        except RetryableError as e:
            return False, f"{e}\nSprawdź połączenie z internetem."
        except (ConfigError, PayloadError) as e:
            return False, str(e)
        except Exception as e:  # nieoczekiwane — do logu
            log.exception("Błąd wysyłania wiadomości testowej")
            return False, f"Nieoczekiwany błąd: {e}"
        log.info("Wiadomość testowa wysłana")
        return True, "Wiadomość testowa wysłana — sprawdź Discorda."

    # --- wnętrze
    def _transport_reset(self) -> None:
        self.transport._dm_channels.clear()

    def _publish(self, **changes) -> None:
        for k, v in changes.items():
            setattr(self.status, k, v)
        if self.on_status:
            try:
                self.on_status(SenderStatus(**asdict(self.status)))
            except Exception:
                log.exception("Błąd callbacku statusu Discorda")

    def _wait(self, seconds: float) -> None:
        self._wake.wait(seconds)
        self._wake.clear()

    def _run(self) -> None:
        log.info("Wątek wysyłki Discord uruchomiony")
        self._publish(state=STATE_OK if self.enabled else STATE_DISABLED, pending=len(self.outbox))
        while not self._stop.is_set():
            try:
                delay = self._step()
            except Exception:
                # Ten wątek nie może umrzeć — inaczej powiadomienia przestaną wychodzić
                log.exception("Nieoczekiwany błąd w wątku wysyłki Discord")
                delay = CONFIG_ERROR_RETRY
            if delay is None:
                self._wait(30)  # nic do roboty — śpij, aż przyjdzie coś nowego
            else:
                self._wait(delay)
        log.info("Wątek wysyłki Discord zatrzymany")

    def _step(self) -> Optional[float]:
        """Wysyła jedno powiadomienie. Zwraca czas oczekiwania albo None, gdy kolejka pusta."""
        settings = self.get_settings()
        if settings.get("method", "none") not in ("webhook", "bot"):
            self._publish(state=STATE_DISABLED, pending=len(self.outbox))
            return None
        item = self.outbox.peek()
        if item is None:
            if self.status.state in (STATE_SENDING, STATE_DISABLED):
                self._publish(state=STATE_OK, pending=0, next_retry_in=0)
            return None

        self._publish(state=STATE_SENDING, pending=len(self.outbox))
        item.attempts += 1
        try:
            self.transport.send(build_payload(item, settings), settings)
        except RetryableError as e:
            self._failures += 1
            delay = e.retry_after if e.retry_after is not None else \
                BACKOFF_STEPS[min(self._failures - 1, len(BACKOFF_STEPS) - 1)]
            if self._failures == 1 or self._failures % 10 == 0:
                log.warning("Nie wysłano powiadomienia (próba %d): %s — ponowię za %.0f s",
                            item.attempts, e, delay)
            self.outbox.touch(item)
            self._publish(state=STATE_OFFLINE, last_error=str(e), pending=len(self.outbox),
                          next_retry_in=delay)
            return delay
        except ConfigError as e:
            log.error("Błąd konfiguracji Discorda: %s", e)
            self._publish(state=STATE_CONFIG_ERROR, last_error=str(e), pending=len(self.outbox),
                          next_retry_in=CONFIG_ERROR_RETRY)
            return CONFIG_ERROR_RETRY
        except PayloadError as e:
            log.error("Discord odrzucił powiadomienie %s — usuwam z kolejki: %s", item.id[:8], e)
            self.outbox.remove(item.id)
            self._publish(last_error=str(e), pending=len(self.outbox))
            return 1

        if self._failures:
            log.info("Połączenie z Discordem przywrócone po %d nieudanych próbach", self._failures)
        self._failures = 0
        self.outbox.remove(item.id)
        log.info("Wysłano powiadomienie: %s (%s)", item.title, item.id[:8])
        self._publish(state=STATE_OK, last_error="", last_success=time.time(),
                      pending=len(self.outbox), next_retry_in=0)
        return 1.0 if len(self.outbox) else None
