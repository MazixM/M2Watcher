"""
Główny plik uruchomieniowy M2Watcher
"""
import sys
import traceback

try:
    from config import Config
    from m2watcher import Metin2Watcher
except ImportError as e:
    print(f"Błąd importu modułów: {e}")
    print(f"Python path: {sys.path}")
    traceback.print_exc()
    sys.exit(1)

# Import bota Discord (opcjonalny)
try:
    from discord_bot import M2WatcherBot
    DISCORD_BOT_AVAILABLE = True
except ImportError:
    DISCORD_BOT_AVAILABLE = False
    M2WatcherBot = None


def main():
    """Główna funkcja"""
    try:
        # Uruchom aplikację
        config = Config()
    except Exception as e:
        print(f"Błąd podczas inicjalizacji konfiguracji: {e}")
        traceback.print_exc()
        input("Naciśnij Enter aby zakończyć...")
        sys.exit(1)
    
    # Uruchom bota Discord jeśli jest włączony
    discord_bot = None
    if DISCORD_BOT_AVAILABLE and config.get("discord.enabled", False):
        bot_token = config.get("discord.bot_token", "")
        if bot_token:
            try:
                discord_bot = M2WatcherBot(config)
                discord_bot.start()  # Uruchom bota w tle
                print("Bot Discord uruchomiony")
            except Exception as e:
                print(f"Błąd uruchamiania bota Discord: {e}")
                discord_bot = None
    
    # Utwórz NotificationManager z botem Discord
    from notifications import NotificationManager
    notification_manager = NotificationManager(config, discord_bot)
    
    watcher = Metin2Watcher(
        check_interval=config.get("check_interval", 2.0),
        network_check_samples=config.get("network_check_samples", 5),
        network_threshold=config.get("network_threshold", 1000),
        debug=config.get("debug", False),
        sound_enabled=config.get("sound_enabled", True),
        sound_wait_for_input=config.get("sound_wait_for_input", True),
        config=config
    )
    
    # Zastąp notification_manager w watcherze naszym z botem
    watcher.notification_manager = notification_manager
    
    try:
        watcher.run(show_status=config.get("show_status", True))
    except KeyboardInterrupt:
        print("\n\nZatrzymywanie aplikacji...")
        if discord_bot:
            try:
                discord_bot.stop()
            except:
                pass
    except Exception as e:
        print(f"\n\nBłąd krytyczny: {e}")
        traceback.print_exc()
        input("Naciśnij Enter aby zakończyć...")
        sys.exit(1)


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"Błąd krytyczny w main(): {e}")
        traceback.print_exc()
        input("Naciśnij Enter aby zakończyć...")
        sys.exit(1)

