package nice.auther.shadow;

import android.view.Surface;

public final class AgentMain {
    private AgentMain() {
    }

    public static void main(String[] args) throws Exception {
        AgentConfig config = AgentConfig.parse(args);
        System.err.println("nice_shadow_agent start transport=tcp_direct rtpHost=" + config.rtpHost + " rtpPort=" + config.rtpPort + " fps=" + config.fps + " maxSize=" + config.maxSize + " bitrate=" + config.bitrate);
        final RtpSender[] senderRef = new RtpSender[1];
        try {
            DisplayMirror.DisplayInfo displayInfo = DisplayMirror.mainDisplayInfo();
            DisplayMirror.EncodedSize encodedSize = DisplayMirror.encodedSize(displayInfo, config.maxSize);
            System.err.println("nice_shadow_agent display width=" + displayInfo.width + " height=" + displayInfo.height + " encodedWidth=" + encodedSize.width + " encodedHeight=" + encodedSize.height);
            RemoteControlHandler controlHandler = new RemoteControlHandler(new RemoteInputInjector(displayInfo.width, displayInfo.height));
            senderRef[0] = createSender(config, controlHandler);
            H264SurfaceEncoder encoder = new H264SurfaceEncoder(config, new H264SurfaceEncoder.FrameSink() {
                @Override
                public void onFrame(byte[] annexBFrame, long presentationTimeUs, boolean marker) throws Exception {
                    senderRef[0].sendAnnexBFrame(annexBFrame, presentationTimeUs, marker);
                }
            });
            Surface inputSurface = encoder.start(encodedSize.width, encodedSize.height);
            DisplayMirror mirror = DisplayMirror.create(inputSurface, displayInfo, encodedSize);
            try {
                while (true) {
                    if (controlHandler.consumeIdrRequest()) {
                        System.err.println("nice_shadow_agent request key frame");
                        encoder.requestKeyFrame();
                    }
                    Thread.sleep(50L);
                    if (!inputSurface.isValid()) {
                        System.err.println("nice_shadow_agent input surface invalid");
                        break;
                    }
                }
            } finally {
                mirror.close();
                encoder.close();
            }
        } catch (Throwable throwable) {
            System.err.println("nice_shadow_agent fatal " + throwable);
            throwable.printStackTrace(System.err);
            throw throwable;
        } finally {
            if (senderRef[0] != null) {
                senderRef[0].close();
            }
        }
    }

    private static RtpSender createSender(AgentConfig config, RemoteControlHandler controlHandler) throws Exception {
        return new TcpRtpSender(config.rtpHost, config.rtpPort, config.mtu, controlHandler);
    }
}
