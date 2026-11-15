import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../providers/theme_provider.dart';

/// Displays the 3-Way Theme Switcher Modal (Light / Dark / System Default)
void showThemeSelectionDialog(BuildContext context) {
  final themeProvider = context.read<ThemeProvider>();
  final currentMode = themeProvider.themeMode;
  final isDark = Theme.of(context).brightness == Brightness.dark;

  showDialog(
    context: context,
    builder: (ctx) {
      return AlertDialog(
        backgroundColor: isDark ? const Color(0xFF161B22) : Colors.white,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(16),
          side: BorderSide(
            color: isDark ? const Color(0xFF30363D) : const Color(0xFFE2E8F0),
          ),
        ),
        title: Row(
          children: [
            Container(
              padding: const EdgeInsets.all(8),
              decoration: BoxDecoration(
                color: const Color(0xFF6366F1).withOpacity(0.15),
                borderRadius: BorderRadius.circular(10),
              ),
              child: const Icon(
                Icons.palette_rounded,
                color: Color(0xFF6366F1),
                size: 20,
              ),
            ),
            const SizedBox(width: 12),
            Text(
              'Select Appearance',
              style: TextStyle(
                color: isDark ? Colors.white : const Color(0xFF0F172A),
                fontSize: 16,
                fontWeight: FontWeight.w700,
              ),
            ),
          ],
        ),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            _buildThemeOption(
              context: ctx,
              title: 'Light Theme',
              subtitle: 'Clean white background (curiosityhub.co.in)',
              icon: Icons.light_mode_rounded,
              iconColor: const Color(0xFFF59E0B),
              mode: ThemeMode.light,
              selected: currentMode == ThemeMode.light,
              isDark: isDark,
              onSelect: () {
                themeProvider.setThemeMode(ThemeMode.light);
                Navigator.of(ctx).pop();
              },
            ),
            const SizedBox(height: 8),
            _buildThemeOption(
              context: ctx,
              title: 'Dark Theme',
              subtitle: 'High-contrast midnight cyber mode',
              icon: Icons.dark_mode_rounded,
              iconColor: const Color(0xFF818CF8),
              mode: ThemeMode.dark,
              selected: currentMode == ThemeMode.dark,
              isDark: isDark,
              onSelect: () {
                themeProvider.setThemeMode(ThemeMode.dark);
                Navigator.of(ctx).pop();
              },
            ),
            const SizedBox(height: 8),
            _buildThemeOption(
              context: ctx,
              title: 'System Default',
              subtitle: 'Follows your device OS settings',
              icon: Icons.brightness_auto_rounded,
              iconColor: const Color(0xFF10B981),
              mode: ThemeMode.system,
              selected: currentMode == ThemeMode.system,
              isDark: isDark,
              onSelect: () {
                themeProvider.setThemeMode(ThemeMode.system);
                Navigator.of(ctx).pop();
              },
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(),
            child: Text(
              'Close',
              style: TextStyle(
                color: isDark ? Colors.white70 : const Color(0xFF64748B),
                fontWeight: FontWeight.w600,
              ),
            ),
          ),
        ],
      );
    },
  );
}

Widget _buildThemeOption({
  required BuildContext context,
  required String title,
  required String subtitle,
  required IconData icon,
  required Color iconColor,
  required ThemeMode mode,
  required bool selected,
  required bool isDark,
  required VoidCallback onSelect,
}) {
  return InkWell(
    onTap: onSelect,
    borderRadius: BorderRadius.circular(12),
    child: Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      decoration: BoxDecoration(
        color: selected
            ? const Color(0xFF6366F1).withOpacity(isDark ? 0.2 : 0.1)
            : (isDark ? const Color(0xFF0D1117) : const Color(0xFFF8FAFC)),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: selected
              ? const Color(0xFF6366F1)
              : (isDark ? const Color(0xFF30363D) : const Color(0xFFE2E8F0)),
          width: selected ? 1.5 : 1,
        ),
      ),
      child: Row(
        children: [
          Icon(icon, color: iconColor, size: 22),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: TextStyle(
                    color: isDark ? Colors.white : const Color(0xFF0F172A),
                    fontSize: 13.5,
                    fontWeight: selected ? FontWeight.w700 : FontWeight.w600,
                  ),
                ),
                Text(
                  subtitle,
                  style: TextStyle(
                    color: isDark ? Colors.white54 : const Color(0xFF64748B),
                    fontSize: 11,
                  ),
                ),
              ],
            ),
          ),
          if (selected)
            const Icon(
              Icons.check_circle_rounded,
              color: Color(0xFF6366F1),
              size: 20,
            ),
        ],
      ),
    ),
  );
}
