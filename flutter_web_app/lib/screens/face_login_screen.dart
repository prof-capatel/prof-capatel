import 'dart:async';
import 'dart:typed_data';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../config/api_config.dart';
import '../providers/auth_provider.dart';
import '../providers/attendance_provider.dart';
import '../services/api_service.dart';
import '../services/camera_web_service.dart';
import '../utils/error_formatter.dart';
import 'employee_mobile_home_screen.dart';
import 'tenant_server_setup_screen.dart';

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
  Uint8List? _capturedImageBytes;
  int _countdownSeconds = 3;
  Timer? _countdownTimer;
  bool _isCountingDown = false;

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
          _errorMessage = ErrorFormatter.format(e);
        });
      }
    }
  }

  void _openSetupScreen() {
    _countdownTimer?.cancel();
    Navigator.of(context).push(
      MaterialPageRoute(builder: (_) => const TenantServerSetupScreen(isEditing: true)),
    ).then((_) {
      if (mounted) {
        setState(() {});
      }
    });
  }

  void _startAutoCaptureCountdown() {
    if (_isAuthenticating || !mounted) return;
    _countdownTimer?.cancel();
    setState(() {
      _countdownSeconds = 3;
      _isCountingDown = true;
    });

    _countdownTimer = Timer.periodic(const Duration(seconds: 1), (timer) {
      if (!mounted) {
        timer.cancel();
        return;
      }
      if (_countdownSeconds > 1) {
        setState(() => _countdownSeconds--);
      } else {
        timer.cancel();
        setState(() => _isCountingDown = false);
        _handleFaceLogin();
      }
    });
  }

  Future<void> _handleFaceLogin() async {
    _countdownTimer?.cancel();
    setState(() => _isCountingDown = false);
    if (_isAuthenticating) return;

    setState(() {
      _isAuthenticating = true;
      _errorMessage = null;
    });

    try {
      final frameBytes = await _cameraService.captureFrame();
      if (frameBytes == null) {
        // User dismissed camera or cancelled
        if (mounted) {
          setState(() {
            _isAuthenticating = false;
          });
        }
        return;
      }

      if (mounted) {
        setState(() {
          _capturedImageBytes = frameBytes;
        });
      }

      final authProvider = context.read<AuthProvider>();
      final success = await authProvider.loginWithFace(frameBytes);

      if (success && mounted) {
        _cameraService.dispose();
        Navigator.of(context).pushReplacement(
          MaterialPageRoute(builder: (_) => const EmployeeMobileHomeScreen()),
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
          _errorMessage = ErrorFormatter.format(e);
          _isAuthenticating = false;
        });
      }
    }
  }

  void _showPasswordLoginDialog() {
    final usernameCtrl = TextEditingController();
    final passwordCtrl = TextEditingController();
    bool isLoggingIn = false;
    String? dialogError;

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
              if (dialogError != null) ...[
                const SizedBox(height: 12),
                Container(
                  padding: const EdgeInsets.all(10),
                  decoration: BoxDecoration(
                    color: const Color(0xFFEF4444).withOpacity(0.15),
                    borderRadius: BorderRadius.circular(8),
                    border: Border.all(color: const Color(0xFFEF4444).withOpacity(0.5)),
                  ),
                  child: Row(
                    children: [
                      const Icon(Icons.error_outline_rounded, color: Color(0xFFEF4444), size: 16),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Text(
                          dialogError!,
                          style: const TextStyle(color: Color(0xFFFCA5A5), fontSize: 12, fontWeight: FontWeight.w600),
                        ),
                      ),
                    ],
                  ),
                ),
              ],
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
                      if (usernameCtrl.text.trim().isEmpty || passwordCtrl.text.trim().isEmpty) {
                        setDialogState(() => dialogError = 'Please enter both username and password.');
                        return;
                      }
                      setDialogState(() {
                        isLoggingIn = true;
                        dialogError = null;
                      });
                      try {
                        final auth = context.read<AuthProvider>();
                        final ok = await auth.loginWithPassword(
                          usernameCtrl.text.trim(),
                          passwordCtrl.text.trim(),
                          tenantSlug: auth.tenantSlug,
                        );

                        if (ok && mounted) {
                          Navigator.of(ctx).pop();
                          _countdownTimer?.cancel();
                          _cameraService.dispose();
                          Navigator.of(context).pushReplacement(
                            MaterialPageRoute(builder: (_) => const EmployeeMobileHomeScreen()),
                          );
                        } else if (mounted) {
                          setDialogState(() {
                            isLoggingIn = false;
                            dialogError = auth.errorMessage ?? 'Invalid credentials. Please verify your username and password.';
                          });
                        }
                      } catch (e) {
                        if (mounted) {
                          setDialogState(() {
                            isLoggingIn = false;
                            dialogError = ErrorFormatter.format(e);
                          });
                        }
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

  void _showServerConfigDialog() {
    final urlCtrl = TextEditingController(text: ApiConfig.baseUrl);

    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: const Color(0xFF161B22),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(16),
          side: BorderSide(color: Colors.white.withOpacity(0.1)),
        ),
        title: const Row(
          children: [
            Icon(Icons.dns_rounded, color: Color(0xFF6366F1)),
            SizedBox(width: 10),
            Text(
              'Server Connection',
              style: TextStyle(color: Colors.white, fontSize: 16, fontWeight: FontWeight.w700),
            ),
          ],
        ),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Backend FastAPI host address:',
              style: TextStyle(color: Colors.white.withOpacity(0.7), fontSize: 13),
            ),
            const SizedBox(height: 8),
            TextField(
              controller: urlCtrl,
              style: const TextStyle(color: Colors.white, fontSize: 13),
              decoration: InputDecoration(
                hintText: 'http://10.192.19.168:8000',
                filled: true,
                fillColor: const Color(0xFF0D1117),
                border: OutlineInputBorder(borderRadius: BorderRadius.circular(10)),
              ),
            ),
            const SizedBox(height: 8),
            Text(
              'Default LAN: http://10.192.19.168:8000',
              style: TextStyle(color: Colors.white.withOpacity(0.4), fontSize: 11),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(),
            child: Text('Cancel', style: TextStyle(color: Colors.white.withOpacity(0.6))),
          ),
          ElevatedButton(
            onPressed: () async {
              final newUrl = urlCtrl.text.trim();
              if (newUrl.isNotEmpty) {
                await ApiConfig.setBaseUrl(newUrl);
                if (mounted) {
                  context.read<AttendanceProvider>().initConfig();
                  Navigator.of(ctx).pop();
                  ScaffoldMessenger.of(context).showSnackBar(
                    SnackBar(content: Text('Server updated to $newUrl')),
                  );
                }
              }
            },
            style: ElevatedButton.styleFrom(backgroundColor: const Color(0xFF6366F1)),
            child: const Text('Save'),
          ),
        ],
      ),
    );
  }

  void _showSwitchOrgDialog() {
    final authProvider = context.read<AuthProvider>();
    final orgCtrl = TextEditingController(text: authProvider.tenantSlug);
    bool isValidating = false;
    String? errorText;

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
              Icon(Icons.business_rounded, color: Color(0xFF6366F1)),
              SizedBox(width: 10),
              Text(
                'Organization Code',
                style: TextStyle(color: Colors.white, fontSize: 16, fontWeight: FontWeight.w700),
              ),
            ],
          ),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'Enter your institution or corporate slug (e.g. pulin1, default):',
                style: TextStyle(color: Colors.white.withOpacity(0.7), fontSize: 13),
              ),
              const SizedBox(height: 12),
              TextField(
                controller: orgCtrl,
                style: const TextStyle(color: Colors.white, fontSize: 14, fontWeight: FontWeight.bold),
                decoration: InputDecoration(
                  hintText: 'e.g. pulin1',
                  filled: true,
                  fillColor: const Color(0xFF0D1117),
                  border: OutlineInputBorder(borderRadius: BorderRadius.circular(10)),
                  errorText: errorText,
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
              style: ElevatedButton.styleFrom(backgroundColor: const Color(0xFF6366F1)),
              onPressed: isValidating
                  ? null
                  : () async {
                      final code = orgCtrl.text.trim().toLowerCase();
                      if (code.isEmpty) return;
                      setDialogState(() {
                        isValidating = true;
                        errorText = null;
                      });

                      try {
                        final res = await ApiService.resolveTenant(code);
                        final tName = res['tenant']?['name'] ?? code;
                        await authProvider.setTenant(code, name: tName);
                        if (mounted) {
                          context.read<AttendanceProvider>().initConfig(tenantSlug: code);
                          Navigator.of(ctx).pop();
                          ScaffoldMessenger.of(context).showSnackBar(
                            SnackBar(
                              content: Text('Connected to $tName ($code)'),
                              backgroundColor: const Color(0xFF10B981),
                            ),
                          );
                        }
                      } catch (e) {
                        setDialogState(() {
                          isValidating = false;
                          errorText = e.toString().replaceAll('Exception:', '').trim();
                        });
                      }
                    },
              child: isValidating
                  ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                  : const Text('Connect Org'),
            ),
          ],
        ),
      ),
    );
  }

  @override
  void dispose() {
    _countdownTimer?.cancel();
    _cameraService.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final branding = context.watch<AttendanceProvider>().geofenceConfig;

    return Scaffold(
      backgroundColor: const Color(0xFF0D1117),
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        elevation: 0,
        actions: [
          Consumer<AuthProvider>(
            builder: (ctx, auth, _) => TextButton.icon(
              style: TextButton.styleFrom(
                foregroundColor: const Color(0xFF818CF8),
                padding: const EdgeInsets.symmetric(horizontal: 10),
              ),
              icon: const Icon(Icons.business_rounded, size: 16),
              label: Text(
                auth.tenantSlug.toUpperCase(),
                style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 12),
              ),
              onPressed: _openSetupScreen,
            ),
          ),
          IconButton(
            icon: const Icon(Icons.tune_rounded, color: Colors.white70),
            tooltip: 'Server & Organization Settings',
            onPressed: _openSetupScreen,
          ),
        ],
      ),
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
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
                    branding?.institutionName ?? 'Curiosity HUB Attendance',
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
                  const SizedBox(height: 8),
                  InkWell(
                    onTap: _openSetupScreen,
                    borderRadius: BorderRadius.circular(20),
                    child: Container(
                      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
                      decoration: BoxDecoration(
                        color: const Color(0xFF6366F1).withOpacity(0.12),
                        borderRadius: BorderRadius.circular(20),
                        border: Border.all(color: const Color(0xFF6366F1).withOpacity(0.35)),
                      ),
                      child: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          const Icon(Icons.business_rounded, color: Color(0xFF818CF8), size: 14),
                          const SizedBox(width: 6),
                          Text(
                            'Org: ${context.watch<AuthProvider>().tenantSlug.toUpperCase()}',
                            style: const TextStyle(color: Color(0xFF818CF8), fontSize: 12, fontWeight: FontWeight.bold),
                          ),
                          const SizedBox(width: 4),
                          const Icon(Icons.swap_horiz_rounded, color: Color(0xFF818CF8), size: 16),
                        ],
                      ),
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
                        // Live front camera viewport (CameraX on Android, HTML5 Video on Web)
                        if (_isCameraReady)
                          Positioned.fill(
                            child: FittedBox(
                              fit: BoxFit.cover,
                              child: SizedBox(
                                width: 400,
                                height: 533,
                                child: _cameraService.buildPreview(),
                              ),
                            ),
                          )
                        else
                          Column(
                            mainAxisAlignment: MainAxisAlignment.center,
                            children: [
                              const CircularProgressIndicator(color: Color(0xFF6366F1)),
                              const SizedBox(height: 12),
                              Text(
                                'Starting front camera...',
                                style: TextStyle(color: Colors.white.withOpacity(0.6), fontSize: 12),
                              ),
                            ],
                          ),

                        // Face reticle oval overlay
                        IgnorePointer(
                          child: Container(
                            width: 190,
                            height: 240,
                            decoration: BoxDecoration(
                              borderRadius: BorderRadius.circular(95),
                              border: Border.all(
                                color: _isAuthenticating
                                    ? const Color(0xFF10B981)
                                    : (_isCountingDown ? const Color(0xFF6366F1) : Colors.white.withOpacity(0.4)),
                                width: 2.5,
                              ),
                            ),
                          ),
                        ),

                        // Auto-Capture Floating Countdown Badge
                        if (_isCountingDown && !_isAuthenticating)
                          Positioned(
                            bottom: 14,
                            child: Container(
                              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 7),
                              decoration: BoxDecoration(
                                color: Colors.black.withOpacity(0.78),
                                borderRadius: BorderRadius.circular(20),
                                border: Border.all(color: const Color(0xFF818CF8)),
                              ),
                              child: Row(
                                mainAxisSize: MainAxisSize.min,
                                children: [
                                  const SizedBox(
                                    width: 12,
                                    height: 12,
                                    child: CircularProgressIndicator(color: Color(0xFF818CF8), strokeWidth: 2),
                                  ),
                                  const SizedBox(width: 8),
                                  Text(
                                    'Auto-capturing in $_countdownSeconds...',
                                    style: const TextStyle(color: Colors.white, fontSize: 11.5, fontWeight: FontWeight.bold),
                                  ),
                                ],
                              ),
                            ),
                          ),

                        if (_isAuthenticating)
                          Container(
                            color: Colors.black.withOpacity(0.65),
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
                      icon: _isAuthenticating
                          ? const SizedBox(
                              width: 18,
                              height: 18,
                              child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                            )
                          : const Icon(Icons.face_retouching_natural_rounded, size: 20),
                      label: Text(
                        _isAuthenticating ? 'Verifying Face Biometrics...' : 'Scan Face to Log In',
                        style: const TextStyle(fontSize: 14.5, fontWeight: FontWeight.w700),
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
