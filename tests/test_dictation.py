import sys
import unittest
import tempfile
from pathlib import Path
from unittest.mock import Mock, call, patch
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import dictation
from dictation import DictationApp, HotkeyTracker, normalize_text, save_history


class DictationTests(unittest.TestCase):
    def test_starts_only_when_ctrl_and_alt_are_down(self):
        tracker = HotkeyTracker()
        self.assertFalse(tracker.key_down('ctrl'))
        self.assertTrue(tracker.key_down('alt'))
        self.assertTrue(tracker.is_recording)

    def test_stops_when_either_modifier_is_released(self):
        tracker = HotkeyTracker()
        tracker.key_down('ctrl')
        tracker.key_down('alt')
        self.assertTrue(tracker.key_up('ctrl'))
        self.assertFalse(tracker.is_recording)

    def test_normalize_text(self):
        self.assertEqual(normalize_text('  Привет   мир.  '), 'Привет мир.')
        self.assertEqual(normalize_text(' \n\t '), '')

    def test_macos_paste_uses_command_v(self):
        app = DictationApp()
        app.controller = Mock()

        with patch('dictation.sys.platform', 'darwin'), \
             patch('dictation.pyperclip.paste', return_value=None), \
             patch('dictation.pyperclip.copy'), \
             patch('dictation.time.sleep'):
            app.paste('Привет, Mac!')

        self.assertEqual(
            app.controller.press.call_args_list,
            [call(dictation.keyboard.Key.cmd), call('v')],
        )
        self.assertEqual(
            app.controller.release.call_args_list,
            [call('v'), call(dictation.keyboard.Key.cmd)],
        )

    def test_history_keeps_ten_latest_entries(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch('dictation.HISTORY_PATH', str(Path(directory) / 'history.txt')), \
                 patch('dictation.HISTORY_JSON_PATH', str(Path(directory) / 'history.json')):
                for number in range(12):
                    save_history(f'Запись {number}', number, now=f'2026-09-22 18:{number:02}:00')
                content = (Path(directory) / 'history.txt').read_text(encoding='utf-8')
                self.assertIn('Запись 11', content)
                self.assertIn('Запись 2', content)
                self.assertNotIn('Запись 1\n', content)

    def test_disabling_cancels_an_in_progress_recording_and_resume_reenables_input(self):
        app = DictationApp()
        app.tracker.key_down('ctrl')
        app.tracker.key_down('alt')
        app.audio_chunks.append(np.array([0.1], dtype=np.float32))
        app.audio_queue.put(np.array([0.2], dtype=np.float32))

        with tempfile.TemporaryDirectory() as directory, patch('dictation.LOG_PATH', str(Path(directory) / 'dictation.log')):
            app.set_enabled(False)
            self.assertFalse(app.enabled)
            self.assertFalse(app.enabled_event.is_set())
            self.assertFalse(app.tracker.is_recording)
            self.assertEqual(app.audio_chunks, [])
            self.assertTrue(app.audio_queue.empty())

            app.set_enabled(True)
            self.assertTrue(app.enabled)
            self.assertTrue(app.enabled_event.is_set())


if __name__ == '__main__':
    unittest.main()
