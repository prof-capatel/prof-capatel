import 'package:shared_preferences/shared_preferences.dart';

class ApiConfig {
  // Default base URL points to the production cloud server out-of-the-box
  static const String defaultBaseUrl = 'https://curiosityhub.co.in';
  static String baseUrl = defaultBaseUrl;

  static const String _storageKey = 'custom_api_base_url';

  static Future<void> loadBaseUrl() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final saved = prefs.getString(_storageKey);
      if (saved != null && saved.trim().isNotEmpty) {
        baseUrl = saved.trim().replaceAll(RegExp(r'/+$'), '');
      } else {
        baseUrl = defaultBaseUrl;
      }
    } catch (_) {
      baseUrl = defaultBaseUrl;
    }
  }

  static Future<void> setBaseUrl(String newUrl) async {
    baseUrl = newUrl.trim().replaceAll(RegExp(r'/+$'), '');
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString(_storageKey, baseUrl);
    } catch (_) {}
  }

  static String get selfConfigUrl => '$baseUrl/api/v1/attendance/self-config';
  static String get selfMarkUrl => '$baseUrl/api/v1/attendance/self-mark';
  static String get attendanceRecordsUrl => '$baseUrl/api/v1/attendance/records';
  static String get faceLoginUrl => '$baseUrl/api/v1/employee/face-login';
  static String get passwordLoginUrl => '$baseUrl/api/v1/auth/login';
  static String get currentUserUrl => '$baseUrl/api/v1/auth/me';

  // Dedicated Employee Mobile & Geofence Endpoints
  static String get employeeCheckInUrl => '$baseUrl/api/v1/employee/check-in';
  static String get employeeHeartbeatUrl => '$baseUrl/api/v1/employee/geofence/heartbeat';
  static String get employeeGeofenceConfigUrl => '$baseUrl/api/v1/employee/geofence/config';
  static String get employeeProfileUrl => '$baseUrl/api/v1/employee/me';
  static String get employeeAttendanceUrl => '$baseUrl/api/v1/employee/attendance';
  static String get employeeChangePasswordUrl => '$baseUrl/api/v1/employee/change-password';
  static String get employeeHasPasswordUrl => '$baseUrl/api/v1/employee/has-password';
  static String get employeePayrollUrl => '$baseUrl/api/v1/employee/payroll';
  static String get employeePayslipsUrl => '$baseUrl/api/v1/employee/payslips';
  static String get employeeLeaveBalancesUrl => '$baseUrl/api/v1/employee/leave/balances';
  static String get employeeLeaveRequestsUrl => '$baseUrl/api/v1/employee/leave/requests';
  static String get employeeLeaveApplyUrl => '$baseUrl/api/v1/employee/leave/apply';
  static String get employeeCompensationUrl => '$baseUrl/api/v1/employee/compensation';
  static String tenantResolveUrl(String identifier) => '$baseUrl/api/v1/tenants/resolve/$identifier';
  static String employeeLeaveCancelUrl(int id) => '$baseUrl/api/v1/employee/leave/requests/$id/cancel';

  // Admin Geofence Breach Audit Trail
  static String get geofenceBreachesUrl => '$baseUrl/api/v1/attendance/geofence-breaches';

  // Public Employee Self-Registration & Onboarding Endpoints
  static String get onboardRegisterUrl => '$baseUrl/api/v1/enroll/onboard/register';
  static String get onboardCaptureSampleUrl => '$baseUrl/api/v1/enroll/onboard/capture-sample';
  static String onboardInfoUrl(String tenantUuid, String token) => '$baseUrl/api/v1/enroll/onboard/info/$tenantUuid/$token';
}
