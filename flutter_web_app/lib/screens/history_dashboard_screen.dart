import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../providers/auth_provider.dart';
import '../providers/attendance_provider.dart';
import '../widgets/attendance_card.dart';
import 'auto_checkin_screen.dart';
import 'face_login_screen.dart';

class HistoryDashboardScreen extends StatefulWidget {
  const HistoryDashboardScreen({Key? key}) : super(key: key);

  @override
  State<HistoryDashboardScreen> createState() => _HistoryDashboardScreenState();
}

class _HistoryDashboardScreenState extends State<HistoryDashboardScreen> {
  final TextEditingController _searchController = TextEditingController();

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _fetchHistory();
    });
  }

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }

  void _fetchHistory() {
    final authProvider = Provider.of<AuthProvider>(context, listen: false);
    final attendanceProvider = Provider.of<AttendanceProvider>(context, listen: false);

    attendanceProvider.loadHistory(
      token: authProvider.currentUser?.token,
      rollNumber: authProvider.currentUser?.rollNumber,
      studentId: authProvider.currentUser?.studentId,
    );
  }

  @override
  Widget build(BuildContext context) {
    final authProvider = Provider.of<AuthProvider>(context);
    final attendanceProvider = Provider.of<AttendanceProvider>(context);
    final user = authProvider.currentUser;
    final records = attendanceProvider.filteredRecords;

    final selfCount = records.where((r) => r.isSelfAttendance).length;
    final nodeCount = records.where((r) => !r.isSelfAttendance && !r.isManualOverride).length;
    final overrideCount = records.where((r) => r.isManualOverride).length;

    return Scaffold(
      backgroundColor: const Color(0xFF0D1117),
      appBar: AppBar(
        backgroundColor: const Color(0xFF161B22),
        elevation: 0,
        title: Row(
          children: [
            Container(
              width: 34,
              height: 34,
              decoration: BoxDecoration(
                gradient: const LinearGradient(
                  colors: [Color(0xFF6366F1), Color(0xFF4F46E5)],
                ),
                borderRadius: BorderRadius.circular(8),
              ),
              child: const Icon(Icons.history_rounded, color: Colors.white, size: 20),
            ),
            const SizedBox(width: 12),
            Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'Attendance History',
                  style: TextStyle(
                    color: Colors.white,
                    fontSize: 16,
                    fontWeight: FontWeight.w700,
                  ),
                ),
                if (user != null)
                  Text(
                    '${user.name} (${user.rollNumber ?? user.username})',
                    style: TextStyle(
                      color: Colors.white.withOpacity(0.55),
                      fontSize: 11,
                    ),
                  ),
              ],
            ),
          ],
        ),
        actions: [
          IconButton(
            tooltip: 'Refresh',
            icon: const Icon(Icons.refresh_rounded, color: Colors.white70),
            onPressed: _fetchHistory,
          ),
          IconButton(
            tooltip: 'Live Check-In Radar',
            icon: const Icon(Icons.radar_rounded, color: Color(0xFF6366F1)),
            onPressed: () {
              Navigator.of(context).pushReplacement(
                MaterialPageRoute(builder: (_) => const AutoCheckInScreen()),
              );
            },
          ),
          PopupMenuButton<String>(
            icon: const Icon(Icons.more_vert_rounded, color: Colors.white70),
            color: const Color(0xFF21262D),
            onSelected: (value) {
              if (value == 'logout') {
                authProvider.logout();
                Navigator.of(context).pushReplacement(
                  MaterialPageRoute(builder: (_) => const FaceLoginScreen()),
                );
              }
            },
            itemBuilder: (context) => [
              PopupMenuItem(
                value: 'profile',
                child: Row(
                  children: [
                    const Icon(Icons.badge_outlined, color: Colors.white70, size: 18),
                    const SizedBox(width: 10),
                    Text(
                      user?.department ?? 'Student',
                      style: const TextStyle(color: Colors.white, fontSize: 13),
                    ),
                  ],
                ),
              ),
              const PopupMenuItem(
                value: 'logout',
                child: Row(
                  children: [
                    Icon(Icons.logout_rounded, color: Color(0xFFEF4444), size: 18),
                    SizedBox(width: 10),
                    Text(
                      'Logout Session',
                      style: TextStyle(color: Color(0xFFEF4444), fontSize: 13, fontWeight: FontWeight.w600),
                    ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(width: 8),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: () async => _fetchHistory(),
        color: const Color(0xFF6366F1),
        backgroundColor: const Color(0xFF161B22),
        child: SingleChildScrollView(
          physics: const AlwaysScrollableScrollPhysics(),
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Summary Metrics Row
              _buildMetricsSummary(records.length, selfCount, nodeCount, overrideCount),
              const SizedBox(height: 16),

              // Search Bar
              _buildSearchBar(attendanceProvider),
              const SizedBox(height: 12),

              // Time Range Filter Chips
              _buildTimeRangeChips(attendanceProvider),
              const SizedBox(height: 10),

              // Status Filter Chips
              _buildStatusFilterChips(attendanceProvider),
              const SizedBox(height: 16),

              // History Log List
              _buildRecordList(attendanceProvider, records),
            ],
          ),
        ),
      ),
      floatingActionButton: FloatingActionButton.extended(
        backgroundColor: const Color(0xFF6366F1),
        foregroundColor: Colors.white,
        icon: const Icon(Icons.camera_alt_outlined, size: 20),
        label: const Text(
          'Mark Attendance',
          style: TextStyle(fontWeight: FontWeight.w700, fontSize: 13),
        ),
        onPressed: () {
          Navigator.of(context).push(
            MaterialPageRoute(builder: (_) => const AutoCheckInScreen()),
          );
        },
      ),
    );
  }

  Widget _buildMetricsSummary(int total, int self, int node, int override) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final cardWidth = (constraints.maxWidth - 24) / 4;
        return Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            _buildMetricTile('Total Logs', '$total', Icons.fact_check_outlined, const Color(0xFF6366F1), cardWidth),
            _buildMetricTile('GPS Self', '$self', Icons.satellite_alt_rounded, const Color(0xFF10B981), cardWidth),
            _buildMetricTile('Node Edge', '$node', Icons.camera_alt_outlined, const Color(0xFF38BDF8), cardWidth),
            _buildMetricTile('Override', '$override', Icons.shield_outlined, const Color(0xFFF59E0B), cardWidth),
          ],
        );
      },
    );
  }

  Widget _buildMetricTile(String title, String count, IconData icon, Color color, double width) {
    return Container(
      width: width > 70 ? width : 75,
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 12),
      decoration: BoxDecoration(
        color: const Color(0xFF161B22),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: color.withOpacity(0.25)),
      ),
      child: Column(
        children: [
          Icon(icon, color: color, size: 18),
          const SizedBox(height: 6),
          Text(
            count,
            style: TextStyle(
              color: color,
              fontSize: 16,
              fontWeight: FontWeight.w800,
            ),
          ),
          const SizedBox(height: 2),
          Text(
            title,
            style: TextStyle(
              color: Colors.white.withOpacity(0.5),
              fontSize: 10,
              fontWeight: FontWeight.w600,
            ),
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
          ),
        ],
      ),
    );
  }

  Widget _buildSearchBar(AttendanceProvider provider) {
    return Container(
      decoration: BoxDecoration(
        color: const Color(0xFF161B22),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: Colors.white.withOpacity(0.08)),
      ),
      child: TextField(
        controller: _searchController,
        style: const TextStyle(color: Colors.white, fontSize: 13),
        onChanged: (q) => provider.setSearchQuery(q),
        decoration: InputDecoration(
          hintText: 'Search by student name, roll number, date, or node...',
          hintStyle: TextStyle(color: Colors.white.withOpacity(0.3), fontSize: 12.5),
          prefixIcon: const Icon(Icons.search_rounded, color: Colors.white38, size: 20),
          suffixIcon: _searchController.text.isNotEmpty
              ? IconButton(
                  icon: const Icon(Icons.clear_rounded, color: Colors.white38, size: 18),
                  onPressed: () {
                    _searchController.clear();
                    provider.setSearchQuery('');
                  },
                )
              : null,
          border: InputBorder.none,
          contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 14),
        ),
      ),
    );
  }

  Widget _buildTimeRangeChips(AttendanceProvider provider) {
    final current = provider.selectedTimeRange;
    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      child: Row(
        children: [
          Text(
            'Time:',
            style: TextStyle(
              color: Colors.white.withOpacity(0.4),
              fontSize: 12,
              fontWeight: FontWeight.w600,
            ),
          ),
          const SizedBox(width: 8),
          _buildChoiceChip(
            label: 'All Time',
            isSelected: current == HistoryFilterTimeRange.all,
            onSelected: () => provider.setTimeRangeFilter(HistoryFilterTimeRange.all),
          ),
          const SizedBox(width: 6),
          _buildChoiceChip(
            label: 'Today',
            isSelected: current == HistoryFilterTimeRange.today,
            onSelected: () => provider.setTimeRangeFilter(HistoryFilterTimeRange.today),
          ),
          const SizedBox(width: 6),
          _buildChoiceChip(
            label: 'Past 7 Days',
            isSelected: current == HistoryFilterTimeRange.thisWeek,
            onSelected: () => provider.setTimeRangeFilter(HistoryFilterTimeRange.thisWeek),
          ),
          const SizedBox(width: 6),
          _buildChoiceChip(
            label: 'This Month',
            isSelected: current == HistoryFilterTimeRange.thisMonth,
            onSelected: () => provider.setTimeRangeFilter(HistoryFilterTimeRange.thisMonth),
          ),
        ],
      ),
    );
  }

  Widget _buildStatusFilterChips(AttendanceProvider provider) {
    final current = provider.selectedStatusFilter ?? 'ALL';
    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      child: Row(
        children: [
          Text(
            'Type:',
            style: TextStyle(
              color: Colors.white.withOpacity(0.4),
              fontSize: 12,
              fontWeight: FontWeight.w600,
            ),
          ),
          const SizedBox(width: 8),
          _buildChoiceChip(
            label: 'All Modes',
            isSelected: current == 'ALL',
            onSelected: () => provider.setStatusFilter('ALL'),
          ),
          const SizedBox(width: 6),
          _buildChoiceChip(
            label: 'GPS Self-Mark',
            isSelected: current == 'SELF',
            icon: Icons.satellite_alt_rounded,
            activeColor: const Color(0xFF10B981),
            onSelected: () => provider.setStatusFilter('SELF'),
          ),
          const SizedBox(width: 6),
          _buildChoiceChip(
            label: 'Classroom Node',
            isSelected: current == 'NODE',
            icon: Icons.camera_alt_outlined,
            activeColor: const Color(0xFF38BDF8),
            onSelected: () => provider.setStatusFilter('NODE'),
          ),
          const SizedBox(width: 6),
          _buildChoiceChip(
            label: 'Overrides',
            isSelected: current == 'OVERRIDE',
            icon: Icons.shield_outlined,
            activeColor: const Color(0xFFF59E0B),
            onSelected: () => provider.setStatusFilter('OVERRIDE'),
          ),
        ],
      ),
    );
  }

  Widget _buildChoiceChip({
    required String label,
    required bool isSelected,
    required VoidCallback onSelected,
    IconData? icon,
    Color activeColor = const Color(0xFF6366F1),
  }) {
    return GestureDetector(
      onTap: onSelected,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 180),
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
        decoration: BoxDecoration(
          color: isSelected ? activeColor.withOpacity(0.18) : const Color(0xFF161B22),
          borderRadius: BorderRadius.circular(8),
          border: Border.all(
            color: isSelected ? activeColor : Colors.white.withOpacity(0.08),
            width: isSelected ? 1.4 : 1,
          ),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            if (icon != null) ...[
              Icon(
                icon,
                size: 13,
                color: isSelected ? activeColor : Colors.white.withOpacity(0.5),
              ),
              const SizedBox(width: 5),
            ],
            Text(
              label,
              style: TextStyle(
                color: isSelected ? activeColor : Colors.white.withOpacity(0.7),
                fontSize: 11.5,
                fontWeight: isSelected ? FontWeight.w700 : FontWeight.w500,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildRecordList(AttendanceProvider provider, List<dynamic> records) {
    if (provider.isLoadingHistory) {
      return Container(
        height: 220,
        alignment: Alignment.center,
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const CircularProgressIndicator(color: Color(0xFF6366F1), strokeWidth: 2.5),
            const SizedBox(height: 14),
            Text(
              'Loading attendance history...',
              style: TextStyle(color: Colors.white.withOpacity(0.5), fontSize: 13),
            ),
          ],
        ),
      );
    }

    if (provider.historyError != null) {
      return Container(
        padding: const EdgeInsets.all(18),
        decoration: BoxDecoration(
          color: const Color(0xFF161B22),
          borderRadius: BorderRadius.circular(14),
          border: Border.all(color: const Color(0xFFEF4444).withOpacity(0.3)),
        ),
        child: Column(
          children: [
            const Icon(Icons.cloud_off_rounded, color: Color(0xFFEF4444), size: 36),
            const SizedBox(height: 10),
            Text(
              'Error Loading Records',
              style: TextStyle(
                color: Colors.white.withOpacity(0.9),
                fontWeight: FontWeight.w700,
                fontSize: 14,
              ),
            ),
            const SizedBox(height: 6),
            Text(
              provider.historyError!,
              style: TextStyle(color: Colors.white.withOpacity(0.5), fontSize: 12),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 14),
            ElevatedButton.icon(
              onPressed: _fetchHistory,
              icon: const Icon(Icons.refresh_rounded, size: 16),
              label: const Text('Try Again'),
              style: ElevatedButton.styleFrom(
                backgroundColor: const Color(0xFF6366F1),
                foregroundColor: Colors.white,
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
              ),
            ),
          ],
        ),
      );
    }

    if (records.isEmpty) {
      return Container(
        height: 220,
        padding: const EdgeInsets.all(24),
        alignment: Alignment.center,
        decoration: BoxDecoration(
          color: const Color(0xFF161B22),
          borderRadius: BorderRadius.circular(14),
          border: Border.all(color: Colors.white.withOpacity(0.08)),
        ),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.inbox_rounded, color: Colors.white.withOpacity(0.2), size: 48),
            const SizedBox(height: 12),
            Text(
              'No attendance logs found',
              style: TextStyle(
                color: Colors.white.withOpacity(0.7),
                fontSize: 14,
                fontWeight: FontWeight.w600,
              ),
            ),
            const SizedBox(height: 6),
            Text(
              'Check in with your camera on campus to create your first record.',
              style: TextStyle(
                color: Colors.white.withOpacity(0.4),
                fontSize: 12,
              ),
              textAlign: TextAlign.center,
            ),
          ],
        ),
      );
    }

    return Column(
      children: records.map((record) => AttendanceRecordCard(record: record)).toList(),
    );
  }
}
