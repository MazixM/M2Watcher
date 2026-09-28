"""Testy modułu optymalizacji — bez Windowsa, na atrapie operacji na procesach."""
import json
import struct
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Optional

APP_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(APP_DIR))

import psutil  # noqa: E402

import optimizer as opt  # noqa: E402
from optimizer import (CORES_LIST, CORES_SPREAD, PRIORITY_BELOW_NORMAL, PRIORITY_NORMAL,  # noqa: E402
                       SOURCE_DEFAULT, SOURCE_DISABLED, SOURCE_OFF, SOURCE_OVERRIDE, Core, CpuTopology,
                       FpsThrottler, Optimizer, Profile)


class FakeBackend(opt.ProcessBackend):
    available = True

    def __init__(self):
        self.suspended = {}
        self.calls = []
        self.affinity = {}
        self.priority = {}
        self.fg: Optional[int] = None
        self.deny = set()

    def _check(self, pid):
        if pid in self.deny:
            raise psutil.AccessDenied(pid)

    def suspend(self, pid):
        self._check(pid)
        self.calls.append(("suspend", pid))
        self.suspended[pid] = self.suspended.get(pid, 0) + 1

    def resume(self, pid):
        self._check(pid)
        self.calls.append(("resume", pid))
        self.suspended[pid] = max(0, self.suspended.get(pid, 0) - 1)

    def get_affinity(self, pid):
        return list(self.affinity.get(pid, range(8)))

    def set_affinity(self, pid, cpus):
        self._check(pid)
        self.affinity[pid] = list(cpus)

    def get_priority(self, pid):
        return self.priority.get(pid, "orig")

    def set_priority(self, pid, value):
        self._check(pid)
        self.priority[pid] = value

    def create_time(self, pid):
        return 1000.0 + pid

    def foreground_pid(self):
        return self.fg


class Clock:
    def __init__(self):
        self.t = 100.0

    def __call__(self):
        return self.t


TOPO = CpuTopology([Core((0, 1)), Core((2, 3)), Core((4, 5)), Core((6, 7))])


class ProfileTests(unittest.TestCase):
    def test_from_dict_validates_and_clamps(self):
        p = opt.profile_from_dict({"fps_limit": "2", "cores_mode": "bogus", "cores": [3, "1", -1, "x", 3],
                                   "background_priority": "realtime"})
        self.assertEqual(p.fps_limit, opt.MIN_FPS)
        self.assertEqual(p.cores_mode, opt.CORES_NONE)
        self.assertEqual(p.cores, (1, 3))
        self.assertEqual(p.background_priority, PRIORITY_NORMAL)
        self.assertFalse(p.is_noop)
        self.assertTrue(opt.profile_from_dict({"fps_limit": 0}).is_noop)

    def test_60_fps_or_more_means_no_limit(self):
        self.assertEqual(opt.clamp_fps(60), 0)
        self.assertEqual(opt.clamp_fps(144), 0)
        self.assertEqual(opt.clamp_fps(30), 30)
        self.assertIsNone(opt.duty_cycle(0))

    def test_duty_cycle_gives_one_60fps_frame_per_period(self):
        run, pause = opt.duty_cycle(20)
        self.assertAlmostEqual(run, 1 / 60)
        self.assertAlmostEqual(run + pause, 1 / 20)

    def test_roundtrip_and_describe(self):
        p = Profile(fps_limit=15, cores_mode=CORES_LIST, cores=(2, 3, 4, 7),
                    background_priority=PRIORITY_BELOW_NORMAL)
        self.assertEqual(opt.profile_from_dict(p.to_dict()), p)
        self.assertIn("15 FPS w tle", p.describe())
        self.assertIn("2–4, 7", p.describe())

    def test_format_cpus(self):
        self.assertEqual(opt.format_cpus([8, 0, 1, 2, 5, 7]), "0–2, 5, 7–8")


class TopologyTests(unittest.TestCase):
    @staticmethod
    def record(cpus, efficiency=0, ptr=8):
        mask = sum(1 << c for c in cpus)
        body = bytes([0, efficiency]) + bytes(20) + struct.pack("<H", 1)
        body += mask.to_bytes(ptr, "little") + struct.pack("<H", 0) + bytes(6)
        return struct.pack("<II", 0, 8 + len(body)) + body

    def test_parses_hybrid_cpu(self):
        buf = b"".join([self.record((0, 1), 1), self.record((2, 3), 1), self.record((4,), 0), self.record((5,), 0)])
        cores = opt.parse_processor_cores(buf, 8)
        self.assertEqual([c.cpus for c in cores], [(0, 1), (2, 3), (4,), (5,)])
        topo = CpuTopology(cores)
        self.assertTrue(topo.hybrid)
        self.assertEqual(topo.cpu_kind(1), "P")
        self.assertEqual(topo.cpu_kind(5), "E")
        self.assertIn("2 P + 2 E", topo.summary())

    def test_parses_32bit_layout(self):
        buf = self.record((0, 1), ptr=4) + self.record((2, 3), ptr=4)
        self.assertEqual([c.cpus for c in opt.parse_processor_cores(buf, 4)], [(0, 1), (2, 3)])

    def test_guess_pairs_hyperthreads(self):
        self.assertEqual(CpuTopology.guess(8, 4).slots(), [(0, 1), (2, 3), (4, 5), (6, 7)])
        self.assertEqual(len(CpuTopology.guess(6, 6).slots()), 6)

    def test_slots_respect_pool(self):
        self.assertEqual(TOPO.slots([2, 3, 5]), [(2, 3), (5,)])


