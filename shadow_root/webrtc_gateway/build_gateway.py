"""Build and optionally deploy the nScreen WebRTC gateway binary."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import os
import shlex
import subprocess
import time
import urllib.error
import urllib.request


GATEWAY_PACKAGE = "./nScreen/shadow_root/webrtc_gateway/cmd/nice-webrtc-gateway"


@dataclass(frozen=True)
class DeployConfig:
    server: str
    remote_path: str
    listen_port: int
    rtp_port: int
    ice_public_ip: str
    ice_udp_port_min: int
    ice_udp_port_max: int
    log_path: str


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    root = Path(__file__).resolve().parent
    repo_root = root.parents[2]
    output = _build_output_path(root, deploy=bool(args.server), output=args.output)

    build_gateway(
        repo_root,
        output,
        goos="linux" if args.server else args.goos,
        goarch=args.goarch,
    )
    print(output)

    if args.server:
        deploy_gateway(
            output,
            DeployConfig(
                server=args.server,
                remote_path=args.remote_path,
                listen_port=args.listen_port,
                rtp_port=args.rtp_port,
                ice_public_ip=args.ice_public_ip or _host_from_server(args.server),
                ice_udp_port_min=args.ice_udp_port_min,
                ice_udp_port_max=args.ice_udp_port_max,
                log_path=args.log_path,
            ),
        )
    return 0


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the nScreen WebRTC gateway. Pass [user@]host to deploy and restart it remotely.",
    )
    parser.add_argument("server", nargs="?", help="Optional remote server, in host or user@host form.")
    parser.add_argument("--output", help="Local output binary path.")
    parser.add_argument("--goos", default=os.environ.get("GOOS", ""), help="Target GOOS for local-only builds.")
    parser.add_argument("--goarch", default=os.environ.get("GOARCH", "amd64"), help="Target GOARCH.")
    parser.add_argument("--remote-path", default="nScreen/nice-webrtc-gateway", help="Remote binary path.")
    parser.add_argument("--listen-port", type=int, default=9080, help="Remote HTTP/WebRTC signaling port.")
    parser.add_argument("--rtp-port", type=int, default=9181, help="Remote Android RTP/control TCP port.")
    parser.add_argument("--ice-public-ip", default="", help="ICE public IP. Defaults to the host part of server.")
    parser.add_argument("--ice-udp-port-min", type=int, default=30000, help="Minimum WebRTC ICE UDP port.")
    parser.add_argument("--ice-udp-port-max", type=int, default=30010, help="Maximum WebRTC ICE UDP port.")
    parser.add_argument("--log-path", default="nScreen/nice-webrtc-gateway.log", help="Remote gateway log path.")
    return parser.parse_args(argv)


def _build_output_path(root: Path, *, deploy: bool, output: str | None) -> Path:
    if output:
        return Path(output)
    name = "nice-webrtc-gateway-linux-amd64" if deploy else "nice-webrtc-gateway"
    return root / "build" / name


def build_gateway(repo_root: Path, output: Path, *, goos: str, goarch: str) -> None:
    target = "/".join(part for part in [goos or os.environ.get("GOOS", "local"), goarch or os.environ.get("GOARCH", "")] if part)
    print(f"[build] target={target} output={output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.setdefault("GOCACHE", "/private/tmp/nscreen_gocache")
    if goos:
        env["GOOS"] = goos
    if goarch:
        env["GOARCH"] = goarch
    subprocess.run(
        ["go", "build", "-o", str(output), GATEWAY_PACKAGE],
        cwd=repo_root,
        env=env,
        check=True,
    )
    print(f"[build] ok bytes={output.stat().st_size}")


def deploy_gateway(binary: Path, config: DeployConfig) -> None:
    remote_dir = _dirname(config.remote_path)
    remote_tmp = f"{config.remote_path}.tmp"
    public_url = f"http://{config.ice_public_ip}:{config.listen_port}/"
    status_url = f"http://{config.ice_public_ip}:{config.listen_port}/status"

    print(f"[deploy] server={config.server}")
    print(f"[deploy] remote_path={config.remote_path}")
    print(f"[deploy] web_url={public_url}")
    print(f"[deploy] rtp_tcp={config.ice_public_ip}:{config.rtp_port}")
    print(f"[deploy] ice_udp={config.ice_udp_port_min}-{config.ice_udp_port_max}")
    print(f"[deploy] log_path={config.log_path}")

    print(f"[deploy] mkdir {remote_dir}")
    run_ssh(config.server, f"mkdir -p {shlex.quote(remote_dir)}")
    print(f"[deploy] upload {binary} -> {config.server}:{remote_tmp}")
    run_scp(binary, config.server, remote_tmp)
    print("[deploy] install binary")
    run_ssh(
        config.server,
        " ".join(
            [
                "mv",
                shlex.quote(remote_tmp),
                shlex.quote(config.remote_path),
                "&&",
                "chmod",
                "+x",
                shlex.quote(config.remote_path),
            ]
        ),
    )
    print("[deploy] restart gateway")
    run_ssh(config.server, _restart_command(config))
    probe = probe_status(status_url)
    print("[deploy] result")
    print(f"  binary: {config.server}:{config.remote_path}")
    print(f"  web:    {public_url}")
    print(f"  status: {status_url}")
    print(f"  rtp:    tcp://{config.ice_public_ip}:{config.rtp_port}")
    print(f"  log:    {config.server}:{config.log_path}")
    print(f"  probe:  {probe}")


def _restart_command(config: DeployConfig) -> str:
    command = [
        config.remote_path,
        "--listen-host",
        "0.0.0.0",
        "--listen-port",
        str(config.listen_port),
        "--ice-public-ip",
        config.ice_public_ip,
        "--ice-udp-port-min",
        str(config.ice_udp_port_min),
        "--ice-udp-port-max",
        str(config.ice_udp_port_max),
        "--rtp-listen-host",
        "0.0.0.0",
        "--rtp-port",
        str(config.rtp_port),
    ]
    quoted_command = " ".join(shlex.quote(part) for part in command)
    log_path = shlex.quote(config.log_path)
    log_dir = shlex.quote(_dirname(config.log_path))
    process_pattern = _pkill_pattern(Path(config.remote_path).name)
    return (
        f"mkdir -p {log_dir} && "
        f"(pkill -f {shlex.quote(process_pattern)} || true) && "
        f"nohup {quoted_command} > {log_path} 2>&1 < /dev/null &"
    )


def run_ssh(server: str, command: str) -> None:
    subprocess.run(["ssh", server, command], check=True)


def run_scp(local_path: Path, server: str, remote_path: str) -> None:
    subprocess.run(["scp", str(local_path), f"{server}:{remote_path}"], check=True)


def probe_status(url: str, *, attempts: int = 8, delay_seconds: float = 0.5) -> str:
    last_error = ""
    for _ in range(attempts):
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                body = response.read(500).decode("utf-8", errors="replace").strip()
                return f"ok http={response.status} body={body}"
        except urllib.error.URLError as exc:
            last_error = str(exc)
        except Exception as exc:
            last_error = str(exc)
        time.sleep(delay_seconds)
    return f"failed {last_error}"


def _host_from_server(server: str) -> str:
    return server.rsplit("@", 1)[-1].split(":", 1)[0]


def _dirname(path: str) -> str:
    if "/" not in path.rstrip("/"):
        return "."
    return path.rstrip("/").rsplit("/", 1)[0] or "/"


def _pkill_pattern(name: str) -> str:
    if not name:
        return name
    return f"[{name[0]}]{name[1:]}"


if __name__ == "__main__":
    raise SystemExit(main())
