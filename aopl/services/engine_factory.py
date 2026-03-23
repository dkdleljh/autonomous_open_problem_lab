from __future__ import annotations

from pathlib import Path
from typing import Any

from aopl.apps.counterexample_engine import (
    CounterexampleEngine,
    DemoCounterexampleEngine,
    RealCounterexampleEngine,
)
from aopl.apps.formalizer import DemoFormalizer, Formalizer, RealFormalizer
from aopl.apps.paper_generator import DemoPaperGenerator, PaperGenerator, RealPaperGenerator
from aopl.apps.proof_engine import DemoProofEngine, ProofEngine, RealProofEngine
from aopl.core.config_store import ConfigStore
from aopl.core.io_utils import read_yaml


class EngineFactory:
    def __init__(self, root: Path, runtime_config: dict[str, Any] | None = None) -> None:
        self.root = root
        self.config_store = ConfigStore(root)
        if isinstance(runtime_config, dict):
            self.runtime_config = self.config_store.runtime(runtime_config)
        else:
            self.runtime_config = self.config_store.runtime()

    def _engine_config(self) -> dict[str, Any]:
        engines = self.runtime_config.get("engines", {}) if isinstance(self.runtime_config, dict) else {}
        return engines if isinstance(engines, dict) else {}

    def backend_summary(self) -> dict[str, str]:
        engines = self._engine_config()
        return {
            "counterexample": str(engines.get("counterexample_backend", "demo")),
            "proof": str(engines.get("proof_backend", "demo")),
            "formalizer": str(engines.get("formalizer_backend", "demo")),
            "paper_generator": str(engines.get("paper_generator_backend", "demo")),
        }

    def counterexample_engine(self) -> CounterexampleEngine:
        backend = str(self._engine_config().get("counterexample_backend", "demo"))
        if backend == "demo":
            return DemoCounterexampleEngine(self.root)
        if backend == "real":
            return RealCounterexampleEngine(self.root)
        raise ValueError(f"알 수 없는 counterexample backend: {backend}")

    def proof_engine(self) -> ProofEngine:
        backend = str(self._engine_config().get("proof_backend", "demo"))
        if backend == "demo":
            return DemoProofEngine(self.root)
        if backend == "real":
            return RealProofEngine(self.root)
        raise ValueError(f"알 수 없는 proof backend: {backend}")

    def formalizer(self) -> Formalizer:
        backend = str(self._engine_config().get("formalizer_backend", "demo"))
        if backend == "demo":
            return DemoFormalizer(self.root)
        if backend == "real":
            return RealFormalizer(self.root)
        raise ValueError(f"알 수 없는 formalizer backend: {backend}")

    def paper_generator(self) -> PaperGenerator:
        backend = str(self._engine_config().get("paper_generator_backend", "demo"))
        if backend == "demo":
            return DemoPaperGenerator(self.root)
        if backend == "real":
            return RealPaperGenerator(self.root)
        raise ValueError(f"알 수 없는 paper generator backend: {backend}")
