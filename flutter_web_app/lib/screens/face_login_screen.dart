import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../providers/auth_provider.dart';
import '../providers/attendance_provider.dart';
import '../services/camera_web_service.dart';
import 'auto_checkin_screen.dart';

class FaceLoginScreen extends StatefulWidget {
  const FaceLoginScreen({Key? key}) : super(key: key);

  @override
  State<FaceLoginScreen> createState() => _FaceLoginScreenState();
}

class _FaceLoginScreenState extends State<FaceLoginScreen> {
  final CameraWebService _cameraService = CameraWebService();
  bool _isCameraReady = false;
  bool _isAuthenticating = false;
  String? _errorMessage;

  @override
  void initState() {
    super.initState();
    _initCamera();
  }

  Future<void> _initCamera() async {
    try {
      await _cameraService.initialize(useFrontCamera: true);
      if (mounted) {
        setState(() {
          _isCameraReady = true;
          _errorMessage = null;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _errorMessage = e.toString().replaceAll('Exception:', '').trim();
        });
      }
    }
  }

  Future<void> _handleFaceLogin() async {
    if (_isAuthenticating) return;

    setState(() {
      _isAuthenticating = true;
      _errorMessage = null;
    });

    try {
      final frameBytes = await _cameraService.captureFrame();
      if (frameBytes == null) {
        throw Exception('Failed to capture camera frame. Please try again.');
      }

      final authProvider = context.read<AuthProvider>();
      final success = await authProvider.loginWithFace(frameBytes);

      if (success && mounted) {
        _cameraService.dispose();
        Navigator.of(context).pushReplacement(
          MaterialPageRoute(builder: (_) => const AutoCheckInScreen()),
        );
      } else if (mounted) {
        setState(() {
          _errorMessage = authProvider.errorMessage ?? 'Face not recognized in institution records.';
          _isAuthenticating = false;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _errorMessage = e.toString().replaceAll('Exception:', '').trim();
          _isAuthenticating = false;
        });
      }
    }
  }

