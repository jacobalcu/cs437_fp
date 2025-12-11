import 'package:flutter/material.dart';
import 'package:video_player/video_player.dart';
import '../api.dart';
import '../models.dart';

class ClipPlayerScreen extends StatefulWidget {
  final EventClip clip;
  final GuardianApi api;

  const ClipPlayerScreen({super.key, required this.clip, required this.api});

  @override
  State<ClipPlayerScreen> createState() => _ClipPlayerScreenState();
}

class _ClipPlayerScreenState extends State<ClipPlayerScreen> {
  VideoPlayerController? _controller;
  Future<void>? _initFuture;

  @override
  void initState() {
    super.initState();
    final url = widget.api.clipUrl(widget.clip);
    _controller = VideoPlayerController.networkUrl(url);
    _initFuture = _controller!.initialize();
  }

  @override
  void dispose() {
    _controller?.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(widget.clip.label)),
      body: _controller == null
          ? const Center(child: Text('No video controller'))
          : FutureBuilder<void>(
              future: _initFuture,
              builder: (context, snapshot) {
                if (snapshot.connectionState == ConnectionState.waiting) {
                  return const Center(child: CircularProgressIndicator());
                }
                if (snapshot.hasError) {
                  return Center(child: Text('Failed to load video: ${snapshot.error}'));
                }
                _controller!.setLooping(false);
                return Column(
                  children: [
                    AspectRatio(
                      aspectRatio: _controller!.value.aspectRatio == 0 ? 16 / 9 : _controller!.value.aspectRatio,
                      child: VideoPlayer(_controller!),
                    ),
                    const SizedBox(height: 12),
                    Row(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        IconButton(
                          icon: Icon(_controller!.value.isPlaying ? Icons.pause_circle : Icons.play_circle),
                          iconSize: 48,
                          onPressed: () {
                            setState(() {
                              if (_controller!.value.isPlaying) {
                                _controller!.pause();
                              } else {
                                _controller!.play();
                              }
                            });
                          },
                        ),
                      ],
                    ),
                  ],
                );
              },
            ),
    );
  }
}
