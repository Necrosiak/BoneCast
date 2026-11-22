"""Custom RTMP server (BoneCast #4) and stream key redaction in logs."""
import asyncio
import importlib.util
import logging
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "defaults"))
sys.modules.setdefault("decky", types.SimpleNamespace(
    logger=logging.getLogger("bonecast-test"), DECKY_PLUGIN_DIR=str(ROOT)))
spec = importlib.util.spec_from_file_location("bonecast_main_custom", ROOT / "main.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
Plugin = module.Plugin


class FakeStream:
    def __init__(self, lines):
        self.lines = [l.encode() + b"\n" for l in lines]

    async def readline(self):
        return self.lines.pop(0) if self.lines else b""


class CustomRtmpTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.cfg = {}
        self.patches = [
            patch.object(Plugin, "_load_cfg", side_effect=lambda: self.cfg),
            patch.object(Plugin, "_save_cfg", side_effect=lambda c: None),
        ]
        for p in self.patches:
            p.start()
        Plugin._stream_proc = None
        Plugin._stream_platform = None

    def tearDown(self):
        for p in self.patches:
            p.stop()

    def test_url_validation(self):
        for url in ("rtmp://push.example.com/game/", "rtmps://live.example.com:443/app",
                    "rtmp://10.0.0.2:1935/live"):
            self.assertTrue(Plugin._valid_rtmp_url(url), url)
        for url in ("", "http://example.com/live", "rtmp:///nohost", "rtmp://a b/c",
                    "rtmp://host:99999/x", "rtmp://h/\n", "x" * 501, None):
            self.assertFalse(Plugin._valid_rtmp_url(url), url)

    def test_target_joins_server_and_key(self):
        self.assertEqual(Plugin._rtmp_target("rtmp://h/game/", "stream-1?a=b"),
                         "rtmp://h/game/stream-1?a=b")
        self.assertEqual(Plugin._rtmp_target("rtmp://h/app", "k"), "rtmp://h/app/k")
        self.assertEqual(Plugin._rtmp_target("rtmp://h/app/key", ""), "rtmp://h/app/key")

    async def test_settings_are_saved_validated_and_key_never_exposed(self):
        r = await Plugin.custom_set_settings({"url": "rtmp://push.example.com/game/",
                                              "key": " stream-abc "})
        self.assertTrue(r["ok"])
        self.assertEqual(self.cfg["custom"], {"url": "rtmp://push.example.com/game/",
                                              "key": "stream-abc"})
        c = (await Plugin.get_config())["custom"]
        self.assertEqual(c["url"], "rtmp://push.example.com/game/")
        self.assertTrue(c["key_set"])
        self.assertNotIn("stream-abc", repr(await Plugin.get_config()))
        self.assertEqual((await Plugin.custom_set_settings({"url": "https://x"}))["error"], "bad_url")
        self.assertEqual((await Plugin.custom_set_settings({"key": "a b"}))["error"], "bad_key")
        self.assertEqual(self.cfg["custom"]["url"], "rtmp://push.example.com/game/")
        await Plugin.custom_set_settings({"url": "", "key": ""})
        self.assertEqual(self.cfg["custom"], {})

    async def test_stream_settings_are_kept_per_platform(self):
        await Plugin.set_stream_settings({"bitrate": 3000}, "custom")
        self.assertEqual(self.cfg["custom"]["stream"]["bitrate"], 3000)
        self.assertNotIn("stream", self.cfg)

    async def test_start_without_server_is_refused(self):
        with patch("shutil.which", return_value="/usr/bin/ffmpeg"):
            r = await Plugin._start_stream_unlocked(False, "custom")
        self.assertEqual(r, {"ok": False, "error": "no_custom"})

    async def test_ffmpeg_output_masks_the_stream_key(self):
        with self.assertLogs("bonecast-test", level="WARNING") as logs:
            await module.stream_watcher(FakeStream([
                "rtmp://push.example.com/game/stream-secret: I/O error"]),
                True, prefix="[stream]", secrets=("stream-secret",))
        self.assertNotIn("stream-secret", "\n".join(logs.output))
        self.assertIn("rtmp://push.example.com/game/***", "\n".join(logs.output))


if __name__ == "__main__":
    unittest.main()
