# M2Watcher: szczegóły techniczne

Instrukcja dla użytkownika jest w [głównym README](../README.md), konfiguracja Discorda w [DISCORD_SETUP.md](DISCORD_SETUP.md).

## Uruchamianie z kodu źródłowego

```bash
cd app
pip install -r requirements.txt
python main.py            # okno aplikacji
python main.py --setup    # wymuś kreator konfiguracji
python main.py --console  # tryb tekstowy bez okna (Enter = zatrzymaj alarm)
```

Wymagany Python 3.10+ z `tkinter` (instalator z python.org ma go domyślnie).

## Budowanie exe

```bash
cd app
pip install -r requirements-build.txt
python build_exe.py       # → dist/M2Watcher.exe (jeden plik, bez okna konsoli)
```

CI (`.github/workflows/build.yml`) na każdym pushu/PR uruchamia testy na Windowsie i buduje exe. Uruchomienie ręczne z podanym `release_tag` tworzy release z plikiem zip.

## Testy

```bash
cd app
python -m unittest discover -s tests -v
```

Testy nie wymagają Windowsa ani internetu: kolejka Discorda, ponawianie, migracja konfiguracji, wykrywanie wylogowania, dźwięki.

## Struktura

| Plik | Odpowiedzialność |
|---|---|
| `main.py` | start: log, konfiguracja, blokada drugiej kopii, GUI lub konsola |
| `controller.py` | łączy monitor, dźwięki i Discord; kolejka zdarzeń do interfejsu |
| `m2watcher.py` | monitor procesów w osobnym wątku (bez blokowania) |
| `discord_client.py` | wysyłka REST (webhook/bot), trwała kolejka `outbox.json`, ponawianie |
| `notifications.py` | treść powiadomień (nazwa urządzenia, kolory, pola) |
| `sounds.py` | dźwięki WAV: wbudowane, własne pliki, głośność, pętla alarmu |
| `config.py` | `config.json`: domyślne wartości, migracja ze starej wersji, zapis atomowy |
| `app_logging.py` | log do pliku z rotacją + przechwytywanie nieobsłużonych wyjątków |
| `gui/` | okno główne, kreator pierwszego uruchomienia, ustawienia |

## Konfiguracja (`%USERPROFILE%\.m2watcher\config.json`)

Zwykle edytujesz ją w oknie **Ustawienia**. Pełny przykład: [config.example.json](config.example.json).

| Klucz | Domyślnie | Opis |
|---|---|---|
| `device_name` | nazwa komputera | nazwa widoczna w powiadomieniach |
| `process_names` | `["metin2client.exe"]` | nazwy pliku gry (bez rozróżniania wielkości liter, `.exe` opcjonalne) |
| `check_interval` | `2.0` | co ile sekund sprawdzać klienty |
| `logout_grace_seconds` | `5.0` | po ilu sekundach bez połączenia uznać wylogowanie |
| `start_minimized` | `false` | start zminimalizowany |
| `debug` | `false` | szczegółowe logi |
| `discord.method` | `none` | `webhook`, `bot` albo `none` |
| `discord.webhook_url` | | adres webhooka |
| `discord.bot_token` / `discord.channel_id` | | dla metody `bot`; brak kanału = wiadomość prywatna |
| `discord.user_id` / `discord.mention_user` | `""` / `true` | kogo oznaczać (@) |
| `discord.notify_events.<zdarzenie>` | `true` | `logout`, `closed`, `reconnect` |
| `sounds.enabled` / `sounds.volume` | `true` / `80` | dźwięk i głośność 0–100 |
| `sounds.repeat_until_ack` | `true` | alarm powtarza się do kliknięcia „Zatrzymaj alarm” |
| `sounds.max_alarm_seconds` | `300` | automatyczne wyciszenie (0 = nigdy) |
| `sounds.events.<zdarzenie>.sound` | | `builtin:alarm`, `builtin:syrena`, `builtin:dzwonek`, `builtin:ping`, `custom` lub `none` |
| `sounds.events.<zdarzenie>.file` | | ścieżka do pliku `.wav` dla `custom` |

Konfiguracja ze starszej wersji (`discord.enabled`, `sound_enabled`, `sound_wait_for_input`…) jest przenoszona automatycznie. Uszkodzony plik jest odkładany jako `config.broken.json`, a aplikacja startuje z ustawieniami domyślnymi.

## Wykrywanie

- **Zamknięcie:** proces zniknął albo jego okno przestało istnieć. Minimalizacja okna nie jest zamknięciem.
- **Wylogowanie:** proces nie ma połączenia TCP `ESTABLISHED` dłużej niż `logout_grace_seconds`.
- **Ponowne zalogowanie:** połączenie wróciło.

Zdarzenia trafiają jednocześnie do dźwięku, do kolejki Discord i do historii w oknie. Monitor działa w osobnym wątku, więc alarm ani wysyłka nie wstrzymują sprawdzania.

## Rozwiązywanie problemów

| Problem | Rozwiązanie |
|---|---|
| Nie wykrywa klienta | Sprawdź nazwę pliku gry w Menedżerze zadań → Szczegóły i wpisz ją w Ustawienia → Ogólne. |
| Fałszywe alarmy przy lagach | Zwiększ „Wylogowanie po braku połączenia” (np. 15 s). |
| Brak dźwięku | Ustawienia → Dźwięki → „Odsłuchaj”. Sprawdź w mikserze głośności Windows, czy M2Watcher nie jest wyciszony. Własny plik musi być `.wav`. |
| Discord nie działa | Karta „Discord” w oknie pokazuje przyczynę. Patrz [DISCORD_SETUP.md](DISCORD_SETUP.md#rozwiązywanie-problemów). |
| „M2Watcher jest już uruchomiony” | Aplikacja działa już w tle (sprawdź pasek zadań). Dwie kopie dawałyby podwójne alarmy. |

Przy każdym zgłoszeniu dołącz `%USERPROFILE%\.m2watcher\logs\m2watcher.log` (przycisk „Otwórz folder logów”).