class PlanTests(unittest.TestCase):
    def plans(self, pids, enabled=True, default=Profile(), overrides=None, fg=None, slot_of=None):
        return opt.build_plans(pids, enabled, default, overrides or {}, fg, TOPO,
                               slot_of if slot_of is not None else {})

    def test_disabled_module_changes_nothing(self):
        plans = self.plans([1, 2], enabled=False, default=Profile(fps_limit=20))
        self.assertEqual({p.source for p in plans.values()}, {SOURCE_DISABLED})
        self.assertEqual({p.fps for p in plans.values()}, {0})

    def test_background_only_limit_skips_foreground_client(self):
        plans = self.plans([1, 2], default=Profile(fps_limit=20, background_priority=PRIORITY_BELOW_NORMAL), fg=2)
        self.assertEqual(plans[1].fps, 20)
        self.assertEqual(plans[2].fps, 0)
        self.assertEqual(plans[1].priority, PRIORITY_BELOW_NORMAL)
        self.assertEqual(plans[2].priority, PRIORITY_NORMAL)

    def test_limit_for_all_windows_applies_to_foreground_too(self):
        plans = self.plans([1], default=Profile(fps_limit=30, fps_background_only=False), fg=1)
        self.assertEqual(plans[1].fps, 30)

    def test_overrides_for_selected_clients(self):
        plans = self.plans([1, 2, 3], default=Profile(fps_limit=20),
                           overrides={2: Profile(fps_limit=10), 3: None})
        self.assertEqual((plans[1].source, plans[1].fps), (SOURCE_DEFAULT, 20))
        self.assertEqual((plans[2].source, plans[2].fps), (SOURCE_OVERRIDE, 10))
        self.assertEqual((plans[3].source, plans[3].fps), (SOURCE_OFF, 0))

    def test_core_list(self):
        plans = self.plans([1], default=Profile(cores_mode=CORES_LIST, cores=(2, 3, 99)))
        self.assertEqual(plans[1].affinity, (2, 3))

    def test_spread_is_stable_and_balanced(self):
        slot_of = {}
        spread = Profile(cores_mode=CORES_SPREAD, cores=(2, 3, 4, 5, 6, 7))
        plans = self.plans([10, 11, 12, 13], default=spread, slot_of=slot_of)
        self.assertEqual([plans[p].affinity for p in (10, 11, 12, 13)], [(2, 3), (4, 5), (6, 7), (2, 3)])
        # Klient 11 zamknięty, pojawia się 14 — zajmuje zwolniony rdzeń, reszta się nie rusza
        plans = self.plans([10, 12, 13, 14], default=spread, slot_of=slot_of)
        self.assertEqual([plans[p].affinity for p in (10, 12, 13, 14)], [(2, 3), (6, 7), (2, 3), (4, 5)])

    def test_assign_slots_without_slots(self):
        self.assertEqual(opt.assign_slots([1, 2], 0, {}), {})


class ThrottlerTests(unittest.TestCase):
    def setUp(self):
        self.backend = FakeBackend()
        self.clock = Clock()
        self.saved = []
        self.t = FpsThrottler(self.backend, clock=self.clock, on_targets_changed=self.saved.append)

    def run_for(self, seconds, step=0.001):
        end = self.clock.t + seconds
        while self.clock.t < end:
            self.t.step()
            self.clock.t += step

    def test_cycles_suspend_and_resume_at_target_rate(self):
        self.t.set_targets({1: (20, True)})
        self.run_for(1.0)
        suspends = sum(1 for c in self.backend.calls if c == ("suspend", 1))
        self.assertTrue(19 <= suspends <= 21, suspends)

    def test_removed_target_is_always_resumed(self):
        self.t.set_targets({1: (10, True)})
        self.run_for(0.05)
        self.assertEqual(self.backend.suspended.get(1), 1)
        self.t.set_targets({})
        self.assertEqual(self.backend.suspended.get(1), 0)
        self.assertEqual(self.saved, [[1], []])

    def test_stop_resumes_everything(self):
        self.t.set_targets({1: (10, False), 2: (10, False)})
        self.run_for(0.2)
        self.t.stop()
        self.assertEqual(sum(self.backend.suspended.values()), 0)

    def test_foreground_client_runs_freely(self):
        self.t.set_targets({1: (10, True)})
        self.run_for(0.05)
        self.backend.fg = 1
        self.run_for(0.2)
        self.assertEqual(self.backend.suspended.get(1), 0)
        count = len(self.backend.calls)
        self.run_for(0.3)
        self.assertEqual(len(self.backend.calls), count)

    def test_access_denied_disables_limit_for_client(self):
        self.backend.deny.add(1)
        self.t.set_targets({1: (10, False)})
        self.run_for(0.2)
        active, error = self.t.status()[1]
        self.assertFalse(active)
        self.assertIn("administrator", error)


