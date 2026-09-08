class ApiConfig {
  // Default base URL for Chrome testing against local FastAPI backend
  static const String defaultBaseUrl = 'http://127.0.0.1:8000';
  static String baseUrl = defaultBaseUrl;

  static String get selfConfigUrl => '$baseUrl/api/v1/attendance/self-config';
  static String get selfMarkUrl => '$baseUrl/api/v1/attendance/self-mark';
  static String get attendanceRecordsUrl => '$baseUrl/api/v1/attendance/records';
  static String get faceLoginUrl => '$baseUrl/api/v1/auth/face-login';
  static String get passwordLoginUrl => '$baseUrl/api/v1/auth/login';
  static String get currentUserUrl => '$baseUrl/api/v1/auth/me';
}
