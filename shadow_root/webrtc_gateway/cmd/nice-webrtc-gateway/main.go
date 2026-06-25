package main

import (
	"flag"
	"fmt"
	"log"
	"net/http"

	gateway "nscreen/webrtc_gateway"
)

func main() {
	listenHost := flag.String("listen-host", "127.0.0.1", "HTTP signaling listen host")
	listenPort := flag.Int("listen-port", 9765, "HTTP signaling listen port")
	icePublicIP := flag.String("ice-public-ip", "", "IP advertised in WebRTC ICE candidates")
	iceUDPPortMin := flag.Int("ice-udp-port-min", 0, "minimum UDP port for WebRTC ICE")
	iceUDPPortMax := flag.Int("ice-udp-port-max", 0, "maximum UDP port for WebRTC ICE")
	rtpListenHost := flag.String("rtp-listen-host", "0.0.0.0", "H.264 RTP listen host")
	rtpPort := flag.Int("rtp-port", 9766, "H.264 RTP/control TCP listen port")
	flag.Parse()

	server := gateway.New(gateway.Config{
		ListenHost:    *listenHost,
		ListenPort:    *listenPort,
		ICEPublicIP:   *icePublicIP,
		ICEUDPPortMin: *iceUDPPortMin,
		ICEUDPPortMax: *iceUDPPortMax,
		RTPListenHost: *rtpListenHost,
		RTPPort:       *rtpPort,
	})
	if err := server.StartMedia(); err != nil {
		log.Fatal(err)
	}
	defer server.Close()
	mux := http.NewServeMux()
	mux.HandleFunc("/", server.ServeIndex)
	mux.HandleFunc("/offer", server.ServeOffer)
	mux.HandleFunc("/webrtc/offer", server.ServeOffer)
	mux.HandleFunc("/status", server.ServeStatus)
	mux.HandleFunc("/events", server.ServeEvents)
	mux.HandleFunc("/wake", server.ServeWake)
	addr := fmt.Sprintf("%s:%d", *listenHost, *listenPort)
	log.Fatal(http.ListenAndServe(addr, mux))
}
