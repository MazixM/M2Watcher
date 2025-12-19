"""
M2Diagnostic - Narzędzie diagnostyczne do analizy klientów Metin2
Pomaga zidentyfikować różnice między zalogowanymi a wylogowanymi klientami
"""

import psutil
import sys
from typing import List, Dict, Optional, Tuple
from datetime import datetime

try:
    import win32gui
    import win32process
    import win32con
    WIN32_AVAILABLE = True
except ImportError:
    WIN32_AVAILABLE = False
    print("UWAGA: win32gui nie jest dostępne. Zainstaluj: pip install pywin32")


def get_all_windows_for_process(pid: int) -> List[Dict]:
    """Pobiera wszystkie okna dla danego procesu"""
    if not WIN32_AVAILABLE:
        return []
    
    windows = []
    
    def callback(hwnd, windows_list):
        try:
            _, found_pid = win32process.GetWindowThreadProcessId(hwnd)
            if found_pid == pid:
                title = win32gui.GetWindowText(hwnd)
                class_name = win32gui.GetClassName(hwnd)
                rect = win32gui.GetWindowRect(hwnd)
                width = rect[2] - rect[0]
                height = rect[3] - rect[1]
                is_visible = win32gui.IsWindowVisible(hwnd)
                is_enabled = win32gui.IsWindowEnabled(hwnd)
                
                # Pobierz style okna
                try:
                    style = win32gui.GetWindowLong(hwnd, win32con.GWL_STYLE)
                except:
                    style = None
                
                windows_list.append({
                    'hwnd': hwnd,
                    'title': title,
                    'class': class_name,
                    'width': width,
                    'height': height,
                    'is_visible': is_visible,
                    'is_enabled': is_enabled,
                    'style': style,
                    'area': width * height
                })
        except Exception as e:
            pass
    
    try:
        win32gui.EnumWindows(callback, windows)
    except Exception:
        pass
    
    return windows


def get_network_info(proc: psutil.Process) -> Dict:
    """Pobiera informacje o aktywności sieciowej"""
    info = {
        'bytes_sent': 0,
        'bytes_recv': 0,
        'total_bytes': 0,
        'connections': 0,
        'connections_info': []
    }
    
    try:
        io_counters = proc.io_counters()
        if io_counters:
            info['bytes_sent'] = io_counters.bytes_sent
            info['bytes_recv'] = io_counters.bytes_recv
            info['total_bytes'] = io_counters.bytes_sent + io_counters.bytes_recv
    except Exception:
        pass
    
    try:
        connections = proc.net_connections()
        info['connections'] = len(connections)
        for conn in connections[:5]:  # Tylko pierwsze 5
            if conn.status:
                info['connections_info'].append({
                    'status': conn.status,
                    'laddr': f"{conn.laddr.ip}:{conn.laddr.port}" if conn.laddr else None,
                    'raddr': f"{conn.raddr.ip}:{conn.raddr.port}" if conn.raddr else None,
                })
    except (psutil.AccessDenied, psutil.NoSuchProcess):
        pass
    
    return info


def get_process_info(proc: psutil.Process) -> Dict:
    """Pobiera szczegółowe informacje o procesie"""
    info = {
        'pid': proc.pid,
        'name': proc.name(),
        'cpu_percent': 0,
        'memory_mb': 0,
        'num_threads': 0,
        'create_time': None,
        'status': None
    }
    
    try:
        info['cpu_percent'] = proc.cpu_percent(interval=0.1)
        info['memory_mb'] = proc.memory_info().rss / (1024 * 1024)
        info['num_threads'] = proc.num_threads()
        info['create_time'] = datetime.fromtimestamp(proc.create_time())
        info['status'] = proc.status()
    except Exception:
        pass
    
    return info


