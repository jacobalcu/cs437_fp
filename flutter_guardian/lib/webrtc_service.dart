import 'dart:async';

import 'package:flutter/widgets.dart';
import 'package:flutter_webrtc/flutter_webrtc.dart';

import 'api.dart';

/// Handles the WebRTC connection to the Pi and exposes a video renderer
/// that LiveScreen can embed.
class WebRTCService {
  WebRTCService(this.api);

  final GuardianApi api;

  RTCPeerConnection? _pc;
  final RTCVideoRenderer renderer = RTCVideoRenderer();
  bool _initialized = false;

  Future<void> init() async {
    if (_initialized) return;
    await renderer.initialize();
    _initialized = true;
  }

  /// Create or recreate the peer connection and start streaming.
  Future<void> connect() async {
    await init();

    // Tear down any previous connection.
    await disconnect();

    // Very simple config; the Pi also uses this STUN server by default.
    final config = <String, dynamic>{
      'iceServers': [
        {'urls': 'stun:stun.l.google.com:19302'},
      ],
      'sdpSemantics': 'unified-plan',
    };

    // Ask to receive both audio and video (what flutter_webrtc 0.9.x expects).
    final offerConstraints = <String, dynamic>{
      'mandatory': {
        'OfferToReceiveAudio': true,
        'OfferToReceiveVideo': true,
      },
      'optional': [],
    };

    final pc = await createPeerConnection(config, offerConstraints);
    _pc = pc;

    // When the Pi sends us a track, attach its stream to the renderer.
    pc.onTrack = (RTCTrackEvent event) {
      if (event.streams.isNotEmpty) {
        renderer.srcObject = event.streams.first;
      }
    };

    // Older stacks may use onAddStream instead of onTrack.
    pc.onAddStream = (MediaStream stream) {
      renderer.srcObject = stream;
    };

    // Create offer and include all ICE candidates in the SDP
    // (no trickle ICE; the server does the same on its side).
    final offer = await pc.createOffer();
    await pc.setLocalDescription(offer);
    await _waitForIceGatheringComplete(pc);

    final localDesc = await pc.getLocalDescription();
    if (localDesc == null || localDesc.sdp == null) {
      throw Exception('Local description missing after createOffer');
    }

    // Send offer to Pi and get answer.
    final answerJson = await api.postWebRTCOffer(localDesc.sdp!);

    final answer = RTCSessionDescription(
      answerJson['sdp'] as String,
      answerJson['type'] as String,
    );

    await pc.setRemoteDescription(answer);

    // If the server sends back ICE servers, apply them (best-effort).
    final iceServers = answerJson['iceServers'];
    if (iceServers is List && iceServers.isNotEmpty) {
      try {
        await pc.setConfiguration(<String, dynamic>{'iceServers': iceServers});
      } catch (_) {
        // Not fatal; connection can still succeed with the original config.
      }
    }
  }

  /// Gracefully close the current connection, if any.
  Future<void> disconnect() async {
    final pc = _pc;
    _pc = null;

    // Detach video but keep the renderer alive so connect() can reuse it.
    renderer.srcObject = null;

    if (pc != null) {
      try {
        await pc.close();
      } catch (_) {
        // ignore
      }
    }
  }

  Future<void> dispose() async {
    await disconnect();
    await renderer.dispose();
  }

  /// Convenience helper for widgets to display the video.
  Widget view() => RTCVideoView(renderer);

  Future<void> _waitForIceGatheringComplete(RTCPeerConnection pc) async {
    if (pc.iceGatheringState ==
        RTCIceGatheringState.RTCIceGatheringStateComplete) {
      return;
    }
    final completer = Completer<void>();
    pc.onIceGatheringState = (RTCIceGatheringState state) {
      if (state ==
              RTCIceGatheringState.RTCIceGatheringStateComplete &&
          !completer.isCompleted) {
        completer.complete();
      }
    };
    await completer.future
        .timeout(const Duration(seconds: 5), onTimeout: () {});
  }
}