class OptimizerTests(unittest.TestCase):
    def setUp(self):
        self.backend = FakeBackend()
        self.settings = {"enabled": True, "default": {}}
        self.pids = [1, 2]
        self.state = Path(tempfile.mkdtemp()) / "throttled.json"
        self.o = Optimizer(lambda: self.settings, lambda: self.pids, backend=self.backend, topology=TOPO,
                           state_path=self.state)

    def test_applies_and_restores_affinity_and_priority(self):
        self.backend.affinity[1] = [0, 1, 2, 3, 4, 5, 6, 7]
        self.settings["default"] = {"cores_mode": "list", "cores": [4, 5], "background_priority": "below_normal"}
        self.o.tick()
        self.assertEqual(self.backend.affinity[1], [4, 5])
        self.assertEqual(self.backend.priority[1], PRIORITY_BELOW_NORMAL)
        # Klient 1 staje się aktywny — wraca pierwotny priorytet, rdzenie zostają
        self.backend.fg = 1
        self.o.tick()
        self.assertEqual(self.backend.priority[1], "orig")
        self.assertEqual(self.backend.affinity[1], [4, 5])
        # Wyłączenie modułu przywraca wszystko
        self.settings["enabled"] = False
        self.o.tick()
        self.assertEqual(self.backend.affinity[1], [0, 1, 2, 3, 4, 5, 6, 7])

    def test_stop_restores_settings(self):
        self.settings["default"] = {"cores_mode": "spread"}
        self.o.tick()
        self.assertEqual(self.backend.affinity[2], [2, 3])
        self.o.stop()
        self.assertEqual(self.backend.affinity[2], list(range(8)))

    def test_override_off_for_selected_client(self):
        self.settings["default"] = {"fps_limit": 20, "fps_background_only": False}
        self.o.set_override([2], None)
        states = self.o.tick()
        self.assertEqual(states[1].fps, 20)
        self.assertEqual((states[2].source, states[2].fps), (SOURCE_OFF, 0))
        self.o.clear_override([2])
        self.assertEqual(self.o.tick()[2].fps, 20)
        self.o.stop()

    def test_errors_are_reported_per_client(self):
        self.backend.deny.add(2)
        self.settings["default"] = {"cores_mode": "list", "cores": [0]}
        states = self.o.tick()
        self.assertEqual(states[1].error, "")
        self.assertIn("administrator", states[2].error)

    def test_closed_client_override_is_forgotten(self):
        self.o.set_override([2], Profile(fps_limit=10))
        self.pids = [1]
        self.o.tick()
        self.assertEqual(self.o.override_of(2), (False, None))

    def test_throttled_list_is_saved_and_recovered_after_crash(self):
        self.settings["default"] = {"fps_limit": 10, "fps_background_only": False}
        self.o.tick()
        saved = json.loads(self.state.read_text(encoding="utf-8"))
        self.assertEqual({e["pid"] for e in saved}, {1, 2})
        # Symulacja: aplikacja zabita w chwili, gdy klient 1 był wstrzymany
        self.backend.suspended = {1: 1}
        fresh = Optimizer(lambda: {}, lambda: [], backend=self.backend, topology=TOPO, state_path=self.state)
        self.assertEqual(fresh.recover_suspended(), 2)
        self.assertEqual(self.backend.suspended[1], 0)
        self.assertFalse(self.state.exists())

    def test_recovery_skips_reused_pid(self):
        self.state.write_text(json.dumps([{"pid": 5, "create_time": 1.0}]), encoding="utf-8")
        self.assertEqual(self.o.recover_suspended(), 0)
        self.assertNotIn(("resume", 5), self.backend.calls)

    def test_unavailable_backend_keeps_module_off(self):
        o = Optimizer(lambda: {"enabled": True, "default": {"fps_limit": 10}}, lambda: [1],
                      backend=opt.ProcessBackend(), topology=TOPO)
        self.assertEqual(o.tick()[1].source, SOURCE_DISABLED)


if __name__ == "__main__":
    unittest.main()
