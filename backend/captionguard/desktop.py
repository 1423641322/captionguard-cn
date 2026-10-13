from __future__ import annotations

import ctypes
import os
import shutil
import sys
import threading
import time
import webbrowser
from pathlib import Path

import pystray
import uvicorn
from PIL import Image, ImageDraw

from . import __version__
from .api import app
from .desktop_support import API_HOST, API_PORT, HEALTH_URL, find_ccx, read_health, startup_command

APP_NAME = "CaptionGuard CN"
RUN_KEY_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_VALUE_NAME = "CaptionGuardCN"
ICON_PATH = Path(__file__).with_name("assets") / "captionguard.png"


def _message(text: str, *, error: bool = False) -> None:
    flags = 0x10 if error else 0x40
    ctypes.windll.user32.MessageBoxW(None, text, APP_NAME, flags)


def _create_icon(healthy: bool) -> Image.Image:
    try:
        with Image.open(ICON_PATH) as source:
            image = source.convert("RGBA").resize((64, 64), Image.Resampling.LANCZOS)
    except OSError:
        image = Image.new("RGBA", (64, 64), (23, 59, 120, 255))
    draw = ImageDraw.Draw(image)
    indicator = (39, 196, 98, 255) if healthy else (245, 158, 11, 255)
    draw.ellipse((45, 45, 61, 61), fill=indicator, outline="white", width=2)
    return image


class LocalServer:
    def __init__(self) -> None:
        self.server: uvicorn.Server | None = None
        self.thread: threading.Thread | None = None
        self.owns_server = False
        self.start_error: str | None = None

    def start(self) -> None:
        if read_health() is not None:
            return
        config = uvicorn.Config(
            app,
            host=API_HOST,
            port=API_PORT,
            log_level="warning",
            access_log=False,
        )
        self.server = uvicorn.Server(config)
        self.thread = threading.Thread(target=self._run, name="captionguard-server", daemon=True)
        self.thread.start()
        self.owns_server = True

    def _run(self) -> None:
        try:
            assert self.server is not None
            self.server.run()
        except Exception as exc:  # pragma: no cover - displayed to the user
            self.start_error = str(exc)

    def stop(self) -> None:
        if not self.owns_server or self.server is None:
            return
        self.server.should_exit = True
        if self.thread is not None:
            self.thread.join(timeout=3)


class TrayApp:
    def __init__(self, *, minimized: bool = False) -> None:
        self.minimized = minimized
        self.server = LocalServer()
        self.icon = pystray.Icon(
            "CaptionGuardCN",
            _create_icon(False),
            APP_NAME,
            menu=pystray.Menu(
                pystray.MenuItem(self._status_label, None, enabled=False),
                pystray.MenuItem("打开服务状态", self.open_status, default=True),
                pystray.MenuItem("安装 Premiere 插件", self.install_plugin),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem(
                    "登录 Windows 后自动启动",
                    self.toggle_startup,
                    checked=lambda _item: self.startup_is_enabled(),
                ),
                pystray.MenuItem("退出", self.exit),
            ),
        )

    def _status_label(self, _item: pystray.MenuItem) -> str:
        payload = read_health()
        if payload is not None:
            return f"服务运行正常 · {payload.get('version', __version__)}"
        if self.server.start_error:
            return "服务启动失败"
        return "服务正在启动"

    def start(self) -> None:
        self.server.start()
        threading.Thread(target=self._watch_health, name="captionguard-health", daemon=True).start()
        self.icon.run()

    def _watch_health(self) -> None:
        for _attempt in range(40):
            payload = read_health()
            if payload is not None:
                self.icon.icon = _create_icon(True)
                self.icon.update_menu()
                if not self.minimized:
                    self.icon.notify(
                        "本地转写服务已启动。请从 Premiere 的“窗口 → UXP 插件”"
                        "打开 CaptionGuard CN。",
                        APP_NAME,
                    )
                return
            if self.server.start_error:
                break
            time.sleep(0.25)
        self.icon.update_menu()
        if not self.minimized:
            _message(f"本地服务启动失败。\n{self.server.start_error or HEALTH_URL}", error=True)

    def open_status(self, _icon: pystray.Icon, _item: pystray.MenuItem) -> None:
        webbrowser.open(HEALTH_URL)

    def install_plugin(self, _icon: pystray.Icon, _item: pystray.MenuItem) -> None:
        source = find_ccx()
        if source is None:
            _message(
                "安装包中未找到 Premiere 插件。请重新下载完整的 CaptionGuard CN EXE。",
                error=True,
            )
            return
        install_dir = (
            Path(os.environ.get("LOCALAPPDATA", Path.home())) / "CaptionGuardCN" / "Installer"
        )
        install_dir.mkdir(parents=True, exist_ok=True)
        destination = install_dir / source.name
        shutil.copy2(source, destination)
        try:
            os.startfile(destination)  # type: ignore[attr-defined]
        except OSError as exc:
            _message(f"无法打开插件安装程序：{exc}", error=True)
            return
        _message(
            "已打开 Creative Cloud 插件安装窗口。完成安装后，请从 Premiere 的“窗口 → UXP 插件”"
            "打开 CaptionGuard CN。"
        )

    def startup_is_enabled(self) -> bool:
        if sys.platform != "win32":
            return False
        try:
            import winreg

            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY_PATH) as key:
                value, _ = winreg.QueryValueEx(key, RUN_VALUE_NAME)
            return value == startup_command()
        except OSError:
            return False

    def toggle_startup(self, _icon: pystray.Icon, _item: pystray.MenuItem) -> None:
        is_packaged = getattr(sys, "frozen", False) or os.getenv("CAPTIONGUARD_LAUNCHER")
        if sys.platform != "win32" or not is_packaged:
            _message("开机启动仅在打包后的 Windows EXE 中可用。")
            return
        try:
            import winreg

            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY_PATH) as key:
                if self.startup_is_enabled():
                    winreg.DeleteValue(key, RUN_VALUE_NAME)
                else:
                    winreg.SetValueEx(key, RUN_VALUE_NAME, 0, winreg.REG_SZ, startup_command())
        except OSError as exc:
            _message(f"无法修改开机启动设置：{exc}", error=True)
        self.icon.update_menu()

    def exit(self, _icon: pystray.Icon, _item: pystray.MenuItem) -> None:
        self.server.stop()
        self.icon.stop()


def run() -> None:
    TrayApp(minimized="--minimized" in sys.argv).start()


if __name__ == "__main__":
    run()
