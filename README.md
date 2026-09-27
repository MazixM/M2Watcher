# M2Watcher

Pilnuje Twoich klientów Metin2 i daje znać, gdy któryś się **wyloguje** albo **zamknie**: głośnym alarmem na komputerze i wiadomością na **Discordzie** (także na telefonie).

## Szybki start (3 kroki)

1. Pobierz najnowszy `M2Watcher-*.zip` z [Releases](https://github.com/MazixM/M2Watcher/releases) i rozpakuj.
2. Uruchom `M2Watcher.exe`. Nie trzeba instalować Pythona ani niczego innego.
3. Przejdź kreator (ok. 2 minuty):
   - wpisz **nazwę urządzenia**, np. „Laptop” albo „PC w pokoju”. Pojawi się w każdym powiadomieniu, więc przy kilku komputerach od razu wiesz, skąd przyszedł alert;
   - wklej **adres webhooka Discord** ([jak go zdobyć — 1 minuta](app/DISCORD_SETUP.md)) i kliknij „Wyślij wiadomość testową”;
   - wybierz dźwięki i głośność.

Gotowe. Zostaw aplikację uruchomioną (możesz ją zminimalizować). Wszystko zmienisz później w **⚙ Ustawienia**.

> Windows SmartScreen może ostrzec przed nieznanym programem. Kliknij „Więcej informacji” → „Uruchom mimo to”.

## Co potrafi

- ✅ Sam wykrywa uruchomione klienty Metin2 (nazwę pliku gry można zmienić dla serwerów prywatnych)
- 🔴 Wykrywa wylogowanie (klient stracił połączenie z serwerem gry)
- ⚠️ Wykrywa zamknięcie lub crash klienta
- 🟢 Wykrywa ponowne zalogowanie
- 🔔 Powiadomienia Discord z nazwą urządzenia i oznaczeniem (@) Ciebie
- 📶 **Brak internetu nie gubi powiadomień.** Czekają w kolejce i wychodzą, gdy sieć wróci, z dopiskiem, o której zdarzenie wykryto
- 🔊 Własne dźwięki dla każdego zdarzenia (wbudowane albo Twój plik `.wav`) i regulacja głośności w aplikacji
- 🪟 Czytelne okno: lista klientów, status Discorda, historia zdarzeń, duży przycisk „Zatrzymaj alarm”
- 📝 Log błędów do pliku (przycisk „Otwórz folder logów”)

## Jak to działa

Aplikacja działa **całkowicie pasywnie**: nie modyfikuje klienta gry i nie ingeruje w jego działanie. Korzysta tylko z publicznych informacji systemu Windows:

- lista procesów i okien, żeby wykryć zamknięcie,
- liczba połączeń sieciowych procesu gry, żeby wykryć wylogowanie. Klient na ekranie logowania nie ma połączenia z serwerem gry; gdy połączenia nie ma dłużej niż kilka sekund (ustawiane), to wylogowanie.

Aplikacja **nie** czyta pamięci gry, nie wstrzykuje kodu, nie klika w okno i nie analizuje obrazu.

**Odpowiedzialność:** według autora aplikacja nie łamie regulaminu gry, bo działa pasywnie. Jednak **używasz jej na własną odpowiedzialność**. Autor nie odpowiada za ewentualne konsekwencje.

## Pliki aplikacji

Wszystko leży w `%USERPROFILE%\.m2watcher\`:

| Plik | Co to jest |
|---|---|
| `config.json` | ustawienia (edytujesz je w oknie Ustawienia) |
| `logs\m2watcher.log` | log błędów — **dołącz go przy zgłaszaniu problemu** |
| `outbox.json` | powiadomienia czekające na wysłanie (np. gdy nie było internetu) |

Szczegóły techniczne, uruchamianie z kodu źródłowego i rozwiązywanie problemów: [app/README.md](app/README.md).

## Wymagania

- Windows 10 lub 11
- (tylko przy uruchamianiu z kodu) Python 3.10+

## Wsparcie projektu

Jeśli aplikacja jest dla Ciebie przydatna, możesz wesprzeć projekt dobrowolną dotacją:

💙 [Wesprzyj projekt na Tipply](https://tipply.pl/u/mazix)

## Licencja

Open Source
