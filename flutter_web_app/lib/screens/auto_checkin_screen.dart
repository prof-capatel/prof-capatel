import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../providers/auth_provider.dart';
import '../providers/attendance_provider.dart';
import '../services/camera_web_service.dart';
import '../widgets/radar_gauge.dart';
import 'history_dashboard_screen.dart';
import 'face_login_screen.dart';

class AutoCheckInScreen extends StatefulWidget {
  const AutoCheckInScreen({Key? key}) : super(key: key);

  @override
  State<AutoCheckInScreen> createState() => _AutoCheckInScreenState();
}

class _AutoCheckInScreenState extends State<AutoCheckInScreen> {
  final CameraWebService _cameraService = CameraWebService();
  bool _isCameraReady = false;
  bool _hasAutoTriggered = false;

  @override
  void initState() {
    super.initState();
    _initFlow();
  }

  Future<void> _initFlow() async {
    final attProvider = context.read<AttendanceProvider>();

    // 1. Start location lookup
    await attProvider.updateLocation();

    // 2. Initialize Camera Feed
    try {
      await _cameraService.initialize(useFrontCamera: true);
      if (mounted) {
        setState(() => _isCameraReady = true);
      }
    } catch (e) {
      debugPrint('Camera init error: $e');
    }

    // 3. Auto-trigger check-in once GPS confirmed inside geofence
    if (attProvider.isInsideGeofence && _isCameraReady && !_hasAutoTriggered) {
      _hasAutoTriggered = true;
      await _executeCheckIn();
    }
  }

  Future<void> _executeCheckIn() async {
    final attProvider = context.read<AttendanceProvider>();
    final authProvider = context.read<AuthProvider>();

    try {
      final frameBytes = await _cameraService.captureFrame();
      if (frameBytes == null) {
        return;
      }

      final result = await attProvider.performAutoCheckIn(frameBytes);
      if (result != null && result['status'] == 'success') {
        final token = result['access_token'] ?? '';
        if (token.isNotEmpty) {
          authProvider.setSessionFromCheckIn(result, token);
        }
      }
    } catch (e) {
      debugPrint('Auto checkin execution error: $e');
    }
  }

