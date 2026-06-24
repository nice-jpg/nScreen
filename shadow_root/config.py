"""Configuration for the local nScreen Android agent runner."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path


ENV_DIR = Path(__file__).resolve().parent / "env"


@dataclass(frozen=True)
class ShadowConfig:
    adb_path: str = "adb"
    adb_serial: str = ""
    video_max_size: int = 720
    video_fps: int = 30
    video_bitrate: str = "2M"
    video_iframe_interval_ms: int = 1000
    webrtc_gateway_host: str = ""
    webrtc_gateway_port: int = 9080
    webrtc_rtp_host: str = ""
    webrtc_rtp_port: int = 9181
    webrtc_rtp_mtu: int = 1200
    android_agent_jar: str = "nScreen/shadow_root/android_agent_project/build/nice_shadow_agent.jar"
    android_agent_remote_path: str = "/data/local/tmp/nice_shadow_agent.jar"
    android_agent_main_class: str = "nice.auther.shadow.AgentMain"

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> "ShadowConfig":
        source = _config_source(env)
        return cls(
            adb_path=source.get("SHADOW_ADB_PATH", "adb"),
            adb_serial=source.get("SHADOW_ADB_SERIAL", ""),
            video_max_size=int(source.get("SHADOW_VIDEO_MAX_SIZE", "720")),
            video_fps=int(source.get("SHADOW_VIDEO_FPS", "30")),
            video_bitrate=source.get("SHADOW_VIDEO_BITRATE", "2M"),
            video_iframe_interval_ms=int(source.get("SHADOW_VIDEO_IFRAME_INTERVAL_MS", "1000")),
            webrtc_gateway_host=source.get("SHADOW_WEBRTC_GATEWAY_HOST", ""),
            webrtc_gateway_port=int(source.get("SHADOW_WEBRTC_GATEWAY_PORT", "9080")),
            webrtc_rtp_host=source.get("SHADOW_WEBRTC_RTP_HOST", ""),
            webrtc_rtp_port=int(source.get("SHADOW_WEBRTC_RTP_PORT", "9181")),
            webrtc_rtp_mtu=int(source.get("SHADOW_WEBRTC_RTP_MTU", "1200")),
            android_agent_jar=source.get(
                "SHADOW_ANDROID_AGENT_JAR",
                "nScreen/shadow_root/android_agent_project/build/nice_shadow_agent.jar",
            ),
            android_agent_remote_path=source.get("SHADOW_ANDROID_AGENT_REMOTE_PATH", "/data/local/tmp/nice_shadow_agent.jar"),
            android_agent_main_class=source.get("SHADOW_ANDROID_AGENT_MAIN_CLASS", "nice.auther.shadow.AgentMain"),
        )


def _config_source(env: dict[str, str] | None) -> dict[str, str]:
    if env is not None:
        return env
    source = _load_env_directory(ENV_DIR)
    source.update(os.environ)
    return source


def _load_env_directory(path: Path = ENV_DIR) -> dict[str, str]:
    if path.is_file():
        return _read_env_file(path)
    if not path.is_dir():
        return {}
    values: dict[str, str] = {}
    for env_file in sorted(path.glob("*.env")):
        values.update(_read_env_file(env_file))
    return values


def _read_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return values
    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        key, separator, value = line.partition("=")
        if not separator:
            continue
        key = key.strip()
        if not key:
            continue
        values[key] = _strip_env_value(value.strip())
    return values


def _strip_env_value(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value
