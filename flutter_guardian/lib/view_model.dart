import 'package:flutter/foundation.dart';
import 'api.dart';
import 'models.dart';

class AppViewModel extends ChangeNotifier {
  final GuardianApi api;
  bool outOfHome = false;
  bool loading = false;
  String baseUrl;
  List<EventClip> clips = const [];

  AppViewModel({GuardianApi? api})
      : api = api ?? GuardianApi(),
        baseUrl = (api ?? GuardianApi()).baseUrl;

  Future<void> bootstrap() async {
    loading = true;
    notifyListeners();
    try {
      outOfHome = await api.fetchState();
      clips = await api.listClips();
    } finally {
      loading = false;
      notifyListeners();
    }
  }

  Future<void> setMode(bool value) async {
    outOfHome = await api.setMode(value);
    notifyListeners();
  }

  Future<void> manualRecord() async {
    await api.manualRecord();
    clips = await api.listClips();
    notifyListeners();
  }

  Future<void> refreshClips() async {
    clips = await api.listClips();
    notifyListeners();
  }

  void updateBaseUrl(String hostPort) {
    api.updateBaseUrl(hostPort);
    baseUrl = api.baseUrl;
    notifyListeners();
  }
}
