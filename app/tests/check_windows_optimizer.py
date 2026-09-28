"""Sprawdzenie modułu optymalizacji na prawdziwym Windowsie (uruchamiane w CI, nie przez unittest).

Proces testowy kręci pętlę na 100% jednego rdzenia. Sprawdzamy, że:
* limit 20 FPS obniża jego zużycie CPU do ok. 1/3 (NtSuspendProcess/NtResumeProcess),
* po zatrzymaniu dławika proces wraca do pełnej pracy (nie zostaje zamrożony),
* affinity i priorytet ustawiają się i wracają do pierwotnych,
* topologia CPU pochodzi z GetLogicalProcessorInformationEx.
"""
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import psutil  # noqa: E402

import optimizer as opt  # noqa: E402


def cpu_percent(proc: psutil.Process, seconds: float = 3.0) -> float:
    c0, w0 = sum(proc.cpu_times()[:2]), time.perf_counter()
    time.sleep(seconds)
    return 100 * (sum(proc.cpu_times()[:2]) - c0) / (time.perf_counter() - w0)


def main() -> int:
    backend = opt.default_backend()
    assert backend.available, "brak backendu Windows"
    topo = opt.CpuTopology.detect()
    print("Topologia:", topo.summary(), "| z Windows:", topo.exact)
    assert topo.exact and topo.logical_cpus, "topologia nie pochodzi z GetLogicalProcessorInformationEx"

    child = subprocess.Popen([sys.executable, "-c", "while True: pass"])
    proc = psutil.Process(child.pid)
    try:
        time.sleep(0.5)
        base = cpu_percent(proc)
        throttler = opt.FpsThrottler(backend)
        throttler.start()
        throttler.set_targets({child.pid: (20, False)})
        time.sleep(0.3)
        limited = cpu_percent(proc)
        throttler.stop()
        time.sleep(0.3)
        after = cpu_percent(proc, 2.0)
        print(f"CPU bez limitu {base:.0f}%, przy 20 FPS {limited:.0f}% (oczekiwane ~{base / 3:.0f}%), "
              f"po zatrzymaniu {after:.0f}%")
        assert limited < base * 0.55, "limit FPS nie obniżył zużycia CPU"
        assert after > base * 0.8, "proces nie wrócił do pełnej pracy po zatrzymaniu dławika"

        pids = [child.pid]
        original_affinity = proc.cpu_affinity()
        original_priority = proc.nice()
        settings = {"enabled": True, "default": {"cores_mode": "spread", "background_priority": "below_normal"}}
        o = opt.Optimizer(lambda: settings, lambda: pids, backend=backend, topology=topo)
        state = o.tick()[child.pid]
        print("Po zastosowaniu:", proc.cpu_affinity(), proc.nice(), state.error or "bez błędów")
        assert not state.error, state.error
        assert proc.cpu_affinity() == list(topo.slots()[0]), "affinity nie ustawione"
        assert proc.nice() == psutil.BELOW_NORMAL_PRIORITY_CLASS, "priorytet nie ustawiony"  # type: ignore[attr-defined]
        o.stop()
        assert proc.cpu_affinity() == original_affinity, "affinity nie przywrócone"
        assert proc.nice() == original_priority, "priorytet nie przywrócony"
        print("OK")
        return 0
    finally:
        child.kill()


if __name__ == "__main__":
    sys.exit(main())
