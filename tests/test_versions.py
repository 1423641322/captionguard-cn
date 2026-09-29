import json
import re
import tomllib
from pathlib import Path

from captionguard import __version__

ROOT = Path(__file__).resolve().parents[1]


def test_release_versions_stay_in_sync() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    manifest = json.loads((ROOT / "plugin" / "manifest.json").read_text(encoding="utf-8"))
    launcher = (ROOT / "launcher" / "Program.cs").read_text(encoding="utf-8")
    launcher_match = re.search(r'AppVersion = "([^"]+)"', launcher)

    assert launcher_match is not None
    assert project["project"]["version"] == __version__
    assert manifest["version"] == __version__
    assert launcher_match.group(1) == __version__
