"""Windows system-tray shell for the local voice-input service."""
from __future__ import annotations

import os
import plistlib
import sys
import subprocess
import threading
from pathlib import Path

if sys.platform == "win32":
    import winreg

import pystray
from PIL import Image, ImageDraw

import dictation
from dictation import DictationApp, status

APP_NAME = "Voice Input"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
MUTEX_NAME = "Local\\VoiceInput.Singleton"
LAUNCH_AGENT_LABEL = "com.divolax.voiceinput"
LAUNCH_AGENT_PATH = Path.home() / "Library" / "LaunchAgents" / f"{LAUNCH_AGENT_LABEL}.plist"
_mutex_handle = None


def app_data_dir() -> Path:
    return Path(dictation.DATA_DIR)


def is_autostart_enabled() -> bool:
    if sys.platform == "darwin":
        return LAUNCH_AGENT_PATH.exists()
    if sys.platform != "win32":
        return False
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            winreg.QueryValueEx(key, APP_NAME)
        return True
    except FileNotFoundError:
        return False


def set_autostart(enabled: bool) -> None:
    if sys.platform == "darwin":
        domain = f"gui/{os.getuid()}"
        subprocess.run(
            ["launchctl", "bootout", domain, str(LAUNCH_AGENT_PATH)],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if not enabled:
            LAUNCH_AGENT_PATH.unlink(missing_ok=True)
            return

        LAUNCH_AGENT_PATH.parent.mkdir(parents=True, exist_ok=True)
        if getattr(sys, "frozen", False):
            app_path = Path(sys.executable).resolve().parents[2]
            program_arguments = ["/usr/bin/open", "-a", str(app_path)]
        else:
            program_arguments = [sys.executable, str(Path(sys.argv[0]).resolve())]
        with LAUNCH_AGENT_PATH.open("wb") as file:
            plistlib.dump(
                {
                    "Label": LAUNCH_AGENT_LABEL,
                    "ProgramArguments": program_arguments,
                    "RunAtLoad": True,
                    "KeepAlive": False,
                },
                file,
            )
        subprocess.run(
            ["launchctl", "bootstrap", domain, str(LAUNCH_AGENT_PATH)],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
        )
        return

    if sys.platform != "win32":
        raise RuntimeError("Automatic startup is not supported on this platform.")
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
        if enabled:
            executable = Path(sys.executable).resolve()
            if getattr(sys, "frozen", False):
                command = f'"{executable}"'
            else:
                script = Path(sys.argv[0]).resolve()
                command = f'"{executable}" "{script}"'
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, command)
        else:
            try:
                winreg.DeleteValue(key, APP_NAME)
            except FileNotFoundError:
                pass


def open_path(path: Path) -> None:
    if sys.platform == "darwin":
        subprocess.run(["open", str(path)], check=False)
    else:
        os.startfile(path)


