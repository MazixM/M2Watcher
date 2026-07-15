"""
Testy kolejki zaległych powiadomień Discord (bez połączenia z Discord API).
"""
import sys
import unittest
from unittest.mock import MagicMock, patch, AsyncMock
from pathlib import Path

# Umożliw import z katalogu app/
sys.path.insert(0, str(Path(__file__).resolve().parent))


class TestPendingNotifications(unittest.TestCase):
    def setUp(self):
        self.discord_mod = MagicMock()
        self.commands_mod = MagicMock()
        # Bot musi być prawdziwym obiektem z atrybutami używanymi w kodzie
        bot_instance = MagicMock()
        bot_instance.is_closed.return_value = False
        bot_instance.loop = MagicMock()
        self.commands_mod.Bot.return_value = bot_instance

        self.modules_patcher = patch.dict(sys.modules, {
            "discord": self.discord_mod,
            "discord.ext": MagicMock(),
            "discord.ext.commands": self.commands_mod,
        })
        self.modules_patcher.start()

        # Odśwież import po zamockowaniu discord
        if "discord_bot" in sys.modules:
            del sys.modules["discord_bot"]
        if "config" in sys.modules:
            del sys.modules["config"]

        with patch("config.Config") as MockConfig:
            mock_config = MockConfig.return_value
            mock_config.get.side_effect = lambda key, default="": {
                "discord.bot_token": "fake-token",
                "discord.guild_id": "1",
                "discord.user_id": "2",
                "discord.channel_id": "3",
            }.get(key, default)
            from discord_bot import M2WatcherBot, PendingNotification
            self.M2WatcherBot = M2WatcherBot
            self.PendingNotification = PendingNotification
            self.bot = M2WatcherBot(mock_config)

    def tearDown(self):
        self.modules_patcher.stop()
        for name in ("discord_bot",):
            if name in sys.modules:
                del sys.modules[name]

    def test_enqueue_and_count(self):
        self.bot._enqueue_pending("msg", "title", "123", 0xff0000)
        self.assertEqual(self.bot.pending_count(), 1)

    def test_max_pending_drops_oldest(self):
        self.bot.MAX_PENDING = 3
        for i in range(5):
            self.bot._enqueue_pending(f"msg{i}", "t", "1", 0xff0000)
        self.assertEqual(self.bot.pending_count(), 3)
        items = self.bot._pop_pending_batch()
        self.assertEqual([i.message for i in items], ["msg2", "msg3", "msg4"])

    def test_requeue_front_preserves_order(self):
        a = self.PendingNotification("a", "t", "1", 1, 1.0)
        b = self.PendingNotification("b", "t", "1", 1, 2.0)
        self.bot._enqueue_pending("c", "t", "1", 1)
        self.bot._requeue_front([a, b])
        items = self.bot._pop_pending_batch()
        self.assertEqual([i.message for i in items], ["a", "b", "c"])

    def test_sync_queues_when_bot_not_ready(self):
        self.bot._bot_ready = False
        self.bot._loop = None
        result = self.bot.send_notification_sync("wylogowanie", "Wylogowanie", "99", 0xff0000)
        self.assertFalse(result)
        self.assertEqual(self.bot.pending_count(), 1)
        pending = self.bot._pop_pending_batch()[0]
        self.assertEqual(pending.message, "wylogowanie")
        self.assertEqual(pending.title, "Wylogowanie")

    def test_flush_requeues_on_network_failure(self):
        import asyncio

        self.bot._enqueue_pending("one", "t", "1", 1)
        self.bot._enqueue_pending("two", "t", "1", 1)

        async def fake_send(message, title, user_id=None, color=0, created_at=None):
            return False  # błąd sieci

        self.bot._send_to_channel = fake_send
        sent = asyncio.get_event_loop().run_until_complete(self.bot._flush_pending())
        self.assertEqual(sent, 0)
        self.assertEqual(self.bot.pending_count(), 2)
        items = self.bot._pop_pending_batch()
        self.assertEqual([i.message for i in items], ["one", "two"])

    def test_flush_sends_all_on_success(self):
        import asyncio

        self.bot._enqueue_pending("one", "t", "1", 1)
        self.bot._enqueue_pending("two", "t", "1", 1)

        async def fake_send(message, title, user_id=None, color=0, created_at=None):
            return True

        self.bot._send_to_channel = fake_send
        sent = asyncio.get_event_loop().run_until_complete(self.bot._flush_pending())
        self.assertEqual(sent, 2)
        self.assertEqual(self.bot.pending_count(), 0)

    def test_flush_skips_config_errors_without_requeue(self):
        import asyncio

        self.bot._enqueue_pending("bad", "t", "1", 1)

        async def fake_send(message, title, user_id=None, color=0, created_at=None):
            return None  # brak kanału

        self.bot._send_to_channel = fake_send
        sent = asyncio.get_event_loop().run_until_complete(self.bot._flush_pending())
        self.assertEqual(sent, 0)
        self.assertEqual(self.bot.pending_count(), 0)


if __name__ == "__main__":
    unittest.main()
