"""Regression tests for unexpected live termination notifications."""
import importlib.util
import logging
import sys
import time
import types
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "defaults"))
sys.modules.setdefault("decky", types.SimpleNamespace(
    logger=logging.getLogger("bonecast-test"), DECKY_PLUGIN_DIR=str(ROOT)))
spec = importlib.util.spec_from_file_location("bonecast_main_test", ROOT / "main.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
Plugin = module.Plugin


class StoppedProcess:
    returncode = 1

    async def wait(self):
        return self.returncode


class StreamAlertTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        Plugin._stream_proc = None
        Plugin._stream_platform = None
        Plugin._resume = None
        Plugin._resume_until_prev = 0.0
        Plugin._pending_stream_alert = None
        Plugin._stream_alert_seq = 0

    async def test_unexpected_exit_without_retry_alerts_once(self):
        proc = StoppedProcess()
        Plugin._stream_proc = proc
        Plugin._stream_platform = "twitch"
        with patch.object(Plugin, "_resume_window", return_value=0), \
             patch.object(Plugin, "stop_stream", new_callable=AsyncMock) as stop:
            await Plugin._watch_stream_exit(proc)
            stop.assert_awaited_once()
        alert = await Plugin.get_stream_alert()
        self.assertEqual(alert["platform"], "twitch")
        await Plugin.ack_stream_alert(alert["id"] + 1)
        self.assertEqual((await Plugin.get_stream_alert())["id"], alert["id"])
        await Plugin.ack_stream_alert(alert["id"])
        self.assertEqual(await Plugin.get_stream_alert(), {})

    async def test_intentional_stop_does_not_alert(self):
        Plugin._stream_platform = "twitch"
        await Plugin._watch_stream_exit(StoppedProcess())
        self.assertEqual(await Plugin.get_stream_alert(), {})

    async def test_expired_reconnection_alerts(self):
        ticket = {"platform": "youtube", "until": time.time() - 1}
        Plugin._resume = ticket
        with patch.object(Plugin, "_yt_end_broadcast", new_callable=AsyncMock) as end:
            await Plugin._auto_resume(ticket)
            end.assert_awaited_once()
        self.assertEqual((await Plugin.get_stream_alert())["platform"], "youtube")

    async def test_successful_reconnection_does_not_alert(self):
        ticket = {"platform": "twitch", "until": time.time() + 10}
        Plugin._resume = ticket
        with patch.object(Plugin, "_ingest_reachable", new_callable=AsyncMock,
                          return_value=True), \
             patch.object(Plugin, "_start_stream_locked", new_callable=AsyncMock,
                          return_value={"ok": True}):
            await Plugin._auto_resume(ticket)
        self.assertIsNone(Plugin._resume)
        self.assertEqual(await Plugin.get_stream_alert(), {})


if __name__ == "__main__":
    unittest.main()
