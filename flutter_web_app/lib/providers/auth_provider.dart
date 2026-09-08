import 'dart:convert';
import 'dart:html' as html;
import 'dart:typed_data';
import 'package:flutter/foundation.dart';
import '../models/user_session.dart';
import '../services/api_service.dart';

class AuthProvider with ChangeNotifier {
  UserSession? _currentUser;
  bool _isLoading = false;
  String? _errorMessage;

  UserSession? get currentUser => _currentUser;
  bool get isAuthenticated => _currentUser != null;
  bool get isLoading => _isLoading;
  String? get errorMessage => _errorMessage;

  static const String _storageKey = 'flutter_attendance_user_session';

  AuthProvider() {
    _loadSessionFromStorage();
  }

  void _loadSessionFromStorage() {
    try {
      final storedData = html.window.localStorage[_storageKey];
      if (storedData != null && storedData.isNotEmpty) {
        final json = jsonDecode(storedData);
        final token = json['token'] ?? '';
        _currentUser = UserSession.fromJson(json, token);
        notifyListeners();
      }
    } catch (e) {
      debugPrint('Error restoring session: $e');
    }
  }

  void _saveSessionToStorage(UserSession session) {
    try {
      html.window.localStorage[_storageKey] = jsonEncode(session.toJson());
    } catch (e) {
      debugPrint('Error persisting session: $e');
    }
  }

  void _clearSessionFromStorage() {
    try {
      html.window.localStorage.remove(_storageKey);
    } catch (_) {}
  }

  /// Logs in via biometric face capture
  Future<bool> loginWithFace(Uint8List imageBytes, {String tenantSlug = 'default'}) async {
    _isLoading = true;
    _errorMessage = null;
    notifyListeners();

    try {
      final session = await ApiService.faceLogin(
        imageBytes: imageBytes,
        tenantSlug: tenantSlug,
      );
      _currentUser = session;
      _saveSessionToStorage(session);
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
        role: (student['user_role'] ?? 'STUDENT').toString().toUpperCase(),
        tenantId: 1,
        tenantName: 'FaceAttendance Campus',
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

  /// Standard credentials login
  Future<bool> loginWithPassword(String username, String password, {int? tenantId}) async {
    _isLoading = true;
    _errorMessage = null;
    notifyListeners();

    try {
      final session = await ApiService.passwordLogin(
        username: username,
        password: password,
        tenantId: tenantId,
      );
      _currentUser = session;
      _saveSessionToStorage(session);
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
