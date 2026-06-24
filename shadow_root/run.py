"""Run the local nScreen Android agent."""

from __future__ import annotations

import argparse
from dataclasses import replace

from .agent_runner import start_android_agent
from .config import ShadowConfig


def main(argv: list[str] | None = None) -> int:
    start_android_agent(_config_from_args(argv))
    return 0


def _config_from_args(argv: list[str] | None = None) -> ShadowConfig:
    parser = argparse.ArgumentParser(description="Start the local Android agent for a remote nScreen gateway.")
    parser.add_argument("--agent-only", action="store_true", help="Accepted for compatibility; this is the only supported mode.")
    parser.add_argument("--adb-path", help="ADB executable path.")
    parser.add_argument("--adb-serial", help="ADB device serial.")
    parser.add_argument("--android-agent-jar", help="Path to the Android H.264 shadow agent jar.")
    parser.add_argument("--android-agent-main-class", help="Android app_process main class.")
    parser.add_argument("--video-max-size", type=int, help="Maximum encoded video dimension.")
    parser.add_argument("--video-fps", type=int, help="Maximum encoded video FPS.")
    parser.add_argument("--video-bitrate", help='Encoded video bitrate, for example "2M" or "900k".')
    parser.add_argument("--video-iframe-interval-ms", type=int, help="H.264 IDR/GOP interval in milliseconds.")
    parser.add_argument("--webrtc-gateway-host", help="Remote gateway host, used for logs and diagnostics.")
    parser.add_argument("--webrtc-gateway-port", type=int, help="Remote gateway HTTP port, used for logs and diagnostics.")
    parser.add_argument("--webrtc-rtp-host", help="Remote host/IP the Android agent should connect to.")
    parser.add_argument("--webrtc-rtp-port", type=int, help="Remote TCP RTP/control port.")
    parser.add_argument("--webrtc-rtp-mtu", type=int, help="RTP packet MTU for Android H.264 sender.")
    args = parser.parse_args(argv)

    config = ShadowConfig.from_env()
    overrides = {
        "adb_path": args.adb_path,
        "adb_serial": args.adb_serial,
        "android_agent_jar": args.android_agent_jar,
        "android_agent_main_class": args.android_agent_main_class,
        "video_max_size": args.video_max_size,
        "video_fps": args.video_fps,
        "video_bitrate": args.video_bitrate,
        "video_iframe_interval_ms": args.video_iframe_interval_ms,
        "webrtc_gateway_host": args.webrtc_gateway_host,
        "webrtc_gateway_port": args.webrtc_gateway_port,
        "webrtc_rtp_host": args.webrtc_rtp_host,
        "webrtc_rtp_port": args.webrtc_rtp_port,
        "webrtc_rtp_mtu": args.webrtc_rtp_mtu,
    }
    return replace(config, **{key: value for key, value in overrides.items() if value is not None})


if __name__ == "__main__":
    raise SystemExit(main())
