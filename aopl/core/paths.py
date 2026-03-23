from __future__ import annotations

import os
import platform
from pathlib import Path


def detect_desktop_path() -> Path:
    system_name = platform.system().lower()
    home = Path.home()
    if system_name == "windows":
        user_profile = os.environ.get("USERPROFILE")
        if user_profile:
            primary = Path(user_profile) / "Desktop"
            if primary.exists():
                return primary
        one_drive = os.environ.get("OneDrive")
        if one_drive:
            secondary = Path(one_drive) / "Desktop"
            if secondary.exists():
                return secondary
        return home / "Desktop"
    if system_name in {"darwin", "linux"}:
        candidate = home / "Desktop"
        if candidate.exists():
            return candidate
        return home
    return home


def detect_project_root(folder_name: str = "autonomous_open_problem_lab") -> Path:
    return detect_desktop_path() / folder_name


def locate_workspace_root(start: Path | None = None) -> Path:
    base = (start or Path.cwd()).resolve()
    for path in [base, *base.parents]:
        if (path / "pyproject.toml").exists() and (path / "aopl").exists():
            return path
    return base
