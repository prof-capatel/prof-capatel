import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../providers/auth_provider.dart';
import '../providers/attendance_provider.dart';
import 'auto_checkin_screen.dart';
import 'face_login_screen.dart';

class SplashScreen extends StatefulWidget {
  const SplashScreen({Key? key}) : super(key: key);

  @override
  State<SplashScreen> createState() => _SplashScreenState();
}

class _SplashScreenState extends State<SplashScreen> {
  @override
  void initState() {
    super.initState();
    _bootstrap();
  }

  Future<void> _bootstrap() async {
    final attProvider = context.read<AttendanceProvider>();
    final authProvider = context.read<AuthProvider>();

    // 1. Fetch geofence configuration from backend
    await attProvider.initConfig();

    // 2. Short splash delay for smooth visual transition
    await Future.delayed(const Duration(milliseconds: 600));

    if (!mounted) return;

    if (authProvider.isAuthenticated) {
      Navigator.of(context).pushReplacement(
        MaterialPageRoute(builder: (_) => const AutoCheckInScreen()),
      );
    } else {
      Navigator.of(context).pushReplacement(
        MaterialPageRoute(builder: (_) => const FaceLoginScreen()),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF0D1117),
      body: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Container(
              width: 80,
              height: 80,
              decoration: BoxDecoration(
                gradient: const LinearGradient(
                  colors: [Color(0xFF6366F1), Color(0xFF4338CA)],
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                ),
                borderRadius: BorderRadius.circular(20),
                boxShadow: [
                  BoxShadow(
                    color: const Color(0xFF6366F1).withOpacity(0.35),
                    blurRadius: 20,
                    offset: const Offset(0, 8),
                  ),
                ],
              ),
              child: const Icon(
                Icons.satellite_alt_rounded,
                color: Colors.white,
                size: 40,
              ),
            ),
            const SizedBox(height: 24),
            const Text(
              'FaceAttendance',
              style: TextStyle(
                color: Colors.white,
                fontSize: 22,
                fontWeight: FontWeight.w800,
                letterSpacing: 0.5,
              ),
            ),
            const SizedBox(height: 8),
            Text(
              'Frictionless Auto-Checkin & Geofence Client',
              style: TextStyle(
                color: Colors.white.withOpacity(0.6),
                fontSize: 13,
              ),
            ),
            const SizedBox(height: 32),
            const SizedBox(
              width: 24,
              height: 24,
              child: CircularProgressIndicator(
                strokeWidth: 2.5,
                valueColor: AlwaysStoppedAnimation<Color>(Color(0xFF6366F1)),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
