# M2Watcher - Monitor klientów Metin2

Program do monitorowania klientów gry Metin2. Wykrywa zamknięcia klientów oraz wylogowania.

## Funkcje

- ✅ Automatyczne wykrywanie uruchomionych klientów Metin2
- ⚠️ Wykrywanie zamknięcia klienta (proces lub okno)
- 🔴 Wykrywanie wylogowania (ekran logowania - okno istnieje, ale brak aktywności sieciowej)
- 🟢 Wykrywanie ponownego zalogowania
- 📊 Wyświetlanie statusu wszystkich klientów
- 🔍 Monitorowanie aktywności sieciowej każdego klienta
- 🪟 Sprawdzanie stanu okien gry (czy istnieją, rozmiar, itp.)

## Wymagania

- Python 3.7+
- Windows (wymagane dla pełnej funkcjonalności wykrywania wylogowań)

## Instalacja

1. Zainstaluj wymagane biblioteki:
```bash
pip install -r requirements.txt
```

## Użycie

### Podstawowe użycie:
```bash
python m2watcher.py
```

### Z niestandardowym interwałem sprawdzania:
```bash
python m2watcher.py -i 5.0
```

### Tryb cichy (tylko ważne wydarzenia):
```bash
python m2watcher.py -q
```

### Z dostosowanymi parametrami wykrywania wylogowania:
```bash
# Więcej próbek (bardziej precyzyjne, ale wolniejsze wykrywanie)
python m2watcher.py -s 10

# Niższy próg (bardziej wrażliwe na wylogowania)
python m2watcher.py -t 500

# Kombinacja parametrów
python m2watcher.py -s 7 -t 2000
```

## Opcje

- `-i, --interval` - Interwał sprawdzania w sekundach (domyślnie: 2.0)
- `-q, --quiet` - Tryb cichy - wyświetla tylko ważne wydarzenia
- `-s, --samples` - Liczba próbek aktywności sieciowej do analizy (domyślnie: 5)
- `-t, --threshold` - Próg aktywności sieciowej w bajtach - poniżej tego uznaje za wylogowanie (domyślnie: 1000)

## Jak działa

Program monitoruje procesy systemowe i wykrywa procesy Metin2 na podstawie nazw:
- `metin2client.exe`
- `metin2client_dx9.exe`
- `metin2client_dx11.exe`
- `metin2.exe`
- `client.exe`

Dla każdego wykrytego klienta:
1. Sprawdza czy proces nadal działa (wykrywanie zamknięcia)
2. Sprawdza tytuł okna gry (wykrywanie wylogowania)
3. Wyświetla status i powiadamia o zmianach

## Wykrywanie zamknięcia i wylogowania

Program używa **dwóch metod** do wykrywania stanu klientów:

### 1. Wykrywanie zamknięcia klienta
- **Zamknięcie procesu**: Gdy proces Metin2 zakończy działanie
- **Zamknięcie okna**: Gdy okno gry zostanie zamknięte (handler okna znika), ale proces może jeszcze działać

### 2. Wykrywanie wylogowania
Program wykrywa wylogowanie na podstawie **aktywności sieciowej** i **stanu okna**:
- Gdy gracz jest zalogowany, klient Metin2 utrzymuje aktywne połączenie z serwerem (wysyła i odbiera dane)
- Gdy nastąpi wylogowanie, pojawia się ekran logowania - okno nadal istnieje, ale aktywność sieciowa spada do zera
- Program monitoruje ilość danych wysyłanych i odbieranych przez proces Metin2
- Jeśli przez określoną liczbę próbek (domyślnie 5) aktywność sieciowa jest poniżej progu (domyślnie 1000 bajtów), a okno nadal istnieje, uznaje to za wylogowanie
- Po ponownym zalogowaniu aktywność sieciowa wzrasta i program wykrywa ponowne zalogowanie

**Dostosowanie:**
- `-s, --samples` - liczba próbek do analizy (domyślnie: 5)
- `-t, --threshold` - próg aktywności sieciowej w bajtach (domyślnie: 1000)

Jeśli program zbyt często lub zbyt rzadko wykrywa wylogowania, możesz dostosować te parametry.

## Przykładowy output

```
============================================================
M2Watcher - Monitor klientów Metin2
============================================================
Sprawdzanie co 2.0 sekund...
Naciśnij Ctrl+C aby zatrzymać

[14:30:15] ✅ Nowy klient wykryty: PID: 1234 | metin2client.exe | Metin2 - Serwer | Zalogowany
[14:30:17] Status klientów (1):
  🟢 PID: 1234 | metin2client.exe | Metin2 - Serwer | Zalogowany

[14:35:20] 🔴 Wylogowanie wykryte (ekran logowania): PID: 1234 | metin2client.exe | Metin2 | Wylogowany
[14:36:10] 🟢 Ponowne zalogowanie: PID: 1234 | metin2client.exe | Metin2 - Serwer | Zalogowany
[14:40:15] ⚠️  Klient zamknięty (okno zamknięte): PID: 1234 | metin2client.exe | Metin2 | Zalogowany
```

## Rozwiązywanie problemów

**Program nie wykrywa wylogowań:**
- Zwiększ liczbę próbek: `-s 10` (daje więcej czasu na wykrycie)
- Obniż próg: `-t 500` (bardziej wrażliwe)
- Sprawdź czy proces Metin2 rzeczywiście przestaje komunikować się z serwerem po wylogowaniu

**Program zbyt często wykrywa wylogowania (fałszywe alarmy):**
- Zwiększ próg: `-t 2000` (wymaga więcej aktywności)
- Zwiększ liczbę próbek: `-s 7` (daje więcej czasu na ocenę)

**Program nie wykrywa klientów:**
- Sprawdź czy nazwa procesu Metin2 jest na liście obsługiwanych (możesz dodać własną w kodzie)
- Uruchom jako administrator jeśli masz problemy z dostępem do procesów

## Licencja

Wolne użycie do celów osobistych.

