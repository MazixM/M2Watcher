"""
M2Watcher - Monitor klientów Metin2
Monitoruje procesy Metin2 i wykrywa zamknięcia oraz wylogowania
"""

import psutil
import time
import sys
import platform
import threading
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

# Import dla dźwięku
try:
    if platform.system() == 'Windows':
        import winsound
        SOUND_AVAILABLE = True
    else:
        SOUND_AVAILABLE = False
except ImportError:
    SOUND_AVAILABLE = False

try:
    import win32gui
    import win32process
    WIN32_AVAILABLE = True
except ImportError:
    WIN32_AVAILABLE = False
    print("Ostrzeżenie: win32gui nie jest dostępne. Wykrywanie wylogowań może być ograniczone.")


@dataclass
class Metin2Client:
    """Reprezentuje klienta Metin2"""
    pid: int
    name: str
    window_title: str
    start_time: datetime
    last_check: datetime
    is_logged_in: bool = True
    network_activity_history: List[int] = None  # Historia aktywności sieciowej
    last_network_bytes: int = 0
    num_connections: int = 0  # Liczba aktywnych połączeń sieciowych
    window_handle: Optional[int] = None  # Handle do głównego okna gry
    window_size: Optional[Tuple[int, int]] = None  # Rozmiar okna (width, height)
    
    def __post_init__(self):
        if self.network_activity_history is None:
            self.network_activity_history = []
    
    def __str__(self):
        status = "Zalogowany" if self.is_logged_in else "Wylogowany"
        connections_info = f"({self.num_connections} połączeń)" if self.num_connections > 0 else "(brak połączeń)"
        return f"PID: {self.pid} | {self.name} | {self.window_title} | {status} {connections_info}"


