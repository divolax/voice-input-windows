"""Local push-to-talk dictation for Windows and macOS.

Hold Ctrl+Alt (Windows) or Control+Option (macOS) to record. Release either key to transcribe and paste.
"""
from __future__ import annotations

import os
import queue
import sys
import threading
import time
import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import Iterable

import numpy as np
import pyperclip
import sounddevice as sd
import av
from faster_whisper import WhisperModel
from pynput import keyboard

# The hidden autostart host may use a legacy Windows console code page.
# Never let a status message terminate dictation because it contains Cyrillic.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="replace")

SAMPLE_RATE = 16_000
CHANNELS = 1
MIN_RECORDING_SECONDS = 0.25
MODEL_NAME = os.environ.get("WHISPER_MODEL", "base")
LANGUAGE = os.environ.get("WHISPER_LANGUAGE", "ru")
if os.environ.get("LOCALAPPDATA"):
    DATA_DIR = Path(os.environ["LOCALAPPDATA"]) / "VoiceInput"
elif sys.platform == "darwin":
    DATA_DIR = Path.home() / "Library" / "Application Support" / "VoiceInput"
else:
    DATA_DIR = Path.home() / ".local" / "share" / "VoiceInput"
LOG_PATH = str(DATA_DIR / "dictation.log")
HISTORY_PATH = str(DATA_DIR / "history.txt")
HISTORY_JSON_PATH = str(DATA_DIR / "history.json")
HISTORY_LIMIT = 10
VK_CONTROL = 0x11
VK_MENU = 0x12
VK_V = 0x56
KEYEVENTF_KEYUP = 0x0002
STATUS_HANDLER = None


def status(message: str) -> None:
    """Record diagnostics even when the app runs hidden at Windows login."""
    line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {message}"
    if sys.stdout is not None:
        try:
            print(line, flush=True)
        except (UnicodeEncodeError, OSError):
            pass
    try:
        Path(LOG_PATH).parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_PATH, "a", encoding="utf-8") as log:
            log.write(line + "\n")
    except OSError:
        pass
    if STATUS_HANDLER is not None:
        try:
            STATUS_HANDLER(message)
        except Exception:
            pass


def normalize_text(text: str) -> str:
    """Collapse whitespace without altering transcription punctuation."""
    return " ".join(text.split())


def save_history(text: str, duration: float, now: str | None = None) -> None:
    """Keep the most recent recognized dictations, regardless of paste success."""
    timestamp = now or time.strftime("%Y-%m-%d %H:%M:%S")
    Path(HISTORY_JSON_PATH).parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(HISTORY_JSON_PATH, "r", encoding="utf-8") as file:
            items = json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        items = []
    items.append({"timestamp": timestamp, "duration_seconds": round(duration, 1), "text": text})
    items = items[-HISTORY_LIMIT:]
    with open(HISTORY_JSON_PATH, "w", encoding="utf-8") as file:
        json.dump(items, file, ensure_ascii=False, indent=2)
    with open(HISTORY_PATH, "w", encoding="utf-8") as file:
        file.write("ПОСЛЕДНИЕ 10 ГОЛОСОВЫХ ЗАПИСЕЙ\n")
        file.write("=" * 40 + "\n\n")
        for index, item in enumerate(reversed(items), 1):
            file.write(f"{index}. {item['timestamp']}  ({item['duration_seconds']} сек.)\n")
            file.write(item["text"] + "\n\n")


@dataclass
class HotkeyTracker:
    """Pure state machine for the Control+Alt/Option hold gesture."""

    held: set[str] = field(default_factory=set)
    is_recording: bool = False

    def key_down(self, key: str) -> bool:
        was_recording = self.is_recording
        self.held.add(key)
        self.is_recording = "ctrl" in self.held and "alt" in self.held
        return not was_recording and self.is_recording

    def key_up(self, key: str) -> bool:
        was_recording = self.is_recording
        self.held.discard(key)
        self.is_recording = "ctrl" in self.held and "alt" in self.held
        return was_recording and not self.is_recording