class TrayShell:
    def __init__(self, service: DictationApp) -> None:
        self.service = service
        self.icon: pystray.Icon | None = None
        self.status_text = "Запуск…"
        self.enabled = True
        dictation.STATUS_HANDLER = self.on_status

    def on_status(self, message: str) -> None:
        self.status_text = message
        if self.icon is not None:
            self.icon.title = f"{APP_NAME} — {message[:80]}"
            self.icon.icon = self.make_icon()
            self.icon.update_menu()

    def make_icon(self) -> Image.Image:
        color = (54, 190, 110) if self.service.enabled else (135, 140, 150)
        if "Recording started" in self.status_text:
            color = (235, 75, 70)
        image = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle((4, 4, 60, 60), radius=16, fill=(31, 35, 42, 255))
        draw.ellipse((20, 13, 44, 42), fill=(245, 247, 250, 255))
        draw.rounded_rectangle((16, 20, 48, 47), radius=14, fill=(245, 247, 250, 255))
        draw.arc((13, 18, 51, 54), 0, 180, fill=(245, 247, 250, 255), width=4)
        draw.line((32, 51, 32, 56), fill=(245, 247, 250, 255), width=3)
        draw.ellipse((44, 44, 58, 58), fill=color, outline=(31, 35, 42, 255), width=2)
        return image

    def toggle_enabled(self, _icon: pystray.Icon, _item: pystray.MenuItem) -> None:
        self.service.set_enabled(not self.service.enabled)
        self.icon.icon = self.make_icon()
        self.icon.update_menu()

    def toggle_autostart(self, _icon: pystray.Icon, _item: pystray.MenuItem) -> None:
        try:
            set_autostart(not is_autostart_enabled())
        except (OSError, subprocess.CalledProcessError) as exc:
            status(f"Could not change automatic startup: {exc}")
        self.icon.update_menu()

    def open_macos_permissions(self, _icon: pystray.Icon, _item: pystray.MenuItem) -> None:
        subprocess.run(["open", "-a", "System Settings"], check=False)

    def open_history(self, _icon: pystray.Icon, _item: pystray.MenuItem) -> None:
        history = Path(dictation.HISTORY_PATH)
        history.parent.mkdir(parents=True, exist_ok=True)
        if not history.exists():
            history.write_text("Пока нет распознанных диктовок.\n", encoding="utf-8")
        open_path(history)

    def open_data_folder(self, _icon: pystray.Icon, _item: pystray.MenuItem) -> None:
        app_data_dir().mkdir(parents=True, exist_ok=True)
        open_path(app_data_dir())

    def exit_app(self, icon: pystray.Icon, _item: pystray.MenuItem) -> None:
        self.service.request_exit()
        icon.stop()

    def run(self) -> None:
        menu_items = [
            pystray.MenuItem(
                lambda _item: "Пауза голосового ввода" if self.service.enabled else "Включить голосовой ввод",
                self.toggle_enabled,
            ),
            pystray.MenuItem(lambda _item: f"Состояние: {self.status_text[:45]}", None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Открыть историю диктовок", self.open_history),
            pystray.MenuItem("Открыть папку данных", self.open_data_folder),
        ]
        if sys.platform == "darwin":
            menu_items.append(pystray.MenuItem("Разрешения macOS", self.open_macos_permissions))
        menu_items.extend(
            [
                pystray.MenuItem(
                    lambda _item: "Отключить автозапуск" if is_autostart_enabled() else "Включить автозапуск",
                    self.toggle_autostart,
                ),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Выход", self.exit_app),
            ]
        )
        self.icon = pystray.Icon(
            APP_NAME,
            self.make_icon(),
            APP_NAME,
            menu=pystray.Menu(*menu_items),
        )
        if sys.platform == "darwin":
            threading.Thread(target=self.service.run, name="dictation-service", daemon=True).start()
            self.icon.run()
            return
        self.icon.run_detached()
        self.service.run()
        self.icon.stop()


def acquire_single_instance() -> bool:
    global _mutex_handle
    if sys.platform != "win32":
        return True
    import ctypes

    kernel32 = ctypes.windll.kernel32
    _mutex_handle = kernel32.CreateMutexW(None, False, MUTEX_NAME)
    return kernel32.GetLastError() != 183


def main() -> None:
    if "--verify-runtime" in sys.argv or os.environ.get("VOICE_INPUT_VERIFY_RUNTIME") == "1":
        try:
            DictationApp().load_model()
            status("Packaged runtime and Whisper model are ready.")
        except Exception as exc:
            status(f"Packaged runtime check failed: {type(exc).__name__}: {exc}")
            if sys.stdout is not None:
                sys.stdout.flush()
            if sys.stderr is not None:
                sys.stderr.flush()
            os._exit(1)
        if sys.stdout is not None:
            sys.stdout.flush()
        if sys.stderr is not None:
            sys.stderr.flush()
        # The frozen macOS GUI runtime can keep helper threads alive after main returns.
        # This smoke-test mode must never fall through to the tray service or hang CI.
        os._exit(0)
    if not acquire_single_instance():
        import ctypes

        ctypes.windll.user32.MessageBoxW(None, "Voice Input уже запущен. Найдите его значок в системном трее.", APP_NAME, 0x40)
        return
    app = DictationApp()
    TrayShell(app).run()


if __name__ == "__main__":
    main()
