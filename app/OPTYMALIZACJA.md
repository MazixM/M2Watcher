# Optymalizacja wielu klientów

Zakładka **Optymalizacja** w oknie M2Watchera. Moduł jest opcjonalny i domyślnie wyłączony.
Przydaje się, gdy na jednym komputerze działa kilka lub kilkanaście klientów Metin2 i procesor
dochodzi do 100%.

## Co można ustawić

Każde ustawienie działa na **wszystkie klienty** (karta „Dla wszystkich klientów”) albo na
**wybrane**: zaznacz je w tabeli (Ctrl / Shift) i kliknij „Własne ustawienia dla zaznaczonych…”.
Przycisk „Wyłącz dla zaznaczonych” zdejmuje z nich optymalizację. Własne ustawienia obowiązują,
dopóki klient działa. Po ponownym uruchomieniu gry klient ma nowy PID i dostaje ustawienia wspólne.

| Ustawienie | Co robi | Kiedy pomaga |
|---|---|---|
| **Limit FPS** (5–59) | Klient jest cyklicznie wstrzymywany i wznawiany: w każdym okresie `1/FPS` pracuje przez czas jednej klatki przy 60 FPS, a przez resztę okresu stoi. | Najbardziej. Klient w tle rysuje tyle samo klatek co aktywny, a limit 20 FPS to ok. 1/3 pracy CPU i GPU. |
| **Tylko w tle** (domyślnie włączone) | Okno, w które klikniesz, od razu wraca do pełnej płynności. Limit wraca, gdy przełączysz się na inne okno. | Zawsze. Grasz jednym klientem, reszta stoi AFK. |
| **Rdzenie: tylko wybrane** | Wszystkie klienty (albo wybrane) dostają zaznaczone rdzenie, np. wszystkie oprócz rdzenia 0, albo tylko rdzenie E. | Gdy chcesz zostawić rdzenie dla aktywnego klienta, systemu, Discorda albo przeglądarki. |
| **Rdzenie: rozłóż** | Każdy klient dostaje inny rdzeń fizyczny z zaznaczonej puli, razem z jego wątkiem HT/SMT. Przy większej liczbie klientów niż rdzeni rdzenie są dzielone po równo. | Gdy klientów jest więcej niż rdzeni: jeden klient nie zajmie połowy procesora. |
| **Priorytet w tle** | „Poniżej normalnego” albo „Niski” dla klientów w tle. Aktywne okno zawsze ma swój zwykły priorytet. | Przy 100% CPU. Aktywny klient i system nie tną się, bo klienty w tle ustępują im pierwszeństwa. |

Dobre ustawienie na start dla wielu klientów AFK: **limit 15–20 FPS w tle, priorytet w tle
„Poniżej normalnego”, rdzenie „Rozłóż” bez rdzenia 0**.

### Jak działa limit FPS i jakie ma ograniczenia

- Klient Metin2 sam trzyma się limitu 60 FPS. Limit M2Watchera zostawia mu czas na jedną taką
  klatkę w każdym okresie, więc 20 FPS oznacza ok. 1/60 s pracy i 2/60 s przerwy. W testach
  proces, który wcześniej zajmował 100% rdzenia, zużywał przy limicie 30/20/10 FPS kolejno
  50/33/17%.
- To przybliżenie. Liczba FPS nie jest mierzona w grze, bo wymagałoby to wstrzykiwania kodu.
- Wstrzymywany jest cały proces, więc w oknie z limitem dźwięk może trzeszczeć, a sterowanie
  działa z opóźnieniem. Dlatego domyślnie limit działa **tylko w tle**. Wyłącz dźwięk
  w klientach AFK.
- Połączenie z serwerem nie zrywa się: przerwy trwają najwyżej ok. 0,2 s (przy 5 FPS), a TCP
  obsługuje system.
- Wstrzymany klient zawsze jest wznawiany: po wyłączeniu modułu, zmianie ustawień, zamknięciu
  klienta i zamknięciu M2Watchera. Jeśli M2Watcher zostanie **zabity** (Menedżer zadań, awaria)
  w chwili wstrzymania klienta, klient stanie. Uruchom wtedy M2Watcher ponownie, a sam go wznowi
  (lista w `%USERPROFILE%\.m2watcher\throttled.json`).

### Uprawnienia

Jeśli gra działa jako administrator, a M2Watcher nie, Windows nie pozwoli zmienić jej procesu.
W kolumnie „Uwagi” pojawi się „brak uprawnień”. Uruchom wtedy M2Watcher jako administrator
(prawy przycisk myszy → „Uruchom jako administrator”).

