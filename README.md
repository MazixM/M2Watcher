# M2Watcher

Aplikacja do monitorowania klientów Metin2.

## Struktura projektu

```
M2Watcher/
├── app/              # Aplikacja kliencka (Python)
│   ├── m2watcher.py  # Główna logika monitorowania
│   ├── config.py    # Zarządzanie konfiguracją
│   ├── notifications.py # Powiadomienia Discord
│   ├── discord_bot.py # Bot Discord
│   ├── main.py      # Punkt wejścia
│   ├── build_exe.py # Skrypt budowania exe
│   └── requirements.txt
```

## Aplikacja kliencka (`app/`)

Monitor klientów Metin2 z wykrywaniem zamknięć i wylogowań.

### Funkcje

- ✅ Automatyczne wykrywanie uruchomionych klientów Metin2
- ⚠️ Wykrywanie zamknięcia klienta (proces lub okno)
- 🔴 Wykrywanie wylogowania (ekran logowania)
- 🟢 Wykrywanie ponownego zalogowania
- 📊 Wyświetlanie statusu wszystkich klientów
- 🔔 Powiadomienia Discord

### Instalacja

```bash
cd app
pip install -r requirements.txt
```

### Użycie

```bash
cd app
python main.py
```

### Budowanie exe

```bash
cd app
python build_exe.py
```

### Konfiguracja

📖 **Poradnik konfiguracji Discord:** [app/DISCORD_SETUP.md](app/DISCORD_SETUP.md)

Więcej informacji w katalogu `app/`.

## Wymagania

- Python 3.7+
- Windows (dla pełnej funkcjonalności)

## Wsparcie projektu

Jeśli aplikacja jest dla Ciebie przydatna, możesz wesprzeć projekt dobrowolną dotacją:

💙 [Wesprzyj projekt na Tipply](https://tipply.pl/u/mazix)

## Licencja

Open Source - zobacz plik LICENSE w repozytorium.
