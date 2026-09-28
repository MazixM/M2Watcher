"""
Optymalizacja wielu klientów Metin2 — moduł opcjonalny, domyślnie wyłączony.

Co robi (dla wszystkich klientów albo tylko dla wybranych):

* **limit FPS** — przybliżony, bez wstrzykiwania kodu: proces klienta jest cyklicznie
  wstrzymywany i wznawiany (jak BES / Battle Encoder Shirasé). Klient Metin2 ma własny limit
  60 FPS, więc w każdym okresie ``1/fps`` dostaje czas na jedną klatkę przy 60 FPS
  (``1/60 s``), a przez resztę okresu stoi. Wynik: ok. ``fps`` klatek na sekundę i
  proporcjonalnie mniejsze zużycie CPU/GPU. Domyślnie tylko dla klientów **w tle** — okno,
  w które klikniesz, od razu dostaje pełną płynność.
* **rdzenie CPU** — przypisanie klientów do wybranych rdzeni (affinity) albo rozłożenie ich
  po rdzeniach fizycznych (każdy klient na innym rdzeniu z wybranej puli).
* **priorytet w tle** — niższy priorytet procesora dla klientów, których okno nie jest aktywne.

Wszystko to zwykłe funkcje Windows (te same, których używa Menedżer zadań). Moduł nie czyta
pamięci gry i niczego do niej nie wstrzykuje. Po wyłączeniu modułu, zmianie ustawień albo
zamknięciu aplikacji klient wraca do pierwotnych ustawień i jest zawsze wznawiany.
Jeśli M2Watcher zostanie zabity w chwili, gdy klient był wstrzymany, przy następnym starcie
aplikacja sama go wznowi (plik ``throttled.json``).
"""
import atexit
import ctypes
import json
import logging
import os
import platform
import struct
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

import psutil

log = logging.getLogger(__name__)

IS_WINDOWS = platform.system() == "Windows"

# Klient Metin2 sam ogranicza się do 60 FPS — to punkt odniesienia dla cyklu pracy
BASE_FPS = 60
MIN_FPS = 5
MAX_LIMIT_FPS = BASE_FPS - 1

CORES_NONE = "none"      # nie zmieniaj rdzeni
CORES_LIST = "list"      # każdy klient może używać wszystkich wybranych rdzeni
CORES_SPREAD = "spread"  # każdy klient na innym rdzeniu fizycznym z wybranej puli
CORE_MODES = (CORES_NONE, CORES_LIST, CORES_SPREAD)

PRIORITY_NORMAL = "normal"
PRIORITY_BELOW_NORMAL = "below_normal"
PRIORITY_IDLE = "idle"
PRIORITIES = (PRIORITY_NORMAL, PRIORITY_BELOW_NORMAL, PRIORITY_IDLE)
PRIORITY_LABELS = {
    PRIORITY_NORMAL: "Bez zmian",
    PRIORITY_BELOW_NORMAL: "Poniżej normalnego",
    PRIORITY_IDLE: "Niski",
}

SOURCE_DEFAULT = "default"    # ustawienia wspólne dla wszystkich
SOURCE_OVERRIDE = "override"  # własne ustawienia klienta
SOURCE_OFF = "off"            # optymalizacja wyłączona dla klienta
SOURCE_DISABLED = "disabled"  # cały moduł wyłączony


# --------------------------------------------------------------------------- profil
@dataclass(frozen=True)
class Profile:
    fps_limit: int = 0                 # 0 = bez limitu
    fps_background_only: bool = True   # limit tylko, gdy okno klienta nie jest aktywne
    cores_mode: str = CORES_NONE
    cores: Tuple[int, ...] = ()        # pula rdzeni logicznych; pusta = wszystkie
    background_priority: str = PRIORITY_NORMAL

    @property
    def is_noop(self) -> bool:
        return (not self.fps_limit and self.cores_mode == CORES_NONE
                and self.background_priority == PRIORITY_NORMAL)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "fps_limit": self.fps_limit,
            "fps_background_only": self.fps_background_only,
            "cores_mode": self.cores_mode,
            "cores": list(self.cores),
            "background_priority": self.background_priority,
        }

    def describe(self) -> str:
        parts = []
        if self.fps_limit:
            parts.append(f"{self.fps_limit} FPS" + (" w tle" if self.fps_background_only else ""))
        if self.cores_mode == CORES_LIST:
            parts.append(f"rdzenie {format_cpus(self.cores)}" if self.cores else "wszystkie rdzenie")
        elif self.cores_mode == CORES_SPREAD:
            parts.append("rozłożone po rdzeniach")
        if self.background_priority != PRIORITY_NORMAL:
            parts.append(f"priorytet w tle: {PRIORITY_LABELS[self.background_priority].lower()}")
        return ", ".join(parts) or "bez zmian"


