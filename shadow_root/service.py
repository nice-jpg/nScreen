"""In-process service switch for the Android shadow agent."""

from __future__ import annotations

import threading
from typing import Any

from .adb import AdbClient
from .android_agent import AndroidShadowAgent
from .config import ShadowConfig


_LOCK = threading.Lock()
_AGENT: AndroidShadowAgent | None = None


def start_shadow_service(config: ShadowConfig | None = None) -> dict[str, Any]:
    global _AGENT
    with _LOCK:
        if _AGENT is not None and _AGENT.status()["running"]:
            return _service_status(_AGENT)
        effective_config = config or ShadowConfig.from_env()
        agent = AndroidShadowAgent(AdbClient(effective_config), effective_config)
        agent.start()
        _AGENT = agent
        return _service_status(agent)


def stop_shadow_service() -> dict[str, Any]:
    global _AGENT
    with _LOCK:
        agent = _AGENT
        _AGENT = None
        if agent is None:
            return {"ok": True, "running": False}
        agent.stop()
        return {"ok": True, "running": False, "agent": agent.status()}


def _service_status(agent: AndroidShadowAgent) -> dict[str, Any]:
    status = agent.status()
    return {"ok": True, "running": bool(status["running"]), "agent": status}
