"""
System powiadomień dla M2Watcher
Obsługuje powiadomienia Discord
"""
import requests
import json
from typing import Optional, Dict
from datetime import datetime
from config import Config

# Import bota Discord (opcjonalny)
try:
    from discord_bot import M2WatcherBot
    DISCORD_BOT_AVAILABLE = True
except ImportError:
    DISCORD_BOT_AVAILABLE = False
    M2WatcherBot = None


class NotificationManager:
    """Zarządza powiadomieniami"""
    
    def __init__(self, config: Config, discord_bot: Optional['M2WatcherBot'] = None):
        self.config = config
        self.discord_enabled = config.get("discord.enabled", False)
        self.discord_bot = discord_bot
    
    def send_discord_bot_message(self, message: str, title: str = "M2Watcher", 
                                 color: int = 0xff0000, user_id: Optional[str] = None) -> bool:
        """
        Wysyła wiadomość przez bota Discord do prywatnego kanału użytkownika.
        
        Args:
            message: Treść wiadomości
            title: Tytuł wiadomości
            color: Kolor embeda (hex)
            user_id: ID użytkownika Discord (opcjonalne)
            
        Returns:
            bool: Czy wysłano pomyślnie
        """
        if not self.discord_enabled or not self.discord_bot:
            return False
        
        try:
            # Jeśli podano user_id, użyj go, w przeciwnym razie użyj domyślnego z konfiguracji
            target_user_id = user_id or self.config.get("discord.user_id", "")
            
            if not target_user_id:
                return False
            
            # Wyślij wiadomość przez bota (użyj synchronicznej metody)
            return self.discord_bot.send_notification_sync(message, title, target_user_id, color)
        except Exception as e:
            print(f"Błąd wysyłania wiadomości przez bota Discord: {e}")
            return False
    
    def notify_logout(self, client_info: str, user_id: Optional[str] = None) -> None:
        """Wysyła powiadomienie o wylogowaniu"""
        message = f"⚠️ Wylogowanie wykryte: {client_info}"
        self._send_all_notifications(message, "Wylogowanie", 0xff0000, user_id)
    
    def notify_client_closed(self, client_info: str, user_id: Optional[str] = None) -> None:
        """Wysyła powiadomienie o zamknięciu klienta"""
        message = f"🔴 Klient zamknięty: {client_info}"
        self._send_all_notifications(message, "Klient zamknięty", 0xff0000, user_id)
    
    def notify_client_crashed(self, client_info: str, user_id: Optional[str] = None) -> None:
        """Wysyła powiadomienie o crashu klienta"""
        message = f"💥 Crash klienta: {client_info}"
        self._send_all_notifications(message, "Crash klienta", 0xff0000, user_id)
    
    def notify_reconnect(self, client_info: str, user_id: Optional[str] = None) -> None:
        """Wysyła powiadomienie o ponownym zalogowaniu"""
        message = f"✅ Ponowne zalogowanie: {client_info}"
        self._send_all_notifications(message, "Ponowne zalogowanie", 0x00ff00, user_id)
    
    def _send_all_notifications(self, message: str, title: str, color: int, user_id: Optional[str] = None) -> None:
        """Wysyła powiadomienia przez wszystkie włączone kanały"""
        # Discord bot
        if self.discord_enabled and self.discord_bot:
            bot_token = self.config.get("discord.bot_token", "")
            if bot_token:
                self.send_discord_bot_message(message, title, color, user_id)

