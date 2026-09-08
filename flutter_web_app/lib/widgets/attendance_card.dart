import 'package:flutter/material.dart';
import '../config/api_config.dart';
import '../models/attendance_record.dart';

class AttendanceRecordCard extends StatelessWidget {
  final AttendanceRecordItem record;

  const AttendanceRecordCard({Key? key, required this.record}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    Color typeColor;
    String typeLabel;
    IconData typeIcon;

    if (record.isManualOverride) {
      typeColor = const Color(0xFFF59E0B);
      typeLabel = 'Manual Override';
      typeIcon = Icons.shield_outlined;
    } else if (record.isSelfAttendance) {
      typeColor = const Color(0xFF10B981);
      typeLabel = record.geoDistanceMeters != null
          ? 'GPS Self (${record.geoDistanceMeters!.toStringAsFixed(0)}m)'
          : 'GPS Self';
      typeIcon = Icons.satellite_alt_rounded;
    } else {
      typeColor = const Color(0xFF6366F1);
      typeLabel = record.nodeId;
      typeIcon = Icons.camera_alt_outlined;
    }

    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: const Color(0xFF161B22),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: Colors.white.withOpacity(0.08)),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.2),
            blurRadius: 8,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Row(
        children: [
          // Avatar or snapshot image
          Container(
            width: 44,
            height: 44,
            decoration: BoxDecoration(
              color: const Color(0xFF21262D),
              borderRadius: BorderRadius.circular(10),
              border: Border.all(color: Colors.white.withOpacity(0.1)),
            ),
            clipBehavior: Clip.antiAlias,
            child: record.snapshotPath != null && record.snapshotPath!.isNotEmpty
                ? Image.network(
                    '${ApiConfig.baseUrl}/data/${record.snapshotPath!}',
                    fit: BoxFit.cover,
                    errorBuilder: (_, __, ___) => _buildAvatarFallback(),
                  )
                : _buildAvatarFallback(),
          ),
          const SizedBox(width: 14),

          // Details Column
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Expanded(
                      child: Text(
                        record.studentName,
                        style: const TextStyle(
                          color: Colors.white,
                          fontSize: 14,
                          fontWeight: FontWeight.w700,
                        ),
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                    Text(
                      record.timestamp,
                      style: TextStyle(
                        color: Colors.white.withOpacity(0.5),
                        fontSize: 11,
                        fontFamily: 'monospace',
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 4),
                Row(
                  children: [
                    Text(
                      'Roll: ${record.rollNumber}',
                      style: TextStyle(
                        color: Colors.white.withOpacity(0.7),
                        fontSize: 12,
                        fontWeight: FontWeight.w500,
                      ),
                    ),
                    const SizedBox(width: 8),
                    Text(
                      '• ${record.department}',
                      style: TextStyle(
                        color: Colors.white.withOpacity(0.5),
                        fontSize: 12,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 8),
                Row(
                  children: [
                    // Mode / Node Badge
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                      decoration: BoxDecoration(
                        color: typeColor.withOpacity(0.15),
                        borderRadius: BorderRadius.circular(6),
                        border: Border.all(color: typeColor.withOpacity(0.3)),
                      ),
                      child: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Icon(typeIcon, color: typeColor, size: 12),
                          const SizedBox(width: 4),
                          Text(
                            typeLabel,
                            style: TextStyle(
                              color: typeColor,
                              fontSize: 11,
                              fontWeight: FontWeight.w700,
                            ),
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(width: 8),

                    // Confidence Match Badge
                    if (!record.isManualOverride && record.matchConfidencePct > 0)
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 3),
                        decoration: BoxDecoration(
                          color: const Color(0xFF10B981).withOpacity(0.12),
                          borderRadius: BorderRadius.circular(6),
                        ),
                        child: Text(
                          '${record.matchConfidencePct.toStringAsFixed(1)}% match',
                          style: const TextStyle(
                            color: Color(0xFF10B981),
                            fontSize: 10.5,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      ),
                  ],
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildAvatarFallback() {
    final initial = record.studentName.isNotEmpty ? record.studentName[0].toUpperCase() : 'U';
    return Center(
      child: Text(
        initial,
        style: const TextStyle(
          color: Color(0xFF6366F1),
          fontWeight: FontWeight.w800,
          fontSize: 16,
        ),
      ),
    );
  }
}
