import 'dart:async';
import 'dart:convert';
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

  // Punch State Machine
  String _currentPunchStatus = 'NOT_CHECKED_IN';
  String _nextPunchAction = 'CHECK_IN';
  String? _lastCheckInShort;
  String? _lastCheckOutShort;

  CheckInStatus _checkInStatus = CheckInStatus.idle;
  String? _statusDetail;
  Map<String, dynamic>? _lastCheckInResult;

  // Background Heartbeat Monitoring
  Timer? _heartbeatTimer;
  bool _isMonitoringActive = false;
  bool _hasActiveBreach = false;
  String? _breachAlertMessage;

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

  String get currentPunchStatus => _currentPunchStatus;
  String get nextPunchAction => _nextPunchAction;
  String? get lastCheckInShort => _lastCheckInShort;
  String? get lastCheckOutShort => _lastCheckOutShort;

  CheckInStatus get checkInStatus => _checkInStatus;
  String? get statusDetail => _statusDetail;
  Map<String, dynamic>? get lastCheckInResult => _lastCheckInResult;

  bool get isMonitoringActive => _isMonitoringActive;
  bool get hasActiveBreach => _hasActiveBreach;
  String? get breachAlertMessage => _breachAlertMessage;

  bool get isLoadingHistory => _isLoadingHistory;
  String? get historyError => _historyError;
  HistoryFilterTimeRange get selectedTimeRange => _selectedTimeRange;
  String? get selectedStatusFilter => _selectedStatusFilter;
  String get searchQuery => _searchQuery;

  List<AttendanceRecordItem> get filteredRecords {
    var list = List<AttendanceRecordItem>.from(_historyRecords);

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

    if (_selectedStatusFilter != null && _selectedStatusFilter != 'ALL') {
      list = list.where((r) {
        if (_selectedStatusFilter == 'SELF') return r.isSelfAttendance;
        if (_selectedStatusFilter == 'OVERRIDE') return r.isManualOverride;
        if (_selectedStatusFilter == 'NODE') return !r.isSelfAttendance && !r.isManualOverride;
        return true;
      }).toList();
    }

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
  Future<void> initConfig({String tenantSlug = 'default', String? token}) async {
    try {
      if (token != null && token.isNotEmpty) {
        final configJson = await ApiService.fetchEmployeeGeofenceConfig(token: token);
        _geofenceConfig = GeofenceConfig.fromJson(configJson);

        final pStatus = configJson['punch_status'] ?? {};
        _currentPunchStatus = pStatus['status'] ?? 'NOT_CHECKED_IN';
        _nextPunchAction = pStatus['next_action'] ?? 'CHECK_IN';
        _lastCheckInShort = pStatus['check_in_time'];
        _lastCheckOutShort = pStatus['check_out_time'];

        if (_currentPunchStatus == 'CHECKED_IN') {
          startHeartbeatMonitoring(token);
        }
      } else {
        _geofenceConfig = await ApiService.fetchGeofenceConfig(tenantSlug: tenantSlug);
      }
      notifyListeners();
      await updateLocation();
    } catch (e) {
      debugPrint('Error fetching geofence config: $e');
    }
  }

  /// Updates current GPS coordinates and computes campus radar distance
  Future<void> updateLocation() async {
    _checkInStatus = CheckInStatus.locating;
    _statusDetail = 'Acquiring high-accuracy GPS coordinates...';
    notifyListeners();

    try {
      final coords = await LocationService.getCurrentLocation();
      _userCoordinates = coords;

      final isGeofenceEnabled = _geofenceConfig?.enableSelfAttendance ?? false;
      final officeName = _geofenceConfig?.locationName;

      if (!isGeofenceEnabled) {
        // Geofencing is disabled for this location/organization:
        // Employees can check in/out from any location without geofence perimeter boundaries!
        _isInsideGeofence = true;
        _geofenceStatusMessage = officeName != null
            ? 'Geofencing Bypassed for $officeName (Any Location Allowed)'
            : 'Geofencing Bypassed (Any Location Allowed)';
        _distanceToCampus = null;
      } else if (_geofenceConfig != null &&
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
        final locTitle = officeName ?? 'office';

        if (coords.isMocked) {
          _isInsideGeofence = false;
          _geofenceStatusMessage =
              'Mock location / GPS spoofing application detected. Real hardware GPS required.';
        } else if (coords.accuracy > maxAccuracy) {
          _isInsideGeofence = false;
          _geofenceStatusMessage =
              'GPS accuracy (±${coords.accuracy.toStringAsFixed(1)}m) exceeds threshold (±${maxAccuracy.toStringAsFixed(0)}m).';
        } else if (dist <= maxRadius) {
          _isInsideGeofence = true;
          _geofenceStatusMessage =
              'Inside $locTitle perimeter (${dist.toStringAsFixed(1)}m / ${maxRadius.toStringAsFixed(0)}m)';
        } else {
          _isInsideGeofence = false;
          _geofenceStatusMessage =
              'Outside $locTitle perimeter (${dist.toStringAsFixed(1)}m away). Radius allowed: ${maxRadius.toStringAsFixed(0)}m.';
        }
      } else {
        _isInsideGeofence = true;
        _geofenceStatusMessage = officeName != null
            ? 'Geofence coordinates pending setup for $officeName'
            : 'Geofence coordinates pending admin setup';
      }

      _checkInStatus = CheckInStatus.idle;
      _statusDetail = null;
      notifyListeners();
    } catch (e) {
      _checkInStatus = CheckInStatus.error;
      _statusDetail = e.toString().replaceAll('Exception:', '').trim();
      _geofenceStatusMessage = 'GPS Error: $_statusDetail';
      notifyListeners();
    }
  }

  /// Mobile Geofenced Check-In / Check-Out Punch
  Future<Map<String, dynamic>?> performAutoCheckIn(Uint8List frameBytes, {String tenantSlug = 'default'}) async {
    return performMobilePunch(token: '', frameBytes: frameBytes);
  }

  Future<Map<String, dynamic>?> performMobilePunch({
    required String token,
    Uint8List? frameBytes,
    String? forcedAction,
  }) async {
    await updateLocation();

    if (_userCoordinates == null) {
      _checkInStatus = CheckInStatus.error;
      _statusDetail = 'GPS location unavailable. Please grant location access.';
      notifyListeners();
      return null;
    }

    if (_userCoordinates!.isMocked) {
      _checkInStatus = CheckInStatus.error;
      _statusDetail = 'Mock location or GPS spoofing application detected. Real hardware GPS is required. This security breach has been logged.';
      notifyListeners();

      try {
        String? photoB64;
        if (frameBytes != null && frameBytes.isNotEmpty) {
          photoB64 = base64Encode(frameBytes);
        }
        await ApiService.employeeMobileCheckIn(
          token: token,
          latitude: _userCoordinates!.latitude,
          longitude: _userCoordinates!.longitude,
          accuracy: _userCoordinates!.accuracy,
          photoBase64: photoB64,
          punchType: forcedAction ?? _nextPunchAction,
          isMockLocation: true,
        );
      } catch (_) {}

      return {'status': 'error', 'message': _statusDetail};
    }

    final isGeofenceEnabled = _geofenceConfig?.enableSelfAttendance ?? false;
    if (isGeofenceEnabled && !_isInsideGeofence) {
      _checkInStatus = CheckInStatus.error;
      _statusDetail = _geofenceStatusMessage ?? 'You are outside the authorized geofence perimeter.';
      notifyListeners();
      return null;
    }

    _checkInStatus = CheckInStatus.submitting;
    _statusDetail = 'Logging geofenced attendance punch...';
    notifyListeners();

    try {
      String? photoB64;
      if (frameBytes != null && frameBytes.isNotEmpty) {
        photoB64 = base64Encode(frameBytes);
      }

      final action = forcedAction ?? _nextPunchAction;
      final result = await ApiService.employeeMobileCheckIn(
        token: token,
        latitude: _userCoordinates!.latitude,
        longitude: _userCoordinates!.longitude,
        accuracy: _userCoordinates!.accuracy,
        photoBase64: photoB64,
        punchType: action,
        isMockLocation: _userCoordinates!.isMocked,
      );

      _lastCheckInResult = result;
      final statusStr = result['status'] ?? 'success';

      if (statusStr == 'success') {
        _checkInStatus = CheckInStatus.success;
        _statusDetail = result['message'] ?? 'Attendance marked successfully!';

        final punchType = result['punch_type'] ?? 'CHECK_IN';
        if (punchType == 'CHECK_IN') {
          _currentPunchStatus = 'CHECKED_IN';
          _nextPunchAction = 'CHECK_OUT';
          _lastCheckInShort = result['check_in_short'] ?? 'Just now';
          startHeartbeatMonitoring(token);
        } else {
          _currentPunchStatus = 'CHECKED_OUT';
          _nextPunchAction = 'CHECK_IN';
          _lastCheckOutShort = result['check_out_short'] ?? 'Just now';
          stopHeartbeatMonitoring();
        }
      } else if (statusStr == 'cooldown') {
        _checkInStatus = CheckInStatus.cooldown;
        _statusDetail = result['message'] ?? 'Cooldown active between punches.';
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

  /// Starts background periodic perimeter heartbeat monitoring while checked in
  void startHeartbeatMonitoring(String token) {
    stopHeartbeatMonitoring();
    _isMonitoringActive = true;

    // Send immediate heartbeat
    _sendHeartbeat(token);

    // Schedule every 60 seconds
    _heartbeatTimer = Timer.periodic(const Duration(seconds: 60), (_) {
      _sendHeartbeat(token);
    });
    notifyListeners();
  }

  void stopHeartbeatMonitoring() {
    _heartbeatTimer?.cancel();
    _heartbeatTimer = null;
    _isMonitoringActive = false;
    _hasActiveBreach = false;
    _breachAlertMessage = null;
    notifyListeners();
  }

  Future<void> _sendHeartbeat(String token) async {
    try {
      final coords = await LocationService.getCurrentLocation();
      _userCoordinates = coords;

      final res = await ApiService.sendGeofenceHeartbeat(
        token: token,
        latitude: coords.latitude,
        longitude: coords.longitude,
        accuracy: coords.accuracy,
        isMockLocation: coords.isMocked,
      );

      final inBounds = res['in_bounds'] ?? true;
      if (!inBounds || coords.isMocked) {
        _hasActiveBreach = true;
        _breachAlertMessage = coords.isMocked
            ? 'Mock location / GPS spoofing detected.'
            : (res['message'] ?? 'Out of bounds detected.');
      } else {
        _hasActiveBreach = false;
        _breachAlertMessage = null;
      }
      notifyListeners();
    } catch (e) {
      debugPrint('Heartbeat tick error: $e');
    }
  }

  /// Loads attendance history for a specific roll number or user
  Future<void> loadHistory({
    String? token,
    String? rollNumber,
    int? studentId,
    int? year,
    int? month,
  }) async {
    _isLoadingHistory = true;
    _historyError = null;
    notifyListeners();

    try {
      final records = await ApiService.fetchAttendanceHistory(
        token: token,
        rollNumber: rollNumber,
        studentId: studentId,
        year: year,
        month: month,
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

  @override
  void dispose() {
    _heartbeatTimer?.cancel();
    super.dispose();
  }
}
