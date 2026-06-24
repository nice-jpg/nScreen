# nScreen

nScreen is a remote Android screen-control module for rooted Android devices.
The current production path is:

```text
Android device
  -> H.264 RTP over TCP
  -> remote Go WebRTC gateway
  -> browser WebRTC video

browser DataChannel controls
  -> remote Go WebRTC gateway
  -> Android agent TCP control channel
  -> Android MotionEvent injection
```

The host connected to the Android device no longer needs to expose a web
service. It only starts the Android agent through ADB. The public web service
runs on the remote server.

## Architecture

### Android Device

The Android side runs `nice.auther.shadow.AgentMain` through `app_process` as
root. The agent:

- mirrors the display into a `Surface`;
- encodes the screen with hardware H.264 through `MediaCodec`;
- sends length-prefixed RTP packets over TCP to the remote gateway;
- receives browser control messages on the same TCP connection;
- injects pointer events with Android `MotionEvent`, preserving all browser
  `pointerdown` / `pointermove` / `pointerup` points and timing from
  `client_time_ms`.

The agent jar is built at:

```text
nScreen/shadow_root/android_agent_project/build/nice_shadow_agent.jar
```

### Device Host

This is the local machine physically connected to the Android device through
ADB. Its only required runtime process is:

```bash
python3 -m nScreen.shadow_root.run --agent-only
```

That command reads config from `nScreen/shadow_root/env/*.env`, pushes the agent
jar to the device, kills stale agent processes, and starts the Android agent.

### Remote Server

The remote server runs the Go gateway binary. It provides:

- browser Web UI;
- WebRTC offer/answer signaling;
- WebRTC video track backed by Android H.264 RTP;
- DataChannel control forwarding to the Android agent.

Example:

```bash
nScreen/shadow_root/webrtc_gateway/build/nice-webrtc-gateway \
  --transport tcp_direct \
  --listen-host 0.0.0.0 \
  --listen-port 9080 \
  --ice-public-ip REMOTE_PUBLIC_IP \
  --ice-udp-port-min 30000 \
  --ice-udp-port-max 30010 \
  --rtp-listen-host 0.0.0.0 \
  --rtp-port 9181 \
  --agent-control-port 9182
```

`--agent-control-port` is retained for compatibility with the Android agent's
local UDP control server. Browser controls are forwarded to the agent through
the TCP RTP connection.

### User Device

Any browser-capable device accesses the remote gateway:

```text
http://REMOTE_PUBLIC_IP:9080/
```

The browser plays the WebRTC video stream and sends pointer events over a
WebRTC DataChannel. If the DataChannel is not open, `/events` is available as
an HTTP fallback.

## Required Network Setup

Open these ports on the remote server firewall/security group:

| Port | Protocol | Direction | Purpose |
| --- | --- | --- | --- |
| `9080` | TCP | browser -> remote | Web UI and WebRTC signaling |
| `9181` | TCP | Android device -> remote | H.264 RTP stream and agent control messages |
| `30000-30010` | UDP | browser <-> remote | WebRTC ICE media transport |

The Android device must be able to reach the remote server IP and TCP RTP port.
You can test from the device host:

```bash
adb shell su -c 'echo PING | toybox nc -w 3 REMOTE_PUBLIC_IP 9181; echo exit:$?'
```

The local device host does not need inbound public ports.

## Configuration

`ShadowConfig.from_env()` reads every `*.env` file under:

```text
nScreen/shadow_root/env/
```

Files are loaded in sorted filename order, then `os.environ` overrides them.
Use `shadow_root.env` for the active profile and `local.env` for local
overrides.

Current minimal active variables:

```sh
SHADOW_PORT=8080

SHADOW_VIDEO_BACKEND=webrtc_h264
SHADOW_VIDEO_MAX_SIZE=720
SHADOW_VIDEO_FPS=30
SHADOW_VIDEO_BITRATE=2M
SHADOW_VIDEO_IFRAME_INTERVAL_MS=1000

SHADOW_WEBRTC_GATEWAY_MANAGED=false
SHADOW_WEBRTC_GATEWAY_HOST=REMOTE_PUBLIC_IP
SHADOW_WEBRTC_GATEWAY_PORT=9080
SHADOW_WEBRTC_ICE_PUBLIC_IP=REMOTE_PUBLIC_IP
SHADOW_WEBRTC_ICE_UDP_PORT_MIN=30000
SHADOW_WEBRTC_ICE_UDP_PORT_MAX=30010

SHADOW_WEBRTC_TRANSPORT=tcp_direct
SHADOW_WEBRTC_RTP_HOST=REMOTE_PUBLIC_IP
SHADOW_WEBRTC_RTP_PORT=9181
SHADOW_WEBRTC_CONTROL_PORT=9182

SHADOW_ANDROID_AGENT_JAR=nScreen/shadow_root/android_agent_project/build/nice_shadow_agent.jar
```

If the repository still contains an older jar path after the directory rename,
update `SHADOW_ANDROID_AGENT_JAR` before starting `--agent-only`.

## Build Commands

Build the Android agent jar:

```bash
python3 nScreen/shadow_root/android_agent_project/build_android_agent.py
```

Build the Go gateway binary:

```bash
GOCACHE=/tmp/nScreen_gocache \
go build -o nScreen/shadow_root/webrtc_gateway/build/nice-webrtc-gateway \
  ./nScreen/shadow_root/webrtc_gateway/cmd/nice-webrtc-gateway
```

