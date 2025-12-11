import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:video_player/video_player.dart';

import '../view_model.dart';
import '../webrtc_service_stub.dart'
    if (dart.library.io) '../webrtc_service.dart';

class LiveScreen extends StatefulWidget {
  const LiveScreen({super.key});

  @override
  State<LiveScreen> createState() => _LiveScreenState();
}

class _LiveScreenState extends State<LiveScreen> {
  VideoPlayerController? _controller;
  bool _loading = true;
  String? _error;
  String? _lastUrl;
  bool _useWebRTC = true;
  WebRTCService? _webrtc;

  @override
  void initState() {
    super.initState();
    _useWebRTC = !kIsWeb;
    _init();
  }

  Future<void> _init() async {
    if (_useWebRTC) {
      await _initWebRTC();
    } else {
      await _initHls();
    }
  }

  Future<void> _initWebRTC() async {
    await _disposeHls();
    setState(() {
      _loading = true;
      _error = null;
    });
    final vm = context.read<AppViewModel>();
    final service = WebRTCService(vm.api);
    _webrtc = service;
    try {
      await service.connect();
      setState(() {
        _loading = false;
      });
    } catch (e) {
      await service.disconnect();
      setState(() {
        _error = 'WebRTC failed: $e';
        _loading = false;
      });
    }
  }

  Future<void> _initHls() async {
    await _disposeWebRTC();
    setState(() {
      _loading = true;
      _error = null;
    });

    final vm = context.read<AppViewModel>();
    final url = vm.api.hlsUrl();
    _lastUrl = url.toString();

    try {
      final c = VideoPlayerController.networkUrl(
        url,
        videoPlayerOptions: VideoPlayerOptions(mixWithOthers: true),
        formatHint: VideoFormat.hls,
      );
      await c.initialize();
      await c.setLooping(true);
      await c.play();
      setState(() {
        _controller = c;
        _loading = false;
      });
    } catch (e) {
      setState(() {
        _error = 'Failed to load stream: $e\nURL: $_lastUrl';
        _loading = false;
      });
    }
  }

  @override
  void dispose() {
    _disposeHls();
    _disposeWebRTC();
    super.dispose();
  }

  Future<void> _disposeHls() async {
    await _controller?.dispose();
    _controller = null;
  }

  Future<void> _disposeWebRTC() async {
    await _webrtc?.dispose();
    _webrtc = null;
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Live Feed')),
      body: Column(
        children: [
          Expanded(
            child: Center(
              child: _loading
                  ? const CircularProgressIndicator()
                  : _error != null
                      ? Text(_error!, textAlign: TextAlign.center)
                      : _useWebRTC
                          ? _webrtc == null
                              ? const Text('WebRTC not initialized')
                              : AspectRatio(aspectRatio: 16 / 9, child: _webrtc!.view())
                          : _controller == null
                              ? const Text('No video controller')
                              : AspectRatio(
                                  aspectRatio: _controller!.value.aspectRatio,
                                  child: VideoPlayer(_controller!),
                                ),
            ),
          ),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
            child: Column(
              children: [
                Row(
                  children: [
                    const Text('Mode:'),
                    const SizedBox(width: 12),
                    ToggleButtons(
                      borderRadius: BorderRadius.circular(8),
                      isSelected: [_useWebRTC, !_useWebRTC],
                      onPressed: (index) async {
                        final nextUseWebRTC = index == 0;
                        if (nextUseWebRTC == _useWebRTC) return;
                        setState(() => _useWebRTC = nextUseWebRTC);
                        await _init();
                      },
                      children: const [
                        Padding(
                          padding: EdgeInsets.symmetric(horizontal: 12),
                          child: Text('WebRTC'),
                        ),
                        Padding(
                          padding: EdgeInsets.symmetric(horizontal: 12),
                          child: Text('HLS'),
                        ),
                      ],
                    ),
                    const Spacer(),
                    FilledButton.icon(
                      onPressed: _init,
                      icon: const Icon(Icons.refresh),
                      label: const Text('Reload'),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ],
      ),
      floatingActionButton: FloatingActionButton.extended(
        heroTag: 'record',
        onPressed: () async {
          await context.read<AppViewModel>().manualRecord();
          if (mounted) {
            ScaffoldMessenger.of(context).showSnackBar(
              const SnackBar(content: Text('Manual recording saved')),
            );
          }
        },
        icon: const Icon(Icons.fiber_manual_record),
        label: const Text('Record'),
      ),
    );
  }
}