class DictationApp:
    def __init__(self) -> None:
        self.tracker = HotkeyTracker()
        self.lock = threading.Lock()
        self.stop_event = threading.Event()
        self.audio_chunks: list[np.ndarray] = []
        self.audio_queue: queue.Queue[np.ndarray] = queue.Queue()
        self.audio_status_queue: queue.Queue[str] = queue.Queue(maxsize=32)
        self.stream: sd.InputStream | None = None
        self.input_sample_rate = SAMPLE_RATE
        self.worker: threading.Thread | None = None
        self.controller = keyboard.Controller()
        self.model: WhisperModel | None = None
        self.model_lock = threading.Lock()
        self.enabled_event = threading.Event()
        self.enabled_event.set()
        self.listener: keyboard.Listener | None = None
        self.enabled = True

    @staticmethod
    def _key_name(key: keyboard.Key | keyboard.KeyCode) -> str | None:
        if key in (keyboard.Key.ctrl, keyboard.Key.ctrl_l, keyboard.Key.ctrl_r):
            return "ctrl"
        if key in (keyboard.Key.alt, keyboard.Key.alt_l, keyboard.Key.alt_r, keyboard.Key.alt_gr):
            return "alt"
        return None

    def load_model(self) -> None:
        """Load only after the first real recording, preserving idle RAM."""
        if self.model is not None:
            return
        with self.model_lock:
            if self.model is not None:
                return
            status(f"Loading Whisper model '{MODEL_NAME}' (CPU/int8).")
            self.model = WhisperModel(MODEL_NAME, device="cpu", compute_type="int8")
            status("Whisper model ready.")

    def _audio_callback(self, indata: np.ndarray, frames: int, time_info: object, audio_status: sd.CallbackFlags) -> None:
        if audio_status:
            try:
                self.audio_status_queue.put_nowait(str(audio_status))
            except queue.Full:
                pass
        if self.tracker.is_recording:
            self.audio_queue.put(indata.copy())

    def start_audio(self) -> None:
        host_apis = sd.query_hostapis()
        wasapi_index = next((i for i, api in enumerate(host_apis) if api["name"] == "Windows WASAPI"), None)
        device = host_apis[wasapi_index]["default_input_device"] if wasapi_index is not None else sd.default.device[0]
        if device is None or device < 0:
            raise RuntimeError("Windows does not have a default microphone input device.")
        device_info = sd.query_devices(device)
        self.input_sample_rate = round(device_info["default_samplerate"])
        self.stream = sd.InputStream(
            device=device,
            samplerate=self.input_sample_rate,
            channels=CHANNELS,
            dtype="float32",
            callback=self._audio_callback,
        )
        self.stream.start()
        status(
            f"Microphone ready: {device_info['name']} via {host_apis[device_info['hostapi']]['name']} "
            f"at {self.input_sample_rate} Hz."
        )

    def _log_audio_statuses(self) -> None:
        while True:
            try:
                audio_status = self.audio_status_queue.get_nowait()
            except queue.Empty:
                return
            status(f"Audio status: {audio_status}")

    def _drain_audio_queue(self) -> None:
        while True:
            try:
                self.audio_queue.get_nowait()
            except queue.Empty:
                return

    def begin_recording(self) -> None:
        with self.lock:
            self._drain_audio_queue()
            self.audio_chunks = []
        status("Recording started.")

    def finish_recording(self) -> None:
        self._log_audio_statuses()
        with self.lock:
            while True:
                try:
                    self.audio_chunks.append(self.audio_queue.get_nowait())
                except queue.Empty:
                    break
            audio = np.concatenate(self.audio_chunks, axis=0).reshape(-1) if self.audio_chunks else np.array([], dtype=np.float32)

        duration = len(audio) / self.input_sample_rate
        if duration < MIN_RECORDING_SECONDS:
            status(f"Recording skipped: too short ({duration:.2f}s).")
            return
        status(f"Recording stopped: {duration:.2f}s. Transcribing.")
        threading.Thread(target=self.transcribe_and_paste, args=(audio, duration), daemon=True).start()

    def transcribe_and_paste(self, audio: np.ndarray, duration: float) -> None:
        try:
            if self.input_sample_rate != SAMPLE_RATE:
                resampler = av.AudioResampler(format="fltp", layout="mono", rate=SAMPLE_RATE)
                frame = av.AudioFrame.from_ndarray(audio.reshape(1, -1), format="fltp", layout="mono")
                frame.sample_rate = self.input_sample_rate
                frames = resampler.resample(frame)
                frames.extend(resampler.resample(None))
                audio = np.concatenate([item.to_ndarray().reshape(-1) for item in frames]).astype(np.float32, copy=False)
            self.load_model()
            if self.model is None:
                return
            segments, _ = self.model.transcribe(
                audio,
                language=LANGUAGE,
                beam_size=3,
                vad_filter=True,
                condition_on_previous_text=False,
            )
            text = normalize_text("".join(segment.text for segment in segments))
            if not text:
                status("No speech recognized; nothing pasted.")
                return
            save_history(text, duration)
            status("Saved to history.txt.")
            self.wait_for_hotkey_release()
            self.paste(text)
            status("Text pasted.")
        except Exception as exc:  # keep listener alive after device/model failures
            status(f"Transcription error: {type(exc).__name__}: {exc}")

    def wait_for_hotkey_release(self) -> None:
        """Avoid sending Alt+Ctrl+V while the user is physically holding a modifier."""
        deadline = time.monotonic() + 2.0
        while self.tracker.held and time.monotonic() < deadline:
            time.sleep(0.02)

    def paste(self, text: str) -> None:
        try:
            previous = pyperclip.paste()
        except pyperclip.PyperclipException:
            previous = None
        pyperclip.copy(text)
        time.sleep(0.15)
        if sys.platform == "darwin":
            status("Sending Command+V.")
            self.send_modifier_v(keyboard.Key.cmd)
        elif sys.platform == "win32":
            import ctypes

            window = ctypes.windll.user32.GetForegroundWindow()
            title_length = ctypes.windll.user32.GetWindowTextLengthW(window)
            title = ctypes.create_unicode_buffer(title_length + 1)
            ctypes.windll.user32.GetWindowTextW(window, title, len(title))
            status(f"Sending Ctrl+V to window={window}, title={title.value!r}.")
            self.send_ctrl_v()
        else:
            status("Sending Ctrl+V.")
            self.send_modifier_v(keyboard.Key.ctrl)
        if previous is not None:
            time.sleep(0.20)
            try:
                if pyperclip.paste() == text:
                    pyperclip.copy(previous)
            except pyperclip.PyperclipException:
                pass

    @staticmethod
    def send_ctrl_v() -> None:
        """Use Windows SendInput, which is more reliable than a hook-driven controller."""
        import ctypes

        user32 = ctypes.windll.user32
        # Clear a physically lingering modifier before forming Ctrl+V.
        user32.keybd_event(VK_MENU, 0, KEYEVENTF_KEYUP, 0)
        user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)
        time.sleep(0.05)
        user32.keybd_event(VK_CONTROL, 0, 0, 0)
        user32.keybd_event(VK_V, 0, 0, 0)
        user32.keybd_event(VK_V, 0, KEYEVENTF_KEYUP, 0)
        user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)

    def send_modifier_v(self, modifier: keyboard.Key) -> None:
        """Use the platform keyboard controller for macOS Command+V."""
        self.controller.press(modifier)
        self.controller.press("v")
        self.controller.release("v")
        self.controller.release(modifier)

    def on_press(self, key: keyboard.Key | keyboard.KeyCode) -> bool | None:
        if key == keyboard.Key.esc:
            status("Exit requested.")
            self.stop_event.set()
            return False
        name = self._key_name(key)
        if name and self.tracker.key_down(name):
            self.begin_recording()
        return None

    def on_release(self, key: keyboard.Key | keyboard.KeyCode) -> None:
        name = self._key_name(key)
        if name and self.tracker.key_up(name):
            self.finish_recording()

    def run(self) -> None:
        while not self.stop_event.is_set():
            if not self.enabled_event.wait(0.25):
                continue
            try:
                self.start_audio()
                self._log_audio_statuses()
                hotkey = "Control+Option" if sys.platform == "darwin" else "Ctrl+Alt"
                status(f"Ready. Hold {hotkey} to record; release both keys to paste.")
                listener = keyboard.Listener(on_press=self.on_press, on_release=self.on_release)
                if sys.platform == "darwin" and not getattr(listener, "IS_TRUSTED", True):
                    status(
                        "macOS permission required: enable Voice Input in System Settings > Privacy & Security > "
                        "Accessibility and Input Monitoring, then restart the app."
                    )
                    time.sleep(2)
                    continue
                self.listener = listener
                if not self.enabled_event.is_set():
                    listener.stop()
                listener.start()
                listener.join()
            except Exception as exc:
                status(f"Startup error: {type(exc).__name__}: {exc}")
                time.sleep(2)
            finally:
                self.listener = None
                if self.stream is not None:
                    try:
                        self.stream.stop()
                    except Exception:
                        pass
                    try:
                        self.stream.close()
                    except Exception:
                        pass
                    self.stream = None
        status("Voice Input stopped.")

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = enabled
        if enabled:
            self.enabled_event.set()
            status("Voice input enabled.")
            return
        self.enabled_event.clear()
        self.tracker.held.clear()
        self.tracker.is_recording = False
        with self.lock:
            self.audio_chunks.clear()
            self._drain_audio_queue()
        if self.listener is not None:
            self.listener.stop()
        status("Voice input paused.")

    def request_exit(self) -> None:
        self.stop_event.set()
        self.enabled_event.set()
        if self.listener is not None:
            self.listener.stop()


if __name__ == "__main__":
    DictationApp().run()
