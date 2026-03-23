from __future__ import annotations

import subprocess
from pathlib import Path


def run_release_script(root: Path, mode: str = "local", bump: str = "patch") -> int:
    script = root / "scripts" / "release" / "create_release.py"
    command = ["python3", str(script), "--mode", mode, "--bump", bump]
    process = subprocess.run(command, cwd=root, check=False)
    return process.returncode
