class UserSession {
  final int id;
  final int? studentId;
  final String username;
  final String name;
  final String role;
  final int tenantId;
  final String tenantName;
  final String? rollNumber;
  final String? department;
  final String? classSemester;
  final String? divisionName;
  final String token;

  UserSession({
    required this.id,
    this.studentId,
    required this.username,
    required this.name,
    required this.role,
    required this.tenantId,
    required this.tenantName,
    this.rollNumber,
    this.department,
    this.classSemester,
    this.divisionName,
    required this.token,
  });

  factory UserSession.fromJson(Map<String, dynamic> json, String token) {
    return UserSession(
      id: json['id'] ?? 0,
      studentId: json['student_id'],
      username: json['username'] ?? '',
      name: json['name'] ?? json['full_name'] ?? 'User',
      role: (json['role'] ?? 'STUDENT').toString().toUpperCase(),
      tenantId: json['tenant_id'] ?? 1,
      tenantName: json['tenant_name'] ?? 'FaceAttendance Campus',
      rollNumber: json['roll_number'],
      department: json['department'],
      classSemester: json['class_semester'],
      divisionName: json['division_name'],
      token: token,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'student_id': studentId,
      'username': username,
      'name': name,
      'role': role,
      'tenant_id': tenantId,
      'tenant_name': tenantName,
      'roll_number': rollNumber,
      'department': department,
      'class_semester': classSemester,
      'division_name': divisionName,
      'token': token,
    };
  }
}