def analyze_metin2_clients():
    """Analizuje wszystkie klienty Metin2"""
    print("=" * 80)
    print("M2Diagnostic - Analiza klientów Metin2")
    print("=" * 80)
    print()
    
    if not WIN32_AVAILABLE:
        print("UWAGA: win32gui nie jest dostępne - informacje o oknach będą ograniczone")
        print("Zainstaluj: pip install pywin32\n")
    
    # Znajdź procesy Metin2
    metin2_processes = []
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            if 'metin2client' in proc.info['name'].lower():
                metin2_processes.append(proc)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    
    if not metin2_processes:
        print("Nie znaleziono żadnych procesów Metin2!")
        return
    
    print(f"Znaleziono {len(metin2_processes)} klientów Metin2\n")
    
    all_data = []
    
    for i, proc in enumerate(metin2_processes, 1):
        print(f"\n{'='*80}")
        print(f"KLIENT #{i} - PID: {proc.pid}")
        print(f"{'='*80}")
        
        # Informacje o procesie
        proc_info = get_process_info(proc)
        print(f"\n[PROCES]")
        print(f"  Nazwa: {proc_info['name']}")
        print(f"  PID: {proc_info['pid']}")
        print(f"  CPU: {proc_info['cpu_percent']:.2f}%")
        print(f"  Pamięć: {proc_info['memory_mb']:.2f} MB")
        print(f"  Wątki: {proc_info['num_threads']}")
        print(f"  Status: {proc_info['status']}")
        print(f"  Czas utworzenia: {proc_info['create_time']}")
        
        # Informacje o oknach
        windows = get_all_windows_for_process(proc.pid)
        print(f"\n[OKNA] - Znaleziono {len(windows)} okien")
        
        if windows:
            # Sortuj po rozmiarze (największe pierwsze)
            windows.sort(key=lambda x: x['area'], reverse=True)
            
            for j, win in enumerate(windows, 1):
                print(f"\n  Okno #{j}:")
                print(f"    Handle: {win['hwnd']}")
                print(f"    Tytuł: '{win['title']}'")
                print(f"    Klasa: '{win['class']}'")
                print(f"    Rozmiar: {win['width']}x{win['height']} (powierzchnia: {win['area']})")
                print(f"    Widoczne: {win['is_visible']}")
                print(f"    Włączone: {win['is_enabled']}")
                if win['style']:
                    print(f"    Style: 0x{win['style']:08X}")
        else:
            if WIN32_AVAILABLE:
                print("  BRAK OKIEN!")
            else:
                print("  (Informacje o oknach wymagają pywin32)")
        
        # Informacje o sieci
        network_info = get_network_info(proc)
        print(f"\n[SIECI]")
        print(f"  Wysłane: {network_info['bytes_sent']:,} bajtów")
        print(f"  Odebrane: {network_info['bytes_recv']:,} bajtów")
        print(f"  Razem: {network_info['total_bytes']:,} bajtów")
        print(f"  Połączenia: {network_info['connections']}")
        if network_info['connections_info']:
            print(f"  Szczegóły połączeń:")
            for conn in network_info['connections_info']:
                print(f"    - Status: {conn['status']}, Lokalne: {conn['laddr']}, Zdalne: {conn['raddr']}")
        
        # Monitoruj aktywność sieciową przez chwilę
        print(f"\n[MONITOROWANIE AKTYWNOŚCI SIECIOWEJ]")
        print("  Zbieranie próbek przez 5 sekund...", end='', flush=True)
        import time
        samples = []
        initial_bytes = network_info['total_bytes']
        
        for i in range(5):
            time.sleep(1)
            print(".", end='', flush=True)
            try:
                io = proc.io_counters()
                if io:
                    total = io.bytes_sent + io.bytes_recv
                    samples.append(total)
            except:
                pass
        
        print()  # Nowa linia po kropkach
        
        if len(samples) > 1:
            diffs = [samples[i] - samples[i-1] for i in range(1, len(samples))]
            avg_diff = sum(diffs) / len(diffs) if diffs else 0
            total_change = samples[-1] - samples[0] if len(samples) > 1 else 0
            print(f"  Początkowa wartość: {initial_bytes:,} bajtów")
            print(f"  Końcowa wartość: {samples[-1]:,} bajtów")
            print(f"  Całkowita zmiana: {total_change:,} bajtów")
            print(f"  Średnia aktywność: {avg_diff:,.0f} bajtów/sekundę")
            if diffs:
                print(f"  Maksymalna różnica: {max(diffs):,} bajtów")
                print(f"  Minimalna różnica: {min(diffs):,} bajtów")
            
            # Analiza
            if network_info['connections'] == 0:
                print(f"  [WYLOGOWANY] Brak połączeń sieciowych!")
            elif total_change < 100 and avg_diff < 20:
                print(f"  [PODEJRZANY] Bardzo niska aktywność - możliwe wylogowanie!")
            elif avg_diff < 100:
                print(f"  [UWAGA] Niska aktywność")
            else:
                print(f"  [OK] Aktywność normalna")
        else:
            print(f"  Nie udało się zebrać próbek")
        
        # Zapisz dane do porównania
        all_data.append({
            'pid': proc_info['pid'],
            'proc_info': proc_info,
            'windows': windows,
            'network_info': network_info,
            'main_window': windows[0] if windows else None
        })
    
    # Porównanie
    print(f"\n\n{'='*80}")
    print("PORÓWNANIE KLIENTÓW")
    print(f"{'='*80}\n")
    
    if len(all_data) >= 2:
        print("Różnice między klientami:\n")
        
        # Porównaj okna
        print("[OKNA]")
        for i, data in enumerate(all_data, 1):
            main_win = data['main_window']
            if main_win:
                print(f"  Klient #{i} (PID {data['pid']}):")
                print(f"    Tytuł: '{main_win['title']}'")
                print(f"    Klasa: '{main_win['class']}'")
                print(f"    Rozmiar: {main_win['width']}x{main_win['height']}")
                print(f"    Widoczne: {main_win['is_visible']}")
            else:
                print(f"  Klient #{i} (PID {data['pid']}): BRAK OKNA")
        
        # Porównaj aktywność sieciową
        print("\n[AKTYWNOŚĆ SIECIOWA]")
        for i, data in enumerate(all_data, 1):
            net = data['network_info']
            print(f"  Klient #{i} (PID {data['pid']}): {net['total_bytes']:,} bajtów, {net['connections']} połączeń")
        
        # Porównaj użycie zasobów
        print("\n[ZASOBY]")
        for i, data in enumerate(all_data, 1):
            proc = data['proc_info']
            print(f"  Klient #{i} (PID {data['pid']}): CPU {proc['cpu_percent']:.2f}%, RAM {proc['memory_mb']:.2f} MB")
    
    print(f"\n{'='*80}")
    print("WSKAZÓWKI:")
    print("1. Sprawdź różnice w tytułach okien")
    print("2. Sprawdź różnice w klasach okien")
    print("3. Sprawdź różnice w aktywności sieciowej")
    print("4. Sprawdź różnice w liczbie połączeń sieciowych")
    print("5. Sprawdź różnice w użyciu CPU/RAM")
    print(f"{'='*80}\n")


if __name__ == '__main__':
    try:
        analyze_metin2_clients()
    except KeyboardInterrupt:
        print("\n\nPrzerwano przez użytkownika.")
    except Exception as e:
        print(f"\n\nBŁĄD: {e}")
        import traceback
        traceback.print_exc()

