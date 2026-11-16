import 'package:flutter/material.dart';

/// Clean, responsive exit confirmation dialog for Android hardware/software back button
Future<bool?> showExitConfirmationDialog(BuildContext context) {
  final isDark = Theme.of(context).brightness == Brightness.dark;
  return showDialog<bool>(
    context: context,
    builder: (ctx) => AlertDialog(
      backgroundColor: isDark ? const Color(0xFF161B22) : Colors.white,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      title: Row(
        children: [
          Container(
            padding: const EdgeInsets.all(8),
            decoration: BoxDecoration(
              color: const Color(0xFFEF4444).withOpacity(0.12),
              shape: BoxShape.circle,
            ),
            child: const Icon(Icons.exit_to_app_rounded, color: Color(0xFFEF4444), size: 22),
          ),
          const SizedBox(width: 12),
          Text(
            'Exit Application',
            style: TextStyle(
              color: isDark ? Colors.white : const Color(0xFF0F172A),
              fontSize: 17,
              fontWeight: FontWeight.bold,
            ),
          ),
        ],
      ),
      content: Text(
        'Are you sure you want to exit Curiosity HUB Attendance?',
        style: TextStyle(
          color: isDark ? Colors.white70 : const Color(0xFF475569),
          fontSize: 14,
          height: 1.4,
        ),
      ),
      actionsPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(ctx).pop(false),
          style: TextButton.styleFrom(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
          ),
          child: Text(
            'Cancel',
            style: TextStyle(
              color: isDark ? Colors.white60 : const Color(0xFF64748B),
              fontWeight: FontWeight.w600,
            ),
          ),
        ),
        ElevatedButton(
          onPressed: () => Navigator.of(ctx).pop(true),
          style: ElevatedButton.styleFrom(
            backgroundColor: const Color(0xFFEF4444),
            padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 10),
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
          ),
          child: const Text(
            'Exit',
            style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold),
          ),
        ),
      ],
    ),
  );
}
