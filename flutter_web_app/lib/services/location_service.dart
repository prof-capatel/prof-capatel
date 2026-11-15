import 'dart:async';
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
  /// Fetches current high-accuracy native hardware GPS coordinates (Cross-platform Android / iOS / Web)
  static Future<UserCoordinates> getCurrentLocation({
    Duration timeout = const Duration(seconds: 10),
  }) async {
    // 1. Check and request location permissions
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

    // 2. Acquire high-accuracy native hardware position
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
}
