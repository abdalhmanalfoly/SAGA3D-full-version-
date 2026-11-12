"""Phase 4 configuration loader (``config/world.yaml`` + ``.env`` overrides). Mirrors the Phase 1-3 pattern:
config files are validated at startup; unknown keys are refused; nothing is hard-coded in business logic."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

import yaml

from .transform import WorldTransform, TransformError

REPO_ROOT = Path(__file__).resolve().parents[2]              # saga-3d-phase-4/ (the CONSOLIDATED main workspace)


class WorldConfigError(ValueError):
    pass


@dataclass
class WorldConfig:
    world_protocol_version: str
    host_version_label: str
    endpoint: dict[str, Any]
    constraints: dict[str, Any]
    gesture_overrides: dict[str, bool | float]
    transform: WorldTransform

    # ------------------------------------------------------------------ useful views
    @property
    def ws_path(self) -> str:
        return str(self.endpoint.get("ws_path", "/ws/world"))

    @property
    def event_buffer_max(self) -> int:
        return int(self.constraints.get("event_buffer_max", 256))

    @property
    def max_objects(self) -> int:
        return int(self.constraints.get("max_objects", 16))

    @property
    def max_pose_hz(self) -> float:
        return float(self.constraints.get("max_pose_hz", 60.0))

    @property
    def hello_timeout_s(self) -> float:
        return float(self.endpoint.get("hello_timeout_s", 5.0))

    @property
    def heartbeat_timeout_s(self) -> float:
        return float(self.endpoint.get("heartbeat_timeout_s", 15.0))


def load_world_config(path: Path | str | None = None) -> WorldConfig:
    p = Path(path) if path else REPO_ROOT / "config" / "world.yaml"
    if not p.exists():
        raise WorldConfigError(f"missing required config file: {p} (copy from the repository checkout)")
    with p.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    _known = {"world_protocol_version", "host_version_label", "endpoint", "constraints", "gesture_overrides", "transform"}
    unknown = set(data) - _known
    if unknown:
        raise WorldConfigError(f"unknown keys in {p.name}: {sorted(unknown)}")
    ver = str(data.get("world_protocol_version", "1.0"))
    if ver != "1.0":
        raise WorldConfigError(f"world_protocol_version {ver!r} not supported by this adapter (expected '1.0')")
    try:
        tr = WorldTransform.from_config(data.get("transform"))
    except TransformError as exc:
        raise WorldConfigError(f"transform: {exc}") from None
    go = dict(data.get("gesture_overrides") or {})
    for k in go:
        if not hasattr(go, k) and k not in {"require_adapter_ack", "ack_timeout_ms", "release_ack_required", "release_ack_timeout_ms"}:
            raise WorldConfigError(f"unknown gesture_overrides key {k!r}")
    return WorldConfig(
        world_protocol_version=ver,
        host_version_label=str(data.get("host_version_label", "saga4-world-1.0")),
        endpoint=dict(data.get("endpoint") or {}),
        constraints=dict(data.get("constraints") or {}),
        gesture_overrides=go,
        transform=tr,
    )


def host_root(env: Mapping[str, str] | None = None) -> Path:
    """Root of the CONSOLIDATED host tree.

    Since the consolidation, the Phase 1-3 implementation lives INSIDE this repository (``host/``),
    and no external repository (no ``SAGA3_ROOT``) is referenced at runtime. The check simply guards
    against a broken checkout."""
    root = REPO_ROOT
    if not (root / "host" / "app" / "main.py").is_file():
        raise WorldConfigError(f"consolidated host tree not found at {root} (expected host/app/main.py)")
    return root
