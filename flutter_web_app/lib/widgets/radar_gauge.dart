import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../providers/attendance_provider.dart';

class RadarGaugeCard extends StatelessWidget {
  const RadarGaugeCard({Key? key}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    final attProvider = context.watch<AttendanceProvider>();
    final isInside = attProvider.isInsideGeofence;
    final dist = attProvider.distanceToCampus;
    final maxRadius = attProvider.geofenceConfig?.geoRadiusMeters ?? 150.0;
    final accuracy = attProvider.userCoordinates?.accuracy;

    Color statusColor;
    String statusText;
    IconData statusIcon;

    if (attProvider.userCoordinates == null) {
      statusColor = Colors.amber;
      statusText = 'Locating GPS...';
      statusIcon = Icons.satellite_alt_rounded;
    } else if (isInside) {
      statusColor = const Color(0xFF10B981);
      statusText = 'Inside Campus Perimeter';
      statusIcon = Icons.check_circle_rounded;
    } else {
      statusColor = const Color(0xFFEF4444);
      statusText = 'Outside Campus Perimeter';
      statusIcon = Icons.cancel_rounded;
    }

    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: const Color(0xFF161B22),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(
          color: statusColor.withOpacity(0.35),
          width: 1.5,
        ),
        boxShadow: [
          BoxShadow(
            color: statusColor.withOpacity(0.08),
            blurRadius: 16,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Row(
                children: [
                  Icon(Icons.radar_rounded, color: statusColor, size: 20),
                  const SizedBox(width: 8),
                  const Text(
                    'Campus Geofence Radar',
                    style: TextStyle(
                      color: Colors.white,
                      fontWeight: FontWeight.w700,
                      fontSize: 14.5,
                    ),
                  ),
                ],
              ),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                decoration: BoxDecoration(
                  color: statusColor.withOpacity(0.15),
                  borderRadius: BorderRadius.circular(20),
                  border: Border.all(color: statusColor.withOpacity(0.4)),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(statusIcon, color: statusColor, size: 14),
                    const SizedBox(width: 5),
                    Text(
                      statusText,
                      style: TextStyle(
                        color: statusColor,
                        fontWeight: FontWeight.w700,
                        fontSize: 11.5,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 14),
          Row(
            children: [
              Expanded(
                child: _buildMetricTile(
                  label: 'CAMPUS DISTANCE',
                  value: dist != null ? '${dist.toStringAsFixed(1)} m' : '-- m',
                  subLabel: 'Max allowed: ${maxRadius.toStringAsFixed(0)}m',
                  valueColor: isInside ? const Color(0xFF10B981) : Colors.white,
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: _buildMetricTile(
                  label: 'GPS ACCURACY',
                  value: accuracy != null ? '± ${accuracy.toStringAsFixed(1)} m' : '± -- m',
                  subLabel: 'HTML5 High Accuracy',
                  valueColor: (accuracy != null && accuracy <= 50.0)
                      ? const Color(0xFF10B981)
                      : const Color(0xFFF59E0B),
                ),
              ),
            ],
          ),
          if (attProvider.geofenceStatusMessage != null) ...[
            const SizedBox(height: 10),
            Text(
              attProvider.geofenceStatusMessage!,
              style: TextStyle(
                color: Colors.white.withOpacity(0.7),
                fontSize: 12,
                height: 1.3,
              ),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildMetricTile({
    required String label,
    required String value,
    required String subLabel,
    required Color valueColor,
  }) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: const Color(0xFF0D1117),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: Colors.white.withOpacity(0.06)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            label,
            style: TextStyle(
              color: Colors.white.withOpacity(0.5),
              fontSize: 10.5,
              fontWeight: FontWeight.w600,
              letterSpacing: 0.5,
            ),
          ),
          const SizedBox(height: 4),
          Text(
            value,
            style: TextStyle(
              color: valueColor,
              fontSize: 16,
              fontWeight: FontWeight.w800,
            ),
          ),
          const SizedBox(height: 2),
          Text(
            subLabel,
            style: TextStyle(
              color: Colors.white.withOpacity(0.4),
              fontSize: 10.5,
            ),
          ),
        ],
      ),
    );
  }
}