### Uczciwie o ryzyku

Moduł korzysta tylko z funkcji Windows, których używają Menedżer zadań, Process Lasso i BES.
Nie czyta pamięci gry, nie wstrzykuje kodu i nie zmienia plików. Nie da się jednak wykluczyć,
że zabezpieczenia gry uznają wstrzymywanie procesu za podejrzane. Zacznij od kilku klientów
i łagodnego limitu. **Używasz na własną odpowiedzialność**, tak samo jak reszty aplikacji.

---

## Research: co jeszcze realnie pomaga przy wielu klientach

Rzeczy sprawdzone w dokumentacji Microsoftu, NVIDIA i Bitsum oraz na forach Metin2. Ocena
dotyczy scenariusza „dużo klientów AFK + jeden aktywny”.

### Już w M2Watcherze

1. **Limit FPS klientów w tle.** Na oficjalnym forum Metin2 gracze zgłaszali, że
   zminimalizowane klienty zużywają tyle CPU, co widoczne, i że po jednej z aktualizacji dało się
   uruchomić 2–3 konta zamiast wcześniejszych 16. To główne źródło obciążenia i limit działa
   dokładnie na nie. Ta sama technika co w BES (Battle Encoder Shirasé).
2. **Niższy priorytet klientów w tle.** Bitsum (Process Lasso) opisuje priorytet „Poniżej
   normalnego” dla uciążliwego procesu jako często bardzo skuteczny, bezpieczny i efektywny,
   z wyłączeniem aktywnego okna. M2Watcher robi to samo: aktywne okno zostaje nietknięte.
3. **Rdzenie (affinity).** Przypięcie do N rdzeni to twardy sufit zużycia CPU. M2Watcher
   rozkłada klienty po rdzeniach fizycznych (zna wątki HT/SMT oraz rdzenie P/E z
   `GetLogicalProcessorInformationEx`). Samo przypięcie „jeden klient = jeden rdzeń” rzadko daje
   więcej FPS. Pomaga przede wszystkim oddzielić klienty w tle od aktywnego klienta i systemu.

### Warte dodania w kolejnych wersjach (od najbardziej opłacalnych)

| Pomysł | Co daje | Koszt / ryzyko | Ocena |
|---|---|---|---|
| **EcoQoS („tryb wydajności”) dla klientów w tle** | `SetProcessInformation(ProcessPowerThrottling)`. Windows 11 obniża taktowanie i na procesorach hybrydowych przenosi proces na rdzenie E. To ten sam mechanizm co listek „Tryb wydajności” w Menedżerze zadań. | Mały (jedno wywołanie API, ten sam wzorzec co priorytet). Na procesorach bez rdzeni E daje głównie niższy pobór prądu. | **Tak.** Szczególnie Intel 12. gen. i nowsze: klienty AFK na rdzeniach E, aktywny na P. |
| **Niski priorytet pamięci klientów w tle** | `ProcessMemoryPriority = LOW`. Przy braku RAM system w pierwszej kolejności zabiera strony klientom AFK, a nie aktywnemu klientowi i przeglądarce. | Mały, bezpieczny (tylko wskazówka dla menedżera pamięci). | **Tak.** Ważne, bo każdy klient to kilkaset MB, a proces 32-bitowy ma sufit ok. 2–4 GB. |
| **Priorytet I/O „niski” w tle** | Doczytywanie map i tekstur przez klienty w tle nie blokuje dysku aktywnemu klientowi. | Mały (`NtSetInformationProcess`, nieudokumentowane). | Opcjonalnie. Zauważalne głównie na HDD. |
| **Profile ustawień gry (`metin2.cfg`)** | Największy zysk na kliencie: `WINDOWED 1`, mała rozdzielczość (800×600), `SHADOW_LEVEL 0` (w nowych klientach też `SHADOW_TARGET_LEVEL`/`SHADOW_QUALITY_LEVEL 0`), `VISIBILITY` 1–2, `EFFECT_LEVEL`, `PRIVATE_SHOP_LEVEL`, `DROP_ITEM_LEVEL` 0, muzyka 0. Forum Metin2 wskazuje wyłączenie cieni jako najskuteczniejszą zmianę. | Średni: to edycja pliku gry. Plik jest wspólny dla klientów z tego samego katalogu (osobny dla instancji w Sandboxie / GfMultibox), a klucze różnią się między serwerami. Plik trzeba oznaczyć jako tylko do odczytu, bo gra go nadpisuje. | **Tak, jako osobny przycisk** „Zastosuj lekki profil grafiki” z kopią zapasową. Poza modułem procesów. |
| **Automatyczne wyciszenie klientów w tle** | Mniej pracy wątku dźwięku i brak trzasków przy limicie FPS. | Średni (API miksera Windows, `ISimpleAudioVolume`). | Miłe w użyciu, niewielki zysk wydajności. |
| **Stopniowe uruchamianie klientów** | Start klienta (ładowanie zasobów) to szczyt CPU i dysku. Kilka naraz = zacięcia i rozłączenia. | M2Watcher nie uruchamia gry. Robi to np. GfMultibox (odstęp przy starcie zbiorczym). | Poza zakresem M2Watchera. |
| **Wyłączenie „zdławienia” samego M2Watchera** | Windows 11 zwalnia zegar i obniża QoS zminimalizowanym aplikacjom. | Już zrobione: dławik ustawia sobie HighQoS i `IGNORE_TIMER_RESOLUTION`, a jego wątek ma wysoki priorytet. | Zrobione. |