For a Linux x86_64 remote server:

```bash
GOOS=linux GOARCH=amd64 GOCACHE=/tmp/nScreen_gocache \
go build -o /tmp/nScreen-webrtc-gateway-linux-amd64 \
  ./nScreen/shadow_root/webrtc_gateway/cmd/nice-webrtc-gateway
```

## Runtime Commands

Start the Android agent on the device host:

```bash
python3 -m nScreen.shadow_root.run --agent-only
```

Run it in the background:

```bash
python3 -c 'import subprocess; log=open("/tmp/nScreen_agent.log", "ab", buffering=0); subprocess.Popen(["python3", "-u", "-m", "nScreen.shadow_root.run", "--agent-only"], stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, start_new_session=True)'
```

Stop it:

```bash
pkill -f 'nScreen.shadow_root.run --agent-only'
```

Legacy local HTTP/session mode is still available:

```bash
python3 -m nScreen.shadow_root.run
```

This starts the Python `shadow_root` HTTP service and can manage a local gateway
when `SHADOW_WEBRTC_GATEWAY_MANAGED=true`. The current remote-server
architecture does not require this mode.

Replay a recorded bundle:

```bash
python3 -m nScreen.replayer <bundle.json>
```

## Remote Gateway HTTP Interfaces

### `GET /`

Returns the browser Web UI.

### `GET /status`

Returns gateway and agent readiness.

Example response:

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

HTTP fallback for browser control events. The preferred path is WebRTC
DataChannel. Payload schema:

```json
{
  "events": [
    {
      "type": "pointerdown",
      "pointer_id": 1,
      "x": 120.5,
      "y": 300.0,
      "width": 402,
      "height": 648.65625,
      "pressure": 0.5,
      "client_time_ms": 1000
    },
    {
      "type": "pointermove",
      "pointer_id": 1,
      "x": 130.0,
      "y": 310.0,
      "width": 402,
      "height": 648.65625,
      "pressure": 0.5,
      "client_time_ms": 1016
    },
    {
      "type": "pointerup",
      "pointer_id": 1,
      "x": 140.0,
      "y": 320.0,
      "width": 402,
      "height": 648.65625,
      "pressure": 0,
      "client_time_ms": 1033
    }
  ]
}
```

The Android agent preserves all received points and maps browser coordinates to
device screen coordinates.

### `POST /wake`

Sends a wake request to the Android agent. The agent executes:

```text
input keyevent KEYCODE_WAKEUP
input keyevent KEYCODE_MENU
```

## Python Function Interfaces

### `nScreen.shadow_root`

Public exports:

- `ShadowConfig`
- `ShadowSession`
- `start_shadow_session(config=None, *, session=None)`
- `AdbClient`
- `AndroidShadowAgent`
- `WebRtcGateway`
- `SshReverseTunnel`
- `tunnel_access_url`
- `TouchEventEncoder`
- `InputStreamInjector`
- `MjpegScreencapStreamer`
- `WebRtcH264Streamer`

Current recommended local entry point:

```python
from nScreen.shadow_root.agent_runner import start_android_agent
from nScreen.shadow_root import ShadowConfig

config = ShadowConfig.from_env()
start_android_agent(config)
```

Legacy Python-hosted UI entry point:

```python
from nScreen.shadow_root import ShadowConfig, start_shadow_session

session = start_shadow_session(config=ShadowConfig.from_env())
```

### `nScreen.replayer`

Public exports:

- `ReplayBundle`
- `replay_bundle(bundle, device=None, remote_packet_dir=..., replay_helper=...)`
- `bundle_to_packet(bundle)`
- `DEFAULT_REMOTE_PACKET_DIR`
- `DEFAULT_REPLAY_HELPER`

Example:

```python
from nScreen.replayer import replay_bundle

result = replay_bundle("recording_bundle.json")
```

Bundle schema requirements:

- `schema_version`
- `created_at`
- `input_device`
- `screen.width`
- `screen.height`
- `raw_getevent_log` or `piar_base64`

`replay_bundle()` pushes a PIAR packet to the rooted Android device and executes:

```text
/data/local/tmp/pi_input_replay <input_device> <packet_path> 0 0
```

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
- `--transport`: Android-to-gateway media transport: `tcp_direct`,
  `adb_reverse_tcp`, or `udp_rtp`.
- `--rtp-listen-host`: host/IP for H.264 RTP TCP/UDP listener.
- `--rtp-port`: H.264 RTP listener port.
- `--agent-control-port`: compatibility control port.
- `--events-url`: deprecated.
- `--events-token`: deprecated.

## Troubleshooting

Check remote gateway status:

```bash
curl http://REMOTE_PUBLIC_IP:9080/status
```

If it shows `control_ready=false`:

- confirm the local agent-only process is running;
- confirm stale Android `app_process` agents were killed;
- confirm the device can reach `REMOTE_PUBLIC_IP:9181`;
- check `/tmp/nScreen_agent.log` or the log path used when starting the
  agent.

Check Android agent process:

```bash
adb shell ps -A -o PID,ARGS | grep nice.auther.shadow.AgentMain
```

Check remote gateway logs on the server:

```bash
tail -f /var/log/nScreen/nice-webrtc-gateway.log
```

Expected gateway log after a healthy agent connection:

```text
rtp tcp accepted
agent control attached
rtp tcp forwarded
```
