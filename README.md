# nScreen

nScreen is a remote Android screen-control module for rooted Android devices.
The active architecture is a direct remote WebRTC gateway path:

```text
Android device
  -> H.264 RTP/control over one TCP connection
  -> remote Go WebRTC gateway
  -> browser WebRTC video

browser DataChannel controls
  -> remote Go WebRTC gateway
  -> Android agent TCP control channel
  -> Android MotionEvent injection
```

The host connected to the Android device only starts the Android agent through
ADB. It does not expose a web service and does not proxy browser traffic.

## Architecture

### Android Device

The Android side runs `nice.auther.shadow.AgentMain` with `app_process` as root.
The agent captures the display into a `Surface`, encodes it with hardware H.264
through `MediaCodec`, sends length-prefixed RTP packets to the remote gateway,
and receives control messages on the same TCP connection.

Browser pointer events are injected with Android `MotionEvent`. All received
`pointerdown`, `pointermove`, and `pointerup` points are replayed in order; the
agent does not collapse a gesture into only start and end coordinates.

### Device Host

The device host is the machine physically connected to the Android device by
ADB. Its runtime command is:

```bash
python3 -m nScreen.shadow_root.run
```

`--agent-only` is accepted for compatibility, but this is now the only supported
mode.

### Remote Server

The remote server runs the Go gateway. It serves the Web UI, handles WebRTC
offer/answer signaling, receives Android H.264 RTP over TCP, and forwards
browser controls to the connected Android agent.

Example:

```bash
nScreen/shadow_root/webrtc_gateway/build/nice-webrtc-gateway \
  --listen-host 0.0.0.0 \
  --listen-port 9080 \
  --ice-public-ip REMOTE_PUBLIC_IP \
  --ice-udp-port-min 30000 \
  --ice-udp-port-max 30010 \
  --rtp-listen-host 0.0.0.0 \
  --rtp-port 9181
```

### User Device

Any browser-capable device can access:

```text
http://REMOTE_PUBLIC_IP:9080/
```

The browser plays the WebRTC video and sends pointer events through a WebRTC
DataChannel. `POST /events` remains as an HTTP fallback when the DataChannel is
not open.

## Required Network Setup

Open these ports on the remote server firewall or security group:

| Port | Protocol | Direction | Purpose |
| --- | --- | --- | --- |
| `9080` | TCP | browser -> remote | Web UI and WebRTC signaling |
| `9181` | TCP | Android device -> remote | H.264 RTP stream and agent control |
| `30000-30010` | UDP | browser <-> remote | WebRTC ICE media transport |

The Android device must be able to reach `REMOTE_PUBLIC_IP:9181`. The local
device host does not need inbound public ports.

## Configuration

`ShadowConfig.from_env()` reads every `*.env` file under:

```text
nScreen/shadow_root/env/
```

Files are loaded in sorted filename order, then `os.environ` overrides them.
Use `shadow_root.env` for shared defaults and `local.env` for private runtime
overrides.

Minimal active variables:

```sh
SHADOW_VIDEO_MAX_SIZE=720
SHADOW_VIDEO_FPS=30
SHADOW_VIDEO_BITRATE=2M
SHADOW_VIDEO_IFRAME_INTERVAL_MS=1000

SHADOW_WEBRTC_GATEWAY_HOST=REMOTE_PUBLIC_IP
SHADOW_WEBRTC_GATEWAY_PORT=9080
SHADOW_WEBRTC_RTP_HOST=REMOTE_PUBLIC_IP
SHADOW_WEBRTC_RTP_PORT=9181

SHADOW_ANDROID_AGENT_JAR=nScreen/shadow_root/android_agent_project/build/nice_shadow_agent.jar
```

Optional ADB overrides:

```sh
SHADOW_ADB_PATH=adb
SHADOW_ADB_SERIAL=
```

## Build Commands

Build the Android agent jar:

```bash
python3 nScreen/shadow_root/android_agent_project/build_android_agent.py
```

Build the Go gateway binary:

```bash
python3 nScreen/shadow_root/webrtc_gateway/build_gateway.py
```

Build and deploy to a remote Linux x86_64 server:

