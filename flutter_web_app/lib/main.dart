import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:provider/provider.dart';
import 'providers/auth_provider.dart';
import 'providers/attendance_provider.dart';
import 'screens/splash_screen.dart';
import 'screens/face_login_screen.dart';
import 'screens/auto_checkin_screen.dart';
import 'screens/history_dashboard_screen.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const AttendanceWebApp());
}

class AttendanceWebApp extends StatelessWidget {
  const AttendanceWebApp({Key? key}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    return MultiProvider(
      providers: [
        ChangeNotifierProvider(create: (_) => AuthProvider()),
        ChangeNotifierProvider(create: (_) => AttendanceProvider()),
      ],
      child: MaterialApp(
        title: 'Smart Attendance Check-In',
        debugShowCheckedModeBanner: false,
        theme: ThemeData(
          useMaterial3: true,
          brightness: Brightness.dark,
          scaffoldBackgroundColor: const Color(0xFF0D1117),
          primaryColor: const Color(0xFF6366F1),
          colorScheme: const ColorScheme.dark(
            primary: Color(0xFF6366F1),
            secondary: Color(0xFF10B981),
            surface: Color(0xFF161B22),
            background: Color(0xFF0D1117),
            error: Color(0xFFEF4444),
          ),
          textTheme: GoogleFonts.plusJakartaSansTextTheme(
            ThemeData.dark().textTheme,
          ),
          appBarTheme: const AppBarTheme(
            backgroundColor: Color(0xFF161B22),
            elevation: 0,
            iconTheme: IconThemeData(color: Colors.white70),
            titleTextStyle: TextStyle(
              color: Colors.white,
              fontSize: 16,
              fontWeight: FontWeight.w700,
            ),
          ),
          inputDecorationTheme: InputDecorationTheme(
            filled: true,
            fillColor: const Color(0xFF21262D),
            hintStyle: TextStyle(color: Colors.white.withOpacity(0.35)),
            border: OutlineInputBorder(
              borderRadius: BorderRadius.circular(10),
              borderSide: BorderSide(color: Colors.white.withOpacity(0.1)),
            ),
            enabledBorder: OutlineInputBorder(
              borderRadius: BorderRadius.circular(10),
              borderSide: BorderSide(color: Colors.white.withOpacity(0.1)),
            ),
            focusedBorder: OutlineInputBorder(
              borderRadius: BorderRadius.circular(10),
              borderSide: const BorderSide(color: Color(0xFF6366F1), width: 1.5),
            ),
          ),
        ),
        initialRoute: '/',
        routes: {
          '/': (context) => const SplashScreen(),
          '/login': (context) => const FaceLoginScreen(),
          '/checkin': (context) => const AutoCheckInScreen(),
          '/history': (context) => const HistoryDashboardScreen(),
        },
      ),
    );
  }
}
