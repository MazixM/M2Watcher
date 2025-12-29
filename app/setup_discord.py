"""
Pomocniczy skrypt do konfiguracji bota Discord dla M2Watcher
"""
import json
from pathlib import Path
from config import Config, CONFIG_FILE

def print_config_location():
    """Wyświetla lokalizację pliku konfiguracyjnego"""
    print("=" * 60)
    print("Lokalizacja pliku konfiguracyjnego:")
    print(f"  {CONFIG_FILE}")
    print("=" * 60)
    print()

def interactive_setup():
    """Interaktywna konfiguracja bota Discord"""
    print("=" * 60)
    print("Konfiguracja bota Discord dla M2Watcher")
    print("=" * 60)
    print()
    print("Aby skonfigurować bota, potrzebujesz:")
    print("  1. Bot Token (z Discord Developer Portal)")
    print("  2. Guild ID (ID serwera Discord)")
    print("  3. User ID (Twoje ID użytkownika Discord - opcjonalne)")
    print()
    print("Szczegółowe instrukcje znajdziesz w pliku DISCORD_SETUP.md")
    print()
    
    config = Config()
    
    # Sprawdź aktualną konfigurację
    current_token = config.get("discord.bot_token", "")
    current_guild_id = config.get("discord.guild_id", "")
    current_user_id = config.get("discord.user_id", "")
    
    print("Aktualna konfiguracja:")
    print(f"  Bot Token: {'✓ Ustawiony' if current_token else '✗ Brak'}")
    print(f"  Guild ID: {'✓ Ustawiony' if current_guild_id else '✗ Brak'}")
    print(f"  User ID: {'✓ Ustawiony' if current_user_id else '✗ Brak (opcjonalne)'}")
    print()
    
    # Pytaj o wartości
    if not current_token:
        print("Wprowadź Bot Token (lub naciśnij Enter aby pominąć):")
        token = input("> ").strip()
        if token:
            config.set("discord.bot_token", token)
            print("✓ Bot Token zapisany")
    else:
        print("Bot Token jest już ustawiony. Czy chcesz go zmienić? (t/n):")
        if input("> ").strip().lower() == 't':
            print("Wprowadź nowy Bot Token:")
            token = input("> ").strip()
            if token:
                config.set("discord.bot_token", token)
                print("✓ Bot Token zaktualizowany")
    
    print()
    
    if not current_guild_id:
        print("Wprowadź Guild ID (ID serwera Discord):")
        guild_id = input("> ").strip()
        if guild_id:
            config.set("discord.guild_id", guild_id)
            print("✓ Guild ID zapisany")
    else:
        print("Guild ID jest już ustawiony. Czy chcesz go zmienić? (t/n):")
        if input("> ").strip().lower() == 't':
            print("Wprowadź nowe Guild ID:")
            guild_id = input("> ").strip()
            if guild_id:
                config.set("discord.guild_id", guild_id)
                print("✓ Guild ID zaktualizowany")
    
    print()
    
    if not current_user_id:
        print("Wprowadź User ID (Twoje ID użytkownika Discord - opcjonalne, naciśnij Enter aby pominąć):")
        user_id = input("> ").strip()
        if user_id:
            config.set("discord.user_id", user_id)
            print("✓ User ID zapisany")
    else:
        print("User ID jest już ustawiony. Czy chcesz go zmienić? (t/n):")
        if input("> ").strip().lower() == 't':
            print("Wprowadź nowe User ID (lub naciśnij Enter aby pominąć):")
            user_id = input("> ").strip()
            if user_id:
                config.set("discord.user_id", user_id)
                print("✓ User ID zaktualizowany")
    
    print()
    print("=" * 60)
    print("Konfiguracja zakończona!")
    print("=" * 60)
    print()
    print("Następne kroki:")
    print("  1. Uruchom aplikację M2Watcher")
    print("  2. Na serwerze Discord użyj komendy: !setup")
    print("  3. Bot utworzy prywatny kanał dla powiadomień")
    print()

def show_instructions():
    """Wyświetla podstawowe instrukcje"""
    print("=" * 60)
    print("Jak skonfigurować bota Discord")
    print("=" * 60)
    print()
    print("1. Utwórz aplikację bota na: https://discord.com/developers/applications")
    print("2. Skopiuj Bot Token z sekcji 'Bot'")
    print("3. Dodaj bota na serwer (OAuth2 → URL Generator)")
    print("4. Włącz tryb deweloperski w Discord (Ustawienia → Zaawansowane)")
    print("5. Skopiuj Guild ID (prawy klik na serwer → Kopiuj ID)")
    print("6. Skopiuj User ID (prawy klik na siebie → Kopiuj ID)")
    print()
    print("Szczegółowe instrukcje: DISCORD_SETUP.md")
    print()
    print("Lokalizacja pliku konfiguracyjnego:")
    print(f"  {CONFIG_FILE}")
    print()

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--interactive":
        print_config_location()
        interactive_setup()
    else:
        print_config_location()
        show_instructions()
        print("Uruchom z flagą --interactive aby rozpocząć interaktywną konfigurację:")
        print("  python setup_discord.py --interactive")