def clamp_fps(value: Any) -> int:
    """0 = bez limitu; wartości >= 60 też oznaczają brak limitu (klient i tak ma 60)."""
    try:
        fps = int(float(value))
    except (TypeError, ValueError):
        return 0
    if fps <= 0 or fps > MAX_LIMIT_FPS:
        return 0
    return max(MIN_FPS, fps)


def profile_from_dict(data: Optional[Dict[str, Any]]) -> Profile:
    data = data or {}
    mode = data.get("cores_mode", CORES_NONE)
    priority = data.get("background_priority", PRIORITY_NORMAL)
    cores: List[int] = []
    for c in data.get("cores") or []:
        try:
            if int(c) >= 0:
                cores.append(int(c))
        except (TypeError, ValueError):
            continue
    return Profile(
        fps_limit=clamp_fps(data.get("fps_limit", 0)),
        fps_background_only=bool(data.get("fps_background_only", True)),
        cores_mode=mode if mode in CORE_MODES else CORES_NONE,
        cores=tuple(sorted(set(cores))),
        background_priority=priority if priority in PRIORITIES else PRIORITY_NORMAL,
    )


def duty_cycle(fps: int) -> Optional[Tuple[float, float]]:
    """(czas pracy, czas wstrzymania) w sekundach dla docelowego FPS; None = bez limitu."""
    fps = clamp_fps(fps)
    if not fps:
        return None
    run = 1.0 / BASE_FPS
    return run, (1.0 / fps) - run


def format_cpus(cpus: Iterable[int]) -> str:
    """[0,1,2,5,7,8] → "0–2, 5, 7–8"."""
    items = sorted(set(cpus))
    out: List[str] = []
    i = 0
    while i < len(items):
        j = i
        while j + 1 < len(items) and items[j + 1] == items[j] + 1:
            j += 1
        out.append(str(items[i]) if i == j else f"{items[i]}–{items[j]}")
        i = j + 1
    return ", ".join(out)


# --------------------------------------------------------------------------- topologia CPU
@dataclass(frozen=True)
class Core:
    cpus: Tuple[int, ...]   # rdzenie logiczne (wątki SMT/HT) tego rdzenia fizycznego
    efficiency: int = 0     # klasa wydajności Windows: wyższa = szybszy rdzeń (P), niższa = E


@dataclass
class CpuTopology:
    cores: List[Core]
    exact: bool = True  # False = zgadnięte z liczby rdzeni (bez danych z Windows)

    @property
    def logical_cpus(self) -> List[int]:
        return sorted(c for core in self.cores for c in core.cpus)

    @property
    def hybrid(self) -> bool:
        return len({core.efficiency for core in self.cores}) > 1

    def cpu_kind(self, cpu: int) -> str:
        """„P” / „E” dla procesorów hybrydowych (Intel 12. gen. i nowsze), inaczej „”."""
        if not self.hybrid:
            return ""
        top = max(core.efficiency for core in self.cores)
        for core in self.cores:
            if cpu in core.cpus:
                return "P" if core.efficiency == top else "E"
        return ""

    def slots(self, pool: Sequence[int] = ()) -> List[Tuple[int, ...]]:
        """Rdzenie fizyczne z puli (każdy jako krotka rdzeni logicznych) — miejsca dla klientów."""
        allowed = set(pool) if pool else set(self.logical_cpus)
        result = []
        for core in sorted(self.cores, key=lambda c: min(c.cpus)):
            cpus = tuple(c for c in core.cpus if c in allowed)
            if cpus:
                result.append(cpus)
        return result

    def summary(self) -> str:
        logical = len(self.logical_cpus)
        text = f"{len(self.cores)} rdzeni fizycznych, {logical} logicznych"
        if self.hybrid:
            top = max(core.efficiency for core in self.cores)
            p = sum(1 for core in self.cores if core.efficiency == top)
            text += f" ({p} P + {len(self.cores) - p} E)"
        return text

    @classmethod
    def guess(cls, logical: int, physical: Optional[int]) -> "CpuTopology":
        logical = max(1, logical)
        if physical and logical == 2 * physical:
            cores = [Core((2 * i, 2 * i + 1)) for i in range(physical)]  # Windows: wątki HT obok siebie
        else:
            cores = [Core((i,)) for i in range(logical)]
        return cls(cores, exact=False)

    @classmethod
    def detect(cls) -> "CpuTopology":
        if IS_WINDOWS:
            try:
                cores = _windows_cores()
                if cores:
                    return cls(cores)
            except Exception:
                log.debug("Nie udało się odczytać topologii CPU z Windows", exc_info=True)
        return cls.guess(psutil.cpu_count(logical=True) or 1, psutil.cpu_count(logical=False))


