from __future__ import annotations

from pathlib import Path
from typing import Any

from aopl.apps.orchestrator import Orchestrator


class RuntimeManager:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.orchestrator = Orchestrator(root)

    def run_unattended(self, limit: int | None = None) -> dict[str, Any]:
        return self.orchestrator.run(limit=limit)
