"""
M2Watcher — monitor klientów Metin2.

Działa pasywnie: czyta wyłącznie listę procesów, okien i połączeń sieciowych systemu.
Nie czyta pamięci gry, nie wstrzykuje kodu i nie klika w okno.

Wykrywanie:
* **zamknięcie** — proces zniknął albo jego okno zostało zamknięte,
* **wylogowanie** — proces nie ma żadnego połączenia TCP w stanie ESTABLISHED dłużej niż
  ``logout_grace_seconds`` (klient na ekranie logowania nie jest połączony z serwerem gry),
* **ponowne zalogowanie** — połączenie wróciło.

Monitor działa w osobnym wątku i nie blokuje niczego — informacje o zdarzeniach przekazuje
przez callback ``on_event``.
"""
import logging
import platform
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple

import psutil

log = logging.getLogger(__name__)

try:
    import win32gui  # type: ignore
    import win32process  # type: ignore
    WIN32_AVAILABLE = True
except ImportError:
    win32gui: Any = None
    win32process: Any = None
    WIN32_AVAILABLE = False
    if platform.system() == "Windows":
        log.warning("Brak pywin32 — wykrywanie zamknięcia okna będzie ograniczone")

METIN2_PROCESS_NAMES = ("metin2client.exe",)


@dataclass
class Metin2Client:
    pid: int
    name: str
    window_title: str
    start_time: datetime
    is_logged_in: bool = True
    num_connections: int = 0
    window_handle: Optional[int] = None
    no_connections_since: Optional[float] = None
    status_since: datetime = field(default_factory=datetime.now)

    @property
    def label(self) -> str:
        return f"{self.window_title} (PID {self.pid})"

    def __str__(self) -> str:
        status = "Zalogowany" if self.is_logged_in else "Wylogowany"
        return f"PID: {self.pid} | {self.name} | {self.window_title} | {status} ({self.num_connections} połączeń)"


@dataclass
class WatchEvent:
    kind: str  # "new" | "logout" | "closed" | "reconnect"
    client: Metin2Client
    details: str = ""
    time: datetime = field(default_factory=datetime.now)


