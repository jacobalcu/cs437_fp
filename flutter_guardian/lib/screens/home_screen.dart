import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../view_model.dart';
import 'live_screen.dart';
import 'clips_screen.dart';
import 'settings_screen.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  @override
  void initState() {
    super.initState();
    Future.microtask(() => context.read<AppViewModel>().bootstrap());
  }

  @override
  Widget build(BuildContext context) {
    final vm = context.watch<AppViewModel>();
    return Scaffold(
      appBar: AppBar(
        title: const Text('Guardian'),
      ),
      body: ListView(
        children: [
          SwitchListTile(
            title: const Text('Out of Home'),
            value: vm.outOfHome,
            onChanged: (v) => vm.setMode(v),
          ),
          ListTile(
            title: const Text('Live Feed'),
            trailing: const Icon(Icons.chevron_right),
            onTap: () => Navigator.push(
              context,
              MaterialPageRoute(builder: (_) => const LiveScreen()),
            ),
          ),
          ListTile(
            title: const Text('Recordings'),
            trailing: const Icon(Icons.chevron_right),
            onTap: () => Navigator.push(
              context,
              MaterialPageRoute(builder: (_) => const ClipsScreen()),
            ),
          ),
          ListTile(
            title: const Text('Settings'),
            trailing: const Icon(Icons.chevron_right),
            onTap: () => Navigator.push(
              context,
              MaterialPageRoute(builder: (_) => const SettingsScreen()),
            ),
          ),
        ],
      ),
    );
  }
}