RELATION_PROCESSOR_CORE = 0


def parse_processor_cores(buf: bytes, ptr_size: int) -> List[Core]:
    """Parsuje wynik GetLogicalProcessorInformationEx(RelationProcessorCore).

    Układ SYSTEM_LOGICAL_PROCESSOR_INFORMATION_EX: Relationship (4 B), Size (4 B), potem
    PROCESSOR_RELATIONSHIP: Flags (1), EfficiencyClass (1), Reserved (20), GroupCount (2),
    GroupMask[] od przesunięcia 24 (GROUP_AFFINITY: Mask (wskaźnik), Group (2), Reserved (6)).
    Uwzględniamy tylko grupę procesorów 0 (affinity procesu i tak działa w jednej grupie).
    """
    cores: List[Core] = []
    offset = 0
    while offset + 8 <= len(buf):
        relationship, size = struct.unpack_from("<II", buf, offset)
        if size <= 0:
            break
        if relationship == RELATION_PROCESSOR_CORE:
            base = offset + 8
            efficiency = buf[base + 1]
            (group_count,) = struct.unpack_from("<H", buf, base + 22)
            mask_at = base + 24
            cpus: List[int] = []
            for _ in range(group_count):
                mask = int.from_bytes(buf[mask_at:mask_at + ptr_size], "little")
                (group,) = struct.unpack_from("<H", buf, mask_at + ptr_size)
                if group == 0:
                    cpus.extend(i for i in range(ptr_size * 8) if mask >> i & 1)
                mask_at += ptr_size + 8
            if cpus:
                cores.append(Core(tuple(cpus), efficiency))
        offset += size
    return cores


def _windows_cores() -> List[Core]:
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)  # type: ignore[attr-defined]
    fn = kernel32.GetLogicalProcessorInformationEx
    fn.argtypes = [ctypes.c_int, ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32)]
    fn.restype = ctypes.c_int
    length = ctypes.c_uint32(0)
    fn(RELATION_PROCESSOR_CORE, None, ctypes.byref(length))
    if not length.value:
        return []
    buf = ctypes.create_string_buffer(length.value)
    if not fn(RELATION_PROCESSOR_CORE, buf, ctypes.byref(length)):
        raise ctypes.WinError(ctypes.get_last_error())  # type: ignore[attr-defined]
    return parse_processor_cores(buf.raw[:length.value], ctypes.sizeof(ctypes.c_void_p))


# --------------------------------------------------------------------------- plan
@dataclass
class ClientPlan:
    pid: int
    source: str
    profile: Profile
    foreground: bool = False
    fps: int = 0                                  # limit działający teraz (0 = brak)
    affinity: Optional[Tuple[int, ...]] = None    # None = pierwotne rdzenie
    priority: str = PRIORITY_NORMAL               # normal = pierwotny priorytet


def assign_slots(pids: Sequence[int], slot_count: int, current: Dict[int, int]) -> Dict[int, int]:
    """Stałe przypisanie klientów do rdzeni: istniejące zostają, nowy trafia na najmniej zajęty."""
    result = {pid: slot for pid, slot in current.items() if pid in pids and 0 <= slot < slot_count}
    if slot_count <= 0:
        return {}
    for pid in pids:
        if pid in result:
            continue
        load = [0] * slot_count
        for slot in result.values():
            load[slot] += 1
        result[pid] = min(range(slot_count), key=lambda s: (load[s], s))
    return result


