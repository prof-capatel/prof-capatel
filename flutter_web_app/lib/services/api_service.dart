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

  /// Passwordless Face-Based Login for Employees
  static Future<UserSession> faceLogin({
    required Uint8List imageBytes,
    String tenantSlug = 'default',
  }) async {
    final uri = Uri.parse(ApiConfig.faceLoginUrl);
    final base64Photo = base64Encode(imageBytes);

    final response = await http.post(
      uri,
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({
        'tenant_identifier': tenantSlug,
        'photo_base64': base64Photo,
      }),
    );

    final json = _tryParseJson(response.body);
    if (response.statusCode == 200 && json != null) {
      final token = json['token'] ?? '';
      final userData = json['employee'] ?? {};
      return UserSession.fromJson(userData, token);
    } else {
      final errorDetail = json?['detail'] ?? 'Face login failed (${response.statusCode})';
      throw Exception(errorDetail);
    }
  }

  /// Standard Password-Based Login (Admin or Employee)
  static Future<UserSession> passwordLogin({
    required String username,
    required String password,
    String? tenantSlug,
    int? tenantId,
  }) async {
    final uri = Uri.parse(ApiConfig.passwordLoginUrl);
    final payload = <String, dynamic>{
      'username': username,
      'password': password,
    };
    if (tenantId != null) {
      payload['tenant_id'] = tenantId;
    }
    if (tenantSlug != null && tenantSlug.isNotEmpty) {
      payload['tenant_identifier'] = tenantSlug;
    }

    final response = await http.post(
      uri,
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode(payload),
    );

    if (response.statusCode == 200) {
      final json = jsonDecode(response.body);
      final token = json['access_token'] ?? '';
      final userData = json['user'] ?? {};
      return UserSession.fromJson(userData, token);
    } else {
      final json = _tryParseJson(response.body);
      final detail = json?['detail'];
      if (response.statusCode == 401) {
        throw Exception(detail ?? 'Invalid credentials (401)');
      } else if (response.statusCode == 403) {
        throw Exception(detail ?? 'Access restricted (403)');
      } else if (response.statusCode == 404) {
        throw Exception(detail ?? 'Target organization or account not found (404)');
      } else if (response.statusCode >= 500) {
        throw Exception('The attendance server encountered a temporary error (${response.statusCode})');
      } else {
        throw Exception(detail ?? 'Login failed (${response.statusCode})');
      }
    }
  }

  /// Dedicated Authenticated Employee Mobile Geofenced Check-In / Check-Out
  static Future<Map<String, dynamic>> employeeMobileCheckIn({
    required String token,
    required double latitude,
    required double longitude,
    double accuracy = 10.0,
    String? photoBase64,
    String punchType = 'AUTO',
    bool isMockLocation = false,
  }) async {
    final uri = Uri.parse(ApiConfig.employeeCheckInUrl);
    final response = await http.post(
      uri,
      headers: {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer $token',
      },
      body: jsonEncode({
        'latitude': latitude,
        'longitude': longitude,
        'accuracy': accuracy,
        'photo_base64': photoBase64,
        'punch_type': punchType,
        'is_mock_location': isMockLocation,
      }),
    );

    final json = _tryParseJson(response.body);
    if (response.statusCode == 200) {
      return json ?? {'status': 'success', 'message': 'Attendance registered'};
    } else {
      throw Exception(json?['detail'] ?? 'Mobile check-in failed (${response.statusCode})');
    }
  }

  /// Periodic Background Geofence Heartbeat (Detects Out-of-Bounds During Active Shifts)
  static Future<Map<String, dynamic>> sendGeofenceHeartbeat({
    required String token,
    required double latitude,
    required double longitude,
    double accuracy = 10.0,
    bool isMockLocation = false,
  }) async {
    final uri = Uri.parse(ApiConfig.employeeHeartbeatUrl);
    final response = await http.post(
      uri,
      headers: {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer $token',
      },
      body: jsonEncode({
        'latitude': latitude,
        'longitude': longitude,
        'accuracy': accuracy,
        'is_mock_location': isMockLocation,
      }),
    );

    final json = _tryParseJson(response.body);
    if (response.statusCode == 200) {
      return json ?? {'status': 'in_bounds'};
    } else {
      throw Exception(json?['detail'] ?? 'Heartbeat sync failed');
    }
  }

  /// Fetches Authenticated Employee Geofence Setup & Live Punch Status
  static Future<Map<String, dynamic>> fetchEmployeeGeofenceConfig({
    required String token,
  }) async {
    final uri = Uri.parse(ApiConfig.employeeGeofenceConfigUrl);
    final response = await http.get(
      uri,
      headers: {'Authorization': 'Bearer $token'},
    );

    if (response.statusCode == 200) {
      return jsonDecode(response.body) as Map<String, dynamic>;
    } else {
      final json = _tryParseJson(response.body);
      throw Exception(json?['detail'] ?? 'Failed to load geofencing status');
    }
  }

  /// Fetches Personal Attendance Logs
  static Future<List<AttendanceRecordItem>> fetchAttendanceHistory({
    String? token,
    String? rollNumber,
    int? studentId,
    String? dateStr,
    String? status,
    int? year,
    int? month,
    int limit = 100,
  }) async {
    // If authenticated employee token is provided, use the dedicated employee attendance endpoint
    // which scopes records automatically to the employee's tenant and student profile,
    // and supports month & year filtering.
    if (token != null && token.isNotEmpty) {
      var url = '${ApiConfig.employeeAttendanceUrl}?limit=$limit';
      if (year != null) {
        url += '&year=$year';
      }
      if (month != null) {
        url += '&month=$month';
      }
      final response = await http.get(
        Uri.parse(url),
        headers: {'Authorization': 'Bearer $token'},
      );

      if (response.statusCode == 200) {
        final json = jsonDecode(response.body);
        final List recordsJson = json['records'] ?? [];
        return recordsJson.map((r) => AttendanceRecordItem.fromJson(r)).toList();
      } else {
        throw Exception('Failed to fetch employee attendance records: ${response.body}');
      }
    }

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

    final response = await http.get(Uri.parse(url), headers: headers);

    if (response.statusCode == 200) {
      final json = jsonDecode(response.body);
      final List recordsJson = json['records'] ?? [];
      return recordsJson.map((r) => AttendanceRecordItem.fromJson(r)).toList();
    } else {
      throw Exception('Failed to fetch attendance records: ${response.body}');
    }
  }

  /// Checks whether authenticated employee has a linked User account with a password set
  static Future<bool> checkEmployeeHasPassword({required String token}) async {
    try {
      final uri = Uri.parse(ApiConfig.employeeHasPasswordUrl);
      final response = await http.get(
        uri,
        headers: {'Authorization': 'Bearer $token'},
      );
      if (response.statusCode == 200) {
        final json = jsonDecode(response.body);
        return json['has_password'] == true;
      }
    } catch (_) {}
    return false;
  }

  /// Changes or sets employee portal password
  static Future<Map<String, dynamic>> changeEmployeePassword({
    required String token,
    String? currentPassword,
    required String newPassword,
    required String confirmPassword,
  }) async {
    final uri = Uri.parse(ApiConfig.employeeChangePasswordUrl);
    final payload = {
      'new_password': newPassword,
      'confirm_password': confirmPassword,
    };
    if (currentPassword != null && currentPassword.isNotEmpty) {
      payload['current_password'] = currentPassword;
    }
    final response = await http.post(
      uri,
      headers: {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer $token',
      },
      body: jsonEncode(payload),
    );
    final json = _tryParseJson(response.body);
    if (response.statusCode == 200 && json != null) {
      return json;
    } else {
      throw Exception(json?['detail'] ?? 'Failed to update password');
    }
  }

  /// Fetches Employee Work Hours & Estimated Wages
  static Future<Map<String, dynamic>> fetchEmployeePayroll({
    required String token,
  }) async {
    final uri = Uri.parse(ApiConfig.employeePayrollUrl);
    final response = await http.get(
      uri,
      headers: {'Authorization': 'Bearer $token'},
    );

    if (response.statusCode == 200) {
      return jsonDecode(response.body) as Map<String, dynamic>;
    } else {
      return {};
    }
  }

  /// Fetches Employee Annual Leave Quotas & Balances
  static Future<List<dynamic>> fetchEmployeeLeaveBalances({
    required String token,
  }) async {
    final uri = Uri.parse(ApiConfig.employeeLeaveBalancesUrl);
    final response = await http.get(
      uri,
      headers: {'Authorization': 'Bearer $token'},
    );

    if (response.statusCode == 200) {
      final json = jsonDecode(response.body);
      return json['balances'] ?? [];
    } else {
      return [];
    }
  }

  /// Resolves tenant identifier (slug, short code, ID, or UUID)
  static Future<Map<String, dynamic>> resolveTenant(String identifier) async {
    final uri = Uri.parse(ApiConfig.tenantResolveUrl(identifier));
    final response = await http.get(uri);
    final json = _tryParseJson(response.body);
    if (response.statusCode == 200 && json != null) {
      return json;
    } else {
      throw Exception(json?['detail'] ?? 'Could not resolve organization code');
    }
  }

  /// Fetches Employee Compensation & Structured CTC Model
  static Future<Map<String, dynamic>> fetchEmployeeCompensation({
    required String token,
  }) async {
    final uri = Uri.parse(ApiConfig.employeeCompensationUrl);
    final response = await http.get(
      uri,
      headers: {'Authorization': 'Bearer $token'},
    );
    if (response.statusCode == 200) {
      return jsonDecode(response.body) as Map<String, dynamic>;
    } else {
      return {};
    }
  }

  /// Fetches Published Monthly Payslips
  static Future<List<dynamic>> fetchEmployeePayslips({
    required String token,
  }) async {
    final uri = Uri.parse(ApiConfig.employeePayslipsUrl);
    final response = await http.get(
      uri,
      headers: {'Authorization': 'Bearer $token'},
    );
    if (response.statusCode == 200) {
      final json = jsonDecode(response.body);
      return json['payslips'] ?? [];
    } else {
      return [];
    }
  }

  /// Fetches Submitted Leave Applications History
  static Future<List<dynamic>> fetchEmployeeLeaveRequests({
    required String token,
  }) async {
    final uri = Uri.parse(ApiConfig.employeeLeaveRequestsUrl);
    final response = await http.get(
      uri,
      headers: {'Authorization': 'Bearer $token'},
    );
    if (response.statusCode == 200) {
      final json = jsonDecode(response.body);
      return json['requests'] ?? [];
    } else {
      return [];
    }
  }

  /// Cancels a Pending Leave Application
  static Future<Map<String, dynamic>> cancelEmployeeLeaveRequest({
    required String token,
    required int requestId,
  }) async {
    final uri = Uri.parse(ApiConfig.employeeLeaveCancelUrl(requestId));
    final response = await http.post(
      uri,
      headers: {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer $token',
      },
    );
    final json = _tryParseJson(response.body);
    if (response.statusCode == 200) {
      return json ?? {'status': 'success', 'message': 'Leave application cancelled'};
    } else {
      throw Exception(json?['detail'] ?? 'Failed to cancel leave application');
    }
  }

  /// Submits an Employee Leave Application
  static Future<Map<String, dynamic>> applyEmployeeLeave({
    required String token,
    required int leaveTypeId,
    required String startDate,
    required String endDate,
    required String reason,
    bool isHalfDay = false,
    String halfDayPeriod = "NONE",
  }) async {
    final uri = Uri.parse(ApiConfig.employeeLeaveApplyUrl);
    final response = await http.post(
      uri,
      headers: {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer $token',
      },
      body: jsonEncode({
        'leave_type_id': leaveTypeId,
        'start_date': startDate,
        'end_date': endDate,
        'reason': reason,
        'is_half_day': isHalfDay,
        'half_day_period': isHalfDay ? halfDayPeriod : "NONE",
      }),
    );

    final json = _tryParseJson(response.body);
    if (response.statusCode == 200) {
      return json ?? {'status': 'success', 'message': 'Leave application submitted'};
    } else {
      throw Exception(json?['detail'] ?? 'Leave application failed');
    }
  }

  /// Fetches tenant metadata, departments, and auto-suggested code for employee self-onboarding
  static Future<Map<String, dynamic>> getOnboardInfo({
    required String tenantUuid,
    required String onboardingToken,
  }) async {
    final uri = Uri.parse(ApiConfig.onboardInfoUrl(tenantUuid, onboardingToken));
    final response = await http.get(uri);
    final json = _tryParseJson(response.body);
    if (response.statusCode == 200 && json != null) {
      return json;
    } else {
      throw Exception(json?['detail'] ?? 'Could not fetch organization onboarding details.');
    }
  }

  /// Registers new employee profile via public tokenized onboarding endpoint
  static Future<Map<String, dynamic>> registerEmployeeOnboard({
    required String tenantUuid,
    required String onboardingToken,
    required String name,
    required String rollNumber,
    String? password,
    String? email,
    int? departmentId,
    String? department,
  }) async {
    final uri = Uri.parse(ApiConfig.onboardRegisterUrl);
    final body = jsonEncode({
      'tenant_uuid': tenantUuid,
      'onboarding_token': onboardingToken,
      'name': name.trim(),
      'roll_number': rollNumber.trim().toUpperCase(),
      'password': (password != null && password.trim().isNotEmpty) ? password.trim() : null,
      'email': (email != null && email.trim().isNotEmpty) ? email.trim() : null,
      'department_id': departmentId,
      'department': (department != null && department.trim().isNotEmpty) ? department.trim() : 'General',
      'role': 'employee',
    });

    final response = await http.post(
      uri,
      headers: {'Content-Type': 'application/json'},
      body: body,
    );
    final json = _tryParseJson(response.body);
    if (response.statusCode == 200 && json != null) {
      return json;
    } else {
      throw Exception(json?['detail'] ?? 'Employee registration failed. Please try again.');
    }
  }

  /// Uploads single multi-angle face sample for registered employee
  static Future<Map<String, dynamic>> uploadOnboardFaceSample({
    required String tenantUuid,
    required String onboardingToken,
    required int studentId,
    required String sampleAngle,
    required Uint8List imageBytes,
  }) async {
    final uri = Uri.parse(ApiConfig.onboardCaptureSampleUrl);
    final request = http.MultipartRequest('POST', uri);
    request.fields['tenant_uuid'] = tenantUuid;
    request.fields['onboarding_token'] = onboardingToken;
    request.fields['student_id'] = studentId.toString();
    request.fields['sample_angle'] = sampleAngle;

    request.files.add(
      http.MultipartFile.fromBytes(
        'image',
        imageBytes,
        filename: 'sample_${sampleAngle}.jpg',
      ),
    );

    final streamedRes = await request.send();
    final res = await http.Response.fromStream(streamedRes);
    final json = _tryParseJson(res.body);
    if (res.statusCode == 200 && json != null) {
      return json;
    } else {
      throw Exception(json?['detail'] ?? 'Biometric capture failed for $sampleAngle angle.');
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
