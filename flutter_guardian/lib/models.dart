import 'dart:convert';

class EventClip {
  final String id;
  final String label;
  final DateTime createdAt;
  final double? duration;
  final String clipPath;
  final String? downloadUrl;

  EventClip({required this.id, required this.label, required this.createdAt, required this.clipPath, this.duration, this.downloadUrl});

  factory EventClip.fromJson(Map<String, dynamic> json) {
    return EventClip(
      id: json['id'] as String,
      label: json['label'] as String? ?? 'clip',
      createdAt: DateTime.fromMillisecondsSinceEpoch(((json['created_ts'] ?? 0) * 1000).toInt()),
      duration: (json['duration'] as num?)?.toDouble(),
      clipPath: json['clip_path'] as String? ?? '',
      downloadUrl: json['download_url'] as String?,
    );
  }

  static List<EventClip> listFromJson(String body) {
    final decoded = jsonDecode(body) as List<dynamic>;
    return decoded.map((e) => EventClip.fromJson(e as Map<String, dynamic>)).toList();
  }
}
