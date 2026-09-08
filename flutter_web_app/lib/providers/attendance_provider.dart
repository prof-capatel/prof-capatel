import 'dart:typed_data';
import 'package:flutter/foundation.dart';
import '../models/geofence_config.dart';
import '../models/attendance_record.dart';
import '../services/api_service.dart';
import '../services/location_service.dart';

enum CheckInStatus {
  idle,
  locating,
  capturing,
  submitting,
  success,
  cooldown,
  error,
}

enum HistoryFilterTimeRange {
  all,
  today,
  thisWeek,
  thisMonth,
}

class AttendanceProvider with ChangeNotifier {
  GeofenceConfig? _geofenceConfig;
  UserCoordinates? _userCoordinates;
  double? _distanceToCampus;
  bool _isInsideGeofence = false;
  String? _geofenceStatusMessage;

  CheckInStatus _checkInStatus = CheckInStatus.idle;
  String? _statusDetail;
  Map<String, dynamic>? _lastCheckInResult;

  List<AttendanceRecordItem> _historyRecords = [];
  bool _isLoadingHistory = false;
  String? _historyError;

  // Filter properties
  HistoryFilterTimeRange _selectedTimeRange = HistoryFilterTimeRange.all;
  String? _selectedStatusFilter;
  String _searchQuery = '';

  // Getters
  GeofenceConfig? get geofenceConfig => _geofenceConfig;
  UserCoordinates? get userCoordinates => _userCoordinates;
  double? get distanceToCampus => _distanceToCampus;
  bool get isInsideGeofence => _isInsideGeofence;
  String? get geofenceStatusMessage => _geofenceStatusMessage;
  CheckInStatus get checkInStatus => _checkInStatus;
  String? get statusDetail => _statusDetail;
  Map<String, dynamic>? get lastCheckInResult => _lastCheckInResult;
  bool get isLoadingHistory => _isLoadingHistory;
  String? get historyError => _historyError;
  HistoryFilterTimeRange get selectedTimeRange => _selectedTimeRange;
  String? get selectedStatusFilter => _selectedStatusFilter;
  String get searchQuery => _searchQuery;

  List<AttendanceRecordItem> get filteredRecords {
    var list = List<AttendanceRecordItem>.from(_historyRecords);

    // 1. Time Range Filter
    final now = DateTime.now();
    if (_selectedTimeRange == HistoryFilterTimeRange.today) {
      final todayStr = "${now.year.toString().padLeft(4, '0')}-${now.month.toString().padLeft(2, '0')}-${now.day.toString().padLeft(2, '0')}";
      list = list.where((r) => r.timestamp.startsWith(todayStr)).toList();
    } else if (_selectedTimeRange == HistoryFilterTimeRange.thisWeek) {
      final weekAgo = now.subtract(const Duration(days: 7));
      list = list.where((r) {
        try {
          final dt = DateTime.parse(r.timestamp.replaceAll(' ', 'T'));
          return dt.isAfter(weekAgo);
        } catch (_) {
          return true;
        }
      }).toList();
    } else if (_selectedTimeRange == HistoryFilterTimeRange.thisMonth) {
      final monthPrefix = "${now.year.toString().padLeft(4, '0')}-${now.month.toString().padLeft(2, '0')}";
      list = list.where((r) => r.timestamp.startsWith(monthPrefix)).toList();
    }

    // 2. Status Filter
    if (_selectedStatusFilter != null && _selectedStatusFilter != 'ALL') {
      list = list.where((r) {
        if (_selectedStatusFilter == 'SELF') return r.isSelfAttendance;
        if (_selectedStatusFilter == 'OVERRIDE') return r.isManualOverride;
        if (_selectedStatusFilter == 'NODE') return !r.isSelfAttendance && !r.isManualOverride;
        return true;
      }).toList();
    }

    // 3. Search Query Filter
    if (_searchQuery.isNotEmpty) {
      final q = _searchQuery.toLowerCase();
      list = list.where((r) =>
        r.studentName.toLowerCase().contains(q) ||
        r.rollNumber.toLowerCase().contains(q) ||
        r.department.toLowerCase().contains(q) ||
        r.nodeId.toLowerCase().contains(q) ||
        r.timestamp.contains(q)
      ).toList();
    }

    return list;
  }

  /// Initializes geofence configuration from backend
  Future<void> initConfig({String tenantSlug = 'default'}) async {
    try {
      _geofenceConfig = await ApiService.fetchGeofenceConfig(tenantSlug: tenantSlug);
      notifyListeners();
    } catch (e) {
      debugPrint('Error fetching geofence config: $e');
    }
  }