def build_plans(pids: Sequence[int], enabled: bool, default: Profile,
                overrides: Dict[int, Optional[Profile]], foreground: Optional[int],
                topology: CpuTopology, slot_of: Dict[int, Tuple[Tuple[int, ...], int]]) -> Dict[int, ClientPlan]:
    """Wylicza, co ma obowiązywać każdego klienta. ``slot_of`` (pid → (pula, rdzeń)) jest aktualizowane."""
    plans: Dict[int, ClientPlan] = {}
    spread_groups: Dict[Tuple[int, ...], List[int]] = {}
    for pid in pids:
        if not enabled:
            source, profile = SOURCE_DISABLED, Profile()
        elif pid in overrides:
            override = overrides[pid]
            source, profile = (SOURCE_OFF, Profile()) if override is None else (SOURCE_OVERRIDE, override)
        else:
            source, profile = SOURCE_DEFAULT, default
        fg = foreground is not None and pid == foreground
        plan = ClientPlan(pid, source, profile, foreground=fg)
        if profile.fps_limit and not (profile.fps_background_only and fg):
            plan.fps = profile.fps_limit
        if not fg:
            plan.priority = profile.background_priority
        if profile.cores_mode == CORES_LIST:
            pool = [c for c in profile.cores if c in topology.logical_cpus]
            plan.affinity = tuple(pool) if pool else None
        elif profile.cores_mode == CORES_SPREAD:
            spread_groups.setdefault(profile.cores, []).append(pid)
        plans[pid] = plan

    for pool, members in spread_groups.items():
        slots = topology.slots(pool)
        current = {pid: s for pid, (p, s) in slot_of.items() if p == pool}
        assigned = assign_slots(members, len(slots), current)
        for pid, slot in assigned.items():
            slot_of[pid] = (pool, slot)
            plans[pid].affinity = slots[slot]
    for pid in list(slot_of):
        if pid not in plans or plans[pid].profile.cores_mode != CORES_SPREAD:
            slot_of.pop(pid, None)
    return plans


# --------------------------------------------------------------------------- backend
class ProcessBackend:
    """Operacje na procesach. Ta wersja nic nie robi (system inny niż Windows)."""
    available = False

    def suspend(self, pid: int) -> None: ...
    def resume(self, pid: int) -> None: ...
    def forget(self, pid: int) -> None: ...
    def get_affinity(self, pid: int) -> List[int]: return []
    def set_affinity(self, pid: int, cpus: Sequence[int]) -> None: ...
    def get_priority(self, pid: int) -> Any: return None
    def set_priority(self, pid: int, value: Any) -> None: ...
    def create_time(self, pid: int) -> float: return psutil.Process(pid).create_time()
    def foreground_pid(self) -> Optional[int]: return None
    def prepare_timing_thread(self) -> None: ...


