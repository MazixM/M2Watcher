# M2Watcher - Aplikacja kliencka

Monitor klientów Metin2 z wykrywaniem zamknięć i wylogowań.

## Funkcje

- ✅ Automatyczne wykrywanie uruchomionych klientów Metin2
- ⚠️ Wykrywanie zamknięcia klienta (proces lub okno)
- 🔴 Wykrywanie wylogowania (ekran logowania)
- 🟢 Wykrywanie ponownego zalogowania
- 📊 Wyświetlanie statusu wszystkich klientów
- 🔔 Powiadomienia Discord
- 🔊 Powiadomienia dźwiękowe

## Wymagania

- Python 3.7+
- Windows (wymagane dla pełnej funkcjonalności)

## Instalacja

```bash
pip install -r requirements.txt
```

## Konfiguracja

Konfiguracja jest automatycznie tworzona przy pierwszym uruchomieniu w `~/.m2watcher/config.json`.

Możesz też skopiować `config.example.json`:

```bash
cp config.example.json ~/.m2watcher/config.json
```

### Konfiguracja Discord

📖 **Szczegółowy poradnik konfiguracji:** [DISCORD_SETUP.md](DISCORD_SETUP.md)

Szybki start:
1. Utwórz swój własny serwer Discord
2. Utwórz aplikację na https://discord.com/developers/applications
3. Utwórz bota i skopiuj token
4. Zaproś bota na swój serwer z odpowiednimi uprawnieniami
5. Ustaw w konfiguracji:
   - `discord.bot_token` - token bota
   - `discord.guild_id` - ID Twojego serwera
   - `discord.user_id` - Twoje Discord User ID
   - `discord.channel_id` - ID kanału do powiadomień (opcjonalne, jeśli puste - wyśle DM)

### Opcje konfiguracji

Wszystkie opcje są konfigurowane w pliku `~/.m2watcher/config.json`:

- `check_interval` - Interwał sprawdzania w sekundach (domyślnie: 2.0)
- `network_check_samples` - Liczba próbek aktywności sieciowej do analizy (domyślnie: 5)
- `network_threshold` - Próg aktywności sieciowej w bajtach - poniżej tego uznaje za wylogowanie (domyślnie: 1000)
- `debug` - Tryb debugowania - wyświetla dodatkowe informacje (domyślnie: false)
- `sound_enabled` - Włącza/wyłącza powiadomienia dźwiękowe (domyślnie: true)
- `sound_wait_for_input` - Czy dźwięk ma się powtarzać aż użytkownik naciśnie Enter (domyślnie: true)
- `show_status` - Wyświetla status wszystkich klientów w konsoli (domyślnie: true)

## Użycie

```bash
python main.py
```

## Budowanie exe

```bash
python build_exe.py
```

Plik exe będzie w katalogu `dist/M2Watcher.exe`.

## Jak działa

Program monitoruje procesy Metin2 i wykrywa:
1. **Zamknięcie klienta** - gdy proces lub okno zostanie zamknięte
2. **Wylogowanie** - gdy aktywność sieciowa spada (brak połączeń ESTABLISHED)
3. **Ponowne zalogowanie** - gdy aktywność sieciowa wzrasta

## Rozwiązywanie problemów

**Program nie wykrywa wylogowań:**
- Zwiększ liczbę próbek w konfiguracji: `"network_check_samples": 10`
- Obniż próg w konfiguracji: `"network_threshold": 500`

**Program zbyt często wykrywa wylogowania:**
- Zwiększ próg w konfiguracji: `"network_threshold": 2000`
- Zwiększ liczbę próbek w konfiguracji: `"network_check_samples": 7`

## Wsparcie projektu

Jeśli aplikacja jest dla Ciebie przydatna, możesz wesprzeć projekt dobrowolną dotacją:

💙 [Wesprzyj projekt na Tipply](https://tipply.pl/u/mazix)