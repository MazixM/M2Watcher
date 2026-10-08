"""Testy logiki bez GUI i bez Windowsa: python -m unittest discover -s tests"""
import json
import os
import sys
import tempfile
import threading
import time
import unittest
import wave
from pathlib import Path
from unittest import mock

APP_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(APP_DIR))
_tmp_home = tempfile.mkdtemp(prefix="m2w-test-")
os.environ["M2WATCHER_HOME"] = _tmp_home

import requests  # noqa: E402

import config as config_mod  # noqa: E402
import discord_client as dc  # noqa: E402
import sounds  # noqa: E402
from m2watcher import Metin2Client, Metin2Watcher  # noqa: E402
from notifications import NotificationManager  # noqa: E402


class FakeResponse:
    def __init__(self, status=200, body=None, headers=None):
        self.status_code = status
        self._body = body if body is not None else {}
        self.headers = headers or {}
        self.content = json.dumps(self._body).encode() if status != 204 else b""
        self.text = json.dumps(self._body)

    def json(self):
        return self._body


class FakeSession:
    """Zwraca kolejne odpowiedzi (lub rzuca wyjątki) i zapamiętuje wywołania."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []
        self.headers = {}

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        r = self.responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


WEBHOOK = "https://discord.com/api/webhooks/123456789012345678/abcDEF-123"


class ConfigTests(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.path = self.dir / "config.json"

    def test_first_run_has_device_name_and_is_not_saved(self):
        cfg = config_mod.Config(self.path)
        self.assertTrue(cfg.is_first_run)
        self.assertTrue(cfg.get("device_name"))
        self.assertFalse(self.path.exists())

    def test_migrates_v1_bot_config(self):
        self.path.write_text(json.dumps({
            "check_interval": 3, "sound_enabled": False, "sound_wait_for_input": False,
            "network_threshold": 1000, "show_status": True,
            "discord": {"enabled": True, "bot_token": "tok", "guild_id": "1", "user_id": "123456789012345678",
                        "channel_id": ""},
        }), encoding="utf-8")
        cfg = config_mod.Config(self.path)
        self.assertEqual(cfg.get("discord.method"), "bot")
        self.assertEqual(cfg.get("discord.bot_token"), "tok")
        self.assertFalse(cfg.get("sounds.enabled"))
        self.assertFalse(cfg.get("sounds.repeat_until_ack"))
        self.assertEqual(cfg.get("check_interval"), 3)
        self.assertIsNone(cfg.get("network_threshold"))
        self.assertTrue(cfg.is_first_run)  # kreator pokaże się, żeby ustawić nazwę urządzenia
        saved = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual(saved["config_version"], config_mod.CONFIG_VERSION)

    def test_v1_placeholders_mean_disabled(self):
        self.path.write_text(json.dumps({"discord": {"enabled": True, "bot_token": "YOUR_BOT_TOKEN"}}))
        cfg = config_mod.Config(self.path)
        self.assertEqual(cfg.get("discord.method"), "none")
        self.assertEqual(cfg.get("discord.bot_token"), "")

    def test_broken_file_is_backed_up(self):
        self.path.write_text("{ to nie jest json")
        cfg = config_mod.Config(self.path)
        self.assertTrue(cfg.load_error)
        self.assertTrue((self.dir / "config.broken.json").exists())
        self.assertEqual(cfg.get("discord.method"), "none")

    def test_nested_defaults_are_not_shared(self):
        a = config_mod.Config(self.dir / "a.json")
        a.set("discord.webhook_url", "x", save=False)
        b = config_mod.Config(self.dir / "b.json")
        self.assertEqual(b.get("discord.webhook_url"), "")

    def test_partial_nested_config_gets_defaults(self):
        self.path.write_text(json.dumps({"config_version": 2, "setup_completed": True,
                                         "discord": {"method": "webhook", "webhook_url": WEBHOOK}}))
        cfg = config_mod.Config(self.path)
        self.assertTrue(cfg.get("discord.notify_events.logout"))
        self.assertFalse(cfg.is_first_run)

    def test_config_from_2_1_with_removed_optimization_still_loads(self):
        # Wersje 2.1.x zapisywały sekcję „optimization” (usunięty moduł) — aktualizacja nie może
        # zgubić ustawień ani wymuszać ponownego kreatora.
        self.path.write_text(json.dumps({
            "config_version": config_mod.CONFIG_VERSION, "setup_completed": True, "device_name": "PC",
            "discord": {"method": "webhook", "webhook_url": WEBHOOK},
            "optimization": {"enabled": True, "default": {"fps_limit": 20, "cores_mode": "spread"}},
        }), encoding="utf-8")
        cfg = config_mod.Config(self.path)
        self.assertFalse(cfg.load_error)
        self.assertFalse(cfg.is_first_run)
        self.assertEqual(cfg.get("device_name"), "PC")
        self.assertEqual(cfg.get("discord.webhook_url"), WEBHOOK)
        self.assertNotIn("optimization", config_mod.DEFAULT_CONFIG)


class ValidationTests(unittest.TestCase):
    def test_webhook_urls(self):
        self.assertTrue(dc.validate_webhook_url(WEBHOOK))
        self.assertTrue(dc.validate_webhook_url("https://discordapp.com/api/webhooks/1/a_b"))
        self.assertFalse(dc.validate_webhook_url("https://example.com/api/webhooks/1/a"))
        self.assertFalse(dc.validate_webhook_url(""))

    def test_settings(self):
        self.assertEqual(dc.validate_settings({"method": "webhook", "webhook_url": WEBHOOK}), [])
        self.assertTrue(dc.validate_settings({"method": "webhook", "webhook_url": "zly"}))
        self.assertTrue(dc.validate_settings({"method": "bot", "bot_token": "t"}))  # brak kanału i usera
        self.assertEqual(dc.validate_settings({"method": "bot", "bot_token": "t",
                                               "user_id": "123456789012345678"}), [])
        self.assertEqual(dc.validate_settings({"method": "none"}), [])


class PayloadTests(unittest.TestCase):
    def test_device_name_and_mention(self):
        item = dc.Notification("logout", "Wylogowanie — Laptop", "opis", 1, "Laptop", [("Klient", "M2")])
        p = dc.build_payload(item, {"user_id": "123456789012345678", "mention_user": True})
        self.assertEqual(p["content"], "<@123456789012345678>")
        self.assertEqual(p["allowed_mentions"], {"users": ["123456789012345678"]})
        self.assertEqual(p["embeds"][0]["fields"][0]["value"], "Laptop")
        self.assertEqual(p["embeds"][0]["footer"]["text"], "M2Watcher")

    def test_delayed_notification_has_note(self):
        item = dc.Notification("logout", "t", "d", 1, "PC", created_at=time.time() - 600)
        p = dc.build_payload(item, {})
        self.assertIn("opóźnieniem 10 min", p["embeds"][0]["footer"]["text"])
        self.assertNotIn("content", p)

    def test_manager_uses_device_name_and_respects_toggles(self):
        cfg = config_mod.Config(Path(tempfile.mkdtemp()) / "c.json")
        cfg.set("device_name", "PC w pokoju", save=False)
        cfg.set("discord.notify_events.reconnect", False, save=False)
        sender = mock.Mock()
        nm = NotificationManager(cfg, sender)
        nm.notify("logout", "Metin2 (PID 1)")
        nm.notify("reconnect", "Metin2 (PID 1)")
        self.assertEqual(sender.enqueue.call_count, 1)
        item = sender.enqueue.call_args[0][0]
        self.assertIn("PC w pokoju", item.title)
        self.assertEqual(item.device, "PC w pokoju")


class SenderTests(unittest.TestCase):
    def make(self, responses, settings=None):
        self.settings = settings or {"method": "webhook", "webhook_url": WEBHOOK}
        self.outbox = dc.Outbox(Path(tempfile.mkdtemp()) / "outbox.json")
        self.session = FakeSession(responses)
        transport = dc.DiscordTransport(session=self.session)
        return dc.DiscordSender(lambda: self.settings, self.outbox, transport)

    def item(self):
        return dc.Notification("logout", "t", "d", 1, "PC")

    def test_offline_keeps_item_and_retries_with_backoff(self):
        s = self.make([requests.ConnectionError("brak sieci"), requests.Timeout(), FakeResponse(200)])
        s.enqueue(self.item())
        self.assertEqual(s._step(), 5)
        self.assertEqual(s.status.state, dc.STATE_OFFLINE)
        self.assertEqual(len(self.outbox), 1)
        self.assertEqual(s._step(), 10)
        self.assertEqual(len(self.outbox), 1)
        self.assertIsNone(s._step())  # wysłane, kolejka pusta
        self.assertEqual(len(self.outbox), 0)
        self.assertEqual(s.status.state, dc.STATE_OK)

    def test_backoff_is_capped(self):
        s = self.make([requests.ConnectionError()] * 10)
        s.enqueue(self.item())
        delays = [s._step() for _ in range(8)]
        self.assertEqual(max(delays), dc.BACKOFF_STEPS[-1])

    def test_queue_survives_restart(self):
        s = self.make([requests.ConnectionError()])
        s.enqueue(self.item())
        s._step()
        reloaded = dc.Outbox(self.outbox.path)
        self.assertEqual(len(reloaded), 1)
        self.assertEqual(reloaded.peek().attempts, 1)

    def test_rate_limit_uses_retry_after(self):
        s = self.make([FakeResponse(429, {"retry_after": 2.5}), FakeResponse(204)])
        s.enqueue(self.item())
        self.assertEqual(s._step(), 2.5)
        self.assertIsNone(s._step())

    def test_config_error_keeps_item(self):
        s = self.make([FakeResponse(404, {"message": "Unknown Webhook"})])
        s.enqueue(self.item())
        self.assertEqual(s._step(), dc.CONFIG_ERROR_RETRY)
        self.assertEqual(s.status.state, dc.STATE_CONFIG_ERROR)
        self.assertEqual(len(self.outbox), 1)

    def test_payload_error_drops_item(self):
        s = self.make([FakeResponse(400, {"message": "bad"})])
        s.enqueue(self.item())
        s._step()
        self.assertEqual(len(self.outbox), 0)

    def test_disabled_does_not_queue(self):
        s = self.make([], settings={"method": "none"})
        s.enqueue(self.item())
        self.assertEqual(len(self.outbox), 0)

    def test_bot_dm_opens_channel_once(self):
        settings = {"method": "bot", "bot_token": "tok", "user_id": "123456789012345678"}
        s = self.make([FakeResponse(200, {"id": "999"}), FakeResponse(200), FakeResponse(200)], settings)
        s.enqueue(self.item())
        s.enqueue(self.item())
        s._step()
        s._step()
        urls = [c[1] for c in self.session.calls]
        self.assertEqual(urls[0], f"{dc.API_BASE}/users/@me/channels")
        self.assertEqual(urls[1:], [f"{dc.API_BASE}/channels/999/messages"] * 2)
        self.assertEqual(self.session.calls[1][2]["headers"]["Authorization"], "Bot tok")

    def test_webhook_request(self):
        s = self.make([FakeResponse(200)])
        s.enqueue(self.item())
        s._step()
        method, url, kwargs = self.session.calls[0]
        self.assertEqual((method, url), ("POST", WEBHOOK))
        self.assertEqual(kwargs["params"], {"wait": "true"})
        self.assertEqual(kwargs["json"]["username"], "M2Watcher")

    def test_worker_thread_delivers(self):
        s = self.make([FakeResponse(200)])
        s.start()
        try:
            s.enqueue(self.item())
            deadline = time.time() + 3
            while len(self.outbox) and time.time() < deadline:
                time.sleep(0.05)
            self.assertEqual(len(self.outbox), 0)
        finally:
            s.stop()

    def test_worker_survives_unexpected_exception(self):
        s = self.make([])
        with mock.patch.object(s, "_step", side_effect=[RuntimeError("boom"), None]), \
                mock.patch.object(s, "_wait", side_effect=lambda _d: s._stop.set()):
            s._run()  # nie może rzucić wyjątku


class WatcherTests(unittest.TestCase):
    def setUp(self):
        self.events = []
        self.watcher = Metin2Watcher(lambda: {"logout_grace_seconds": 5}, self.events.append)

    def client(self, logged_in=True):
        from datetime import datetime
        return Metin2Client(pid=1, name="metin2client.exe", window_title="M2", start_time=datetime.now(),
                            is_logged_in=logged_in)

    def test_grace_period(self):
        c = self.client()
        self.assertTrue(self.watcher.evaluate_login(c, 0, now=100))
        self.assertTrue(self.watcher.evaluate_login(c, 0, now=104))
        self.assertFalse(self.watcher.evaluate_login(c, 0, now=105.1))

    def test_connection_resets_timer(self):
        c = self.client()
        self.watcher.evaluate_login(c, 0, now=100)
        self.assertTrue(self.watcher.evaluate_login(c, 2, now=103))
        self.assertTrue(self.watcher.evaluate_login(c, 0, now=106))
        self.assertIsNotNone(c.no_connections_since)

    def _fake_proc(self, pid):
        proc = mock.Mock()
        proc.pid = pid
        proc.name.return_value = "metin2client.exe"
        return proc

    def test_update_emits_events(self):
        proc = self._fake_proc(42)
        conns = {"n": 1}
        with mock.patch.object(self.watcher, "find_metin2_processes", side_effect=lambda: procs[:]), \
                mock.patch.object(self.watcher, "count_connections", side_effect=lambda p: conns["n"]), \
                mock.patch.object(self.watcher, "find_window", return_value=(None, None)), \
                mock.patch("m2watcher.time.monotonic", side_effect=lambda: clock[0]):
            procs, clock = [proc], [0.0]
            self.watcher.update_clients()
            conns["n"] = 0
            self.watcher.update_clients()
            clock[0] = 6
            self.watcher.update_clients()
            conns["n"] = 1
            self.watcher.update_clients()
            procs.clear()
            self.watcher.update_clients()
        self.assertEqual([e.kind for e in self.events], ["new", "logout", "reconnect", "closed"])

    def test_process_name_matching(self):
        w = Metin2Watcher(lambda: {"process_names": ["Metin2Release", "game.exe"]})
        self.assertEqual(w.process_names, ("metin2release", "game.exe"))

    def test_event_handler_error_does_not_break_loop(self):
        w = Metin2Watcher(lambda: {}, on_event=mock.Mock(side_effect=RuntimeError("x")))
        w._emit("new", self.client())  # nie rzuca


class SoundTests(unittest.TestCase):
    def setUp(self):
        self.cache = Path(tempfile.mkdtemp())

    def test_builtin_sounds_are_valid_wav(self):
        player = sounds.SoundPlayer(lambda: {}, cache_dir=self.cache)
        for name in sounds.BUILTIN_SOUNDS:
            path = player.resolve_file(f"builtin:{name}", "", 50)
            self.assertIsNone(sounds.validate_wav(str(path)), name)

    def test_volume_scaling(self):
        raw = sounds.samples_to_wav(sounds.builtin_samples("ping"), 1.0)
        half = sounds.scale_wav(raw, 0.5)

        def peak(data):
            import array
            import io
            with wave.open(io.BytesIO(data)) as w:
                a = array.array("h")
                a.frombytes(w.readframes(w.getnframes()))
            return max(abs(x) for x in a)
        self.assertAlmostEqual(peak(half) / peak(raw), 0.5, delta=0.01)

    def test_validate_wav(self):
        self.assertTrue(sounds.validate_wav("/nie/ma/takiego.wav"))
        mp3 = self.cache / "a.mp3"
        mp3.write_bytes(b"x")
        self.assertIn(".wav", sounds.validate_wav(str(mp3)))
        bad = self.cache / "b.wav"
        bad.write_bytes(b"nie wav")
        self.assertTrue(sounds.validate_wav(str(bad)))

    def test_reconnect_does_not_interrupt_alarm(self):
        settings = {"enabled": True, "repeat_until_ack": True,
                    "events": {"logout": {"sound": "builtin:alarm"}, "reconnect": {"sound": "builtin:dzwonek"}}}
        states = []
        player = sounds.SoundPlayer(lambda: settings, on_alarm_change=states.append, cache_dir=self.cache)
        with mock.patch.object(player, "_start_backend") as backend:
            self.assertTrue(player.play_event("logout"))
            self.assertTrue(player.alarm_active)
            self.assertFalse(player.play_event("reconnect"))
            self.assertEqual(backend.call_count, 1)
            self.assertTrue(backend.call_args[0][1])  # loop=True
            player.stop()
        self.assertEqual(states, [True, False])

    def test_disabled_and_none(self):
        player = sounds.SoundPlayer(lambda: {"enabled": False}, cache_dir=self.cache)
        self.assertFalse(player.play_event("logout"))
        player = sounds.SoundPlayer(lambda: {"events": {"logout": {"sound": "none"}}}, cache_dir=self.cache)
        self.assertFalse(player.play_event("logout"))

    def test_auto_stop(self):
        settings = {"repeat_until_ack": True, "max_alarm_seconds": 0.1,
                    "events": {"logout": {"sound": "builtin:ping"}}}
        player = sounds.SoundPlayer(lambda: settings, cache_dir=self.cache)
        stopped = threading.Event()
        player.on_alarm_change = lambda active: (not active) and stopped.set()
        with mock.patch.object(player, "_start_backend"):
            player.play_event("logout")
            self.assertTrue(stopped.wait(2))


if __name__ == "__main__":
    unittest.main()
