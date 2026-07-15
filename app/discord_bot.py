"""
Bot Discord dla M2Watcher
Obsługuje powiadomienia na własnym serwerze użytkownika
"""
import discord
from discord.ext import commands
from typing import Optional, Deque, List
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
import asyncio
import threading
from config import Config


@dataclass
class PendingNotification:
    """Zaległe powiadomienie oczekujące na wysyłkę"""
    message: str
    title: str
    user_id: Optional[str]
    color: int
    created_at: float


class M2WatcherBot:
    """Bot Discord dla M2Watcher"""
    
    MAX_PENDING = 50
    RETRY_INTERVAL_SECONDS = 30
    
    def __init__(self, config: Config):
        self.config = config
        self.bot_token = config.get("discord.bot_token", "")
        self.guild_id = config.get("discord.guild_id", "")
        self.user_id = config.get("discord.user_id", "")
        self.channel_id = config.get("discord.channel_id", "")
        self._loop = None
        self._bot_ready = False
        self._pending: Deque[PendingNotification] = deque()
        self._pending_lock = threading.Lock()
        self._retry_started = False
        
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        
        self.bot = commands.Bot(command_prefix='!', intents=intents)
        self.setup_commands()
    
    def _enqueue_pending(self, message: str, title: str, user_id: Optional[str],
                         color: int, created_at: Optional[float] = None) -> None:
        """Dodaje powiadomienie do kolejki zaległych"""
        item = PendingNotification(
            message=message,
            title=title,
            user_id=user_id,
            color=color,
            created_at=created_at if created_at is not None else datetime.now(timezone.utc).timestamp()
        )
        with self._pending_lock:
            if len(self._pending) >= self.MAX_PENDING:
                self._pending.popleft()
                print("Kolejka zaległych powiadomień Discord pełna — usunięto najstarsze")
            self._pending.append(item)
            count = len(self._pending)
        print(f"Powiadomienie Discord dodane do kolejki oczekujących (łącznie: {count})")
    
    def _pop_pending_batch(self) -> List[PendingNotification]:
        """Pobiera wszystkie zaległe powiadomienia z kolejki"""
        with self._pending_lock:
            items = list(self._pending)
            self._pending.clear()
            return items
    
    def _requeue_front(self, items: List[PendingNotification]) -> None:
        """Wstawia niewysłane powiadomienia z powrotem na początek kolejki"""
        if not items:
            return
        with self._pending_lock:
            for item in reversed(items):
                self._pending.appendleft(item)
                while len(self._pending) > self.MAX_PENDING:
                    self._pending.pop()
    
    def pending_count(self) -> int:
        """Zwraca liczbę zaległych powiadomień"""
        with self._pending_lock:
            return len(self._pending)
    
    def setup_commands(self) -> None:
        """Konfiguruje komendy bota"""
        
        @self.bot.event
        async def on_ready():
            print(f'Bot Discord zalogowany jako {self.bot.user}')
            self._loop = asyncio.get_event_loop()
            self._bot_ready = True
            
            # Wyślij zaległe powiadomienia po (ponownym) połączeniu
            await self._flush_pending()
            
            if not self._retry_started:
                self._retry_started = True
                self.bot.loop.create_task(self._pending_retry_loop())
        
        @self.bot.event
        async def on_resumed():
            # Po wznowieniu sesji Discord spróbuj wysłać zaległe
            await self._flush_pending()
    
    async def _resolve_channel(self, user_id: Optional[str] = None):
        """Znajduje kanał docelowy dla powiadomienia"""
        channel = None
        target_user_id = user_id or self.user_id
        
        if self.channel_id:
            channel = self.bot.get_channel(int(self.channel_id))
        
        if not channel and target_user_id:
            user = self.bot.get_user(int(target_user_id))
            if user:
                channel = await user.create_dm()
        
        if not channel and self.guild_id:
            guild = self.bot.get_guild(int(self.guild_id))
            if guild:
                for ch in guild.text_channels:
                    if ch.permissions_for(guild.me).send_messages:
                        channel = ch
                        break
        
        return channel, target_user_id
    
    async def _send_to_channel(self, message: str, title: str,
                               user_id: Optional[str] = None, color: int = 0xff0000,
                               created_at: Optional[float] = None) -> Optional[bool]:
        """
        Wysyła powiadomienie do kanału Discord (bez kolejkowania przy błędzie).
        
        Returns:
            True — wysłano pomyślnie
            False — błąd sieci/wysyłki (warto ponowić)
            None — brak kanału / błąd konfiguracji (nie kolejkuj)
        """
        if not self.bot_token:
            return None
        
        try:
            channel, target_user_id = await self._resolve_channel(user_id)
            
            if not channel:
                return None
            
            if created_at is not None:
                embed_timestamp = datetime.fromtimestamp(created_at, tz=timezone.utc)
            else:
                embed_timestamp = discord.utils.utcnow()
            
            embed = discord.Embed(
                title=title,
                description=message,
                color=discord.Color(color),
                timestamp=embed_timestamp
            )
            embed.set_footer(text="M2Watcher")
            
            content = f"<@{target_user_id}>" if target_user_id else None
            await channel.send(content=content, embed=embed)
            return True
        except Exception as e:
            print(f"Błąd wysyłania powiadomienia Discord: {e}")
            return False
    
    async def _flush_pending(self) -> int:
        """
        Próbuje wysłać wszystkie zaległe powiadomienia.
        
        Returns:
            int: Liczba pomyślnie wysłanych powiadomień
        """
        items = self._pop_pending_batch()
        if not items:
            return 0
        
        print(f"Wysyłanie {len(items)} zaległych powiadomień Discord...")
        sent = 0
        remaining: List[PendingNotification] = []
        
        for i, item in enumerate(items):
            result = await self._send_to_channel(
                item.message, item.title, item.user_id, item.color, item.created_at
            )
            if result is True:
                sent += 1
            elif result is False:
                # Błąd sieci — odłóż bieżące i resztę, zachowaj kolejność
                remaining = items[i:]
                break
            # result is None (brak kanału) — pomiń, nie ma sensu ponawiać
        
        if remaining:
            self._requeue_front(remaining)
            print(f"Wysłano {sent}/{len(items)} zaległych powiadomień "
                  f"(pozostało w kolejce: {self.pending_count()})")
        elif sent > 0:
            print(f"Wysłano wszystkie zaległe powiadomienia Discord ({sent})")
        elif items:
            print("Nie udało się wysłać zaległych powiadomień Discord "
                  "(brak kanału lub błąd konfiguracji)")
        
        return sent
    
    async def _pending_retry_loop(self) -> None:
        """Okresowo ponawia wysyłkę zaległych powiadomień (np. po powrocie internetu)"""
        while not self.bot.is_closed():
            try:
                await asyncio.sleep(self.RETRY_INTERVAL_SECONDS)
                if self.pending_count() > 0 and self._bot_ready:
                    await self._flush_pending()
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Błąd podczas ponawiania zaległych powiadomień Discord: {e}")
    
    async def send_notification(self, message: str, title: str = "M2Watcher", 
                               user_id: Optional[str] = None, color: int = 0xff0000,
                               enqueue_on_fail: bool = True) -> bool:
        """
        Wysyła powiadomienie przez bota Discord do kanału z konfiguracji lub DM.
        Przy błędzie połączenia dodaje powiadomienie do kolejki zaległych.
        
        Args:
            message: Treść wiadomości
            title: Tytuł wiadomości
            user_id: ID użytkownika Discord (używane do DM jeśli brak channel_id)
            color: Kolor embeda (hex)
            enqueue_on_fail: Czy dodać do kolejki przy nieudanej wysyłce
            
        Returns:
            bool: Czy wysłano pomyślnie
        """
        if not self.bot_token:
            return False
        
        created_at = datetime.now(timezone.utc).timestamp()
        result = await self._send_to_channel(message, title, user_id, color, created_at)
        
        if result is True:
            return True
        
        # Kolejkuj tylko przy błędzie wysyłki (sieć), nie przy braku kanału
        if result is False and enqueue_on_fail:
            self._enqueue_pending(message, title, user_id, color, created_at)
        
        return False
    
    async def run(self) -> None:
        """Uruchamia bota"""
        if not self.bot_token:
            print("Brak tokenu bota Discord")
            return
        
        try:
            await self.bot.start(self.bot_token)
        except Exception as e:
            print(f"Błąd uruchamiania bota Discord: {e}")
    
    def start(self) -> None:
        """Uruchamia bota w tle"""
        if self.bot_token:
            thread = threading.Thread(target=lambda: asyncio.run(self.run()), daemon=True)
            thread.start()
    
    def stop(self) -> None:
        """Zatrzymuje bota"""
        if self._loop and self.bot and not self.bot.is_closed():
            try:
                future = asyncio.run_coroutine_threadsafe(self.bot.close(), self._loop)
                future.result(timeout=5)
            except Exception:
                pass
        self._bot_ready = False
    
    def send_notification_sync(self, message: str, title: str = "M2Watcher", 
                               user_id: Optional[str] = None, color: int = 0xff0000) -> bool:
        """
        Synchroniczna metoda do wysyłania powiadomień (może być wywoływana z głównego wątku).
        Przy braku gotowości bota lub błędzie sieci powiadomienie trafia do kolejki zaległych.
        
        Args:
            message: Treść wiadomości
            title: Tytuł wiadomości
            user_id: ID użytkownika Discord
            color: Kolor embeda (hex)
            
        Returns:
            bool: Czy wysłano pomyślnie (False oznacza kolejkowanie lub błąd)
        """
        # Bot jeszcze niegotowy (np. brak internetu przy starcie) — kolejkuj
        if not self._bot_ready or not self._loop:
            self._enqueue_pending(message, title, user_id, color)
            print("Bot Discord niegotowy — powiadomienie dodane do kolejki oczekujących")
            return False
        
        try:
            future = asyncio.run_coroutine_threadsafe(
                self.send_notification(message, title, user_id, color, enqueue_on_fail=True),
                self._loop
            )
            return future.result(timeout=15)
        except Exception as e:
            print(f"Błąd wysyłania powiadomienia Discord (sync): {e}")
            self._enqueue_pending(message, title, user_id, color)
            return False
