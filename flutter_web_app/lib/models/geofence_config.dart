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
  });

  factory GeofenceConfig.fromJson(Map<String, dynamic> json) {
    return GeofenceConfig(
      tenantId: json['tenant_id'] ?? 1,
      tenantSlug: json['tenant_slug'] ?? 'default',
      institutionName: json['institution_name'] ?? 'FaceAttendance Campus',
      shortCode: json['short_code'] ?? 'FA-HUB',
      logoUrl: json['logo_url'],
      primaryAccentColor: json['primary_accent_color'] ?? '#6366f1',
      enableSelfAttendance: json['enable_self_attendance'] ?? false,
      isConfigured: json['is_configured'] ?? false,
      geoLatitude: json['geo_latitude'] != null ? (json['geo_latitude'] as num).toDouble() : null,
      geoLongitude: json['geo_longitude'] != null ? (json['geo_longitude'] as num).toDouble() : null,
      geoRadiusMeters: (json['geo_radius_meters'] as num?)?.toDouble() ?? 150.0,
      maxGpsAccuracyMeters: (json['max_gps_accuracy_meters'] as num?)?.toDouble() ?? 50.0,
      faceThreshold: (json['face_threshold'] as num?)?.toDouble() ?? 0.52,
    );
  }
}
