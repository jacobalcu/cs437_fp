import 'package:flutter/widgets.dart';

/// Web stub to allow building without flutter_webrtc.
class WebRTCService {
  WebRTCService(dynamic _); // ignore: unused_element, avoid_unused_constructor_parameters
  final Widget renderer = const SizedBox.shrink();

  Future<void> init() async {}
  Future<void> connect() async {}
  Future<void> disconnect() async {}
  Future<void> dispose() async {}

  Widget view() => const SizedBox.shrink();
}
