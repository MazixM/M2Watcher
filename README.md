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

### Jak działa aplikacja

Aplikacja działa w sposób całkowicie pasywny - **nie modyfikuje** i **nie ingeruje** w działanie klienta gry Metin2. Program monitoruje system operacyjny (procesy, okna, aktywność sieciową) i wykrywa zamknięcia oraz wylogowania. Aplikacja nie używa modyfikacji pamięci, wstrzykiwania kodu, czytania pamięci procesu gry ani analizy obrazu ekranu - korzysta wyłącznie z publicznych API systemu Windows.

### ⚠️ Ważne informacje

**Odpowiedzialność:** Według autora, aplikacja nie łamie regulaminu gry Metin2, ponieważ działa w sposób całkowicie pasywny i nie ingeruje w działanie klienta gry. Jednak **używasz aplikacji na własną odpowiedzialność**. Autor nie ponosi odpowiedzialności za ewentualne konsekwencje wynikające z użycia aplikacji.

### Funkcje

- ✅ Automatyczne wykrywanie uruchomionych klientów Metin2
- ⚠️ Wykrywanie zamknięcia klienta (proces lub okno)
- 🔴 Wykrywanie wylogowania (ekran logowania)
- 🟢 Wykrywanie ponownego zalogowania
- 📊 Wyświetlanie statusu wszystkich klientów
- 🔔 Powiadomienia Discord

### Instalacja

**Gotowy plik exe:** Pobierz z [Releases](https://github.com/MazixM/M2Watcher/releases)

**Lub zbuduj z kodu źródłowego:**
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

- Python 3.7+ (Jeśli uruchamiana jest wersja exe, to python nie jest wymagany)
- System operacyjny Windows

## Wsparcie projektu

Jeśli aplikacja jest dla Ciebie przydatna, możesz wesprzeć projekt dobrowolną dotacją:

💙 [Wesprzyj projekt na Tipply](https://tipply.pl/u/mazix)

## Licencja

Open Source - zobacz plik LICENSE w repozytorium.