class WindowsBackend(ProcessBackend):
    available = True

    PROCESS_SUSPEND_RESUME = 0x0800
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    THREAD_PRIORITY_HIGHEST = 2
    PROCESS_POWER_THROTTLING_EXECUTION_SPEED = 0x1
    PROCESS_POWER_THROTTLING_IGNORE_TIMER_RESOLUTION = 0x4
    PROCESS_POWER_THROTTLING = 4  # PROCESS_INFORMATION_CLASS.ProcessPowerThrottling

    def __init__(self):
        w = ctypes.WinDLL  # type: ignore[attr-defined]
        self.k32 = w("kernel32", use_last_error=True)
        self.ntdll = w("ntdll")
        self.user32 = w("user32")
        self.k32.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
        self.k32.OpenProcess.restype = ctypes.c_void_p
        self.k32.CloseHandle.argtypes = [ctypes.c_void_p]
        for name in ("NtSuspendProcess", "NtResumeProcess"):
            fn = getattr(self.ntdll, name)
            fn.argtypes = [ctypes.c_void_p]
            fn.restype = ctypes.c_long
        self.user32.GetForegroundWindow.restype = ctypes.c_void_p
        self.user32.GetWindowThreadProcessId.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32)]
        self.k32.GetCurrentThread.restype = ctypes.c_void_p
        self.k32.SetThreadPriority.argtypes = [ctypes.c_void_p, ctypes.c_int]
        self.k32.GetCurrentProcess.restype = ctypes.c_void_p
        self.k32.SetProcessInformation.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_uint32]
        self._handles: Dict[int, int] = {}
        self._priority_classes = {
            PRIORITY_NORMAL: psutil.NORMAL_PRIORITY_CLASS,  # type: ignore[attr-defined]
            PRIORITY_BELOW_NORMAL: psutil.BELOW_NORMAL_PRIORITY_CLASS,  # type: ignore[attr-defined]
            PRIORITY_IDLE: psutil.IDLE_PRIORITY_CLASS,  # type: ignore[attr-defined]
        }

    def _handle(self, pid: int) -> int:
        handle = self._handles.get(pid)
        if handle is None:
            handle = self.k32.OpenProcess(self.PROCESS_SUSPEND_RESUME | self.PROCESS_QUERY_LIMITED_INFORMATION,
                                          False, pid)
            if not handle:
                err = ctypes.get_last_error()  # type: ignore[attr-defined]
                if err == 5:
                    raise psutil.AccessDenied(pid)
                raise psutil.NoSuchProcess(pid)
            self._handles[pid] = handle
        return handle

    def _nt(self, fn, pid: int) -> None:
        status = fn(self._handle(pid))
        if status < 0:
            raise OSError(f"{fn.__name__}(PID {pid}) zwrócił 0x{status & 0xFFFFFFFF:08X}")

    def suspend(self, pid: int) -> None:
        self._nt(self.ntdll.NtSuspendProcess, pid)

    def resume(self, pid: int) -> None:
        self._nt(self.ntdll.NtResumeProcess, pid)

    def forget(self, pid: int) -> None:
        handle = self._handles.pop(pid, None)
        if handle:
            self.k32.CloseHandle(handle)

    def get_affinity(self, pid: int) -> List[int]:
        return psutil.Process(pid).cpu_affinity()

    def set_affinity(self, pid: int, cpus: Sequence[int]) -> None:
        psutil.Process(pid).cpu_affinity(list(cpus))

    def get_priority(self, pid: int) -> Any:
        return psutil.Process(pid).nice()

    def set_priority(self, pid: int, value: Any) -> None:
        psutil.Process(pid).nice(self._priority_classes.get(value, value))

    def foreground_pid(self) -> Optional[int]:
        hwnd = self.user32.GetForegroundWindow()
        if not hwnd:
            return None
        pid = ctypes.c_uint32(0)
        self.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        return pid.value or None

    def prepare_timing_thread(self) -> None:
        """Wątek dławika ma dostać procesor nawet przy 100% obciążenia przez klienty,
        a Windows 11 nie może go spowalniać (EcoQoS, zgrubny zegar), gdy okno M2Watchera
        jest zminimalizowane — inaczej klienty stałyby wstrzymane dłużej, niż trzeba."""
        try:
            self.k32.SetThreadPriority(self.k32.GetCurrentThread(), self.THREAD_PRIORITY_HIGHEST)

            class State(ctypes.Structure):
                _fields_ = [("Version", ctypes.c_uint32), ("ControlMask", ctypes.c_uint32),
                            ("StateMask", ctypes.c_uint32)]
            state = State(1, self.PROCESS_POWER_THROTTLING_EXECUTION_SPEED
                          | self.PROCESS_POWER_THROTTLING_IGNORE_TIMER_RESOLUTION, 0)
            self.k32.SetProcessInformation(self.k32.GetCurrentProcess(), self.PROCESS_POWER_THROTTLING,
                                           ctypes.byref(state), ctypes.sizeof(state))
        except Exception:
            log.debug("Nie udało się ustawić priorytetu wątku dławika", exc_info=True)


def default_backend() -> ProcessBackend:
    if IS_WINDOWS:
        try:
            return WindowsBackend()
        except Exception:
            log.exception("Nie udało się przygotować operacji na procesach Windows")
    return ProcessBackend()


def describe_error(e: BaseException) -> str:
    if isinstance(e, psutil.AccessDenied):
        return "brak uprawnień — uruchom M2Watcher jako administrator"
    if isinstance(e, psutil.NoSuchProcess):
        return "proces zakończony"
    return str(e) or e.__class__.__name__


# --------------------------------------------------------------------------- dławik FPS
@dataclass
class _Throttled:
    fps: int
    background_only: bool
    suspended: bool = False
    next_at: float = 0.0
    error: str = ""


