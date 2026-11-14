import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';
import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../models/user_session.dart';
import '../services/api_service.dart';

class AuthProvider with ChangeNotifier {
  UserSession? _currentUser;
  bool _isLoading = false;
  String? _errorMessage;
  String _tenantSlug = 'default';
  String _tenantName = '';
  bool _isInitialized = false;
  Completer<void>? _initCompleter;

  UserSession? get currentUser => _currentUser;
  bool get isAuthenticated => _currentUser != null;
  bool get isLoading => _isLoading;
  String? get errorMessage => _errorMessage;
  String get tenantSlug => _tenantSlug;
  String get tenantName => _tenantName;
  bool get isInitialized => _isInitialized;

  static const String _storageKey = 'flutter_attendance_user_session';
  static const String _tenantKey = 'employee_tenant_slug';
  static const String _tenantNameKey = 'employee_tenant_name';
  static const String _lastActiveKey = 'employee_session_last_active';

  AuthProvider() {
    _initCompleter = Completer<void>();
    _loadSessionFromStorage();
  }

  /// Ensures SharedPreferences session restoration completes before route decisions
  Future<void> ensureInitialized() async {
    if (_isInitialized) return;
    if (_initCompleter != null) {
      await _initCompleter!.future;
    }
  }

  Future<void> _loadSessionFromStorage() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final savedSlug = prefs.getString(_tenantKey);
      if (savedSlug != null && savedSlug.trim().isNotEmpty) {
        _tenantSlug = savedSlug.trim().toLowerCase();
      }

      final savedName = prefs.getString(_tenantNameKey);
      if (savedName != null && savedName.trim().isNotEmpty) {
        _tenantName = savedName.trim();
      }

      final storedData = prefs.getString(_storageKey);
      final lastActiveEpoch = prefs.getInt(_lastActiveKey);

      if (storedData != null && storedData.isNotEmpty) {
        final now = DateTime.now().millisecondsSinceEpoch;
        // 7 days inactivity window: 7 * 24 * 60 * 60 * 1000 ms
        const sevenDaysMs = 7 * 24 * 60 * 60 * 1000;

        if (lastActiveEpoch != null && (now - lastActiveEpoch) > sevenDaysMs) {
          debugPrint('Session expired after 7 days of inactivity. Requiring re-login.');
          _currentUser = null;
          await prefs.remove(_storageKey);
          await prefs.remove(_lastActiveKey);
        } else {
          final json = jsonDecode(storedData);
          final token = json['token'] ?? '';
          _currentUser = UserSession.fromJson(json, token);
          // Refresh activity timestamp on successful app launch
          await prefs.setInt(_lastActiveKey, now);
        }
      }
    } catch (e) {
      debugPrint('Error restoring session: $e');
    } finally {
      _isInitialized = true;
      if (_initCompleter != null && !_initCompleter!.isCompleted) {
        _initCompleter!.complete();
      }
      notifyListeners();
    }
  }

  /// Updates session activity to prolong the 7-day inactivity clock
  Future<void> touchSessionActivity() async {
    if (_currentUser == null) return;
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setInt(_lastActiveKey, DateTime.now().millisecondsSinceEpoch);
    } catch (_) {}
  }

  Future<void> setTenant(String slug, {String? name}) async {
    _tenantSlug = slug.trim().toLowerCase();
    if (name != null && name.trim().isNotEmpty) {
      _tenantName = name.trim();
    }
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString(_tenantKey, _tenantSlug);
      if (name != null) await prefs.setString(_tenantNameKey, _tenantName);
    } catch (_) {}
    notifyListeners();
  }

  Future<void> switchOrganization() async {
    _currentUser = null;
    _tenantSlug = 'default';
    _tenantName = '';
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.remove(_storageKey);
      await prefs.remove(_lastActiveKey);
      await prefs.remove(_tenantKey);
      await prefs.remove(_tenantNameKey);
    } catch (_) {}
    notifyListeners();
  }

  Future<void> _saveSessionToStorage(UserSession session) async {
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString(_storageKey, jsonEncode(session.toJson()));
      await prefs.setInt(_lastActiveKey, DateTime.now().millisecondsSinceEpoch);
      if (_tenantSlug.isNotEmpty) {
        await prefs.setString(_tenantKey, _tenantSlug);
      }
      if (_tenantName.isNotEmpty) {
        await prefs.setString(_tenantNameKey, _tenantName);
      }
    } catch (e) {
      debugPrint('Error persisting session: $e');
    }
  }

  Future<void> _clearSessionFromStorage() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.remove(_storageKey);
      await prefs.remove(_lastActiveKey);
    } catch (_) {}
  }

  /// Logs in via biometric face capture
  Future<bool> loginWithFace(Uint8List imageBytes, {String? tenantSlug}) async {
    _isLoading = true;
    _errorMessage = null;
    notifyListeners();

    final slug = (tenantSlug != null && tenantSlug.isNotEmpty) ? tenantSlug : _tenantSlug;

    try {
      final session = await ApiService.faceLogin(
        imageBytes: imageBytes,
        tenantSlug: slug,
      );
      _currentUser = session;
      await _saveSessionToStorage(session);
      _isLoading = false;
      notifyListeners();
      return true;
    } catch (e) {
      _errorMessage = e.toString().replaceAll('Exception:', '').trim();
      _isLoading = false;
      notifyListeners();
      return false;
    }
  }

  /// Sets session from successful self-attendance check-in response
  void setSessionFromCheckIn(Map<String, dynamic> checkInData, String token) {
    try {
      final student = checkInData['student'] ?? {};
      final session = UserSession(
        id: student['id'] ?? 0,
        studentId: student['id'],
        username: student['roll_number'] ?? 'student',
        name: student['name'] ?? 'User',
        role: (student['user_role'] ?? 'EMPLOYEE').toString().toUpperCase(),
        tenantId: checkInData['tenant_id'] ?? 1,
        tenantName: checkInData['tenant_name'] ?? _tenantName,
        rollNumber: student['roll_number'],
        department: student['department'],
        classSemester: student['class_semester'],
        divisionName: student['division_name'],
        token: token,
      );
      _currentUser = session;
      _saveSessionToStorage(session);
      notifyListeners();
    } catch (e) {
      debugPrint('Error setting session from checkin: $e');
    }
  }

  /// Standard credentials login with tenant identifier support
  Future<bool> loginWithPassword(String username, String password, {String? tenantSlug, int? tenantId}) async {
    _isLoading = true;
    _errorMessage = null;
    notifyListeners();

    final slug = (tenantSlug != null && tenantSlug.isNotEmpty) ? tenantSlug : _tenantSlug;

    try {
      final session = await ApiService.passwordLogin(
        username: username,
        password: password,
        tenantSlug: slug,
        tenantId: tenantId,
      );
      _currentUser = session;
      await _saveSessionToStorage(session);
      _isLoading = false;
      notifyListeners();
      return true;
    } catch (e) {
      _errorMessage = e.toString().replaceAll('Exception:', '').trim();
      _isLoading = false;
      notifyListeners();
      return false;
    }
  }

  void logout() {
    _currentUser = null;
    _clearSessionFromStorage();
    notifyListeners();
  }
}
