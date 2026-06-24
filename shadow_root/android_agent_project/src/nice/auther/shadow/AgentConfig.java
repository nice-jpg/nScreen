package nice.auther.shadow;

import java.util.HashMap;
import java.util.Map;

final class AgentConfig {
    final int maxSize;
    final int fps;
    final String bitrate;
    final int iFrameIntervalMs;
    final String rtpHost;
    final int rtpPort;
    final int mtu;

    private AgentConfig(
            int maxSize,
            int fps,
            String bitrate,
            int iFrameIntervalMs,
            String rtpHost,
            int rtpPort,
            int mtu
    ) {
        this.maxSize = maxSize;
        this.fps = fps;
        this.bitrate = bitrate;
        this.iFrameIntervalMs = iFrameIntervalMs;
        this.rtpHost = rtpHost;
        this.rtpPort = rtpPort;
        this.mtu = mtu;
    }

    static AgentConfig parse(String[] args) {
        Map<String, String> values = new HashMap<>();
        for (int i = 0; i < args.length; i++) {
            if (i + 1 < args.length) {
                values.put(args[i], args[i + 1]);
                i++;
            }
        }
        AgentConfig config = new AgentConfig(
                intValue(values, "--max-size", 720),
                intValue(values, "--fps", 30),
                values.getOrDefault("--bitrate", "2M"),
                intValue(values, "--i-frame-interval-ms", 1000),
                values.getOrDefault("--rtp-host", "127.0.0.1"),
                intValue(values, "--rtp-port", 0),
                intValue(values, "--mtu", 1200)
        );
        config.validate();
        return config;
    }

    int widthHint() {
        return maxSize;
    }

    int heightHint() {
        return maxSize;
    }

    int bitrateBitsPerSecond() {
        String normalized = bitrate.trim().toUpperCase();
        if (normalized.endsWith("M")) {
            return Integer.parseInt(normalized.substring(0, normalized.length() - 1)) * 1000 * 1000;
        }
        if (normalized.endsWith("K")) {
            return Integer.parseInt(normalized.substring(0, normalized.length() - 1)) * 1000;
        }
        return Integer.parseInt(normalized);
    }

    private void validate() {
        if (rtpPort <= 0) {
            throw new IllegalArgumentException("rtp-port is required");
        }
        if (fps <= 0 || maxSize <= 0 || mtu < 256) {
            throw new IllegalArgumentException("max-size/fps/mtu are invalid");
        }
    }

    private static int intValue(Map<String, String> values, String key, int fallback) {
        if (!values.containsKey(key)) {
            return fallback;
        }
        return Integer.parseInt(values.get(key));
    }
}
