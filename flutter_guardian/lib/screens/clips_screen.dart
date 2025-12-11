import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';
import '../models.dart';
import '../view_model.dart';
import 'clip_player_screen.dart';

class ClipsScreen extends StatelessWidget {
  const ClipsScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final vm = context.watch<AppViewModel>();
    return Scaffold(
      appBar: AppBar(title: const Text('Recordings')),
      body: RefreshIndicator(
        onRefresh: vm.refreshClips,
        child: vm.clips.isEmpty
            ? ListView(
                children: const [Padding(padding: EdgeInsets.all(24), child: Center(child: Text('No recordings yet')))],
              )
            : ListView.builder(
                itemCount: vm.clips.length,
                itemBuilder: (context, index) {
                  final clip = vm.clips[index];
                  return ListTile(
                    title: Text(clip.label),
                    subtitle: Text(DateFormat.yMd().add_jm().format(clip.createdAt)),
                    trailing: Text('${(clip.duration ?? 0).toStringAsFixed(0)}s'),
                    onTap: () {
                      Navigator.push(
                        context,
                        MaterialPageRoute(
                          builder: (_) => ClipPlayerScreen(
                            clip: clip,
                            api: vm.api,
                          ),
                        ),
                      );
                    },
                  );
                },
              ),
      ),
    );
  }
}
