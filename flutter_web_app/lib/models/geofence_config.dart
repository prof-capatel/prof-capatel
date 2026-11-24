class GeofenceConfig {
  final int tenantId;
  final String tenantSlug;
  final String institutionName;
  final String shortCode;
  final String? logoUrl;
  final String primaryAccentColor;
  final bool enableSelfAttendance;
  final bool isConfigured;
  final double? geoLatitude;
  final double? geoLongitude;
  final double geoRadiusMeters;
  final double maxGpsAccuracyMeters;
  final double faceThreshold;
  final bool mobileRequireFaceVerification;
  final int? locationId;
  final String? locationName;
  final bool isLocationAssigned;

  GeofenceConfig({
    required this.tenantId,
    required this.tenantSlug,
    required this.institutionName,
    required this.shortCode,
    this.logoUrl,
    required this.primaryAccentColor,
    required this.enableSelfAttendance,
    required this.isConfigured,
    this.geoLatitude,
    this.geoLongitude,
    required this.geoRadiusMeters,
    required this.maxGpsAccuracyMeters,
    required this.faceThreshold,
    this.mobileRequireFaceVerification = false,
    this.locationId,
    this.locationName,
    this.isLocationAssigned = false,
  });

  factory GeofenceConfig.fromJson(Map<String, dynamic> json) {
    return GeofenceConfig(
      tenantId: json['tenant_id'] ?? 1,
      tenantSlug: json['tenant_slug'] ?? 'default',
      institutionName: json['institution_name'] ?? 'FaceAttendance Campus',
      shortCode: json['short_code'] ?? 'FA-HUB',
      logoUrl: json['logo_url'],
      primaryAccentColor: json['primary_accent_color'] ?? '#6366f1',
      enableSelfAttendance: json['geofence_enabled'] ?? json['enable_self_attendance'] ?? false,
      isConfigured: json['is_configured'] ?? (json['geo_latitude'] != null && json['geo_longitude'] != null),
      geoLatitude: json['geo_latitude'] != null ? (json['geo_latitude'] as num).toDouble() : (json['center_latitude'] != null ? (json['center_latitude'] as num).toDouble() : null),
      geoLongitude: json['geo_longitude'] != null ? (json['geo_longitude'] as num).toDouble() : (json['center_longitude'] != null ? (json['center_longitude'] as num).toDouble() : null),
      geoRadiusMeters: (json['geo_radius_meters'] as num?)?.toDouble() ?? (json['radius_meters'] as num?)?.toDouble() ?? 150.0,
      maxGpsAccuracyMeters: (json['max_gps_accuracy_meters'] as num?)?.toDouble() ?? 50.0,
      faceThreshold: (json['face_threshold'] as num?)?.toDouble() ?? 0.52,
      mobileRequireFaceVerification: json['mobile_require_face_verification'] ?? false,
      locationId: json['location_id'],
      locationName: json['location_name'],
      isLocationAssigned: json['is_location_assigned'] ?? (json['location_id'] != null),
    );
  }
}
