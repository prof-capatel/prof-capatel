import 'dart:async';
import 'dart:html' as html;
import 'dart:math' as math;

class UserCoordinates {
  final double latitude;
  final double longitude;
  final double accuracy;

  UserCoordinates({
    required this.latitude,
    required this.longitude,
    required this.accuracy,
  });
}

class LocationService {
  /// Fetches current high-accuracy HTML5 GPS coordinates from Chrome browser
  static Future<UserCoordinates> getCurrentLocation({
    Duration timeout = const Duration(seconds: 10),
  }) async {
    final geolocation = html.window.navigator.geolocation;
    final completer = Completer<UserCoordinates>();

    try {
      geolocation.getCurrentPosition(
        enableHighAccuracy: true,
        timeout: timeout,
        maximumAge: const Duration(seconds: 2),
      ).then((pos) {
        final coords = pos.coords;
        if (coords != null && coords.latitude != null && coords.longitude != null) {
          completer.complete(UserCoordinates(
            latitude: coords.latitude!.toDouble(),
            longitude: coords.longitude!.toDouble(),
            accuracy: (coords.accuracy ?? 10.0).toDouble(),
          ));
        } else {
          completer.completeError('Unable to extract coordinates from browser.');
        }
      }).catchError((err) {
        completer.completeError('Location access error: $err. Please ensure location permissions are granted in Chrome.');
      });
    } catch (e) {
      completer.completeError('Geolocation API not supported or error: $e');
    }

    return completer.future.timeout(
      timeout,
      onTimeout: () => throw TimeoutException('Geolocation request timed out. Please check GPS settings.'),
    );
  }

  /// Calculates great-circle distance between two GPS coordinates in meters using Haversine formula
  static double calculateDistance(double lat1, double lon1, double lat2, double lon2) {
    const double R = 6371000.0; // Earth radius in meters
    final double phi1 = lat1 * (math.pi / 180.0);
    final double phi2 = lat2 * (math.pi / 180.0);
    final double deltaPhi = (lat2 - lat1) * (math.pi / 180.0);
    final double deltaLambda = (lon2 - lon1) * (math.pi / 180.0);

    final double a = math.sin(deltaPhi / 2.0) * math.sin(deltaPhi / 2.0) +
        math.cos(phi1) * math.cos(phi2) * math.sin(deltaLambda / 2.0) * math.sin(deltaLambda / 2.0);
    final double c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a));

    return R * c;
  }
}
