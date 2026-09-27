# Powiadomienia Discord: konfiguracja

Są dwa sposoby. **Wybierz webhook.** To jeden adres do skopiowania, bez tworzenia bota. Bot jest potrzebny tylko wtedy, gdy chcesz dostawać wiadomości **prywatne** (DM).

---

## Sposób 1: Webhook (zalecany, ok. 1 minuta)

### 1. Własny serwer Discord
Masz już swój serwer? Przejdź do kroku 2. Jeśli nie: w Discordzie kliknij **„+”** (Dodaj serwer) → **„Stwórz własny”** → **„Dla mnie i znajomych”** → nadaj nazwę, np. „M2Watcher”.

### 2. Utwórz webhook
1. Najedź na kanał tekstowy (np. `#ogólny`) i kliknij **⚙ (Edytuj kanał)**.
2. **Integracje** → **Webhooki** → **Nowy webhook**.
3. Kliknij utworzony webhook i **„Kopiuj adres URL webhooka”**.

Adres wygląda tak: `https://discord.com/api/webhooks/123456789012345678/AbCdEf...`

### 3. Wklej w M2Watcher
W kreatorze (albo w **⚙ Ustawienia → Discord**):
1. wybierz **Webhook**,
2. wklej adres w pole **Adres URL webhooka**,
3. kliknij **Wyślij wiadomość testową**. Na kanale powinna pojawić się wiadomość z nazwą Twojego urządzenia.

### 4. (Zalecane) Oznaczanie, żeby telefon zadzwonił
Gdy wiadomość Cię oznacza (@), Discord powiadomi Cię nawet przy wyciszonym kanale.
1. Discord → **Ustawienia użytkownika → Zaawansowane → Tryb dewelopera** (włącz).
2. Kliknij prawym przyciskiem na swój nick → **„Kopiuj ID użytkownika”**.
3. Wklej w M2Watcher w pole **Twoje ID użytkownika** i zostaw zaznaczone **Oznaczaj mnie (@)**.

> Adres webhooka traktuj jak hasło: kto go zna, może pisać na Twój kanał. Jeśli wycieknie, usuń webhook w Discordzie i utwórz nowy.

---

## Sposób 2: Bot (wiadomości prywatne, dla zaawansowanych)

> Discord pozwala botowi wysyłać wiadomości dopiero wtedy, gdy choć raz połączył się z Discordem na żywo (gateway). Boty używane w starszej wersji M2Watcher spełniają ten warunek. Nowy bot może zwrócić błąd „Ten bot nigdy nie połączył się z Discordem”; wtedy użyj webhooka.

1. Wejdź na https://discord.com/developers/applications → **New Application** → nadaj nazwę.
2. Zakładka **Bot** → **Reset Token** → skopiuj token. *Intenty uprzywilejowane nie są potrzebne.*
3. Zakładka **OAuth2 → URL Generator**: zaznacz scope **bot** i uprawnienie **Send Messages**. Otwórz wygenerowany link i dodaj bota na swój serwer. Bot musi mieć z Tobą wspólny serwer, żeby mógł napisać prywatnie.
4. W M2Watcher: **⚙ Ustawienia → Discord → Bot Discord**:
   - **Token bota**: wklej token,
   - **ID kanału**: zostaw puste, jeśli chcesz DM, albo wpisz ID kanału (prawy klik na kanał → „Kopiuj ID kanału”),
   - **Twoje ID użytkownika**: wymagane dla DM (patrz krok 4 w sposobie 1).
5. Kliknij **Wyślij wiadomość testową**.

> Starsze wersje M2Watcher używały bota z `guild_id`. Twoja konfiguracja zostanie przeniesiona automatycznie; przy pierwszym starcie nowej wersji pokaże się kreator, żeby uzupełnić nazwę urządzenia.

---

## Kilka komputerów

Na każdym komputerze wpisz **inną nazwę urządzenia**. Wszystkie mogą używać tego samego webhooka. W każdej wiadomości zobaczysz np. „🔴 Wylogowanie — Laptop”.

## Brak internetu

Jeśli internet zniknie, powiadomienia **nie przepadają**. Karta „Discord” w oknie aplikacji pokaże „Brak połączenia • N w kolejce”, a wiadomości wyjdą same, gdy sieć wróci (także po restarcie aplikacji). Wiadomość wysłana z opóźnieniem ma w stopce dopisek, o ile minut się spóźniła; godzina wykrycia jest w polu „Wykryto”.

## Rozwiązywanie problemów

| Komunikat | Co zrobić |
|---|---|
| `HTTP 404: nie znaleziono webhooka/kanału` | Webhook został usunięty albo adres jest ucięty. Skopiuj go ponownie. |
| `HTTP 401: nieprawidłowy token bota` | Zresetuj token w Developer Portal i wklej nowy. |
| `HTTP 403: bot nie ma uprawnień…` | Dodaj botowi uprawnienie *Send Messages* do kanału. Przy DM: bot musi być na wspólnym serwerze, a Ty musisz mieć włączone „Wiadomości prywatne od członków serwera”. |
| `Brak połączenia z Discordem` | Sprawdź internet. Powiadomienia czekają w kolejce; „Ponów teraz” wymusza próbę od razu. |

Jeśli dalej nie działa: **Otwórz folder logów** w aplikacji i dołącz `m2watcher.log` do zgłoszenia na GitHubie.
