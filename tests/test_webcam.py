"""Webcam overlay in a corner of the stream (BoneCast #3)."""
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
spec = importlib.util.spec_from_file_location("bonecast_main_webcam", ROOT / "main.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
Plugin = module.Plugin

LISTING = """\
[video4linux2,v4l2 @ 0x1] Raw       :     yuyv422 :           YUYV 4:2:2 : 640x480 176x144 320x240 1280x720 1920x1080
[video4linux2,v4l2 @ 0x1] Compressed:       mjpeg :          Motion-JPEG : 640x480 176x144 320x240 424x240 1280x720 1920x1080
"""


class WebcamTests(unittest.TestCase):
    def test_mode_prefers_mjpeg_and_smallest_wide_enough(self):
        # 16:9 first: 424x240 rather than 320x240, 1280x720 rather than 640x480
        self.assertEqual(Plugin._webcam_mode(LISTING, 320), ("mjpeg", (424, 240)))
        self.assertEqual(Plugin._webcam_mode(LISTING, 480), ("mjpeg", (1280, 720)))
        self.assertEqual(Plugin._webcam_mode(LISTING, 5000), ("mjpeg", (1920, 1080)))
        raw_only = LISTING.splitlines()[0]
        self.assertEqual(Plugin._webcam_mode(raw_only, 400), ("yuyv422", (1280, 720)))
        four_three = "Compressed: mjpeg : Motion-JPEG : 640x480 320x240"
        self.assertEqual(Plugin._webcam_mode(four_three, 300), ("mjpeg", (320, 240)))
        self.assertIsNone(Plugin._webcam_mode("nothing here", 320))

    def test_overlay_corners(self):
        g = Plugin._webcam_overlay(3, 1280, 720, "br", 25)
        self.assertIn("[3:v]scale=320:-2", g)
        self.assertIn("x=W-w-18:y=H-h-18", g)
        self.assertIn("x=18:y=18", Plugin._webcam_overlay(3, 1280, 720, "tl", 25))
        self.assertIn("x=W-w-18:y=18", Plugin._webcam_overlay(3, 1280, 720, "tr", 25))
        self.assertIn("x=18:y=H-h-18", Plugin._webcam_overlay(3, 1280, 720, "bl", 25))
        # unknown values fall back to bottom right, 25 %
        self.assertIn("scale=320:-2", Plugin._webcam_overlay(2, 1280, 720, "zz", 99))
        self.assertIn("x=W-w-18:y=H-h-18", Plugin._webcam_overlay(2, 1280, 720, "zz", 99))

    def test_overlay_listens_for_the_brb_command(self):
        g = Plugin._webcam_overlay(3, 1280, 720, "br", 25, 47811)
        self.assertIn(r"zmq=bind_address=tcp\\://127.0.0.1\\:47811", g)
        self.assertIn("overlay@bccam=", g)
        self.assertNotIn("zmq", Plugin._webcam_overlay(3, 1280, 720, "br", 25))

    def test_defaults_keep_webcam_off(self):
        self.assertFalse(Plugin._WEBCAM_DEFAULTS["on"])
        self.assertEqual(Plugin._WEBCAM_DEFAULTS["pos"], "br")
        self.assertNotIn("webcam", Plugin._STREAM_DEFAULTS)


class WebcamSettingsTests(unittest.IsolatedAsyncioTestCase):
    """One webcam setting for every platform, validated on save."""

    def setUp(self):
        self.cfg = {}
        self.p = [patch.object(Plugin, "_load_cfg", side_effect=lambda: self.cfg),
                  patch.object(Plugin, "_save_cfg", side_effect=lambda c: None)]
        for x in self.p:
            x.start()
        Plugin._stream_proc = None
        Plugin._cam_preview_size = None

    def tearDown(self):
        for x in self.p:
            x.stop()

    async def test_saved_globally_and_sanitized(self):
        r = await Plugin.set_webcam_settings({"on": True, "pos": "tl", "size": 33, "opacity": 0.4})
        self.assertTrue(r["ok"])
        self.assertEqual(self.cfg["webcam"]["pos"], "tl")
        self.assertEqual((await Plugin.get_config())["webcam"]["size"], 33)
        r = await Plugin.set_webcam_settings({"pos": "middle", "size": 99, "opacity": 7})
        self.assertEqual(r["settings"]["pos"], "br")
        self.assertEqual(r["settings"]["size"], 25)
        self.assertEqual(r["settings"]["opacity"], 1.0)

    async def test_stale_preview_frame_is_removed(self):
        import tempfile, os
        with tempfile.TemporaryDirectory() as d, \
                patch.object(Plugin, "_cam_preview_dir", return_value=d):
            open(os.path.join(d, "frame.raw"), "wb").write(b"old")
            Plugin._clear_cam_frame()
            self.assertFalse(os.path.exists(os.path.join(d, "frame.raw")))
            Plugin._clear_cam_frame()  # absent : pas d'erreur

    async def test_toggle_is_live_when_camera_is_in_the_stream(self):
        class P:  returncode = None
        Plugin._stream_proc = P(); Plugin._cam_zmq_port = 5555; Plugin._brb_on = False
        self.cfg["webcam"] = {"on": True}
        try:
            with patch.object(Plugin, "_webcam_show", return_value=True) as show:
                r = await Plugin.set_webcam_settings({"on": False})
                show.assert_awaited_once_with(False)
                self.assertTrue(r["live"])
                show.reset_mock()
                await Plugin.set_webcam_settings({"opacity": 0.5})
                show.assert_not_awaited()
                Plugin._brb_on = True  # pendant la pause, la caméra reste masquée
                await Plugin.set_webcam_settings({"on": True})
                show.assert_not_awaited()
        finally:
            Plugin._stream_proc = None; Plugin._cam_zmq_port = None; Plugin._brb_on = False


if __name__ == "__main__":
    unittest.main()
