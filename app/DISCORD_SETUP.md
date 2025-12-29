# Instrukcja konfiguracji bota Discord dla M2Watcher

## Krok 1: Utworzenie aplikacji bota na Discord Developer Portal

1. Przejdź na stronę: https://discord.com/developers/applications
2. Zaloguj się do swojego konta Discord
3. Kliknij przycisk **"New Application"** (Nowa aplikacja)
4. Wprowadź nazwę aplikacji (np. "M2Watcher Bot") i kliknij **"Create"**

## Krok 2: Utworzenie bota

1. W menu po lewej stronie wybierz **"Bot"**
2. W sekcji **"Token"** kliknij **"Reset Token"** lub **"Copy"** aby skopiować token bota
   - ⚠️ **WAŻNE**: Zapisz ten token w bezpiecznym miejscu! Będzie potrzebny w konfiguracji.
   - Token wygląda mniej więcej tak: `MTIzNDU2Nzg5MDEyMzQ1Njc4OTA.Xxxxxx.xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`

## Krok 3: Utworzenie własnego serwera Discord

1. W aplikacji Discord kliknij przycisk **"+"** (Dodaj serwer)
2. Wybierz **"Stwórz swój własny"**
3. Nadaj serwerowi nazwę (np. "M2Watcher Notifications")
4. Kliknij **"Utwórz"**

**Uwaga:** Każdy użytkownik musi mieć swój własny serwer Discord dla powiadomień.

## Krok 4: Dodanie bota na serwer

1. W menu po lewej stronie wybierz **"OAuth2"** → **"OAuth2 URL Generator"**
2. W sekcji **"SCOPES"** zaznacz:
   - ✅ **bot**
3. W sekcji **"BOT PERMISSIONS"** zaznacz:
   - ✅ **Send Messages**
4. Skopiuj wygenerowany URL (znajduje się na dole strony)
5. Otwórz ten URL w przeglądarce
6. Wybierz serwer, na którym chcesz dodać bota
7. Kliknij **"Authorize"** i potwierdź

## Krok 5: Pobranie ID serwera (Guild ID)

1. Włącz tryb deweloperski w Discord:
   - Otwórz Discord
   - Przejdź do **Ustawienia** → **Zaawansowane** → **Tryb deweloperski** (włącz)
2. Na serwerze Discord kliknij prawym przyciskiem myszy na nazwę serwera
3. Wybierz **"Kopiuj ID"** (Copy ID)
   - To jest Twoje **Guild ID**

## Krok 6: Pobranie ID użytkownika (User ID)

1. Upewnij się, że tryb deweloperski jest włączony (patrz Krok 5)
2. Kliknij prawym przyciskiem myszy na swoje imię/avatar w Discord
3. Wybierz **"Kopiuj ID"** (Copy ID)
   - To jest Twoje **User ID**

## Krok 7: Pobranie ID kanału (Channel ID) - opcjonalne, gdy chcemy mieć powiadomienie na 

1. Upewnij się, że tryb deweloperski jest włączony
2. Na swoim serwerze Discord kliknij prawym przyciskiem myszy na kanał, do którego chcesz otrzymywać powiadomienia
3. Wybierz **"Kopiuj ID"** (Copy ID)
   - To jest **Channel ID**
   - **Uwaga:** Jeśli nie podasz `channel_id`, bot wyśle powiadomienia przez DM (prywatną wiadomość)

## Krok 8: Konfiguracja w M2Watcher

1. Otwórz plik konfiguracyjny:
   - Windows: `C:\Users\[TwojaNazwaUżytkownika]\.m2watcher\config.json`

2. Zaktualizuj sekcję `discord` w pliku `config.json`:

```json
{
  "discord": {
    "enabled": true,
    "bot_token": "TWÓJ_BOT_TOKEN_TUTAJ",
    "guild_id": "TWÓJ_GUILD_ID_TUTAJ",
    "user_id": "TWÓJ_USER_ID_TUTAJ",
    "channel_id": "TWÓJ_CHANNEL_ID_TUTAJ"
  }
}
```

**Przykład z kanałem:**
```json
{
  "discord": {
    "enabled": true,
    "bot_token": "MTIzNDU2Nzg5MDEyMzQ1Njc4OTA.Xxxxxx.xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    "guild_id": "123456789012345678",
    "user_id": "987654321098765432",
    "channel_id": "111111111111111111"
  }
}
```

**Przykład bez kanału (powiadomienia przez DM):**
```json
{
  "discord": {
    "enabled": true,
    "bot_token": "MTIzNDU2Nzg5MDEyMzQ1Njc4OTA.Xxxxxx.xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    "guild_id": "123456789012345678",
    "user_id": "987654321098765432",
    "channel_id": ""
  }
}
```

**Uwaga:** Jeśli `channel_id` jest pusty, bot automatycznie wyśle powiadomienia przez DM (prywatną wiadomość).

## Krok 10: Uruchomienie bota

1. Uruchom aplikację M2Watcher
2. Bot powinien automatycznie połączyć się z serwerem Discord
3. W konsoli powinieneś zobaczyć: `Bot Discord zalogowany jako [Nazwa Bota]`
4. Powiadomienia będą automatycznie wysyłane do kanału z `channel_id` lub przez DM

## Rozwiązywanie problemów

### Bot nie łączy się z serwerem
- Sprawdź czy token bota jest poprawny
- Upewnij się, że bot został dodany na serwer (Krok 4)
- Sprawdź czy `guild_id` jest poprawne

### Bot nie odpowiada na komendy
- Upewnij się, że bot ma uprawnienia do czytania i wysyłania wiadomości
- Sprawdź czy bot jest online na serwerze

### Nie można utworzyć kanału
- Upewnij się, że bot ma uprawnienie **"Manage Channels"**
- Sprawdź czy bot ma odpowiednie uprawnienia w kategorii

### Powiadomienia nie przychodzą
- Sprawdź czy `user_id` w konfiguracji jest poprawne
- Sprawdź czy `channel_id` jest poprawne (lub zostaw puste dla DM)
- Sprawdź czy bot jest uruchomiony (powinien być widoczny jako online na serwerze)
- Jeśli używasz DM, upewnij się, że bot może wysyłać Ci wiadomości (sprawdź ustawienia prywatności Discord)

## Bezpieczeństwo

⚠️ **WAŻNE**: Nigdy nie udostępniaj swojego tokenu bota publicznie!
- Token bota daje pełny dostęp do bota
- Jeśli token zostanie skradziony, natychmiast zresetuj go w Discord Developer Portal
- Nie commituj pliku `config.json` z tokenem do repozytorium Git