```bash
python3 nScreen/shadow_root/webrtc_gateway/build_gateway.py user@REMOTE_PUBLIC_IP
```

When a server is provided, the script cross-compiles the gateway for
`linux/amd64`, uploads it to `nScreen/nice-webrtc-gateway` on the remote server,
and restarts it with the standard ports. Override defaults as needed:

```bash
python3 nScreen/shadow_root/webrtc_gateway/build_gateway.py user@REMOTE_PUBLIC_IP \
  --remote-path nScreen/nice-webrtc-gateway \
  --listen-port 9080 \
  --rtp-port 9181 \
  --ice-udp-port-min 30000 \
  --ice-udp-port-max 30010
```

## Runtime Commands

Start the Android agent on the device host:

```bash
python3 -m nScreen.shadow_root.run
```

Run it in the background:

```bash
python3 -c 'import subprocess; log=open("/tmp/nScreen_agent.log", "ab", buffering=0); subprocess.Popen(["python3", "-u", "-m", "nScreen.shadow_root.run"], stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, start_new_session=True)'
```

Stop the local runner:

```bash
pkill -f 'nScreen.shadow_root.run'
```

## Remote Gateway HTTP Interfaces

### `GET /`

Returns the browser Web UI.

### `GET /status`

Returns gateway and Android agent readiness.

```json
{
  "ok": true,
  "recording": false,
  "video": {
    "backend": "webrtc_h264",
    "transport": "tcp_direct",
    "rtp_port": 9181
  },
  "webrtc_gateway": {
    "running": true,
    "control_ready": true,
    "listen_host": "0.0.0.0",
    "listen_port": 9080,
    "ice_public_ip": "REMOTE_PUBLIC_IP"
  }
}
```

`control_ready=false` means the Android agent has not connected to the gateway.

### `POST /webrtc/offer`

Accepts a non-trickle WebRTC offer and returns an answer.

Request:

```json
{"type": "offer", "sdp": "..."}
```

Response:

```json
{"type": "answer", "sdp": "..."}
```

`POST /offer` is an alias.

### `POST /events`

HTTP fallback for browser control events. The preferred path is the WebRTC
DataChannel.

```json
{
  "events": [
    {
      "type": "pointermove",
      "pointer_id": 1,
      "x": 120.5,
      "y": 300.0,
      "width": 402,
      "height": 648.65625,
      "pressure": 0.5,
      "client_time_ms": 1000
    }
  ]
}
```

### `POST /wake`

Sends a wake request to the Android agent.

## Python Function Interfaces

`nScreen.shadow_root` exports:

- `ShadowConfig`
- `AdbClient`
- `AndroidShadowAgent`
- `start_android_agent(config=None)`
- `start_shadow_service(config=None)`
- `stop_shadow_service()`

Example:

```python
from nScreen.shadow_root import ShadowConfig, start_shadow_service, stop_shadow_service

config = ShadowConfig.from_env()
start_result = start_shadow_service(config)
stop_result = stop_shadow_service()
```

`start_shadow_service()` and `stop_shadow_service()` are non-blocking,
same-process switches for the Android agent. `start_android_agent()` remains the
blocking runner used by `python3 -m nScreen.shadow_root.run`.

## Go Gateway CLI

Binary:

```text
nScreen/shadow_root/webrtc_gateway/build/nice-webrtc-gateway
```

Flags:

- `--listen-host`: HTTP/WebRTC signaling bind host.
- `--listen-port`: HTTP/WebRTC signaling bind port.
- `--ice-public-ip`: public IP advertised in ICE candidates.
- `--ice-udp-port-min`: minimum UDP port for WebRTC ICE.
- `--ice-udp-port-max`: maximum UDP port for WebRTC ICE.
- `--rtp-listen-host`: host/IP for the Android TCP RTP/control listener.
- `--rtp-port`: TCP RTP/control listener port.

## Troubleshooting

Check remote gateway status:

```bash
curl http://REMOTE_PUBLIC_IP:9080/status
```

If `control_ready=false`, confirm the device host agent is running and the
Android device can reach `REMOTE_PUBLIC_IP:9181`.

Expected gateway log after a healthy agent connection:

```text
rtp tcp accepted
agent control attached
rtp tcp forwarded
```
