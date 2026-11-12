"""Bridged access to the CONSOLIDATED Phase 1-3 pure modules (host tree inside this repository).

These modules are stdlib-only (no pydantic/fastapi), so they can load without installing the host
dependencies. The heavier host imports happen in attach.py.
"""
from __future__ import annotations

import dataclasses
import sys
from pathlib import Path

from .config import host_root


class P3:
    """Loaded-once facade over the consolidated Phase 1-3 sources of truth."""

    def __init__(self, root: Path | None = None):
        root = root or host_root()
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))
        from host.app.gesture import agent as gesture_agent
        from host.app.gesture import config as gesture_config
        from host.app.gesture import events as gesture_events
        from host.app.gesture import pinch as gesture_pinch
        from host.app.coordination import audit as coordination_audit

        self.GestureAgent = gesture_agent.GestureAgent
        self.HandSample = gesture_agent.HandSample
        self.InteractionObject = gesture_agent.InteractionObject
        self.GestureOutput = gesture_agent.GestureOutput
        self.InteractionEvent = gesture_events.InteractionEvent
        self.EventDeduper = gesture_events.EventDeduper
        self.EventType = gesture_events.EventType
        self.GestureState = gesture_events.GestureState
        self.pinch_ratio = gesture_pinch.pinch_ratio
        self.combine_view_ratios = gesture_pinch.combine_view_ratios
        self.load_gesture_config = gesture_config.load_gesture_config
        self.GestureCfg = gesture_config.GestureCfg
        self.GestureConfigError = gesture_config.GestureConfigError
        self.AuditLog = coordination_audit.AuditLog

    # ------------------------------------------------------------------ config
    def gesture_cfg_with(self, overrides: dict):
        """Phase 3 default config (config/gesture.yaml in this repository) + the documented world-adapter overrides.

        Only the handshake fields may be overridden (require_adapter_ack / ack timeouts / release ack);
        perception thresholds are never silently changed by the world adapter."""
        allowed = {"require_adapter_ack", "release_ack_required", "ack_timeout_ms", "release_ack_timeout_ms"}
        unknown = set(overrides) - allowed
        if unknown:
            raise ValueError(f"world gesture_overrides keys must be in {sorted(allowed)}, got {sorted(unknown)}")
        cfg = self.load_gesture_config()                      # default location = the Phase 1-3 config dir
        cfg = dataclasses.replace(cfg, **overrides)
        cfg.validate()
        return cfg


def p3(root: Path | None = None) -> P3:
    return P3(root)
