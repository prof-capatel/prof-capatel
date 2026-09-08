class AttendanceRecordItem {
  final int id;
  final int? studentId;
  final String studentName;
  final String rollNumber;
  final String department;
  final String userRole;
  final String classSemester;
  final String divisionName;
  final String nodeId;
  final String timestamp;
  final double confidenceDistance;
  final double matchConfidencePct;
  final String status;
  final String? snapshotPath;
  final bool isManualOverride;
  final String? overrideReason;
  final double? geoLatitude;
  final double? geoLongitude;
  final double? geoDistanceMeters;
  final bool isSelfAttendance;

  AttendanceRecordItem({
    required this.id,
    this.studentId,
    required this.studentName,
    required this.rollNumber,
    required this.department,
    required this.userRole,
    required this.classSemester,
    required this.divisionName,
    required this.nodeId,
    required this.timestamp,
    required this.confidenceDistance,
    required this.matchConfidencePct,
    required this.status,
    this.snapshotPath,
    required this.isManualOverride,
    this.overrideReason,
    this.geoLatitude,
    this.geoLongitude,
    this.geoDistanceMeters,
    required this.isSelfAttendance,
  });

  factory AttendanceRecordItem.fromJson(Map<String, dynamic> json) {
    return AttendanceRecordItem(
      id: json['id'] ?? 0,
      studentId: json['student_id'],
      studentName: json['student_name'] ?? 'Unknown',
      rollNumber: json['roll_number'] ?? 'N/A',
      department: json['department'] ?? 'General',
      userRole: json['user_role'] ?? 'student',
      classSemester: json['class_semester'] ?? 'General',
      divisionName: json['division_name'] ?? 'N/A',
      nodeId: json['node_id'] ?? 'DEFAULT',
      timestamp: json['timestamp'] ?? '',
      confidenceDistance: (json['confidence_distance'] as num?)?.toDouble() ?? 0.0,
      matchConfidencePct: (json['match_confidence_pct'] as num?)?.toDouble() ?? 0.0,
      status: json['status'] ?? 'PRESENT',
      snapshotPath: json['snapshot_path'],
      isManualOverride: json['is_manual_override'] ?? false,
      overrideReason: json['override_reason'],
      geoLatitude: (json['geo_latitude'] as num?)?.toDouble(),
      geoLongitude: (json['geo_longitude'] as num?)?.toDouble(),
      geoDistanceMeters: (json['geo_distance_meters'] as num?)?.toDouble(),
      isSelfAttendance: json['is_self_attendance'] ?? false,
    );
  }
}
