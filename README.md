# M2Watcher

Pilnuje Twoich klientów Metin2 i daje znać, gdy któryś się **wyloguje** albo **zamknie**: głośnym alarmem na komputerze i wiadomością na **Discordzie** (także na telefonie).

## Szybki start (3 kroki)

1. Pobierz **[M2Watcher.zip](https://github.com/MazixM/M2Watcher/releases/latest/download/M2Watcher.zip)** (zawsze najnowsza wersja) i rozpakuj **cały** folder `M2Watcher` w dowolne miejsce. Starsze wydania: [Releases](https://github.com/MazixM/M2Watcher/releases).
2. Uruchom `M2Watcher.exe` z tego folderu. Nie trzeba instalować Pythona ani niczego innego. Nie kopiuj samego exe gdzie indziej — potrzebuje folderu `_internal` obok siebie.
3. Przejdź kreator (ok. 2 minuty):
   - wpisz **nazwę urządzenia**, np. „Laptop” albo „PC w pokoju”. Pojawi się w każdym powiadomieniu, więc przy kilku komputerach od razu wiesz, skąd przyszedł alert;
   - wklej **adres webhooka Discord** ([jak go zdobyć — 1 minuta](app/DISCORD_SETUP.md)) i kliknij „Wyślij wiadomość testową”;
   - wybierz dźwięki i głośność.

Gotowe. Zostaw aplikację uruchomioną (możesz ją zminimalizować). Wszystko zmienisz później w **⚙ Ustawienia**.

> Windows SmartScreen może ostrzec przed nieznanym programem. Kliknij „Więcej informacji” → „Uruchom mimo to”. Jeśli antywirus zgłasza plik jako zagrożenie — patrz [Antywirus zgłasza M2Watcher](#antywirus-zgłasza-m2watcher).

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
- ⚡ **Optymalizacja wielu klientów** (opcjonalna zakładka): limit FPS dla okien w tle, przypisanie klientów do rdzeni procesora i niższy priorytet w tle — dla wszystkich albo tylko wybranych klientów. Szczegóły i research: [app/OPTYMALIZACJA.md](app/OPTYMALIZACJA.md)

## Jak to działa

Aplikacja działa **całkowicie pasywnie**: nie modyfikuje klienta gry i nie ingeruje w jego działanie. Korzysta tylko z publicznych informacji systemu Windows:

- lista procesów i okien, żeby wykryć zamknięcie,
- liczba połączeń sieciowych procesu gry, żeby wykryć wylogowanie. Klient na ekranie logowania nie ma połączenia z serwerem gry; gdy połączenia nie ma dłużej niż kilka sekund (ustawiane), to wylogowanie.

Aplikacja **nie** czyta pamięci gry, nie wstrzykuje kodu, nie klika w okno i nie analizuje obrazu.

**Wyjątek: zakładka Optymalizacja.** Jest domyślnie wyłączona. Gdy ją włączysz, M2Watcher zmienia procesy gry tymi samymi funkcjami Windows, których używa Menedżer zadań: rdzenie procesora i priorytet. Przy limicie FPS dodatkowo cyklicznie wstrzymuje proces klienta, tak jak BES. Nadal nie czyta pamięci gry i niczego do niej nie wstrzykuje. Po wyłączeniu klienty wracają do pierwotnych ustawień.

**Odpowiedzialność:** według autora aplikacja nie łamie regulaminu gry, bo działa pasywnie. Jednak **używasz jej na własną odpowiedzialność**. Autor nie odpowiada za ewentualne konsekwencje.

## Pliki aplikacji

Wszystko leży w `%USERPROFILE%\.m2watcher\`:

| Plik | Co to jest |
|---|---|
| `config.json` | ustawienia (edytujesz je w oknie Ustawienia) |
| `logs\m2watcher.log` | log błędów — **dołącz go przy zgłaszaniu problemu** |
| `outbox.json` | powiadomienia czekające na wysłanie (np. gdy nie było internetu) |
| `throttled.json` | klienty z limitem FPS — pozwala je wznowić, gdyby M2Watcher został zabity |

Szczegóły techniczne, uruchamianie z kodu źródłowego i rozwiązywanie problemów: [app/README.md](app/README.md).

## Antywirus zgłasza M2Watcher

Część antywirusów potrafi zgłosić `M2Watcher.exe` jako zagrożenie — to **fałszywy alarm**. Nie chodzi o to, że plik jest niebezpieczny, tylko o to, jak jest zbudowany: to program w Pythonie spakowany PyInstallerem, a takie pliki modele heurystyczne (nazwy typu `!ml`, „Static AI”, „confidence 70%”) często oznaczają na wszelki wypadek. M2Watcher działa całkowicie pasywnie: nie czyta pamięci gry, nie wstrzykuje kodu, nie modyfikuje plików gry.

Co robimy, żeby tego uniknąć (bez płatnego certyfikatu):

- budujemy w trybie katalogowym (exe + folder `_internal`), a nie jako jeden „samorozpakowujący się” plik — ten drugi wygląda dla antywirusów jak droper i był flagowany przez kilka silników, folder ma 0 wykryć;
- budujemy bez kompresji UPX (kojarzonej z malware);
- bootloader PyInstallera jest kompilowany ze źródeł w CI, więc nie ma odcisku wspólnego z próbkami, na których uczą się modele AV;
- exe ma pełne metadane (autor, opis, wersja) i ikonę;
- każdy build jest publicznie budowany na GitHub Actions z tego kodu (możesz sprawdzić i zbudować sam);
- pracujemy nad darmowym podpisem cyfrowym dla projektów open source ([SignPath](https://about.signpath.io/product/open-source)).

Jeśli mimo to Twój antywirus blokuje plik:

1. Sprawdź aktualny wynik na [VirusTotal](https://www.virustotal.com/) — wklej plik albo jego skrót SHA-256. Kilka wykryć z silników ML to typowy fałszywy alarm.
2. Dodaj folder `M2Watcher` (cały, z `_internal`) do wyjątków antywirusa.
3. Możesz zgłosić fałszywy alarm producentowi antywirusa (np. [Microsoft](https://www.microsoft.com/en-us/wdsi/filesubmission) → „Incorrectly detected as malware”) — to pomaga wszystkim użytkownikom.
4. Nie ufasz gotowemu plikowi? [Zbuduj exe samodzielnie ze źródeł](app/README.md#budowanie-exe) — kod jest w całości otwarty.

## Wymagania

- Windows 10 lub 11
- (tylko przy uruchamianiu z kodu) Python 3.10+

## Wsparcie projektu

Jeśli aplikacja jest dla Ciebie przydatna, możesz wesprzeć projekt dobrowolną dotacją:

💙 [Wesprzyj projekt na Tipply](https://tipply.pl/u/mazix)

## Licencja

[MIT](LICENSE) — możesz używać, zmieniać i rozpowszechniać, zachowując informację o autorze.
