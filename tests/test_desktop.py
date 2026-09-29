from pathlib import Path

from captionguard.desktop_support import find_ccx, startup_command


def test_find_ccx_searches_bundled_subdirectories(tmp_path: Path) -> None:
    package = tmp_path / "plugin" / "CaptionGuard.ccx"
    package.parent.mkdir()
    package.write_bytes(b"ccx")
    assert find_ccx(tmp_path) == package


def test_startup_command_quotes_executable_path() -> None:
    assert startup_command(Path(r"C:\Program Files\CaptionGuard\CaptionGuard-CN.exe")) == (
        '"C:\\Program Files\\CaptionGuard\\CaptionGuard-CN.exe" --minimized'
    )


def test_startup_command_uses_packaged_launcher(monkeypatch) -> None:
    monkeypatch.setenv("CAPTIONGUARD_LAUNCHER", r"D:\Apps\CaptionGuard-CN.exe")
    assert startup_command() == '"D:\\Apps\\CaptionGuard-CN.exe" --minimized'
