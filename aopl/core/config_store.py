from __future__ import annotations

from pathlib import Path
from typing import Any

from aopl.core.io_utils import read_yaml

VALID_BACKENDS = {"demo", "real"}


class ConfigStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self._cache: dict[Path, dict[str, Any]] = {}

    def _load_dict(self, path: Path) -> dict[str, Any]:
        cached = self._cache.get(path)
        if cached is not None:
            return dict(cached)
        payload = read_yaml(path, default={})
        data = payload if isinstance(payload, dict) else {}
        self._cache[path] = dict(data)
        return dict(data)

    def runtime(self, override: dict[str, Any] | None = None) -> dict[str, Any]:
        data = self._load_dict(self.root / "configs" / "global" / "runtime.yaml")
        if isinstance(override, dict):
            for key, value in override.items():
                data[key] = value
        self._validate_runtime(data)
        return data

    def scoring(self) -> dict[str, Any]:
        data = self._load_dict(self.root / "configs" / "scoring" / "default.yaml")
        selection = data.get("selection", {})
        if isinstance(selection, dict):
            threshold = selection.get("min_score", 0.55)
            if not isinstance(threshold, (int, float)) or not 0 <= float(threshold) <= 1:
                raise ValueError("scoring.selection.min_score는 0 이상 1 이하여야 합니다.")
        return data

    def problem_domain(self, domain: str) -> dict[str, Any]:
        data = self._load_dict(self.root / "configs" / "problems" / f"{domain}.yaml")
        enabled = data.get("enabled", True)
        if not isinstance(enabled, bool):
            raise ValueError(f"configs/problems/{domain}.yaml 의 enabled는 bool 이어야 합니다.")
        priority_boost = data.get("priority_boost", 1.0)
        if not isinstance(priority_boost, (int, float)) or float(priority_boost) < 0:
            raise ValueError(
                f"configs/problems/{domain}.yaml 의 priority_boost는 0 이상의 수여야 합니다."
            )
        return data

    def obligation_thresholds(self) -> dict[str, Any]:
        data = self._load_dict(self.root / "configs" / "formalization" / "obligation_thresholds.yaml")
        max_unresolved = data.get("max_unresolved_obligations", 12)
        max_release = data.get("max_unresolved_for_release", 8)
        if not isinstance(max_unresolved, int) or max_unresolved < 0:
            raise ValueError("max_unresolved_obligations는 0 이상의 정수여야 합니다.")
        if not isinstance(max_release, int) or max_release < 0:
            raise ValueError("max_unresolved_for_release는 0 이상의 정수여야 합니다.")
        return data

    def lean(self) -> dict[str, Any]:
        data = self._load_dict(self.root / "configs" / "formalization" / "lean.yaml")
        build = data.get("build", {})
        if isinstance(build, dict):
            try_build = build.get("try_build", True)
            if not isinstance(try_build, bool):
                raise ValueError("formalization.build.try_build는 bool 이어야 합니다.")
        return data

    def mathlib_mapping(self) -> dict[str, Any]:
        return self._load_dict(self.root / "configs" / "formalization" / "mathlib_mapping.yaml")

    def paper_section_rules(self) -> dict[str, Any]:
        data = self._load_dict(self.root / "configs" / "paper" / "section_rules.yaml")
        required_sections = data.get("required_sections", [])
        if not isinstance(required_sections, list):
            raise ValueError("paper.required_sections는 배열이어야 합니다.")
        return data

    def paper_journal_style(self) -> dict[str, Any]:
        return self._load_dict(self.root / "configs" / "paper" / "journal_style.yaml")

    def quality_policy(self) -> dict[str, Any]:
        data = self._load_dict(self.root / "configs" / "global" / "quality_policy.yaml")
        doctor = data.get("doctor", {})
        if not isinstance(doctor, dict):
            raise ValueError("quality_policy.doctor 는 객체여야 합니다.")
        default_profile = doctor.get("default_profile", "local")
        if not isinstance(default_profile, str) or not default_profile:
            raise ValueError("quality_policy.doctor.default_profile 은 문자열이어야 합니다.")
        profiles = doctor.get("profiles", {})
        if not isinstance(profiles, dict) or not profiles:
            raise ValueError("quality_policy.doctor.profiles 는 비어 있지 않은 객체여야 합니다.")
        for profile_name, profile in profiles.items():
            if not isinstance(profile, dict):
                raise ValueError(f"quality_policy.doctor.profiles.{profile_name} 는 객체여야 합니다.")
            min_score = profile.get("min_score", 100)
            if not isinstance(min_score, (int, float)) or not 0 <= float(min_score) <= 100:
                raise ValueError(
                    f"quality_policy.doctor.profiles.{profile_name}.min_score 는 0 이상 100 이하여야 합니다."
                )
            required_checks = profile.get("required_checks", [])
            if not isinstance(required_checks, list) or any(
                not isinstance(item, str) or not item for item in required_checks
            ):
                raise ValueError(
                    f"quality_policy.doctor.profiles.{profile_name}.required_checks 는 문자열 배열이어야 합니다."
                )
        if default_profile not in profiles:
            raise ValueError("quality_policy.doctor.default_profile 이 profiles에 정의되어야 합니다.")
        return data

    def _validate_runtime(self, data: dict[str, Any]) -> None:
        engines = data.get("engines", {})
        if isinstance(engines, dict):
            for key in [
                "counterexample_backend",
                "proof_backend",
                "formalizer_backend",
                "paper_generator_backend",
            ]:
                backend = engines.get(key, "demo")
                if backend not in VALID_BACKENDS:
                    raise ValueError(f"runtime.engines.{key} 는 demo 또는 real 이어야 합니다.")
        gates = data.get("gates", {})
        if isinstance(gates, dict):
            reliability = gates.get("harvest_min_reliability", 0.75)
            if not isinstance(reliability, (int, float)) or not 0 <= float(reliability) <= 1:
                raise ValueError("runtime.gates.harvest_min_reliability는 0 이상 1 이하여야 합니다.")
        release = data.get("release", {})
        if isinstance(release, dict):
            for key in [
                "allow_demo_release",
                "require_formal_build_success",
                "require_pdf_build_success",
                "require_verification_pass",
            ]:
                value = release.get(key, False)
                if not isinstance(value, bool):
                    raise ValueError(f"runtime.release.{key} 는 bool 이어야 합니다.")
