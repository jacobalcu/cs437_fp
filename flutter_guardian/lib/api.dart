import 'dart:convert';

import 'package:http/http.dart' as http;
import 'models.dart';

class GuardianApi {
  GuardianApi({String? baseUrl}) : _baseUrl = baseUrl ?? 'http://192.168.50.137:9001';

  String _baseUrl;
  String get baseUrl => _baseUrl;

  void updateBaseUrl(String hostPort) {
    var sanitized = hostPort.trim();
    sanitized = sanitized.replaceFirst(RegExp(r'^https?://'), '');
    if (sanitized.endsWith('/')) sanitized = sanitized.substring(0, sanitized.length - 1);
    _baseUrl = 'http://$sanitized';
  }

  Uri _u(String path) => Uri.parse('$_baseUrl$path');

  Future<bool> fetchState() async {
    final res = await http.get(_u('/api/system/state'));
    if (res.statusCode != 200) throw Exception('state ${res.statusCode}');
    final json = jsonDecode(res.body) as Map<String, dynamic>;
    return json['out_of_home'] as bool? ?? false;
  }

  Future<bool> setMode(bool outOfHome) async {
    final res = await http.post(
      _u('/api/system/mode'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'out_of_home': outOfHome}),
    );
    if (res.statusCode != 200) throw Exception('mode ${res.statusCode}');
    final json = jsonDecode(res.body) as Map<String, dynamic>;
    return json['out_of_home'] as bool? ?? outOfHome;
  }

  Future<void> manualRecord() async {
    final res = await http.post(
      _u('/api/events/manual-record'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'label': 'manual'}),
    );
    if (res.statusCode != 200) throw Exception('manual ${res.statusCode}');
  }

  Future<List<EventClip>> listClips() async {
    final res = await http.get(_u('/api/events/recordings'));
    if (res.statusCode != 200) throw Exception('clips ${res.statusCode}');
    return EventClip.listFromJson(res.body);
  }

  Uri clipUrl(EventClip clip) {
    final path = clip.downloadUrl ?? '/api/events/recordings/${clip.id}';
    return _u(path);
  }

  Future<Map<String, dynamic>> postWebRTCOffer(String sdp) async {
    final res = await http.post(
      _u('/api/events/live/webrtc-offer'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'sdp': sdp, 'type': 'offer'}),
    );
    if (res.statusCode != 200) {
      throw Exception('webrtc offer ${res.statusCode}: ${res.body}');
    }
    return jsonDecode(res.body) as Map<String, dynamic>;
  }

  Uri hlsUrl() => _u('/api/events/live/hls/playlist.m3u8');
}