class FpsThrottler:
    """Wątek, który cyklicznie wstrzymuje i wznawia klienty z limitem FPS.

    Każda operacja wstrzymania/wznowienia odbywa się pod blokadą, więc ``set_targets`` i
    ``stop`` zawsze zostawiają usunięte klienty wznowione.
    """

    FOREGROUND_POLL = 0.05
    MAX_SLEEP = 0.05
    FAILURES_BEFORE_GIVE_UP = 3

    def __init__(self, backend: ProcessBackend, clock: Callable[[], float] = time.perf_counter,
                 on_targets_changed: Optional[Callable[[List[int]], None]] = None):
        self.backend = backend
        self.clock = clock
        self.on_targets_changed = on_targets_changed
        self._lock = threading.RLock()
        self._targets: Dict[int, _Throttled] = {}
        self._failures: Dict[int, int] = {}
        self._wake = threading.Event()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._foreground: Optional[int] = None
        self._foreground_at = -1.0
        self._counter = 0

    # --- sterowanie
    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="FpsThrottler", daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 2.0) -> None:
        self._stop.set()
        self._wake.set()
        if self._thread:
            self._thread.join(timeout)
        self.set_targets({})

    def set_targets(self, targets: Dict[int, Tuple[int, bool]]) -> None:
        """pid → (fps, tylko w tle). Klienty spoza listy są od razu wznawiane."""
        with self._lock:
            before = set(self._targets)
            for pid in list(self._targets):
                if pid not in targets:
                    self._release(pid)
            now = self.clock()
            for pid, (fps, background_only) in targets.items():
                cycle = duty_cycle(fps)
                if cycle is None:
                    if pid in self._targets:
                        self._release(pid)
                    continue
                state = self._targets.get(pid)
                if state is None:
                    # Rozsunięcie faz: klienty nie ruszają wszystkie w tej samej chwili
                    phase = (self._counter * 0.618) % 1.0
                    self._counter += 1
                    self._targets[pid] = _Throttled(fps, background_only, next_at=now + phase * sum(cycle))
                else:
                    state.fps, state.background_only = fps, background_only
            changed = set(self._targets) != before
        if changed and self.on_targets_changed:
            self.on_targets_changed(sorted(self._targets))
        self._wake.set()

    def status(self) -> Dict[int, Tuple[bool, str]]:
        """pid → (czy teraz dławiony, błąd)."""
        with self._lock:
            return {pid: (not st.error, st.error) for pid, st in self._targets.items()}

    # --- wątek
    def _release(self, pid: int) -> None:
        state = self._targets.pop(pid, None)
        self._failures.pop(pid, None)
        if state and state.suspended:
            try:
                self.backend.resume(pid)
            except Exception as e:
                if psutil.pid_exists(pid):  # zamknięty klient to nie problem, żywy i wstrzymany — tak
                    log.warning("Nie udało się wznowić PID %s: %s", pid, describe_error(e))
        self.backend.forget(pid)

    def _foreground_pid(self, now: float) -> Optional[int]:
        if now - self._foreground_at >= self.FOREGROUND_POLL:
            try:
                self._foreground = self.backend.foreground_pid()
            except Exception:
                self._foreground = None
            self._foreground_at = now
        return self._foreground

    def step(self) -> Optional[float]:
        """Wykonuje zaległe przełączenia; zwraca czas do następnego (None = brak klientów)."""
        with self._lock:
            if not self._targets:
                return None
            now = self.clock()
            foreground = self._foreground_pid(now)
            nearest: Optional[float] = None
            for pid, st in list(self._targets.items()):
                cycle = duty_cycle(st.fps)
                if cycle is None:
                    continue
                if st.background_only and pid == foreground:
                    # Użytkownik kliknął w ten klient — natychmiast pełna płynność
                    if st.suspended:
                        self._toggle(pid, st, suspend=False)
                    st.next_at = now
                    continue
                if st.error:
                    continue
                if now >= st.next_at:
                    run, pause = cycle
                    if st.suspended:
                        self._toggle(pid, st, suspend=False)
                        st.next_at = now + run
                    else:
                        self._toggle(pid, st, suspend=True)
                        st.next_at = now + pause
                wait = st.next_at - now
                nearest = wait if nearest is None else min(nearest, wait)
            return nearest if nearest is not None else self.FOREGROUND_POLL

    def _toggle(self, pid: int, st: _Throttled, suspend: bool) -> None:
        try:
            (self.backend.suspend if suspend else self.backend.resume)(pid)
            st.suspended = suspend
            self._failures.pop(pid, None)
        except Exception as e:
            count = self._failures.get(pid, 0) + 1
            self._failures[pid] = count
            if count < self.FAILURES_BEFORE_GIVE_UP and not isinstance(e, (psutil.AccessDenied,
                                                                           psutil.NoSuchProcess)):
                return
            st.error = describe_error(e)
            log.warning("Limit FPS dla PID %s nie działa: %s", pid, st.error)
            if st.suspended:
                try:
                    self.backend.resume(pid)
                    st.suspended = False
                except Exception:
                    pass  # kolejna próba przy usunięciu klienta z listy (_release)

    def _run(self) -> None:
        self.backend.prepare_timing_thread()
        log.info("Limit FPS: wątek uruchomiony")
        while not self._stop.is_set():
            try:
                wait = self.step()
            except Exception:
                log.exception("Błąd wątku limitu FPS")
                wait = 0.5
            if wait is None:
                self._wake.wait(0.5)
                self._wake.clear()
            elif wait > 0:
                # time.sleep ma rozdzielczość ~1 ms (Python 3.11+ na Windows); Event.wait ~15 ms
                time.sleep(min(wait, self.MAX_SLEEP))
        log.info("Limit FPS: wątek zatrzymany")


