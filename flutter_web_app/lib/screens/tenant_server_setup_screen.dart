import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../config/api_config.dart';
import '../providers/auth_provider.dart';
import '../providers/attendance_provider.dart';
import '../providers/theme_provider.dart';
import '../services/api_service.dart';
import '../utils/error_formatter.dart';
import '../widgets/theme_dialog.dart';
import 'face_login_screen.dart';

class TenantServerSetupScreen extends StatefulWidget {
  final bool isEditing;

  const TenantServerSetupScreen({
    Key? key,
    this.isEditing = false,
  }) : super(key: key);

  @override
  State<TenantServerSetupScreen> createState() => _TenantServerSetupScreenState();
}

class _TenantServerSetupScreenState extends State<TenantServerSetupScreen> {
  final _formKey = GlobalKey<FormState>();
  late final TextEditingController _orgCtrl;
  late final TextEditingController _urlCtrl;
  bool _isLoading = false;
  String? _errorMessage;

  @override
  void initState() {
    super.initState();
    final auth = context.read<AuthProvider>();
    final currentSlug = auth.tenantSlug == 'default' ? '' : auth.tenantSlug;
    _orgCtrl = TextEditingController(text: currentSlug);
    _urlCtrl = TextEditingController(text: ApiConfig.baseUrl);
  }

  @override
  void dispose() {
    _orgCtrl.dispose();
    _urlCtrl.dispose();
    super.dispose();
  }