  /// Updates current browser GPS coordinates and computes campus radar distance
  Future<void> updateLocation() async {
    _checkInStatus = CheckInStatus.locating;
    _statusDetail = 'Acquiring high-accuracy HTML5 GPS coordinates...';
    notifyListeners();

    try {
      final coords = await LocationService.getCurrentLocation();
      _userCoordinates = coords;

      if (_geofenceConfig != null &&
          _geofenceConfig!.geoLatitude != null &&
          _geofenceConfig!.geoLongitude != null) {
        final dist = LocationService.calculateDistance(
          coords.latitude,
          coords.longitude,
          _geofenceConfig!.geoLatitude!,
          _geofenceConfig!.geoLongitude!,
        );
        _distanceToCampus = dist;

        final maxRadius = _geofenceConfig!.geoRadiusMeters;
        final maxAccuracy = _geofenceConfig!.maxGpsAccuracyMeters;

        if (coords.accuracy > maxAccuracy) {
          _isInsideGeofence = false;
          _geofenceStatusMessage =
              'GPS accuracy (±${coords.accuracy.toStringAsFixed(1)}m) exceeds threshold (±${maxAccuracy.toStringAsFixed(0)}m).';
        } else if (dist <= maxRadius) {
          _isInsideGeofence = true;
          _geofenceStatusMessage =
              'Inside campus perimeter (${dist.toStringAsFixed(1)}m / ${maxRadius.toStringAsFixed(0)}m)';
        } else {
          _isInsideGeofence = false;
          _geofenceStatusMessage =
              'Outside campus boundary (${dist.toStringAsFixed(1)}m away). Radius allowed: ${maxRadius.toStringAsFixed(0)}m.';
        }
      }

      _checkInStatus = CheckInStatus.idle;
      _statusDetail = null;
      notifyListeners();
    } catch (e) {
      _checkInStatus = CheckInStatus.error;
      _statusDetail = e.toString();
      _geofenceStatusMessage = 'Unable to get location: $e';
      notifyListeners();
    }
  }

  /// Performs full auto-checkin: GPS + Camera Frame Capture
  Future<Map<String, dynamic>?> performAutoCheckIn(Uint8List frameBytes, {String tenantSlug = 'default'}) async {
    if (_userCoordinates == null) {
      await updateLocation();
      if (_userCoordinates == null) {
        _checkInStatus = CheckInStatus.error;
        _statusDetail = 'GPS location unavailable. Please grant location permissions in Chrome.';
        notifyListeners();
        return null;
      }
    }

    if (!_isInsideGeofence) {
      _checkInStatus = CheckInStatus.error;
      _statusDetail = _geofenceStatusMessage ?? 'You must be on campus premises to mark attendance.';
      notifyListeners();
      return null;
    }

    _checkInStatus = CheckInStatus.submitting;
    _statusDetail = 'Verifying face biometrics and logging attendance...';
    notifyListeners();

    try {
      final result = await ApiService.submitSelfAttendance(
        latitude: _userCoordinates!.latitude,
        longitude: _userCoordinates!.longitude,
        accuracy: _userCoordinates!.accuracy,
        imageBytes: frameBytes,
        tenantSlug: tenantSlug,
      );

      _lastCheckInResult = result;
      final statusStr = result['status'] ?? 'success';

      if (statusStr == 'success') {
        _checkInStatus = CheckInStatus.success;
        _statusDetail = result['message'] ?? 'Attendance marked successfully!';
      } else if (statusStr == 'cooldown') {
        _checkInStatus = CheckInStatus.cooldown;
        _statusDetail = result['message'] ?? 'Already checked in recently.';
      }

      notifyListeners();
      return result;
    } catch (e) {
      _checkInStatus = CheckInStatus.error;
      _statusDetail = e.toString().replaceAll('Exception:', '').trim();
      notifyListeners();
      return null;
    }
  }

  /// Loads attendance history for a specific roll number or user
  Future<void> loadHistory({String? token, String? rollNumber, int? studentId}) async {
    _isLoadingHistory = true;
    _historyError = null;
    notifyListeners();

    try {
      final records = await ApiService.fetchAttendanceHistory(
        token: token,
        rollNumber: rollNumber,
        studentId: studentId,
      );
      _historyRecords = records;
      _isLoadingHistory = false;
      notifyListeners();
    } catch (e) {
      _historyError = e.toString().replaceAll('Exception:', '').trim();
      _isLoadingHistory = false;
      notifyListeners();
    }
  }

  void setTimeRangeFilter(HistoryFilterTimeRange range) {
    _selectedTimeRange = range;
    notifyListeners();
  }

  void setStatusFilter(String? status) {
    _selectedStatusFilter = status;
    notifyListeners();
  }

  void setSearchQuery(String query) {
    _searchQuery = query;
    notifyListeners();
  }

  void resetStatus() {
    _checkInStatus = CheckInStatus.idle;
    _statusDetail = null;
    notifyListeners();
  }
}
