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

Build jest w trybie jednego pliku (`--onefile`), bez UPX, z metadanymi wersji (z `version.py`) i ikoną
(`assets/m2watcher.ico`). W CI bootloader PyInstallera jest dodatkowo kompilowany ze źródeł — świadomie,
żeby ograniczyć fałszywe alarmy antywirusów bez utraty wygody jednego pliku (tryb `--onedir` dawał mniej
wykryć, ale wymagał folderu `_internal` obok exe i psuł się w praktyce). Szczegóły i dalsze kroki
(m.in. podpis cyfrowy): [issue o fałszywych alarmach](https://github.com/MazixM/M2Watcher/issues/7)
oraz [SIGNING.md](../SIGNING.md).

### Build eksperymentalny: Nuitka

```bash
cd app
pip install -r requirements-nuitka.txt
python build_nuitka.py    # → dist/M2Watcher.exe (kompilacja do C, jeden plik)
```

Nuitka kompiluje kod Pythona do C zamiast pakować bytecode. Binarka nie ma archiwum PYZ ani bootloadera
PyInstallera, na którym uczą się modele antywirusowe, więc zwykle dostaje mniej fałszywych alarmów.
Buduje ją osobny workflow `build-nuitka.yml` (na PR-ach, obok głównego builda) — porównujemy wynik na
VirusTotal, zanim ewentualnie zastąpi PyInstallera. Wymaga kompilatora C (Windows: MSVC; Linux: gcc +
`patchelf`).

## Wydania (release)

CI (`.github/workflows/build.yml`) na każdym PR-ze uruchamia testy na Windowsie, buduje folder z exe
(artefakt do pobrania z zakładki Actions) i — jeśli jest sekret `VIRUSTOTAL_API_KEY` — skanuje exe na
VirusTotal, dopisując wynik do komentarza w PR-ze.

**Każdy udany push do `main` sam tworzy release** `v.X.Y.Z` z plikiem `M2Watcher-<commit>.zip` (zip z folderem `M2Watcher`) i opisem: lista zmian od poprzedniego wydania, link do commitów i instrukcja instalacji.

Numer wersji:
- bazą jest `__version__` w `app/version.py`,
- jeśli release z tą wersją już istnieje, patch podbija się automatycznie (`2.0.0` → `2.0.1` → `2.0.2`…),
- żeby wydać nową wersję minor/major, zmień `app/version.py` (np. na `2.1.0`) w PR-ze.

Release można też utworzyć ręcznie: Actions → Build EXE → Run workflow → zaznacz „Utwórz release”.
Numer wersji liczy `.github/scripts/next_version.py`, a opis `.github/scripts/release_notes.sh`.

## Testy

```bash
cd app
python -m unittest discover -s tests -v
```

Testy nie wymagają Windowsa ani internetu: kolejka Discorda, ponawianie, migracja konfiguracji, wykrywanie wylogowania, dźwięki.

Moduł optymalizacji ma testy logiki na atrapie procesów (`tests/test_optimizer.py`), a CI na Windowsie dodatkowo uruchamia `tests/check_windows_optimizer.py`: prawdziwe wstrzymywanie procesu, pomiar zużycia CPU, affinity, priorytet i ich przywrócenie.

## Struktura

| Plik | Odpowiedzialność |
|---|---|
| `main.py` | start: log, konfiguracja, blokada drugiej kopii, GUI lub konsola |
| `controller.py` | łączy monitor, dźwięki i Discord; kolejka zdarzeń do interfejsu |
| `m2watcher.py` | monitor procesów w osobnym wątku (bez blokowania) |
| `discord_client.py` | wysyłka REST (webhook/bot), trwała kolejka `outbox.json`, ponawianie |
| `notifications.py` | treść powiadomień (nazwa urządzenia, kolory, pola) |
| `sounds.py` | dźwięki WAV: wbudowane, własne pliki, głośność, pętla alarmu |
| `optimizer.py` | opcjonalna optymalizacja: limit FPS (wstrzymywanie/wznawianie), rdzenie CPU, priorytet w tle — [OPTYMALIZACJA.md](OPTYMALIZACJA.md) |
| `config.py` | `config.json`: domyślne wartości, migracja ze starej wersji, zapis atomowy |
| `app_logging.py` | log do pliku z rotacją + przechwytywanie nieobsłużonych wyjątków |
| `build_exe.py` | build PyInstaller (`--onefile`): metadane wersji, ikona, bez UPX |
| `assets/m2watcher.ico` | ikona aplikacji i exe |
| `gui/` | okno główne (zakładki Monitor i Optymalizacja), kreator pierwszego uruchomienia, ustawienia |

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
| `optimization.enabled` | `false` | moduł optymalizacji wielu klientów |
| `optimization.default.fps_limit` | `0` | limit FPS dla wszystkich klientów (0 = bez limitu, 5–59) |
| `optimization.default.fps_background_only` | `true` | limit tylko dla okien w tle |
| `optimization.default.cores_mode` | `none` | `none`, `list` (tylko wybrane rdzenie) albo `spread` (każdy klient na innym rdzeniu) |
| `optimization.default.cores` | `[]` | pula rdzeni logicznych (pusta = wszystkie) |
| `optimization.default.background_priority` | `normal` | `normal`, `below_normal` albo `idle` dla klientów w tle |

Własne ustawienia wybranych klientów ustawia się w oknie (zakładka Optymalizacja) i nie są zapisywane — obowiązują do zamknięcia klienta.

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
