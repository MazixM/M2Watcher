"""
Spina wszystkie części aplikacji: konfigurację, monitor, dźwięki i wysyłkę na Discord.
GUI i tryb konsolowy korzystają z tego samego kontrolera.
"""
import logging
import queue
from typing import Dict

from app_logging import set_debug
from config import Config, EVENT_LABELS
from discord_client import DiscordSender, SenderStatus
from m2watcher import Metin2Watcher, WatchEvent
from notifications import NotificationManager
from sounds import SoundPlayer

log = logging.getLogger(__name__)


class AppController:
    """Wątki w tle wrzucają wiadomości do ``ui_queue``; interfejs je odbiera u siebie.

    Wiadomości: ("event", WatchEvent), ("discord", SenderStatus), ("alarm", bool)
    """

    def __init__(self, config: Config):
        self.config = config
        self.ui_queue: "queue.Queue[tuple]" = queue.Queue()
        self.sender = DiscordSender(
            lambda: self.config.get("discord", {}),
            on_status=lambda st: self.ui_queue.put(("discord", st)),
        )
        self.notifications = NotificationManager(config, self.sender)
        self.sounds = SoundPlayer(
            lambda: self.config.get("sounds", {}),
            on_alarm_change=lambda active: self.ui_queue.put(("alarm", active)),
        )
        self.watcher = Metin2Watcher(
            lambda: {
                "check_interval": self.config.get("check_interval", 2.0),
                "process_names": self.config.get("process_names", []),
                "logout_grace_seconds": self.config.get("logout_grace_seconds", 5.0),
            },
            on_event=self._on_event,
        )

    def start(self) -> None:
        self.sender.start()
        self.watcher.start()

    def shutdown(self) -> None:
        log.info("Zamykanie aplikacji")
        self.sounds.stop()
        self.watcher.stop()
        self.sender.stop()

    # --- zdarzenia monitora (wątek Watcher)
    def _on_event(self, event: WatchEvent) -> None:
        self.ui_queue.put(("event", event))
        if event.kind == "new":
            return
        self.notifications.notify(event.kind, event.client.label, event.details)
        self.sounds.play_event(event.kind)

    # --- akcje interfejsu
    def stop_alarm(self) -> None:
        self.sounds.stop()

    def apply_settings(self, data: Dict) -> None:
        self.config.replace(data)
        set_debug(bool(self.config.get("debug", False)))
        if self.config.get("discord.method", "none") == "none" and len(self.sender.outbox):
            log.info("Discord wyłączony — czyszczę %d niewysłanych powiadomień", len(self.sender.outbox))
            self.sender.outbox.clear()
        self.sender.settings_changed()
        log.info("Zapisano ustawienia (urządzenie: %s, Discord: %s)",
                 self.config.get("device_name"), self.config.get("discord.method"))

    def discord_status(self) -> SenderStatus:
        return self.sender.status

    @staticmethod
    def event_text(event: WatchEvent) -> str:
        if event.kind == "new":
            return f"Wykryto klienta: {event.client.label}"
        label = EVENT_LABELS.get(event.kind, event.kind)
        extra = f" — {event.details}" if event.details else ""
        return f"{label}: {event.client.label}{extra}"
