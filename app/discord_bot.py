"""
Bot Discord dla M2Watcher
Obsługuje powiadomienia na własnym serwerze użytkownika
"""
import discord
from discord.ext import commands
from typing import Optional, Dict
import asyncio
from config import Config


class M2WatcherBot:
    """Bot Discord dla M2Watcher"""
    
    def __init__(self, config: Config):
        self.config = config
        self.bot_token = config.get("discord.bot_token", "")
        self.guild_id = config.get("discord.guild_id", "")
        self.user_id = config.get("discord.user_id", "")
        self.channel_id = config.get("discord.channel_id", "")
        self._loop = None
        self._bot_ready = False
        
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        
        self.bot = commands.Bot(command_prefix='!', intents=intents)
        self.setup_commands()
    
    def setup_commands(self) -> None:
        """Konfiguruje komendy bota"""
        
        @self.bot.event
        async def on_ready():
            print(f'Bot Discord zalogowany jako {self.bot.user}')
            self._loop = asyncio.get_event_loop()
            self._bot_ready = True
    
    async def send_notification(self, message: str, title: str = "M2Watcher", 
                               user_id: Optional[str] = None, color: int = 0xff0000) -> bool:
        """
        Wysyła powiadomienie przez bota Discord do kanału z konfiguracji lub DM.
        
        Args:
            message: Treść wiadomości
            title: Tytuł wiadomości
            user_id: ID użytkownika Discord (używane do DM jeśli brak channel_id)
            color: Kolor embeda (hex)
            
        Returns:
            bool: Czy wysłano pomyślnie
        """
        if not self.bot_token:
            return False
        
        try:
            channel = None
            target_user_id = user_id or self.user_id
            
            # Najpierw spróbuj użyć channel_id z konfiguracji
            if self.channel_id:
                channel = self.bot.get_channel(int(self.channel_id))
            
            # Jeśli nie ma kanału, spróbuj wysłać DM
            if not channel and target_user_id:
                user = self.bot.get_user(int(target_user_id))
                if user:
                    channel = await user.create_dm()
            
            # Jeśli nadal nie ma kanału i mamy guild_id, spróbuj znaleźć pierwszy dostępny kanał tekstowy
            if not channel and self.guild_id:
                guild = self.bot.get_guild(int(self.guild_id))
                if guild:
                    # Znajdź pierwszy kanał tekstowy, do którego bot ma dostęp
                    for ch in guild.text_channels:
                        if ch.permissions_for(guild.me).send_messages:
                            channel = ch
                            break
            
            if channel:
                embed = discord.Embed(
                    title=title,
                    description=message,
                    color=discord.Color(color),
                    timestamp=discord.utils.utcnow()
                )
                embed.set_footer(text="M2Watcher")
                
                # Dodaj mention tylko jeśli mamy user_id
                content = f"<@{target_user_id}>" if target_user_id else None
                await channel.send(content=content, embed=embed)
                return True
            
            return False
        except Exception as e:
            print(f"Błąd wysyłania powiadomienia Discord: {e}")
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
            import threading
            thread = threading.Thread(target=lambda: asyncio.run(self.run()), daemon=True)
            thread.start()
    
    def send_notification_sync(self, message: str, title: str = "M2Watcher", 
                               user_id: Optional[str] = None, color: int = 0xff0000) -> bool:
        """
        Synchroniczna metoda do wysyłania powiadomień (może być wywoływana z głównego wątku).
        
        Args:
            message: Treść wiadomości
            title: Tytuł wiadomości
            user_id: ID użytkownika Discord
            color: Kolor embeda (hex)
            
        Returns:
            bool: Czy wysłano pomyślnie
        """
        if not self._bot_ready or not self._loop:
            return False
        
        try:
            import asyncio
            future = asyncio.run_coroutine_threadsafe(
                self.send_notification(message, title, user_id, color),
                self._loop
            )
            return future.result(timeout=10)  # Timeout 10 sekund
        except Exception as e:
            print(f"Błąd wysyłania powiadomienia Discord (sync): {e}")
            return False