### Rzeczy spoza aplikacji, które warto znać

- **NVIDIA: „Background Application Max Frame Rate”** (Panel sterowania NVIDIA → Zarządzaj
  ustawieniami 3D → Ustawienia programu → `metin2client.exe`). Sterownik ogranicza FPS okien
  w tle. Działa dla całego pliku exe, bez wybierania pojedynczych klientów, oszczędza tylko GPU,
  a przy włączonym G-Sync/VRR jest wyłączone. Dobrze łączy się z limitem M2Watchera.
  **AMD:** Radeon Chill / Frame Rate Target Control. **RTSS:** limit dla exe, ale działa przez
  wstrzyknięcie do procesu.
- **Plan zasilania „Wysoka wydajność”** i wyłączenie parkowania rdzeni na komputerze
  stacjonarnym. Mniej opóźnień przy budzeniu rdzeni.
- **Windows 11 a zegar systemowy:** od Windows 11 zminimalizowane lub zasłonięte okna nie
  dostają podwyższonej rozdzielczości zegara. Dla klientów w tle to korzystne (rzadsze
  wybudzenia).
- **Czego nie robić:** twardych limitów pamięci (Job Object) i agresywnego czyszczenia working
  setu. Brak pamięci w kliencie 32-bitowym to crash, a nie spowolnienie. Nie odblokowuj też
  limitu 60 FPS: więcej klatek to więcej CPU, a poprawka krążąca na forach jest oznaczona jako
  błędna.

### Źródła

- [Metin2 UK — The game consuming a lot of CPU](https://board.en.metin2.gameforge.com/index.php?thread%2F98670-the-game-consuming-a-lot-of-cpu-what-happened-in-span-of-a-few-days%2F=) — zminimalizowane klienty zużywają CPU jak widoczne
- [Metin2 Beta — Game Performance](https://board.beta.metin2.gameforge.com/index.php/Thread/87-Game-Performance/) — wyłączenie cieni
- [Metin2Dev — 60 fps limit](https://metin2.dev/topic/16418-60-fps-limit/), [Maximum FPS to 250](https://metin2.dev/topic/23352-maximum-fps-to-250/) — domyślny limit 60 FPS
- [nicolasCDT/Metin2_config](https://github.com/nicolasCDT/Metin2_config) — klucze `metin2.cfg`
- [BES — Battle Encoder Shirasé](https://mion.yosei.fi/BES/) — ograniczanie CPU przez wstrzymywanie procesu
- [Bitsum — CPU affinities](https://bitsum.com/cpu-affinities/), [Process Lasso FAQ](https://bitsum.com/process-lasso-faq/), [CPU Limiter](https://bitsum.com/docs/limiting-cpu-use-with-process-lasso-cpu-limiter/) — affinity i priorytet „Poniżej normalnego”
- [Microsoft — SetProcessInformation](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-setprocessinformation) — EcoQoS, priorytet pamięci
- [Microsoft — MEMORY_PRIORITY_INFORMATION](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/ns-processthreadsapi-memory_priority_information)
- [Microsoft — timeBeginPeriod](https://learn.microsoft.com/en-us/windows/win32/api/timeapi/nf-timeapi-timebeginperiod), [Bruce Dawson — Windows Timer Resolution: The Great Rule Change](https://randomascii.wordpress.com/2020/10/04/windows-timer-resolution-the-great-rule-change/)
- [NVIDIA — Manage 3D Settings (Background Application Max Frame Rate)](https://www.nvidia.com/content/Control-Panel-Help/vLatest/en-us/mergedProjects/3D%20Settings/Manage_3D_Settings_(reference).htm)