class Metin2Watcher:
    """Główna klasa monitorująca klienty Metin2"""
    
    # Możliwe nazwy procesów Metin2
    METIN2_PROCESS_NAMES = [
        'metin2client.exe',
    ]
    
    # Tytuły okien wskazujące na ekran logowania/wylogowanie
    LOGIN_SCREEN_INDICATORS = [
        'metin2',
        'login',
        'logowanie',
        'select server',
        'wybierz serwer'
    ]
    
    def __init__(self, check_interval: float = 2.0, network_check_samples: int = 5, 
                 network_threshold: int = 1000, debug: bool = False, sound_enabled: bool = True,
                 sound_wait_for_input: bool = True):
        """
        Inicjalizuje monitor
        
        Args:
            check_interval: Czas między sprawdzeniami w sekundach
            network_check_samples: Liczba próbek aktywności sieciowej do analizy
            network_threshold: Próg aktywności sieciowej (bajty) - poniżej tego uznaje za wylogowanie
            debug: Czy wyświetlać informacje debugowania
            sound_enabled: Czy odtwarzać dźwięk przy wylogowaniu
            sound_wait_for_input: Czy dźwięk ma się powtarzać aż użytkownik naciśnie Enter
        """
        self.check_interval = check_interval
        self.network_check_samples = network_check_samples
        self.network_threshold = network_threshold
        self.debug = debug
        self.sound_enabled = sound_enabled and SOUND_AVAILABLE
        self.sound_wait_for_input = sound_wait_for_input
        self.clients: Dict[int, Metin2Client] = {}
        self.running = False
    
    def _play_sound_loop(self, stop_event):
        """Odtwarza dźwięk w pętli aż do zatrzymania"""
        try:
            if platform.system() == 'Windows' and SOUND_AVAILABLE:
                while not stop_event.is_set():
                    # Odtwórz trzy krótkie beepy
                    for i in range(3):
                        if stop_event.is_set():
                            break
                        winsound.Beep(800, 200)
                        if i < 2:  # Nie czekaj po ostatnim beepie
                            time.sleep(0.1)  # Krótka przerwa między beepami
                    # Przerwa przed następnym cyklem
                    if not stop_event.is_set():
                        time.sleep(0.5)
        except Exception:
            pass
    
    def play_logout_sound(self, wait_for_input: bool = True):
        """
        Odtwarza dźwięk powiadomienia o wylogowaniu.
        Jeśli wait_for_input=True, dźwięk będzie się powtarzał aż użytkownik naciśnie Enter.
        Zwraca True jeśli dźwięk został odtworzony, False w przeciwnym razie.
        """
        if not self.sound_enabled:
            return False
        
        try:
            if platform.system() == 'Windows' and SOUND_AVAILABLE:
                if wait_for_input:
                    # Utwórz event do zatrzymania dźwięku
                    stop_event = threading.Event()
                    
                    # Uruchom dźwięk w osobnym wątku
                    sound_thread = threading.Thread(target=self._play_sound_loop, args=(stop_event,), daemon=True)
                    sound_thread.start()
                    
                    # Wyświetl komunikat i czekaj na input
                    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] [UWAGA] Naciśnij Enter aby zatrzymać dźwięk powiadomienia...")
                    try:
                        input()  # Czeka na Enter
                    except (EOFError, KeyboardInterrupt):
                        pass
                    
                    # Zatrzymaj dźwięk
                    stop_event.set()
                    sound_thread.join(timeout=1.0)  # Czekaj max 1 sekundę na zakończenie wątku
                    return True
                else:
                    # Tylko jeden cykl dźwięku
                    for i in range(3):
                        winsound.Beep(800, 200)
                        if i < 2:
                            time.sleep(0.1)
                    return True
        except Exception as e:
            # W przypadku błędu, spróbuj alternatywnego dźwięku
            try:
                winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
                return True
            except:
                # Jeśli wszystko zawiedzie, spróbuj prostego beep
                try:
                    winsound.Beep(1000, 500)
                    return True
                except:
                    return False
        return False
    
    def handle_client_closed(self, client: Metin2Client, reason: str):
        """
        Obsługuje zamknięcie klienta - wyświetla komunikat i odtwarza dźwięk.
        
        Args:
            client: Klient który został zamknięty
            reason: Powód zamknięcia (np. "proces zakończony", "okno zamknięte")
        """
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [UWAGA] Klient zamknięty ({reason}): {client}")
        # Odtwórz dźwięk powiadomienia (tak samo jak przy wylogowaniu)
        if self.play_logout_sound(wait_for_input=self.sound_wait_for_input):
            if not self.sound_wait_for_input:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] [DŹWIĘK] Odtworzono powiadomienie dźwiękowe")
        
    def find_metin2_processes(self) -> List[psutil.Process]:
        """Znajduje wszystkie uruchomione procesy Metin2"""
        processes = []
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                proc_name = proc.info['name'].lower()
                if any(metin2_name.lower() in proc_name for metin2_name in self.METIN2_PROCESS_NAMES):
                    processes.append(proc)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return processes
    
    def get_window_info(self, pid: int) -> Tuple[Optional[int], Optional[str], Optional[Tuple[int, int]]]:
        """
        Pobiera informacje o oknie dla danego procesu.
        Zwraca: (handle, title, size) lub (None, None, None) jeśli nie znaleziono
        """
        if not WIN32_AVAILABLE:
            return None, None, None
            
        window_info = []
        
        def callback(hwnd, windows):
            try:
                _, found_pid = win32process.GetWindowThreadProcessId(hwnd)
                if found_pid == pid:
                    # Sprawdź czy to jest główne okno (ma tytuł i jest widoczne lub ma rozmiar)
                    title = win32gui.GetWindowText(hwnd)
                    rect = win32gui.GetWindowRect(hwnd)
                    width = rect[2] - rect[0]
                    height = rect[3] - rect[1]
                    
                    # Filtruj bardzo małe okna (prawdopodobnie nie są głównym oknem gry)
                    if width > 100 and height > 100:
                        # Preferuj widoczne okna, ale zbieraj też niewidoczne
                        is_visible = win32gui.IsWindowVisible(hwnd)
                        windows.append((hwnd, title, (width, height), is_visible))
            except Exception:
                pass
        
        try:
            win32gui.EnumWindows(callback, window_info)
            if window_info:
                # Sortuj: najpierw widoczne, potem po rozmiarze
                window_info.sort(key=lambda x: (x[3], x[2][0] * x[2][1]), reverse=True)
                hwnd, title, size, _ = window_info[0]
                # Jeśli tytuł jest pusty, spróbuj pobrać klasę okna jako tytuł
                if not title or title.strip() == "":
                    try:
                        class_name = win32gui.GetClassName(hwnd)
                        title = f"[{class_name}]"
                    except Exception:
                        title = "Metin2"
                return hwnd, title, size
        except Exception as e:
            # Debug: można wykomentować w produkcji
            # print(f"Błąd podczas pobierania okna dla PID {pid}: {e}")
            pass
        
        return None, None, None
    
    def _find_any_window(self, pid: int) -> Tuple[Optional[int], Optional[str], Optional[Tuple[int, int]]]:
        """Znajduje jakiekolwiek okno procesu, nawet bardzo małe"""
        if not WIN32_AVAILABLE:
            return None, None, None
            
        window_info = []
        
        def callback(hwnd, windows):
            try:
                _, found_pid = win32process.GetWindowThreadProcessId(hwnd)
                if found_pid == pid:
                    title = win32gui.GetWindowText(hwnd)
                    rect = win32gui.GetWindowRect(hwnd)
                    width = rect[2] - rect[0]
                    height = rect[3] - rect[1]
                    # Przyjmij nawet małe okna
                    if width > 50 and height > 50:
                        is_visible = win32gui.IsWindowVisible(hwnd)
                        windows.append((hwnd, title, (width, height), is_visible))
            except Exception:
                pass
        
        try:
            win32gui.EnumWindows(callback, window_info)
            if window_info:
                window_info.sort(key=lambda x: (x[3], x[2][0] * x[2][1]), reverse=True)
                hwnd, title, size, _ = window_info[0]
                if not title or title.strip() == "":
                    try:
                        class_name = win32gui.GetClassName(hwnd)
                        title = f"[{class_name}]"
                    except Exception:
                        title = "Metin2"
                return hwnd, title, size
        except Exception:
            pass
        
        return None, None, None
    
    def get_window_title(self, pid: int) -> Optional[str]:
        """Pobiera tytuł okna dla danego procesu (zachowana dla kompatybilności)"""
        _, title, _ = self.get_window_info(pid)
        return title
    
    def is_window_closed(self, hwnd: Optional[int]) -> bool:
        """Sprawdza czy okno zostało zamknięte"""
        if not WIN32_AVAILABLE or hwnd is None:
            return False
        
        try:
            # Sprawdź czy okno nadal istnieje
            return not win32gui.IsWindow(hwnd)
        except Exception:
            return True
    
    def is_login_screen_visible(self, hwnd: Optional[int], window_size: Optional[Tuple[int, int]]) -> bool:
        """
        Sprawdza czy widoczny jest ekran logowania na podstawie właściwości okna.
        Ekran logowania Metin2 ma charakterystyczne właściwości:
        - Okno nadal istnieje (nie jest zamknięte)
        - Może mieć inny rozmiar niż podczas gry
        - Może mieć charakterystyczną klasę okna
        """
        if not WIN32_AVAILABLE or hwnd is None:
            return False
        
        try:
            # Sprawdź czy okno nadal istnieje
            if not win32gui.IsWindow(hwnd):
                return False
            
            # Sprawdź czy okno jest widoczne
            if not win32gui.IsWindowVisible(hwnd):
                return False
            
            # Sprawdź rozmiar okna - ekran logowania może mieć inny rozmiar
            # (to wymaga dostosowania do konkretnych serwerów)
            # Na razie zakładamy że jeśli okno istnieje i jest widoczne,
            # ale aktywność sieciowa jest zerowa, to może być ekran logowania
            
            # Możemy też sprawdzić klasę okna
            try:
                class_name = win32gui.GetClassName(hwnd)
                # Niektóre ekrany logowania mogą mieć charakterystyczne klasy
                # (wymaga dostosowania)
            except Exception:
                pass
            
            # Główna logika: jeśli okno istnieje, ale aktywność sieciowa jest zerowa,
            # prawdopodobnie jest to ekran logowania
            # Ta metoda będzie używana w połączeniu z wykrywaniem sieciowym
            return False  # Domyślnie nie wykrywamy ekranu logowania tylko po oknie
            
        except Exception:
            return False
    
    def get_network_activity(self, proc: psutil.Process) -> Tuple[int, int]:
        """
        Pobiera aktywność sieciową procesu.
        Zwraca: (total_bytes, num_connections)
        """
        total_bytes = 0
        num_connections = 0
        
        try:
            io_counters = proc.io_counters()
            if io_counters:
                # Suma wysłanych i odebranych bajtów
                total_bytes = io_counters.bytes_sent + io_counters.bytes_recv
        except (psutil.NoSuchProcess, psutil.AccessDenied, AttributeError):
            pass
        
        try:
            # Sprawdź liczbę aktywnych połączeń sieciowych
            connections = proc.net_connections()
            if connections:
                # Licz tylko ESTABLISHED połączenia
                num_connections = len([c for c in connections if c.status == 'ESTABLISHED'])
        except (psutil.NoSuchProcess, psutil.AccessDenied, AttributeError):
            pass
        
        return total_bytes, num_connections
    
    def is_logged_in_by_network(self, client: Metin2Client, current_bytes: int, num_connections: int) -> bool:
        """
        Sprawdza czy klient jest zalogowany na podstawie aktywności sieciowej.
        Główny wskaźnik: liczba aktywnych połączeń sieciowych (ESTABLISHED).
        Jeśli brak połączeń = wylogowany.
        """
        # Aktualizuj liczbę połączeń
        client.num_connections = num_connections
        
        # GŁÓWNY WSKAŹNIK: Jeśli brak połączeń sieciowych, klient jest wylogowany
        if num_connections == 0:
            return False
        
        # Dla nowych klientów (bez historii) zakładamy że są zalogowani
        # i zbieramy próbki przed oceną
        if client.last_network_bytes == 0:
            client.last_network_bytes = current_bytes
            return True  # Nowy klient z połączeniem - zakładamy że jest zalogowany
        
        # Oblicz zmianę aktywności sieciowej (różnica między sprawdzeniami)
        bytes_diff = current_bytes - client.last_network_bytes
        
        # Jeśli różnica jest ujemna (co może się zdarzyć przy restarcie licznika),
        # zresetuj historię
        if bytes_diff < 0:
            client.last_network_bytes = current_bytes
            client.network_activity_history.clear()
            return True  # Reset - zakładamy że jest zalogowany
        
        # Dodaj różnicę do historii
        client.network_activity_history.append(bytes_diff)
        
        # Zachowaj tylko ostatnie N próbek
        if len(client.network_activity_history) > self.network_check_samples:
            client.network_activity_history.pop(0)
        
        # Aktualizuj ostatnią wartość
        client.last_network_bytes = current_bytes
        
        # Jeśli mamy wystarczająco próbek, sprawdź aktywność
        if len(client.network_activity_history) >= self.network_check_samples:
            # Sprawdź czy ostatnie próbki pokazują brak aktywności
            recent_activity = client.network_activity_history[-self.network_check_samples:]
            total_recent_activity = sum(recent_activity)
            
            # Średnia aktywność na próbkę
            avg_activity = total_recent_activity / len(recent_activity)
            
            # Jeśli przez ostatnie próbki nie było żadnej aktywności sieciowej,
            # prawdopodobnie nastąpiło wylogowanie
            # Sprawdzamy zarówno całkowitą aktywność jak i średnią
            if total_recent_activity < self.network_threshold and avg_activity < (self.network_threshold / self.network_check_samples):
                return False
        
        # Jeśli nie mamy jeszcze wystarczająco próbek lub aktywność jest wystarczająca
        return True
    
    def is_logged_in(self, window_title: str) -> bool:
        """
        Sprawdza czy klient jest zalogowany na podstawie tytułu okna.
        UWAGA: Ta metoda może nie działać jeśli tytuł okna się nie zmienia.
        Używana jako metoda pomocnicza, główna metoda to is_logged_in_by_network.
        """
        if not window_title:
            return True  # Jeśli nie możemy sprawdzić, zakładamy że jest zalogowany
        
        title_lower = window_title.lower()
        
        # Jeśli tytuł zawiera wskaźniki ekranu logowania, użytkownik jest wylogowany
        for indicator in self.LOGIN_SCREEN_INDICATORS:
            if indicator in title_lower:
                # Ale sprawdźmy czy to nie jest normalny tytuł z "metin2" w nazwie
                # Ekran logowania zwykle ma specyficzne tytuły
                if 'select server' in title_lower or 'wybierz serwer' in title_lower:
                    return False
                # Jeśli tytuł jest bardzo krótki (tylko "metin2"), może to być ekran logowania
                if len(title_lower.split()) <= 2 and 'metin2' in title_lower:
                    return False
        
        # Jeśli tytuł zawiera nazwę postaci lub serwera, prawdopodobnie jest zalogowany
        # (to wymaga dostosowania do konkretnych serwerów)
        return True
    
    def update_clients(self):
        """Aktualizuje listę monitorowanych klientów"""
        current_processes = self.find_metin2_processes()
        current_pids = {proc.pid for proc in current_processes}
        
        # Sprawdź czy któryś klient się zamknął (proces zniknął)
        for pid in list(self.clients.keys()):
            if pid not in current_pids:
                client = self.clients[pid]
                self.handle_client_closed(client, "proces zakończony")
                del self.clients[pid]
        
        # Sprawdź czy okna istniejących klientów zostały zamknięte
        for pid, client in list(self.clients.items()):
            if pid in current_pids:  # Proces nadal istnieje
                if self.is_window_closed(client.window_handle):
                    self.handle_client_closed(client, "okno zamknięte")
                    del self.clients[pid]
        
        # Dodaj nowe klienty i zaktualizuj istniejące
        for proc in current_processes:
            try:
                pid = proc.pid
                name = proc.name()
                hwnd, window_title, window_size = self.get_window_info(pid)
                # Jeśli nie znaleziono okna, spróbuj jeszcze raz z mniejszymi wymaganiami
                if hwnd is None:
                    hwnd, window_title, window_size = self._find_any_window(pid)
                window_title = window_title or f"Metin2 (PID: {pid})"
                network_bytes, num_connections = self.get_network_activity(proc)
                
                if pid not in self.clients:
                    # Nowy klient
                    client = Metin2Client(
                        pid=pid,
                        name=name,
                        window_title=window_title,
                        start_time=datetime.now(),
                        last_check=datetime.now(),
                        is_logged_in=(num_connections > 0),  # Zalogowany jeśli ma połączenia
                        last_network_bytes=network_bytes,
                        num_connections=num_connections,
                        window_handle=hwnd,
                        window_size=window_size
                    )
                    self.clients[pid] = client
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] [OK] Nowy klient wykryty: {client}")
                else:
                    # Aktualizuj istniejący klient
                    client = self.clients[pid]
                    old_logged_in = client.is_logged_in
                    client.window_title = window_title
                    client.window_handle = hwnd
                    client.window_size = window_size
                    client.last_check = datetime.now()
                    
                    # Sprawdź status logowania na podstawie aktywności sieciowej
                    is_logged_in_network = self.is_logged_in_by_network(client, network_bytes, num_connections)
                    client.num_connections = num_connections
                    
                    # Sprawdź czy okno nadal istnieje (jeśli nie, to zamknięcie)
                    # Tylko jeśli wcześniej mieliśmy handle okna
                    if client.window_handle is not None and self.is_window_closed(client.window_handle):
                        # Okno zamknięte - to jest zamknięcie, nie wylogowanie
                        self.handle_client_closed(client, "okno zamknięte")
                        del self.clients[pid]
                        continue
                    
                    # Jeśli nie znaleziono okna, ale wcześniej było, może okno zostało zamknięte
                    if client.window_handle is not None and hwnd is None:
                        self.handle_client_closed(client, "okno zniknęło")
                        del self.clients[pid]
                        continue
                    
                    # Jeśli okno istnieje, ale aktywność sieciowa jest zerowa,
                    # prawdopodobnie jest to ekran logowania (wylogowanie)
                    # Użyj wykrywania sieciowego jako głównej metody
                    client.is_logged_in = is_logged_in_network
                    
                    # Sprawdź czy nastąpiło wylogowanie
                    if old_logged_in and not client.is_logged_in:
                        print(f"[{datetime.now().strftime('%H:%M:%S')}] [WYLOGOWANY] Wylogowanie wykryte (ekran logowania): {client}")
                        # Odtwórz dźwięk powiadomienia
                        if self.play_logout_sound(wait_for_input=self.sound_wait_for_input):
                            if not self.sound_wait_for_input:
                                print(f"[{datetime.now().strftime('%H:%M:%S')}] [DŹWIĘK] Odtworzono powiadomienie dźwiękowe")
                    elif not old_logged_in and client.is_logged_in:
                        print(f"[{datetime.now().strftime('%H:%M:%S')}] [ZALOGOWANY] Ponowne zalogowanie: {client}")
                        
            except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
                continue
    
    def print_status(self, debug: bool = False):
        """Wyświetla aktualny status wszystkich klientów"""
        if not self.clients:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Brak aktywnych klientów Metin2")
            return
        
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Status klientów ({len(self.clients)}):")
        for client in self.clients.values():
            status_icon = "[ZALOGOWANY]" if client.is_logged_in else "[WYLOGOWANY]"
            print(f"  {status_icon} {client}")
            if debug:
                # Wyświetl informacje debugowania
                recent_activity = sum(client.network_activity_history[-5:]) if len(client.network_activity_history) > 0 else 0
                print(f"      Debug: Aktywność sieciowa (ostatnie 5 próbek): {recent_activity} bajtów")
                print(f"      Debug: Historia próbek: {len(client.network_activity_history)}/{self.network_check_samples}")
        print()
    
    def run(self, show_status: bool = True):
        """Uruchamia monitor w pętli"""
        self.running = True
        print("=" * 60)
        print("M2Watcher - Monitor klientów Metin2")
        print("=" * 60)
        print(f"Sprawdzanie co {self.check_interval} sekund...")
        if self.sound_enabled:
            if self.sound_wait_for_input:
                print("Dźwięk powiadomień: WŁĄCZONY (powtarza się aż do naciśnięcia Enter)")
            else:
                print("Dźwięk powiadomień: WŁĄCZONY (tylko raz)")
        else:
            print("Dźwięk powiadomień: WYŁĄCZONY")
        print("Naciśnij Ctrl+C aby zatrzymać\n")
        
        try:
            while self.running:
                self.update_clients()
                if show_status and self.clients:
                    self.print_status(debug=self.debug)
                time.sleep(self.check_interval)
        except KeyboardInterrupt:
            print("\n\nZatrzymywanie monitora...")
            self.running = False


