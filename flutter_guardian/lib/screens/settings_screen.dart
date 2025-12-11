import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../view_model.dart';

class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key});

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  late TextEditingController _controller;

  @override
  void initState() {
    super.initState();
    final vm = context.read<AppViewModel>();
    _controller = TextEditingController(text: vm.baseUrl);
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final vm = context.watch<AppViewModel>();
    return Scaffold(
      appBar: AppBar(title: const Text('Settings')),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('Pi Host (host:port)', style: TextStyle(fontWeight: FontWeight.bold)),
            TextField(
              controller: _controller,
              decoration: const InputDecoration(hintText: '192.168.50.137:9001'),
              autocorrect: false,
            ),
            const SizedBox(height: 12),
            ElevatedButton(
              onPressed: () {
                vm.updateBaseUrl(_controller.text);
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(content: Text('Updated base URL')),
                );
              },
              child: const Text('Apply'),
            ),
            const SizedBox(height: 12),
            Text('Current: ${vm.baseUrl}'),
          ],
        ),
      ),
    );
  }
}