  Future<void> _handleConnect() async {
    if (!_formKey.currentState!.validate()) return;

    final enteredOrg = _orgCtrl.text.trim().toLowerCase();
    var enteredUrl = _urlCtrl.text.trim().replaceAll(RegExp(r'/+$'), '');

    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });

    try {
      // 1. Temporarily store and test endpoint
      await ApiConfig.setBaseUrl(enteredUrl);

      // 2. Resolve organization tenant via backend
      final res = await ApiService.resolveTenant(enteredOrg);
      final tenantData = res['tenant'] ?? {};
      final resolvedName = tenantData['name'] ?? enteredOrg;

      if (!mounted) return;

      final auth = context.read<AuthProvider>();
      await auth.completeSetup(
        tenantSlug: enteredOrg,
        tenantName: resolvedName,
        serverUrl: enteredUrl,
      );

      final attProvider = context.read<AttendanceProvider>();
      await attProvider.initConfig(tenantSlug: enteredOrg);

      if (!mounted) return;

      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Connected to $resolvedName ($enteredOrg)'),
          backgroundColor: const Color(0xFF10B981),
        ),
      );

      if (widget.isEditing) {
        Navigator.of(context).pop();
      } else {
        Navigator.of(context).pushReplacement(
          MaterialPageRoute(builder: (_) => const FaceLoginScreen()),
        );
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _errorMessage = ErrorFormatter.format(e);
          _isLoading = false;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;

    return Scaffold(
      backgroundColor: isDark ? const Color(0xFF0D1117) : const Color(0xFFF8FAFC),
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        elevation: 0,
        title: Text(
          widget.isEditing ? 'Server & Organization' : 'Initial Setup',
          style: TextStyle(
            color: isDark ? Colors.white : const Color(0xFF0F172A),
            fontSize: 16,
            fontWeight: FontWeight.bold,
          ),
        ),
        leading: widget.isEditing
            ? IconButton(
                icon: Icon(Icons.arrow_back_rounded, color: isDark ? Colors.white : const Color(0xFF0F172A)),
                onPressed: () => Navigator.of(context).pop(),
              )
            : null,
        actions: [
          Consumer<ThemeProvider>(
            builder: (ctx, themeProv, _) => IconButton(
              icon: Icon(themeProv.themeIcon, color: isDark ? Colors.white70 : const Color(0xFF0F172A), size: 20),
              tooltip: 'Theme: ${themeProv.themeDisplayName}',
              onPressed: () => showThemeSelectionDialog(context),
            ),
          ),
        ],
      ),
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 20),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 440),
              child: Form(
                key: _formKey,
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    // Brand Logo
                    Center(
                      child: Container(
                        width: 64,
                        height: 64,
                        decoration: BoxDecoration(
                          gradient: const LinearGradient(
                            colors: [Color(0xFF6366F1), Color(0xFF4338CA)],
                            begin: Alignment.topLeft,
                            end: Alignment.bottomRight,
                          ),
                          borderRadius: BorderRadius.circular(18),
                          boxShadow: [
                            BoxShadow(
                              color: const Color(0xFF6366F1).withOpacity(0.35),
                              blurRadius: 18,
                              offset: const Offset(0, 6),
                            ),
                          ],
                        ),
                        child: const Icon(
                          Icons.satellite_alt_rounded,
                          color: Colors.white,
                          size: 34,
                        ),
                      ),
                    ),
                    const SizedBox(height: 20),

                    // App Title
                    Text(
                      'Curiosity HUB',
                      textAlign: TextAlign.center,
                      style: TextStyle(
                        color: isDark ? Colors.white : const Color(0xFF0F172A),
                        fontSize: 22,
                        fontWeight: FontWeight.w800,
                        letterSpacing: 0.5,
                      ),
                    ),
                    const SizedBox(height: 6),
                    Text(
                      'Enterprise Attendance & Payroll Onboarding',
                      textAlign: TextAlign.center,
                      style: TextStyle(
                        color: isDark ? Colors.white60 : const Color(0xFF64748B),
                        fontSize: 13,
                      ),
                    ),
                    const SizedBox(height: 28),

                    // Setup Card
                    Container(
                      padding: const EdgeInsets.all(20),
                      decoration: BoxDecoration(
                        color: isDark ? const Color(0xFF161B22) : Colors.white,
                        borderRadius: BorderRadius.circular(16),
                        border: Border.all(color: isDark ? Colors.white.withOpacity(0.08) : const Color(0xFFE2E8F0)),
                        boxShadow: [
                          BoxShadow(
                            color: Colors.black.withOpacity(isDark ? 0.3 : 0.05),
                            blurRadius: 12,
                            offset: const Offset(0, 4),
                          ),
                        ],
                      ),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Row(
                            children: [
                              const Icon(Icons.tune_rounded, color: Color(0xFF818CF8), size: 18),
                              const SizedBox(width: 8),
                              Text(
                                'Organization & Server Setup',
                                style: TextStyle(
                                  color: isDark ? Colors.white : const Color(0xFF0F172A),
                                  fontSize: 15,
                                  fontWeight: FontWeight.w700,
                                ),
                              ),
                            ],
                          ),
                          const SizedBox(height: 6),
                          Text(
                            'Configure your organization credentials to connect this device with your enterprise workspace.',
                            style: TextStyle(
                              color: isDark ? Colors.white55 : const Color(0xFF64748B),
                              fontSize: 12,
                            ),
                          ),
                          const SizedBox(height: 20),

                          // Tenant Code Field
                          Text(
                            'Organization Code / Identifier',
                            style: TextStyle(
                              color: isDark ? Colors.white70 : const Color(0xFF475569),
                              fontSize: 12.5,
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                          const SizedBox(height: 6),
                          TextFormField(
                            controller: _orgCtrl,
                            style: TextStyle(color: isDark ? Colors.white : const Color(0xFF0F172A), fontSize: 14),
                            decoration: InputDecoration(
                              hintText: 'e.g. pulin1, ssec, gecm',
                              hintStyle: TextStyle(color: isDark ? Colors.white30 : const Color(0xFF94A3B8)),
                              prefixIcon: const Icon(Icons.business_rounded, color: Color(0xFF818CF8), size: 20),
                              filled: true,
                              fillColor: isDark ? const Color(0xFF0D1117) : const Color(0xFFF1F5F9),
                              border: OutlineInputBorder(
                                borderRadius: BorderRadius.circular(12),
                                borderSide: BorderSide(color: isDark ? Colors.white.withOpacity(0.12) : const Color(0xFFE2E8F0)),
                              ),
                              enabledBorder: OutlineInputBorder(
                                borderRadius: BorderRadius.circular(12),
                                borderSide: BorderSide(color: isDark ? Colors.white.withOpacity(0.12) : const Color(0xFFE2E8F0)),
                              ),
                              focusedBorder: OutlineInputBorder(
                                borderRadius: BorderRadius.circular(12),
                                borderSide: const BorderSide(color: Color(0xFF6366F1), width: 1.5),
                              ),
                              contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
                            ),
                            validator: (val) {
                              if (val == null || val.trim().isEmpty) {
                                return 'Please enter your organization code';
                              }
                              return null;
                            },
                          ),
                          const SizedBox(height: 16),

                          // Server URL Field
                          Text(
                            'Server Endpoint URL',
                            style: TextStyle(
                              color: isDark ? Colors.white70 : const Color(0xFF475569),
                              fontSize: 12.5,
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                          const SizedBox(height: 6),
                          TextFormField(
                            controller: _urlCtrl,
                            keyboardType: TextInputType.url,
                            style: TextStyle(color: isDark ? Colors.white : const Color(0xFF0F172A), fontSize: 13),
                            decoration: InputDecoration(
                              hintText: 'https://curiosityhub.co.in',
                              hintStyle: TextStyle(color: isDark ? Colors.white30 : const Color(0xFF94A3B8)),
                              prefixIcon: const Icon(Icons.dns_rounded, color: Color(0xFF818CF8), size: 20),
                              filled: true,
                              fillColor: isDark ? const Color(0xFF0D1117) : const Color(0xFFF1F5F9),
                              border: OutlineInputBorder(
                                borderRadius: BorderRadius.circular(12),
                                borderSide: BorderSide(color: isDark ? Colors.white.withOpacity(0.12) : const Color(0xFFE2E8F0)),
                              ),
                              enabledBorder: OutlineInputBorder(
                                borderRadius: BorderRadius.circular(12),
                                borderSide: BorderSide(color: isDark ? Colors.white.withOpacity(0.12) : const Color(0xFFE2E8F0)),
                              ),
                              focusedBorder: OutlineInputBorder(
                                borderRadius: BorderRadius.circular(12),
                                borderSide: const BorderSide(color: Color(0xFF6366F1), width: 1.5),
                              ),
                              contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
                            ),
                            validator: (val) {
                              if (val == null || val.trim().isEmpty) {
                                return 'Please enter the server endpoint';
                              }
                              final uri = Uri.tryParse(val.trim());
                              if (uri == null || (!uri.hasScheme || !uri.scheme.startsWith('http'))) {
                                return 'Please enter a valid URL (e.g. https://curiosityhub.co.in)';
                              }
                              return null;
                            },
                          ),
                          const SizedBox(height: 6),
                          Text(
                            'Default: https://curiosityhub.co.in',
                            style: TextStyle(
                              color: isDark ? Colors.white38 : const Color(0xFF94A3B8),
                              fontSize: 11,
                            ),
                          ),

                          // Error notification banner
                          if (_errorMessage != null) ...[
                            const SizedBox(height: 16),
                            Container(
                              padding: const EdgeInsets.all(12),
                              decoration: BoxDecoration(
                                color: const Color(0xFFEF4444).withOpacity(0.14),
                                borderRadius: BorderRadius.circular(10),
                                border: Border.all(color: const Color(0xFFEF4444).withOpacity(0.45)),
                              ),
                              child: Row(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  const Icon(Icons.error_outline_rounded, color: Color(0xFFEF4444), size: 18),
                                  const SizedBox(width: 8),
                                  Expanded(
                                    child: Text(
                                      _errorMessage!,
                                      style: const TextStyle(
                                        color: Color(0xFFFCA5A5),
                                        fontSize: 12,
                                        fontWeight: FontWeight.w500,
                                      ),
                                    ),
                                  ),
                                ],
                              ),
                            ),
                          ],

                          const SizedBox(height: 24),

                          // Connect & Continue Button
                          SizedBox(
                            width: double.infinity,
                            height: 48,
                            child: ElevatedButton.icon(
                              onPressed: _isLoading ? null : _handleConnect,
                              icon: _isLoading
                                  ? const SizedBox(
                                      width: 18,
                                      height: 18,
                                      child: CircularProgressIndicator(
                                        strokeWidth: 2,
                                        color: Colors.white,
                                      ),
                                    )
                                  : const Icon(Icons.arrow_forward_rounded, size: 18),
                              label: Text(
                                _isLoading ? 'Connecting to Server...' : 'Connect & Continue',
                                style: const TextStyle(
                                  fontSize: 14.5,
                                  fontWeight: FontWeight.w700,
                                  letterSpacing: 0.3,
                                ),
                              ),
                              style: ElevatedButton.styleFrom(
                                backgroundColor: const Color(0xFF6366F1),
                                foregroundColor: Colors.white,
                                shape: RoundedRectangleBorder(
                                  borderRadius: BorderRadius.circular(12),
                                ),
                                elevation: 3,
                              ),
                            ),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