  @override
  void dispose() {
    _cameraService.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final authProvider = context.watch<AuthProvider>();
    final attProvider = context.watch<AttendanceProvider>();
    final user = authProvider.currentUser;

    return Scaffold(
      backgroundColor: const Color(0xFF0D1117),
      appBar: AppBar(
        backgroundColor: const Color(0xFF161B22),
        elevation: 0,
        title: Row(
          children: [
            Container(
              padding: const EdgeInsets.all(6),
              decoration: BoxDecoration(
                color: const Color(0xFF6366F1).withOpacity(0.2),
                borderRadius: BorderRadius.circular(8),
              ),
              child: const Icon(Icons.satellite_alt_rounded, color: Color(0xFF6366F1), size: 18),
            ),
            const SizedBox(width: 10),
            Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  user != null ? 'Hello, ${user.name}' : 'Auto Check-In Portal',
                  style: const TextStyle(fontSize: 14.5, fontWeight: FontWeight.w700, color: Colors.white),
                ),
                Text(
                  user?.rollNumber != null ? 'Roll: ${user!.rollNumber}' : 'Frictionless Presence',
                  style: TextStyle(fontSize: 11, color: Colors.white.withOpacity(0.5)),
                ),
              ],
            ),
          ],
        ),
        actions: [
          IconButton(
            icon: const Icon(Icons.history_rounded, color: Colors.white),
            tooltip: 'Attendance History',
            onPressed: () {
              Navigator.of(context).push(
                MaterialPageRoute(builder: (_) => const HistoryDashboardScreen()),
              );
            },
          ),
          IconButton(
            icon: const Icon(Icons.logout_rounded, color: Colors.white70),
            tooltip: 'Sign Out',
            onPressed: () {
              authProvider.logout();
              _cameraService.dispose();
              Navigator.of(context).pushReplacement(
                MaterialPageRoute(builder: (_) => const FaceLoginScreen()),
              );
            },
          ),
        ],
      ),
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(16),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 520),
              child: Column(
                children: [
                  // Geofence Radar Card
                  const RadarGaugeCard(),
                  const SizedBox(height: 16),

                  // Camera Viewport Card
                  Container(
                    width: double.infinity,
                    height: 280,
                    decoration: BoxDecoration(
                      color: Colors.black,
                      borderRadius: BorderRadius.circular(20),
                      border: Border.all(
                        color: attProvider.isInsideGeofence
                            ? const Color(0xFF10B981)
                            : Colors.white.withOpacity(0.1),
                        width: 2,
                      ),
                      boxShadow: [
                        BoxShadow(
                          color: Colors.black.withOpacity(0.3),
                          blurRadius: 12,
                          offset: const Offset(0, 4),
                        ),
                      ],
                    ),
                    clipBehavior: Clip.antiAlias,
                    child: Stack(
                      alignment: Alignment.center,
                      children: [
                        if (_isCameraReady)
                          HtmlElementView(viewType: _cameraService.viewType)
                        else
                          const Center(
                            child: CircularProgressIndicator(color: Color(0xFF6366F1)),
                          ),

                        // Face reticle overlay
                        Container(
                          width: 180,
                          height: 180,
                          decoration: BoxDecoration(
                            shape: BoxShape.circle,
                            border: Border.all(
                              color: attProvider.isInsideGeofence
                                  ? const Color(0xFF10B981)
                                  : Colors.white.withOpacity(0.5),
                              width: 2,
                            ),
                          ),
                        ),

                        // Submitting spinner overlay
                        if (attProvider.checkInStatus == CheckInStatus.submitting)
                          Container(
                            color: Colors.black.withOpacity(0.65),
                            child: const Column(
                              mainAxisAlignment: MainAxisAlignment.center,
                              children: [
                                CircularProgressIndicator(color: Color(0xFF6366F1)),
                                SizedBox(height: 12),
                                Text(
                                  'Verifying biometric vectors & GPS...',
                                  style: TextStyle(
                                    color: Colors.white,
                                    fontSize: 13,
                                    fontWeight: FontWeight.w600,
                                  ),
                                ),
                              ],
                            ),
                          ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 16),

                  // Result Feedback Card (Success / Cooldown / Error)
                  if (attProvider.checkInStatus == CheckInStatus.success)
                    _buildResultCard(
                      isSuccess: true,
                      title: 'Attendance Verified & Logged!',
                      subtitle: attProvider.statusDetail ?? 'Presence marked successfully.',
                      icon: Icons.check_circle_rounded,
                      color: const Color(0xFF10B981),
                    )
                  else if (attProvider.checkInStatus == CheckInStatus.cooldown)
                    _buildResultCard(
                      isSuccess: false,
                      title: 'Already Marked Recently',
                      subtitle: attProvider.statusDetail ?? 'Cooldown active.',
                      icon: Icons.access_time_filled_rounded,
                      color: const Color(0xFFF59E0B),
                    )
                  else if (attProvider.checkInStatus == CheckInStatus.error)
                    _buildResultCard(
                      isSuccess: false,
                      title: 'Verification Incomplete',
                      subtitle: attProvider.statusDetail ?? 'Please check campus perimeter.',
                      icon: Icons.error_rounded,
                      color: const Color(0xFFEF4444),
                    ),

                  const SizedBox(height: 16),

                  // Action Buttons
                  Row(
                    children: [
                      Expanded(
                        child: SizedBox(
                          height: 48,
                          child: ElevatedButton.icon(
                            onPressed: (_isCameraReady && attProvider.checkInStatus != CheckInStatus.submitting)
                                ? _executeCheckIn
                                : null,
                            icon: const Icon(Icons.camera_alt_rounded, size: 18),
                            label: const Text(
                              'Mark Presence Now',
                              style: TextStyle(fontSize: 14, fontWeight: FontWeight.w700),
                            ),
                            style: ElevatedButton.styleFrom(
                              backgroundColor: const Color(0xFF6366F1),
                              foregroundColor: Colors.white,
                              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                            ),
                          ),
                        ),
                      ),
                      const SizedBox(width: 10),
                      SizedBox(
                        height: 48,
                        child: OutlinedButton.icon(
                          onPressed: () {
                            Navigator.of(context).push(
                              MaterialPageRoute(builder: (_) => const HistoryDashboardScreen()),
                            );
                          },
                          icon: const Icon(Icons.history_rounded, size: 18),
                          label: const Text('View History'),
                          style: OutlinedButton.styleFrom(
                            foregroundColor: Colors.white,
                            side: BorderSide(color: Colors.white.withOpacity(0.2)),
                            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                          ),
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildResultCard({
    required bool isSuccess,
    required String title,
    required String subtitle,
    required IconData icon,
    required Color color,
  }) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: color.withOpacity(0.12),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: color.withOpacity(0.35)),
      ),
      child: Row(
        children: [
          Icon(icon, color: color, size: 28),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: TextStyle(
                    color: color,
                    fontSize: 14,
                    fontWeight: FontWeight.w700,
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  subtitle,
                  style: TextStyle(
                    color: Colors.white.withOpacity(0.8),
                    fontSize: 12,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