class Metin2Watcher:
    """Monitor klientów. ``update_clients`` można też wywoływać ręcznie (np. w testach)."""

    def __init__(self, get_settings: Callable[[], Dict] = lambda: {},
                 on_event: Optional[Callable[[WatchEvent], None]] = None):
        self.get_settings = get_settings
        self.on_event = on_event
        self.clients: Dict[int, Metin2Client] = {}
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self.last_error: str = ""
        self.last_check: Optional[datetime] = None

    # ---------------------------------------------------------------- wątek
    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="Watcher", daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 3.0) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout)

    @property
    def running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def _run(self) -> None:
        log.info("Monitor klientów uruchomiony")
        consecutive_errors = 0
        while not self._stop.is_set():
            try:
                self.update_clients()
                if consecutive_errors:
                    log.info("Monitor działa ponownie po %d błędach", consecutive_errors)
                consecutive_errors = 0
                self.last_error = ""
            except Exception as e:
                # Pojedynczy błąd (np. chwilowy brak dostępu do procesu) nie może zatrzymać monitora
                consecutive_errors += 1
                self.last_error = str(e)
                if consecutive_errors == 1 or consecutive_errors % 30 == 0:
                    log.exception("Błąd podczas sprawdzania klientów (%d z rzędu)", consecutive_errors)
            interval = float(self.get_settings().get("check_interval", 2.0) or 2.0)
            self._stop.wait(max(0.5, interval))
        log.info("Monitor klientów zatrzymany")

    def snapshot(self) -> List[Metin2Client]:
        with self._lock:
            return sorted(self.clients.values(), key=lambda c: c.pid)

    def _emit(self, kind: str, client: Metin2Client, details: str = "") -> None:
        log.info("Zdarzenie %s: %s %s", kind, client, details)
        if self.on_event:
            try:
                self.on_event(WatchEvent(kind, client, details))
            except Exception:
                log.exception("Błąd obsługi zdarzenia %s", kind)

    # ---------------------------------------------------------------- system
    @property
    def process_names(self) -> Tuple[str, ...]:
        names = self.get_settings().get("process_names") or METIN2_PROCESS_NAMES
        return tuple(n.strip().lower() for n in names if n and n.strip())

    def find_metin2_processes(self) -> List[psutil.Process]:
        processes = []
        names = self.process_names
        for proc in psutil.process_iter(["pid", "name"]):
            try:
                name = (proc.info.get("name") or "").lower()
                if any(name in (n, n + ".exe") for n in names):
                    processes.append(proc)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return processes

    @staticmethod
    def count_connections(proc: psutil.Process) -> int:
        try:
            getter = getattr(proc, "net_connections", None) or proc.connections  # psutil < 6
            return sum(1 for c in getter(kind="tcp") if c.status == psutil.CONN_ESTABLISHED)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            return 0

    @staticmethod
    def find_window(pid: int) -> Tuple[Optional[int], Optional[str]]:
        """Największe widoczne okno procesu: (hwnd, tytuł)."""
        if not WIN32_AVAILABLE:
            return None, None
        found: List[Tuple[bool, int, int, str]] = []

        def callback(hwnd, _):
            try:
                _, owner = win32process.GetWindowThreadProcessId(hwnd)
                if owner != pid:
                    return True
                left, top, right, bottom = win32gui.GetWindowRect(hwnd)
                w, h = right - left, bottom - top
                if w > 50 and h > 50:
                    title = win32gui.GetWindowText(hwnd) or f"[{win32gui.GetClassName(hwnd)}]"
                    found.append((bool(win32gui.IsWindowVisible(hwnd)), w * h, hwnd, title))
            except Exception:
                pass
            return True

        try:
            win32gui.EnumWindows(callback, None)
        except Exception:
            log.debug("EnumWindows nie powiodło się", exc_info=True)
        if not found:
            return None, None
        found.sort(reverse=True)
        _, _, hwnd, title = found[0]
        return hwnd, title

    @staticmethod
    def is_window_closed(hwnd: Optional[int]) -> bool:
        if not WIN32_AVAILABLE or hwnd is None:
            return False
        try:
            return not win32gui.IsWindow(hwnd)
        except Exception:
            return True

    # ---------------------------------------------------------------- logika
    def evaluate_login(self, client: Metin2Client, num_connections: int, now: Optional[float] = None) -> bool:
        """Zalogowany = ma połączenie; wylogowany = brak połączeń dłużej niż okres karencji."""
        now = time.monotonic() if now is None else now
        grace = float(self.get_settings().get("logout_grace_seconds", 5.0))
        client.num_connections = num_connections
        if num_connections > 0:
            client.no_connections_since = None
            return True
        if client.no_connections_since is None:
            client.no_connections_since = now
        if not client.is_logged_in:
            return False
        return (now - client.no_connections_since) < grace

    def update_clients(self) -> None:
        processes = self.find_metin2_processes()
        current = {p.pid: p for p in processes}
        self.last_check = datetime.now()

        with self._lock:
            known = dict(self.clients)

        # Zamknięte procesy
        for pid, client in known.items():
            if pid not in current:
                self._remove(pid)
                self._emit("closed", client, "proces zakończony")

        for pid, proc in current.items():
            try:
                name = proc.name()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
            hwnd, title = self.find_window(pid)
            connections = self.count_connections(proc)
            client = known.get(pid)

            if client is None:
                client = Metin2Client(
                    pid=pid, name=name, window_title=title or "Metin2",
                    start_time=datetime.now(), is_logged_in=connections > 0,
                    num_connections=connections, window_handle=hwnd,
                )
                with self._lock:
                    self.clients[pid] = client
                self._emit("new", client)
                continue

            # Okno zamknięte, choć proces jeszcze żyje (np. zawieszony przy wyjściu).
            # Sprawdzamy uchwyt, a nie to, czy okno „widać” — zminimalizowane okno ma
            # rozmiar ~160×28 i nie może być brane za zamknięte.
            if client.window_handle is not None and self.is_window_closed(client.window_handle):
                self._remove(pid)
                self._emit("closed", client, "okno zamknięte")
                continue

            if hwnd is not None:
                client.window_handle = hwnd
                client.window_title = title or client.window_title
            was_logged_in = client.is_logged_in
            client.is_logged_in = self.evaluate_login(client, connections)

            if was_logged_in and not client.is_logged_in:
                client.status_since = datetime.now()
                self._emit("logout", client, "brak połączenia z serwerem gry")
            elif not was_logged_in and client.is_logged_in:
                client.status_since = datetime.now()
                self._emit("reconnect", client)

    def _remove(self, pid: int) -> None:
        with self._lock:
            self.clients.pop(pid, None)
