"""The "add microphone" option must capture a real microphone, not a virtual source."""
import importlib.util
import logging
import sys
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "defaults"))
sys.modules.setdefault("decky", types.SimpleNamespace(
    logger=logging.getLogger("bonecast-test"), DECKY_PLUGIN_DIR=str(ROOT)))
spec = importlib.util.spec_from_file_location("bonecast_main_mic_test", ROOT / "main.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
Plugin = module.Plugin

WAVE = "alsa_input.usb-Elgato_Systems_Elgato_Wave_3-00.mono-fallback"


class MicSourceTests(unittest.TestCase):
    def test_real_default_is_kept(self):
        self.assertEqual(Plugin._pick_mic(WAVE, ["steamcord_silence_mic", WAVE]), WAVE)

    def test_steamcord_silent_mic_falls_back_to_the_real_microphone(self):
        names = ["steamcord_silence_mic", "alsa_output.pci-0000_01_00.1.hdmi-stereo.monitor", WAVE]
        self.assertEqual(Plugin._pick_mic("steamcord_silence_mic", names), WAVE)

    def test_monitor_default_falls_back_to_the_real_microphone(self):
        self.assertEqual(Plugin._pick_mic("alsa_output.x.monitor", ["alsa_output.x.monitor", WAVE]), WAVE)

    def test_no_real_microphone_gives_none(self):
        self.assertIsNone(Plugin._pick_mic("steamcord_silence_mic",
                                           ["steamcord_silence_mic", "alsa_output.x.monitor"]))


if __name__ == "__main__":
    unittest.main()