  void _showPasswordLoginDialog() {
    final usernameCtrl = TextEditingController();
    final passwordCtrl = TextEditingController();
    bool isLoggingIn = false;

    showDialog(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setDialogState) => AlertDialog(
          backgroundColor: const Color(0xFF161B22),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(16),
            side: BorderSide(color: Colors.white.withOpacity(0.1)),
          ),
          title: const Row(
            children: [
              Icon(Icons.lock_outline_rounded, color: Color(0xFF6366F1)),
              SizedBox(width: 10),
              Text(
                'Password Sign In',
                style: TextStyle(color: Colors.white, fontSize: 16, fontWeight: FontWeight.w700),
              ),
            ],
          ),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              TextField(
                controller: usernameCtrl,
                style: const TextStyle(color: Colors.white),
                decoration: InputDecoration(
                  labelText: 'Username or Roll Number',
                  labelStyle: TextStyle(color: Colors.white.withOpacity(0.6)),
                  filled: true,
                  fillColor: const Color(0xFF0D1117),
                  border: OutlineInputBorder(borderRadius: BorderRadius.circular(10)),
                ),
              ),
              const SizedBox(height: 12),
              TextField(
                controller: passwordCtrl,
                obscureText: true,
                style: const TextStyle(color: Colors.white),
                decoration: InputDecoration(
                  labelText: 'Password',
                  labelStyle: TextStyle(color: Colors.white.withOpacity(0.6)),
                  filled: true,
                  fillColor: const Color(0xFF0D1117),
                  border: OutlineInputBorder(borderRadius: BorderRadius.circular(10)),
                ),
              ),
            ],
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.of(ctx).pop(),
              child: Text('Cancel', style: TextStyle(color: Colors.white.withOpacity(0.6))),
            ),
            ElevatedButton(
              onPressed: isLoggingIn
                  ? null
                  : () async {
                      setDialogState(() => isLoggingIn = true);
                      final auth = context.read<AuthProvider>();
                      final ok = await auth.loginWithPassword(
                        usernameCtrl.text.trim(),
                        passwordCtrl.text.trim(),
                      );
                      setDialogState(() => isLoggingIn = false);

                      if (ok && mounted) {
                        Navigator.of(ctx).pop();
                        _cameraService.dispose();
                        Navigator.of(context).pushReplacement(
                          MaterialPageRoute(builder: (_) => const AutoCheckInScreen()),
                        );
                      }
                    },
              style: ElevatedButton.styleFrom(
                backgroundColor: const Color(0xFF6366F1),
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
              ),
              child: isLoggingIn
                  ? const SizedBox(
                      width: 16,
                      height: 16,
                      child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                    )
                  : const Text('Sign In'),
            ),
          ],
        ),
      ),
    );
  }

  @override
  void dispose() {
    _cameraService.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final branding = context.watch<AttendanceProvider>().geofenceConfig;

    return Scaffold(
      backgroundColor: const Color(0xFF0D1117),
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 24),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 460),
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  // Header Logo & Acronym
                  Container(
                    width: 56,
                    height: 56,
                    decoration: BoxDecoration(
                      gradient: const LinearGradient(
                        colors: [Color(0xFF6366F1), Color(0xFF4338CA)],
                        begin: Alignment.topLeft,
                        end: Alignment.bottomRight,
                      ),
                      borderRadius: BorderRadius.circular(14),
                    ),
                    child: const Icon(Icons.face_retouching_natural_rounded, color: Colors.white, size: 30),
                  ),
                  const SizedBox(height: 14),
                  Text(
                    branding?.institutionName ?? 'FaceAttendance Campus',
                    style: const TextStyle(
                      color: Colors.white,
                      fontSize: 18,
                      fontWeight: FontWeight.w800,
                    ),
                    textAlign: TextAlign.center,
                  ),
                  const SizedBox(height: 4),
                  Text(
                    'Biometric Face Sign In',
                    style: TextStyle(
                      color: Colors.white.withOpacity(0.6),
                      fontSize: 13,
                    ),
                  ),
                  const SizedBox(height: 20),

                  // Camera Preview Container
                  Container(
                    width: double.infinity,
                    height: 320,
                    decoration: BoxDecoration(
                      color: const Color(0xFF161B22),
                      borderRadius: BorderRadius.circular(20),
                      border: Border.all(
                        color: _isAuthenticating
                            ? const Color(0xFF6366F1)
                            : Colors.white.withOpacity(0.1),
                        width: 2,
                      ),
                      boxShadow: [
                        BoxShadow(
                          color: Colors.black.withOpacity(0.4),
                          blurRadius: 16,
                          offset: const Offset(0, 6),
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
                          Column(
                            mainAxisAlignment: MainAxisAlignment.center,
                            children: [
                              const CircularProgressIndicator(color: Color(0xFF6366F1)),
                              const SizedBox(height: 12),
                              Text(
                                'Starting camera feed...',
                                style: TextStyle(color: Colors.white.withOpacity(0.6), fontSize: 12),
                              ),
                            ],
                          ),

                        // Face reticle circle overlay
                        Container(
                          width: 200,
                          height: 200,
                          decoration: BoxDecoration(
                            shape: BoxShape.circle,
                            border: Border.all(
                              color: _isAuthenticating
                                  ? const Color(0xFF6366F1)
                                  : Colors.white.withOpacity(0.6),
                              width: 2.5,
                            ),
                          ),
                        ),

                        if (_isAuthenticating)
                          Container(
                            color: Colors.black.withOpacity(0.6),
                            child: const Column(
                              mainAxisAlignment: MainAxisAlignment.center,
                              children: [
                                CircularProgressIndicator(color: Color(0xFF6366F1)),
                                SizedBox(height: 12),
                                Text(
                                  'Verifying biometric vectors...',
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
                  const SizedBox(height: 14),

                  // Error message banner if any
                  if (_errorMessage != null)
                    Container(
                      width: double.infinity,
                      margin: const EdgeInsets.only(bottom: 14),
                      padding: const EdgeInsets.all(12),
                      decoration: BoxDecoration(
                        color: const Color(0xFFEF4444).withOpacity(0.15),
                        borderRadius: BorderRadius.circular(10),
                        border: Border.all(color: const Color(0xFFEF4444).withOpacity(0.4)),
                      ),
                      child: Row(
                        children: [
                          const Icon(Icons.error_outline_rounded, color: Color(0xFFEF4444), size: 18),
                          const SizedBox(width: 8),
                          Expanded(
                            child: Text(
                              _errorMessage!,
                              style: const TextStyle(color: Color(0xFFFCA5A5), fontSize: 12),
                            ),
                          ),
                        ],
                      ),
                    ),

                  // Action Buttons
                  SizedBox(
                    width: double.infinity,
                    height: 48,
                    child: ElevatedButton.icon(
                      onPressed: (_isCameraReady && !_isAuthenticating) ? _handleFaceLogin : null,
                      icon: const Icon(Icons.camera_alt_rounded, size: 18),
                      label: const Text(
                        'Authenticate with Face',
                        style: TextStyle(fontSize: 14.5, fontWeight: FontWeight.w700),
                      ),
                      style: ElevatedButton.styleFrom(
                        backgroundColor: const Color(0xFF6366F1),
                        foregroundColor: Colors.white,
                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                        elevation: 4,
                      ),
                    ),
                  ),
                  const SizedBox(height: 12),

                  // Password login fallback
                  TextButton.icon(
                    onPressed: _showPasswordLoginDialog,
                    icon: Icon(Icons.key_rounded, size: 16, color: Colors.white.withOpacity(0.7)),
                    label: Text(
                      'Use Username & Password instead',
                      style: TextStyle(color: Colors.white.withOpacity(0.7), fontSize: 12.5),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
