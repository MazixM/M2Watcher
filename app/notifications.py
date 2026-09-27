"""
Budowanie treści powiadomień Discord dla zdarzeń monitora.
"""
import logging
from typing import Optional

from config import Config, EVENT_LABELS
from discord_client import DiscordSender, Notification

log = logging.getLogger(__name__)

EVENT_STYLE = {
    "logout": ("🔴", 0xED4245),
    "closed": ("⚠️", 0xFAA61A),
    "reconnect": ("🟢", 0x3BA55D),
}


class NotificationManager:
    """Zamienia zdarzenia monitora na powiadomienia i wrzuca je do kolejki wysyłki."""

    def __init__(self, config: Config, sender: Optional[DiscordSender]):
        self.config = config
        self.sender = sender

    @property
    def device_name(self) -> str:
        return self.config.get("device_name", "") or "Nieznane urządzenie"

    def build(self, event: str, client_label: str, details: str = "") -> Notification:
        icon, color = EVENT_STYLE.get(event, ("ℹ️", 0x5865F2))
        label = EVENT_LABELS.get(event, event)
        device = self.device_name
        fields = [("🎮 Klient", client_label)]
        if details:
            fields.append(("ℹ️ Szczegóły", details))
        return Notification(
            event=event,
            title=f"{icon} {label} — {device}",
            description=f"**{label}** na urządzeniu **{device}**.",
            color=color,
            device=device,
            fields=fields,
        )

    def notify(self, event: str, client_label: str, details: str = "") -> None:
        if not self.sender:
            return
        if not self.config.get(f"discord.notify_events.{event}", True):
            log.debug("Powiadomienie %s wyłączone w ustawieniach", event)
            return
        try:
            self.sender.enqueue(self.build(event, client_label, details))
        except Exception:
            log.exception("Nie udało się dodać powiadomienia do kolejki")
