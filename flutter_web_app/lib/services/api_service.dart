import 'dart:convert';
import 'dart:typed_data';
import 'package:http/http.dart' as http;
import '../config/api_config.dart';
import '../models/geofence_config.dart';
import '../models/user_session.dart';
import '../models/attendance_record.dart';

class ApiService {
  /// Fetches institutional geofencing configuration from FastAPI backend
  static Future<GeofenceConfig> fetchGeofenceConfig({String tenantSlug = 'default'}) async {
    final uri = Uri.parse('${ApiConfig.selfConfigUrl}?tenant_slug=$tenantSlug');
    final response = await http.get(uri);

    if (response.statusCode == 200) {
      final json = jsonDecode(response.body);
      return GeofenceConfig.fromJson(json);
    } else {
      throw Exception('Failed to load geofencing configuration: ${response.body}');
    }
  }

  /// Face-Based Login: Ingests selfie frame, extracts 1:N vectors, and returns UserSession with token
  static Future<UserSession> faceLogin({
    required Uint8List imageBytes,
    String tenantSlug = 'default',
  }) async {
    final uri = Uri.parse(ApiConfig.faceLoginUrl);
    final request = http.MultipartRequest('POST', uri);

    request.fields['tenant_slug'] = tenantSlug;
    request.files.add(http.MultipartFile.fromBytes(
      'frame',
      imageBytes,
      filename: 'face_login.jpg',
    ));

    final streamedResponse = await request.send();
    final responseBody = await streamedResponse.stream.bytesToString();

    if (streamedResponse.statusCode == 200) {
      final json = jsonDecode(responseBody);
      final token = json['access_token'] ?? '';
      final userData = json['user'] ?? {};
      return UserSession.fromJson(userData, token);
    } else {
      final json = _tryParseJson(responseBody);
      final errorDetail = json?['detail'] ?? 'Face login failed ($responseBody)';
      throw Exception(errorDetail);
    }
  }

  /// Standard Password-Based Login
  static Future<UserSession> passwordLogin({
    required String username,
    required String password,
    int? tenantId,
  }) async {
    final uri = Uri.parse(ApiConfig.passwordLoginUrl);
    final response = await http.post(
      uri,
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({
        'username': username,
        'password': password,
        'tenant_id': tenantId ?? 1,
      }),
    );

    if (response.statusCode == 200) {
      final json = jsonDecode(response.body);
      final token = json['access_token'] ?? '';
      final userData = json['user'] ?? {};
      return UserSession.fromJson(userData, token);
    } else {
      final json = _tryParseJson(response.body);
      throw Exception(json?['detail'] ?? 'Login failed (${response.statusCode})');
    }
  }

  /// Frictionless Self-Attendance Auto-Checkin (GPS + Camera Frame)
  static Future<Map<String, dynamic>> submitSelfAttendance({
    required double latitude,
    required double longitude,
    required double accuracy,
    required Uint8List imageBytes,
    String tenantSlug = 'default',
  }) async {
    final uri = Uri.parse(ApiConfig.selfMarkUrl);
    final request = http.MultipartRequest('POST', uri);

    request.fields['latitude'] = latitude.toString();
    request.fields['longitude'] = longitude.toString();
    request.fields['accuracy'] = accuracy.toString();
    request.fields['tenant_slug'] = tenantSlug;

    request.files.add(http.MultipartFile.fromBytes(
      'frame',
      imageBytes,
      filename: 'self_mark.jpg',
    ));

    final streamedResponse = await request.send();
    final responseBody = await streamedResponse.stream.bytesToString();
    final json = _tryParseJson(responseBody);

    if (streamedResponse.statusCode == 200) {
      return json ?? {'status': 'success', 'message': 'Attendance marked successfully'};
    } else {
      final errorDetail = json?['detail'] ?? 'Attendance verification failed ($responseBody)';
      throw Exception(errorDetail);
    }
  }

  /// Fetches Personal Attendance Logs with Filtering
  static Future<List<AttendanceRecordItem>> fetchAttendanceHistory({
    String? token,
    String? rollNumber,
    int? studentId,
    String? dateStr,
    String? status,
    int limit = 100,
  }) async {
    var url = '${ApiConfig.attendanceRecordsUrl}?limit=$limit';
    if (rollNumber != null && rollNumber.isNotEmpty) {
      url += '&roll_number=${Uri.encodeComponent(rollNumber)}';
    }
    if (studentId != null) {
      url += '&student_id=$studentId';
    }
    if (dateStr != null && dateStr.isNotEmpty) {
      url += '&date_str=${Uri.encodeComponent(dateStr)}';
    }

    final headers = <String, String>{};
    if (token != null && token.isNotEmpty) {
      headers['Authorization'] = 'Bearer $token';
    }

    final response = await http.get(Uri.parse(url), headers: headers);

    if (response.statusCode == 200) {
      final json = jsonDecode(response.body);
      final List recordsJson = json['records'] ?? [];
      return recordsJson.map((r) => AttendanceRecordItem.fromJson(r)).toList();
    } else {
      throw Exception('Failed to fetch attendance records: ${response.body}');
    }
  }

  static Map<String, dynamic>? _tryParseJson(String text) {
    try {
      return jsonDecode(text) as Map<String, dynamic>;
    } catch (_) {
      return null;
    }
  }
}
