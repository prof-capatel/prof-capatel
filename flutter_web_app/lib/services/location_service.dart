import 'dart:async';
import 'package:flutter/foundation.dart';
import 'package:geolocator/geolocator.dart';

class UserCoordinates {
  final double latitude;
  final double longitude;
  final double accuracy;
  final bool isMocked;

  UserCoordinates({
    required this.latitude,
    required this.longitude,
    required this.accuracy,
    this.isMocked = false,
  });
}

class LocationService {
  // Developer Mock GPS overrides for local device testing
  static bool isMockModeEnabled = false;
  static double? mockLatitude;
  static double? mockLongitude;

  /// Fetches current high-accuracy GPS coordinates (Cross-platform Android / iOS / Web)
  static Future<UserCoordinates> getCurrentLocation({
    Duration timeout = const Duration(seconds: 10),
  }) async {
    // 1. Check if mock mode is active for local testing
    if (isMockModeEnabled && mockLatitude != null && mockLongitude != null) {
      debugPrint('[MOCK-GPS] Using developer mock coordinates: $mockLatitude, $mockLongitude');
      return UserCoordinates(
        latitude: mockLatitude!,
        longitude: mockLongitude!,
        accuracy: 5.0,
        isMocked: true,
      );
    }

    // 2. Check and request location permissions
    bool serviceEnabled = await Geolocator.isLocationServiceEnabled();
    if (!serviceEnabled) {
      throw Exception('Location services are disabled. Please turn on device GPS.');
    }

    LocationPermission permission = await Geolocator.checkPermission();
    if (permission == LocationPermission.denied) {
      permission = await Geolocator.requestPermission();
      if (permission == LocationPermission.denied) {
        throw Exception('Location permissions are denied. Please grant location access.');
      }
    }

    if (permission == LocationPermission.deniedForever) {
      throw Exception('Location permissions are permanently denied. Please enable them in app settings.');
    }

    // 3. Acquire high-accuracy position
    try {
      final position = await Geolocator.getCurrentPosition(
        locationSettings: const LocationSettings(
          accuracy: LocationAccuracy.high,
          timeLimit: Duration(seconds: 10),
        ),
      );

      return UserCoordinates(
        latitude: position.latitude,
        longitude: position.longitude,
        accuracy: position.accuracy,
        isMocked: position.isMocked,
      );
    } catch (e) {
      throw Exception('Failed to obtain GPS coordinates: $e');
    }
  }

  /// Calculates great-circle distance between two GPS coordinates in meters
  static double calculateDistance(double lat1, double lon1, double lat2, double lon2) {
    return Geolocator.distanceBetween(lat1, lon1, lat2, lon2);
  }

  /// Sets or clears developer mock coordinates
  static void setMockCoordinates(double? lat, double? lon) {
    if (lat != null && lon != null) {
      isMockModeEnabled = true;
      mockLatitude = lat;
      mockLongitude = lon;
    } else {
      isMockModeEnabled = false;
      mockLatitude = null;
      mockLongitude = null;
    }
  }
}