def main():
    """Główna funkcja programu"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Monitor klientów Metin2')
    parser.add_argument(
        '-i', '--interval',
        type=float,
        default=2.0,
        help='Interwał sprawdzania w sekundach (domyślnie: 2.0)'
    )
    parser.add_argument(
        '-q', '--quiet',
        action='store_true',
        help='Tryb cichy - wyświetla tylko ważne wydarzenia'
    )
    parser.add_argument(
        '-s', '--samples',
        type=int,
        default=5,
        help='Liczba próbek aktywności sieciowej do analizy (domyślnie: 5)'
    )
    parser.add_argument(
        '-t', '--threshold',
        type=int,
        default=1000,
        help='Próg aktywności sieciowej w bajtach - poniżej tego uznaje za wylogowanie (domyślnie: 1000)'
    )
    parser.add_argument(
        '-d', '--debug',
        action='store_true',
        help='Tryb debugowania - wyświetla dodatkowe informacje o aktywności sieciowej'
    )
    parser.add_argument(
        '--no-sound',
        action='store_true',
        help='Wyłącza odtwarzanie dźwięku przy wylogowaniu'
    )
    parser.add_argument(
        '--sound-once',
        action='store_true',
        help='Odtwarza dźwięk tylko raz (nie czeka na Enter)'
    )
    
    args = parser.parse_args()
    
    watcher = Metin2Watcher(
        check_interval=args.interval,
        network_check_samples=args.samples,
        network_threshold=args.threshold,
        debug=args.debug,
        sound_enabled=not args.no_sound,
        sound_wait_for_input=not args.sound_once
    )
    watcher.run(show_status=not args.quiet)


if __name__ == '__main__':
    main()