# --------------------------------------------------------------------------- całość
@dataclass
class ClientOptState:
    pid: int
    source: str
    profile: Profile
    foreground: bool
    fps: int
    affinity: Optional[Tuple[int, ...]]
    priority: str
    error: str = ""


@dataclass
class _Original:
    affinity: Optional[List[int]] = None
    priority: Any = None
    applied_affinity: Optional[Tuple[int, ...]] = None
    applied_priority: str = PRIORITY_NORMAL
    errors: Dict[str, str] = field(default_factory=dict)


class Optimizer:
    """Stosuje ustawienia optymalizacji do klientów wykrytych przez monitor."""

    INTERVAL = 0.25

    def __init__(self, get_settings: Callable[[], Dict], get_pids: Callable[[], List[int]],
                 backend: Optional[ProcessBackend] = None, topology: Optional[CpuTopology] = None,
                 state_path: Optional[Path] = None):
        self.get_settings = get_settings
        self.get_pids = get_pids
        self.backend = backend if backend is not None else default_backend()
        self.topology = topology if topology is not None else CpuTopology.detect()
        self.state_path = state_path
        self.throttler = FpsThrottler(self.backend, on_targets_changed=self._save_throttled)
        self._lock = threading.RLock()
        self._overrides: Dict[int, Optional[Profile]] = {}
        self._originals: Dict[int, _Original] = {}
        self._slot_of: Dict[int, Tuple[Tuple[int, ...], int]] = {}
        self._states: Dict[int, ClientOptState] = {}
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._atexit_registered = False

    @property
    def available(self) -> bool:
        return self.backend.available

    # --- cykl życia
    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self.recover_suspended()
        self._stop.clear()
        self.throttler.start()
        self._thread = threading.Thread(target=self._run, name="Optimizer", daemon=True)
        self._thread.start()
        if not self._atexit_registered:
            atexit.register(self.stop)
            self._atexit_registered = True

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(2.0)
        self.throttler.stop()
        with self._lock:
            for pid in list(self._originals):
                self._restore(pid)

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                self.tick()
            except Exception:
                log.exception("Błąd modułu optymalizacji")
            self._stop.wait(self.INTERVAL)

    # --- nadpisania dla wybranych klientów (tylko w pamięci — PID zmienia się po restarcie gry)
    def set_override(self, pids: Iterable[int], profile: Optional[Profile]) -> None:
        with self._lock:
            for pid in pids:
                self._overrides[pid] = profile

    def clear_override(self, pids: Iterable[int]) -> None:
        with self._lock:
            for pid in pids:
                self._overrides.pop(pid, None)

    def override_of(self, pid: int) -> Tuple[bool, Optional[Profile]]:
        with self._lock:
            return pid in self._overrides, self._overrides.get(pid)

    def states(self) -> Dict[int, ClientOptState]:
        with self._lock:
            return dict(self._states)

    # --- główna pętla
    def tick(self) -> Dict[int, ClientOptState]:
        settings = self.get_settings() or {}
        enabled = bool(settings.get("enabled", False)) and self.available
        default = profile_from_dict(settings.get("default"))
        pids = list(self.get_pids())
        try:
            foreground = self.backend.foreground_pid() if enabled else None
        except Exception:
            foreground = None

        with self._lock:
            for pid in list(self._overrides):
                if pid not in pids:
                    self._overrides.pop(pid)
            plans = build_plans(pids, enabled, default, self._overrides, foreground, self.topology, self._slot_of)
            targets = {pid: (p.profile.fps_limit, p.profile.fps_background_only)
                       for pid, p in plans.items() if p.profile.fps_limit}
            self.throttler.set_targets(targets)
            throttle_status = self.throttler.status()

            for pid in list(self._originals):
                if pid not in plans:
                    self._originals.pop(pid, None)  # proces zniknął — nie ma czego przywracać
            states: Dict[int, ClientOptState] = {}
            for pid, plan in plans.items():
                errors = self._apply(plan)
                active, fps_error = throttle_status.get(pid, (False, ""))
                if fps_error:
                    errors["fps"] = fps_error
                states[pid] = ClientOptState(
                    pid, plan.source, plan.profile, plan.foreground, plan.fps if active else 0,
                    plan.affinity, plan.priority, error="; ".join(sorted(set(errors.values()))))
            self._states = states
            return states

    def _apply(self, plan: ClientPlan) -> Dict[str, str]:
        pid = plan.pid
        orig = self._originals.get(pid)
        wants_change = plan.affinity is not None or plan.priority != PRIORITY_NORMAL
        if orig is None:
            if not wants_change:
                return {}
            orig = self._originals[pid] = _Original()
            try:
                orig.affinity = self.backend.get_affinity(pid)
            except Exception as e:
                orig.errors["affinity"] = describe_error(e)
            try:
                orig.priority = self.backend.get_priority(pid)
            except Exception as e:
                orig.errors["priority"] = describe_error(e)

        if plan.affinity != orig.applied_affinity:
            target = plan.affinity if plan.affinity is not None else orig.affinity
            try:
                if target:
                    self.backend.set_affinity(pid, list(target))
                orig.applied_affinity = plan.affinity
                orig.errors.pop("affinity", None)
            except Exception as e:
                orig.errors["affinity"] = describe_error(e)
                orig.applied_affinity = plan.affinity  # nie ponawiaj co 250 ms

        if plan.priority != orig.applied_priority:
            target = plan.priority if plan.priority != PRIORITY_NORMAL else orig.priority
            try:
                if target is not None:
                    self.backend.set_priority(pid, target)
                orig.applied_priority = plan.priority
                orig.errors.pop("priority", None)
            except Exception as e:
                orig.errors["priority"] = describe_error(e)
                orig.applied_priority = plan.priority

        errors = dict(orig.errors)
        if not wants_change and orig.applied_affinity is None and orig.applied_priority == PRIORITY_NORMAL:
            self._originals.pop(pid, None)  # wszystko przywrócone
        return errors

    def _restore(self, pid: int) -> None:
        orig = self._originals.pop(pid, None)
        if not orig:
            return
        try:
            if orig.applied_affinity is not None and orig.affinity:
                self.backend.set_affinity(pid, orig.affinity)
            if orig.applied_priority != PRIORITY_NORMAL and orig.priority is not None:
                self.backend.set_priority(pid, orig.priority)
        except Exception as e:
            log.info("Nie przywrócono ustawień PID %s: %s", pid, describe_error(e))

    # --- zabezpieczenie przed klientem zamrożonym po awarii M2Watchera
    def _save_throttled(self, pids: List[int]) -> None:
        if not self.state_path:
            return
        try:
            if not pids:
                self.state_path.unlink(missing_ok=True)
                return
            entries = []
            for pid in pids:
                try:
                    entries.append({"pid": pid, "create_time": self.backend.create_time(pid)})
                except Exception:
                    continue
            self.state_path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.state_path.with_suffix(".tmp")
            tmp.write_text(json.dumps(entries), encoding="utf-8")
            os.replace(tmp, self.state_path)
        except Exception:
            log.debug("Nie udało się zapisać listy dławionych klientów", exc_info=True)

    def recover_suspended(self) -> int:
        """Wznawia klienty, które mogły zostać wstrzymane, gdy M2Watcher został zabity."""
        if not self.state_path or not self.state_path.exists():
            return 0
        recovered = 0
        try:
            entries = json.loads(self.state_path.read_text(encoding="utf-8"))
            for entry in entries if isinstance(entries, list) else []:
                pid = int(entry.get("pid", 0))
                try:
                    if abs(self.backend.create_time(pid) - float(entry.get("create_time", 0))) > 1.0:
                        continue  # PID należy już do innego procesu
                    self.backend.resume(pid)
                    self.backend.forget(pid)
                    recovered += 1
                except Exception:
                    continue
            if recovered:
                log.warning("Wznowiono %d klientów wstrzymanych przed poprzednim zamknięciem", recovered)
        except Exception:
            log.exception("Nie udało się odczytać %s", self.state_path)
        try:
            self.state_path.unlink(missing_ok=True)
        except OSError:
            pass
        return recovered
