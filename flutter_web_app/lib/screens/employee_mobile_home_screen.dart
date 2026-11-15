import 'dart:async';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';

import '../providers/attendance_provider.dart';
import '../providers/auth_provider.dart';
import '../providers/theme_provider.dart';
import '../services/api_service.dart';
import '../services/camera_web_service.dart';
import '../utils/error_formatter.dart';
import '../widgets/radar_gauge.dart';
import '../widgets/theme_dialog.dart';
import 'face_login_screen.dart';
import 'tenant_server_setup_screen.dart';

class EmployeeMobileHomeScreen extends StatefulWidget {
  const EmployeeMobileHomeScreen({Key? key}) : super(key: key);

  @override
  State<EmployeeMobileHomeScreen> createState() => _EmployeeMobileHomeScreenState();
}

class _EmployeeMobileHomeScreenState extends State<EmployeeMobileHomeScreen> {
  int _currentTabIndex = 0;

  // Punch Filter state
  int _selectedPunchYear = DateTime.now().year;
  int _selectedPunchMonth = DateTime.now().month;

  static const List<String> _monthNames = [
    '', 'January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December'
  ];

  String _monthName(int m) => (m >= 1 && m <= 12) ? _monthNames[m] : '';

  // Wages / Compensation state
  bool _isLoadingWages = false;
  Map<String, dynamic>? _payrollData;
  bool _isLoadingCompensation = false;
  Map<String, dynamic>? _compensationData;
  bool _isLoadingPayslips = false;
  List<dynamic> _payslips = [];

  // Leaves state
  int _leavesSubTabIndex = 0; // 0 = Quotas, 1 = My Requests
  bool _isLoadingLeaves = false;
  List<dynamic> _leaveBalances = [];
  bool _isLoadingRequests = false;
  List<dynamic> _leaveRequests = [];

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _initData();
    });
  }

  Future<void> _initData() async {
    final authProvider = context.read<AuthProvider>();
    final attProvider = context.read<AttendanceProvider>();
    final token = authProvider.currentUser?.token;

    if (token != null) {
      await attProvider.initConfig(token: token);
      await attProvider.loadHistory(
        token: token,
        rollNumber: authProvider.currentUser?.rollNumber,
        year: _selectedPunchYear,
        month: _selectedPunchMonth,
      );
      _loadPayrollData();
      _loadCompensationData();
      _loadPayslips();
      _loadLeaveBalances();
      _loadLeaveRequests();
    }
  }

  Future<void> _loadPayrollData() async {
    final token = context.read<AuthProvider>().currentUser?.token;
    if (token == null) return;
    setState(() => _isLoadingWages = true);
    try {
      final data = await ApiService.fetchEmployeePayroll(token: token);
      if (mounted) setState(() => _payrollData = data);
    } catch (_) {}
    if (mounted) setState(() => _isLoadingWages = false);
  }

  Future<void> _loadCompensationData() async {
    final token = context.read<AuthProvider>().currentUser?.token;
    if (token == null) return;
    setState(() => _isLoadingCompensation = true);
    try {
      final data = await ApiService.fetchEmployeeCompensation(token: token);
      if (mounted) setState(() => _compensationData = data);
    } catch (_) {}
    if (mounted) setState(() => _isLoadingCompensation = false);
  }

  Future<void> _loadPayslips() async {
    final token = context.read<AuthProvider>().currentUser?.token;
    if (token == null) return;
    setState(() => _isLoadingPayslips = true);
    try {
      final list = await ApiService.fetchEmployeePayslips(token: token);
      if (mounted) setState(() => _payslips = list);
    } catch (_) {}
    if (mounted) setState(() => _isLoadingPayslips = false);
  }

  Future<void> _loadLeaveBalances() async {
    final token = context.read<AuthProvider>().currentUser?.token;
    if (token == null) return;
    setState(() => _isLoadingLeaves = true);
    try {
      final list = await ApiService.fetchEmployeeLeaveBalances(token: token);
      if (mounted) setState(() => _leaveBalances = list);
    } catch (_) {}
    if (mounted) setState(() => _isLoadingLeaves = false);
  }

  Future<void> _loadLeaveRequests() async {
    final token = context.read<AuthProvider>().currentUser?.token;
    if (token == null) return;
    setState(() => _isLoadingRequests = true);
    try {
      final list = await ApiService.fetchEmployeeLeaveRequests(token: token);
      if (mounted) setState(() => _leaveRequests = list);
    } catch (_) {}
    if (mounted) setState(() => _isLoadingRequests = false);
  }

  Future<void> _reloadAttendancePunches() async {
    final token = context.read<AuthProvider>().currentUser?.token;
    final roll = context.read<AuthProvider>().currentUser?.rollNumber;
    await context.read<AttendanceProvider>().loadHistory(
      token: token,
      rollNumber: roll,
      year: _selectedPunchYear,
      month: _selectedPunchMonth == 0 ? null : _selectedPunchMonth,
    );
  }

  Future<void> _showChangePasswordDialog() async {
    final token = context.read<AuthProvider>().currentUser?.token;
    if (token == null) return;

    bool hasPassword = false;
    try {
      hasPassword = await ApiService.checkEmployeeHasPassword(token: token);
    } catch (_) {}

    if (!mounted) return;

    final formKey = GlobalKey<FormState>();
    final currentPasswordController = TextEditingController();
    final newPasswordController = TextEditingController();
    final confirmPasswordController = TextEditingController();
    bool obscureCurrent = true;
    bool obscureNew = true;
    bool obscureConfirm = true;
    bool isSubmitting = false;
    String? errorMessage;

    await showDialog(
      context: context,
      barrierDismissible: !isSubmitting,
      builder: (ctx) {
        return StatefulBuilder(
          builder: (dialogCtx, setDialogState) {
            final isDark = Theme.of(context).brightness == Brightness.dark;
            return AlertDialog(
              backgroundColor: isDark ? const Color(0xFF161B22) : Colors.white,
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(16),
                side: BorderSide(color: isDark ? const Color(0xFF30363D) : const Color(0xFFE2E8F0)),
              ),
              title: Row(
                children: [
                  Container(
                    padding: const EdgeInsets.all(8),
                    decoration: BoxDecoration(
                      color: const Color(0xFF10B981).withOpacity(0.15),
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: const Icon(Icons.key_rounded, color: Color(0xFF10B981), size: 22),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Text(
                      hasPassword ? 'Change Password' : 'Set Account Password',
                      style: TextStyle(color: isDark ? Colors.white : const Color(0xFF0F172A), fontSize: 17, fontWeight: FontWeight.bold),
                    ),
                  ),
                ],
              ),
              content: SizedBox(
                width: 380,
                child: SingleChildScrollView(
                  child: Form(
                    key: formKey,
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        if (!hasPassword)
                          Container(
                            padding: const EdgeInsets.all(12),
                            margin: const EdgeInsets.only(bottom: 16),
                            decoration: BoxDecoration(
                              color: const Color(0xFF0D9488).withOpacity(0.12),
                              borderRadius: BorderRadius.circular(10),
                              border: Border.all(color: const Color(0xFF0D9488).withOpacity(0.3)),
                            ),
                            child: Row(
                              children: [
                                const Icon(Icons.info_outline, color: Color(0xFF14B8A6), size: 18),
                                const SizedBox(width: 10),
                                Expanded(
                                  child: Text(
                                    'You were registered via Face Recognition. Create your initial portal password below.',
                                    style: TextStyle(color: isDark ? const Color(0xFFCCFBF1) : const Color(0xFF0F766E), fontSize: 12),
                                  ),
                                ),
                              ],
                            ),
                          ),
                        if (hasPassword) ...[
                          TextFormField(
                            controller: currentPasswordController,
                            obscureText: obscureCurrent,
                            style: TextStyle(color: isDark ? Colors.white : const Color(0xFF0F172A), fontSize: 14),
                            decoration: InputDecoration(
                              labelText: 'Current Password',
                              labelStyle: TextStyle(color: isDark ? Colors.white70 : const Color(0xFF64748B), fontSize: 13),
                              prefixIcon: Icon(Icons.lock_outline, color: isDark ? Colors.white54 : const Color(0xFF64748B), size: 20),
                              suffixIcon: IconButton(
                                icon: Icon(obscureCurrent ? Icons.visibility_off : Icons.visibility, color: isDark ? Colors.white54 : const Color(0xFF64748B), size: 18),
                                onPressed: () => setDialogState(() => obscureCurrent = !obscureCurrent),
                              ),
                              filled: true,
                              fillColor: isDark ? const Color(0xFF0D1117) : const Color(0xFFF1F5F9),
                              border: OutlineInputBorder(borderRadius: BorderRadius.circular(10), borderSide: BorderSide(color: isDark ? const Color(0xFF30363D) : const Color(0xFFCBD5E1))),
                              enabledBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(10), borderSide: BorderSide(color: isDark ? const Color(0xFF30363D) : const Color(0xFFCBD5E1))),
                              focusedBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(10), borderSide: const BorderSide(color: Color(0xFF10B981))),
                            ),
                            validator: (v) {
                              if (hasPassword && (v == null || v.trim().isEmpty)) {
                                return 'Please enter current password';
                              }
                              return null;
                            },
                          ),
                          const SizedBox(height: 14),
                        ],
                        TextFormField(
                          controller: newPasswordController,
                          obscureText: obscureNew,
                          style: TextStyle(color: isDark ? Colors.white : const Color(0xFF0F172A), fontSize: 14),
                          decoration: InputDecoration(
                            labelText: 'New Password (min 6 chars)',
                            labelStyle: TextStyle(color: isDark ? Colors.white70 : const Color(0xFF64748B), fontSize: 13),
                            prefixIcon: Icon(Icons.password_rounded, color: isDark ? Colors.white54 : const Color(0xFF64748B), size: 20),
                            suffixIcon: IconButton(
                              icon: Icon(obscureNew ? Icons.visibility_off : Icons.visibility, color: isDark ? Colors.white54 : const Color(0xFF64748B), size: 18),
                              onPressed: () => setDialogState(() => obscureNew = !obscureNew),
                            ),
                            filled: true,
                            fillColor: isDark ? const Color(0xFF0D1117) : const Color(0xFFF1F5F9),
                            border: OutlineInputBorder(borderRadius: BorderRadius.circular(10), borderSide: BorderSide(color: isDark ? const Color(0xFF30363D) : const Color(0xFFCBD5E1))),
                            enabledBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(10), borderSide: BorderSide(color: isDark ? const Color(0xFF30363D) : const Color(0xFFCBD5E1))),
                            focusedBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(10), borderSide: const BorderSide(color: Color(0xFF10B981))),
                          ),
                          validator: (v) {
                            if (v == null || v.trim().length < 6) {
                              return 'Password must be at least 6 characters';
                            }
                            return null;
                          },
                        ),
                        const SizedBox(height: 14),
                        TextFormField(
                          controller: confirmPasswordController,
                          obscureText: obscureConfirm,
                          style: TextStyle(color: isDark ? Colors.white : const Color(0xFF0F172A), fontSize: 14),
                          decoration: InputDecoration(
                            labelText: 'Confirm New Password',
                            labelStyle: TextStyle(color: isDark ? Colors.white70 : const Color(0xFF64748B), fontSize: 13),
                            prefixIcon: Icon(Icons.check_circle_outline, color: isDark ? Colors.white54 : const Color(0xFF64748B), size: 20),
                            suffixIcon: IconButton(
                              icon: Icon(obscureConfirm ? Icons.visibility_off : Icons.visibility, color: isDark ? Colors.white54 : const Color(0xFF64748B), size: 18),
                              onPressed: () => setDialogState(() => obscureConfirm = !obscureConfirm),
                            ),
                            filled: true,
                            fillColor: isDark ? const Color(0xFF0D1117) : const Color(0xFFF1F5F9),
                            border: OutlineInputBorder(borderRadius: BorderRadius.circular(10), borderSide: BorderSide(color: isDark ? const Color(0xFF30363D) : const Color(0xFFCBD5E1))),
                            enabledBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(10), borderSide: BorderSide(color: isDark ? const Color(0xFF30363D) : const Color(0xFFCBD5E1))),
                            focusedBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(10), borderSide: const BorderSide(color: Color(0xFF10B981))),
                          ),
                          validator: (v) {
                            if (v != newPasswordController.text) {
                              return 'Passwords do not match';
                            }
                            return null;
                          },
                        ),
                        if (errorMessage != null) ...[
                          const SizedBox(height: 12),
                          Text(
                            errorMessage!,
                            style: const TextStyle(color: Colors.redAccent, fontSize: 12, fontWeight: FontWeight.w600),
                          ),
                        ],
                      ],
                    ),
                  ),
                ),
              ),
              actions: [
                TextButton(
                  onPressed: isSubmitting ? null : () => Navigator.of(ctx).pop(),
                  child: Text('Cancel', style: TextStyle(color: isDark ? Colors.white60 : const Color(0xFF64748B))),
                ),
                ElevatedButton(
                  style: ElevatedButton.styleFrom(
                    backgroundColor: const Color(0xFF10B981),
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                  ),
                  onPressed: isSubmitting
                      ? null
                      : () async {
                          if (!formKey.currentState!.validate()) return;
                          setDialogState(() {
                            isSubmitting = true;
                            errorMessage = null;
                          });
                          try {
                            final res = await ApiService.changeEmployeePassword(
                              token: token,
                              currentPassword: hasPassword ? currentPasswordController.text.trim() : null,
                              newPassword: newPasswordController.text.trim(),
                              confirmPassword: confirmPasswordController.text.trim(),
                            );
                            if (mounted) {
                              Navigator.of(ctx).pop();
                              ScaffoldMessenger.of(context).showSnackBar(
                                SnackBar(
                                  content: Text(res['message'] ?? 'Password updated successfully!'),
                                  backgroundColor: const Color(0xFF10B981),
                                ),
                              );
                            }
                          } catch (e) {
                            setDialogState(() {
                              isSubmitting = false;
                              errorMessage = ErrorFormatter.format(e);
                            });
                          }
                        },
                  child: isSubmitting
                      ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(color: Colors.white, strokeWidth: 2))
                      : const Text('Save Password', style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
                ),
              ],
            );
          },
        );
      },
    );
  }

  /// Initiates the punch flow: displays the live front-camera modal for facial & geofence verification
  void _handlePunchAction() {
    final attProvider = context.read<AttendanceProvider>();
    final isCheckedIn = attProvider.currentPunchStatus == 'CHECKED_IN';
    final action = isCheckedIn ? 'CHECK_OUT' : 'CHECK_IN';

    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (ctx) => _PunchCameraModal(
        punchAction: action,
        onPunchSuccess: () async {
          final authProvider = context.read<AuthProvider>();
          final token = authProvider.currentUser?.token;
          if (token != null) {
            await attProvider.loadHistory(token: token, rollNumber: authProvider.currentUser?.rollNumber);
            _loadPayrollData();
          }
        },
      ),
    );
  }

  void _showApplyLeaveModal() {
    final formKey = GlobalKey<FormState>();
    int? selectedTypeId = _leaveBalances.isNotEmpty ? _leaveBalances.first['leave_type_id'] : null;
    final reasonController = TextEditingController();
    DateTime startDate = DateTime.now();
    DateTime endDate = DateTime.now();
    bool isHalfDay = false;
    String halfDayPeriod = "FIRST_HALF";
    bool isSubmitting = false;

    final isDark = Theme.of(context).brightness == Brightness.dark;

    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: isDark ? const Color(0xFF161B22) : Colors.white,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (ctx) {
        return StatefulBuilder(
          builder: (context, setModalState) {
            final days = (endDate.difference(startDate).inDays + 1);
            final double computedDays = (isHalfDay && days == 1) ? 0.5 : days.toDouble();

            return Padding(
              padding: EdgeInsets.only(
                left: 20,
                right: 20,
                top: 20,
                bottom: MediaQuery.of(ctx).viewInsets.bottom + 20,
              ),
              child: Form(
                key: formKey,
                child: SingleChildScrollView(
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Text('Apply for Leave', style: TextStyle(color: isDark ? Colors.white : const Color(0xFF0F172A), fontSize: 18, fontWeight: FontWeight.bold)),
                          IconButton(
                            icon: Icon(Icons.close_rounded, color: isDark ? Colors.white54 : const Color(0xFF64748B), size: 20),
                            onPressed: () => Navigator.pop(ctx),
                          ),
                        ],
                      ),
                      const SizedBox(height: 14),

                      // Leave Category
                      DropdownButtonFormField<int>(
                        dropdownColor: isDark ? const Color(0xFF0D1117) : Colors.white,
                        style: TextStyle(color: isDark ? Colors.white : const Color(0xFF0F172A), fontSize: 13),
                        decoration: InputDecoration(
                          labelText: 'Leave Category',
                          labelStyle: TextStyle(color: isDark ? Colors.white.withOpacity(0.6) : const Color(0xFF64748B), fontSize: 12),
                          filled: true,
                          fillColor: isDark ? const Color(0xFF0D1117) : const Color(0xFFF1F5F9),
                          border: OutlineInputBorder(borderRadius: BorderRadius.circular(10), borderSide: BorderSide(color: isDark ? const Color(0xFF30363D) : const Color(0xFFCBD5E1))),
                          enabledBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(10), borderSide: BorderSide(color: isDark ? const Color(0xFF30363D) : const Color(0xFFCBD5E1))),
                        ),
                        value: selectedTypeId,
                        items: _leaveBalances.map<DropdownMenuItem<int>>((b) {
                          return DropdownMenuItem<int>(
                            value: b['leave_type_id'],
                            child: Text('${b['leave_type_name']} (${b['remaining_days']}d available)'),
                          );
                        }).toList(),
                        onChanged: (val) => setModalState(() => selectedTypeId = val),
                        validator: (v) => v == null ? 'Please select category' : null,
                      ),
                      const SizedBox(height: 12),

                      // Date Pickers Row
                      Row(
                        children: [
                          Expanded(
                            child: InkWell(
                              onTap: () async {
                                final d = await showDatePicker(
                                  context: context,
                                  initialDate: startDate,
                                  firstDate: DateTime.now().subtract(const Duration(days: 30)),
                                  lastDate: DateTime.now().add(const Duration(days: 365)),
                                );
                                if (d != null) {
                                  setModalState(() {
                                    startDate = d;
                                    if (endDate.isBefore(startDate)) endDate = startDate;
                                  });
                                }
                              },
                              child: InputDecorator(
                                decoration: InputDecoration(
                                  labelText: 'Start Date',
                                  labelStyle: TextStyle(color: isDark ? Colors.white.withOpacity(0.6) : const Color(0xFF64748B), fontSize: 12),
                                  filled: true,
                                  fillColor: isDark ? const Color(0xFF0D1117) : const Color(0xFFF1F5F9),
                                  border: OutlineInputBorder(borderRadius: BorderRadius.circular(10), borderSide: BorderSide(color: isDark ? const Color(0xFF30363D) : const Color(0xFFCBD5E1))),
                                  enabledBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(10), borderSide: BorderSide(color: isDark ? const Color(0xFF30363D) : const Color(0xFFCBD5E1))),
                                ),
                                child: Text(
                                  DateFormat('yyyy-MM-dd').format(startDate),
                                  style: TextStyle(color: isDark ? Colors.white : const Color(0xFF0F172A), fontSize: 13),
                                ),
                              ),
                            ),
                          ),
                          const SizedBox(width: 10),
                          Expanded(
                            child: InkWell(
                              onTap: () async {
                                final d = await showDatePicker(
                                  context: context,
                                  initialDate: endDate.isBefore(startDate) ? startDate : endDate,
                                  firstDate: startDate,
                                  lastDate: DateTime.now().add(const Duration(days: 365)),
                                );
                                if (d != null) {
                                  setModalState(() => endDate = d);
                                }
                              },
                              child: InputDecorator(
                                decoration: InputDecoration(
                                  labelText: 'End Date',
                                  labelStyle: TextStyle(color: isDark ? Colors.white.withOpacity(0.6) : const Color(0xFF64748B), fontSize: 12),
                                  filled: true,
                                  fillColor: isDark ? const Color(0xFF0D1117) : const Color(0xFFF1F5F9),
                                  border: OutlineInputBorder(borderRadius: BorderRadius.circular(10), borderSide: BorderSide(color: isDark ? const Color(0xFF30363D) : const Color(0xFFCBD5E1))),
                                  enabledBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(10), borderSide: BorderSide(color: isDark ? const Color(0xFF30363D) : const Color(0xFFCBD5E1))),
                                ),
                                child: Text(
                                  DateFormat('yyyy-MM-dd').format(endDate),
                                  style: TextStyle(color: isDark ? Colors.white : const Color(0xFF0F172A), fontSize: 13),
                                ),
                              ),
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 12),

                      // Half Day Toggle
                      SwitchListTile(
                        contentPadding: EdgeInsets.zero,
                        title: Text('Half-Day Leave', style: TextStyle(color: isDark ? Colors.white : const Color(0xFF0F172A), fontSize: 13, fontWeight: FontWeight.w600)),
                        subtitle: Text(
                          isHalfDay ? 'Applicable for single day leave only (0.5 day deduction)' : 'Full day leave allocation',
                          style: TextStyle(color: isDark ? Colors.white.withOpacity(0.5) : const Color(0xFF64748B), fontSize: 11),
                        ),
                        value: isHalfDay,
                        activeColor: const Color(0xFF6366F1),
                        onChanged: (val) {
                          setModalState(() {
                            isHalfDay = val;
                            if (val) endDate = startDate; // enforce 1 day
                          });
                        },
                      ),

                      // Half Day Session Dropdown
                      if (isHalfDay) ...[
                        const SizedBox(height: 6),
                        DropdownButtonFormField<String>(
                          dropdownColor: isDark ? const Color(0xFF0D1117) : Colors.white,
                          style: TextStyle(color: isDark ? Colors.white : const Color(0xFF0F172A), fontSize: 13),
                          decoration: InputDecoration(
                            labelText: 'Half-Day Session',
                            labelStyle: TextStyle(color: isDark ? Colors.white.withOpacity(0.6) : const Color(0xFF64748B), fontSize: 12),
                            filled: true,
                            fillColor: isDark ? const Color(0xFF0D1117) : const Color(0xFFF1F5F9),
                            border: OutlineInputBorder(borderRadius: BorderRadius.circular(10), borderSide: BorderSide(color: isDark ? const Color(0xFF30363D) : const Color(0xFFCBD5E1))),
                            enabledBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(10), borderSide: BorderSide(color: isDark ? const Color(0xFF30363D) : const Color(0xFFCBD5E1))),
                          ),
                          value: halfDayPeriod,
                          items: const [
                            DropdownMenuItem(value: 'FIRST_HALF', child: Text('First Half (Morning Shift)')),
                            DropdownMenuItem(value: 'SECOND_HALF', child: Text('Second Half (Afternoon Shift)')),
                          ],
                          onChanged: (val) => setModalState(() => halfDayPeriod = val ?? 'FIRST_HALF'),
                        ),
                      ],
                      const SizedBox(height: 12),

                      // Duration Badge
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                        decoration: BoxDecoration(
                          color: const Color(0xFF6366F1).withOpacity(0.12),
                          borderRadius: BorderRadius.circular(8),
                          border: Border.all(color: const Color(0xFF6366F1).withOpacity(0.3)),
                        ),
                        child: Row(
                          children: [
                            const Icon(Icons.info_outline_rounded, color: Color(0xFF818CF8), size: 16),
                            const SizedBox(width: 8),
                            Text(
                              'Total Duration: $computedDays day(s)',
                              style: const TextStyle(color: Color(0xFF818CF8), fontSize: 12, fontWeight: FontWeight.bold),
                            ),
                          ],
                        ),
                      ),
                      const SizedBox(height: 12),

                      // Reason Field
                      TextFormField(
                        controller: reasonController,
                        style: TextStyle(color: isDark ? Colors.white : const Color(0xFF0F172A), fontSize: 13),
                        maxLines: 2,
                        decoration: InputDecoration(
                          labelText: 'Reason for Leave',
                          labelStyle: TextStyle(color: isDark ? Colors.white.withOpacity(0.6) : const Color(0xFF64748B), fontSize: 12),
                          filled: true,
                          fillColor: isDark ? const Color(0xFF0D1117) : const Color(0xFFF1F5F9),
                          border: OutlineInputBorder(borderRadius: BorderRadius.circular(10), borderSide: BorderSide(color: isDark ? const Color(0xFF30363D) : const Color(0xFFCBD5E1))),
                          enabledBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(10), borderSide: BorderSide(color: isDark ? const Color(0xFF30363D) : const Color(0xFFCBD5E1))),
                        ),
                        validator: (v) => (v == null || v.trim().isEmpty) ? 'Please enter justification' : null,
                      ),
                      const SizedBox(height: 16),

                      // Submit Button
                      SizedBox(
                        width: double.infinity,
                        height: 44,
                        child: ElevatedButton(
                          style: ElevatedButton.styleFrom(
                            backgroundColor: const Color(0xFF6366F1),
                            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                          ),
                          onPressed: isSubmitting
                              ? null
                              : () async {
                                  if (formKey.currentState?.validate() ?? false) {
                                    final token = context.read<AuthProvider>().currentUser?.token;
                                    if (token == null || selectedTypeId == null) return;
                                    setModalState(() => isSubmitting = true);
                                    try {
                                      final fmt = DateFormat('yyyy-MM-dd');
                                      final res = await ApiService.applyEmployeeLeave(
                                        token: token,
                                        leaveTypeId: selectedTypeId!,
                                        startDate: fmt.format(startDate),
                                        endDate: fmt.format(endDate),
                                        reason: reasonController.text.trim(),
                                        isHalfDay: isHalfDay,
                                        halfDayPeriod: isHalfDay ? halfDayPeriod : 'NONE',
                                      );
                                      Navigator.pop(ctx);
                                      ScaffoldMessenger.of(context).showSnackBar(
                                        SnackBar(
                                          content: Text(res['message'] ?? 'Leave application submitted!'),
                                          backgroundColor: const Color(0xFF10B981),
                                        ),
                                      );
                                      _loadLeaveBalances();
                                      _loadLeaveRequests();
                                    } catch (e) {
                                      setModalState(() => isSubmitting = false);
                                      ScaffoldMessenger.of(context).showSnackBar(
                                        SnackBar(
                                          content: Text(ErrorFormatter.format(e)),
                                          backgroundColor: const Color(0xFFEF4444),
                                        ),
                                      );
                                    }
                                  }
                                },
                          child: isSubmitting
                              ? const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(color: Colors.white, strokeWidth: 2))
                              : const Text('Submit Application', style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            );
          },
        );
      },
    );
  }

  void _showCancelLeaveDialog(int requestId) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: isDark ? const Color(0xFF161B22) : Colors.white,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(14),
          side: BorderSide(color: isDark ? const Color(0xFF30363D) : const Color(0xFFE2E8F0)),
        ),
        title: Text('Cancel Leave Application', style: TextStyle(color: isDark ? Colors.white : const Color(0xFF0F172A), fontSize: 16, fontWeight: FontWeight.bold)),
        content: Text(
          'Are you sure you want to cancel this pending leave application? Your reserved quota will be restored immediately.',
          style: TextStyle(color: isDark ? Colors.white70 : const Color(0xFF475569), fontSize: 13),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: Text('Back', style: TextStyle(color: isDark ? Colors.white54 : const Color(0xFF64748B))),
          ),
          ElevatedButton(
            style: ElevatedButton.styleFrom(
              backgroundColor: const Color(0xFFEF4444),
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
            ),
            onPressed: () async {
              Navigator.pop(ctx);
              final token = context.read<AuthProvider>().currentUser?.token;
              if (token == null) return;
              try {
                final res = await ApiService.cancelEmployeeLeaveRequest(token: token, requestId: requestId);
                ScaffoldMessenger.of(context).showSnackBar(
                  SnackBar(
                    content: Text(res['message'] ?? 'Leave application cancelled.'),
                    backgroundColor: const Color(0xFF10B981),
                  ),
                );
                _loadLeaveBalances();
                _loadLeaveRequests();
              } catch (e) {
                ScaffoldMessenger.of(context).showSnackBar(
                  SnackBar(
                    content: Text(ErrorFormatter.format(e)),
                    backgroundColor: const Color(0xFFEF4444),
                  ),
                );
              }
            },
            child: const Text('Yes, Cancel', style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
          ),
        ],
      ),
    );
  }

  void _handleSwitchOrganization() async {
    final authProvider = context.read<AuthProvider>();
    await authProvider.switchOrganization();
    if (mounted) {
      Navigator.of(context).pushAndRemoveUntil(
        MaterialPageRoute(builder: (_) => const TenantServerSetupScreen()),
        (route) => false,
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final authProvider = context.watch<AuthProvider>();
    final attProvider = context.watch<AttendanceProvider>();
    final user = authProvider.currentUser;
    final isDark = Theme.of(context).brightness == Brightness.dark;

    return Scaffold(
      backgroundColor: isDark ? const Color(0xFF0D1117) : const Color(0xFFF8FAFC),
      appBar: AppBar(
        backgroundColor: isDark ? const Color(0xFF161B22) : Colors.white,
        elevation: 0,
        title: Row(
          children: [
            CircleAvatar(
              radius: 16,
              backgroundColor: const Color(0xFF6366F1),
              child: Text(
                user?.name.isNotEmpty == true ? user!.name[0].toUpperCase() : 'E',
                style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold, fontSize: 13),
              ),
            ),
            const SizedBox(width: 10),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    user?.name ?? 'Employee Hub',
                    style: TextStyle(
                      color: isDark ? Colors.white : const Color(0xFF0F172A),
                      fontSize: 14,
                      fontWeight: FontWeight.w700,
                    ),
                    overflow: TextOverflow.ellipsis,
                  ),
                  Row(
                    children: [
                      Text(
                        user?.rollNumber != null ? 'ID: ${user!.rollNumber}' : 'Workforce',
                        style: TextStyle(
                          color: isDark ? Colors.white54 : const Color(0xFF64748B),
                          fontSize: 11,
                        ),
                      ),
                      if (authProvider.tenantSlug.isNotEmpty) ...[
                        Text(
                          ' • ',
                          style: TextStyle(color: isDark ? Colors.white30 : const Color(0xFF94A3B8), fontSize: 11),
                        ),
                        Flexible(
                          child: Text(
                            authProvider.tenantName,
                            style: TextStyle(
                              color: isDark ? const Color(0xFF818CF8) : const Color(0xFF4F46E5),
                              fontSize: 11,
                              fontWeight: FontWeight.w600,
                            ),
                            overflow: TextOverflow.ellipsis,
                          ),
                        ),
                      ],
                    ],
                  ),
                ],
              ),
            ),
          ],
        ),
        actions: [
          // Theme Switcher 3-Way Action (Light / Dark / System Default)
          Consumer<ThemeProvider>(
            builder: (ctx, themeProv, _) => IconButton(
              icon: Icon(themeProv.themeIcon, color: isDark ? Colors.white70 : const Color(0xFF0F172A), size: 20),
              tooltip: 'Theme: ${themeProv.themeDisplayName}',
              onPressed: () => showThemeSelectionDialog(context),
            ),
          ),
          // Change Password action
          IconButton(
            icon: const Icon(Icons.key_rounded, color: Color(0xFF10B981), size: 20),
            tooltip: 'Change Password',
            onPressed: _showChangePasswordDialog,
          ),
          // Switch Org action
          IconButton(
            icon: const Icon(Icons.business_rounded, color: Color(0xFF818CF8), size: 20),
            tooltip: 'Switch Organization',
            onPressed: _handleSwitchOrganization,
          ),
          IconButton(
            icon: Icon(Icons.logout_rounded, color: isDark ? Colors.white70 : const Color(0xFF64748B), size: 20),
            tooltip: 'Sign Out',
            onPressed: () {
              authProvider.logout();
              Navigator.of(context).pushReplacement(
                MaterialPageRoute(builder: (_) => const FaceLoginScreen()),
              );
            },
          ),
        ],
      ),
      body: SafeArea(
        child: IndexedStack(
          index: _currentTabIndex,
          children: [
            _buildPresenceTab(attProvider),
            _buildTimelineTab(attProvider),
            _buildWagesTab(),
            _buildLeavesTab(),
          ],
        ),
      ),
      bottomNavigationBar: BottomNavigationBar(
        currentIndex: _currentTabIndex,
        onTap: (idx) => setState(() => _currentTabIndex = idx),
        backgroundColor: isDark ? const Color(0xFF161B22) : Colors.white,
        selectedItemColor: const Color(0xFF6366F1),
        unselectedItemColor: isDark ? Colors.white38 : const Color(0xFF94A3B8),
        type: BottomNavigationBarType.fixed,
        selectedFontSize: 11,
        unselectedFontSize: 10,
        items: const [
          BottomNavigationBarItem(icon: Icon(Icons.fingerprint_rounded), label: 'Presence'),
          BottomNavigationBarItem(icon: Icon(Icons.schedule_rounded), label: 'Punches'),
          BottomNavigationBarItem(icon: Icon(Icons.wallet_rounded), label: 'Wages'),
          BottomNavigationBarItem(icon: Icon(Icons.beach_access_rounded), label: 'Leaves'),
        ],
      ),
    );
  }

  // --------------------------------------------------------------------------
  // Tab 1: Presence & Biometric Punch
  // --------------------------------------------------------------------------
  Widget _buildPresenceTab(AttendanceProvider attProvider) {
    final isCheckedIn = attProvider.currentPunchStatus == 'CHECKED_IN';
    final isDark = Theme.of(context).brightness == Brightness.dark;

    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 520),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              // Out of Bounds Alert Banner
              if (attProvider.hasActiveBreach)
                Container(
                  margin: const EdgeInsets.only(bottom: 14),
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: const Color(0xFFEF4444).withOpacity(0.15),
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(color: const Color(0xFFEF4444)),
                  ),
                  child: Row(
                    children: [
                      const Icon(Icons.warning_amber_rounded, color: Color(0xFFEF4444), size: 24),
                      const SizedBox(width: 10),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            const Text('Out-of-Bounds Perimeter Alert', style: TextStyle(color: Color(0xFFEF4444), fontWeight: FontWeight.bold, fontSize: 13)),
                            const SizedBox(height: 2),
                            Text(
                              attProvider.breachAlertMessage ?? 'You are currently outside the authorized campus perimeter. An audit event is being logged.',
                              style: TextStyle(color: isDark ? Colors.white.withOpacity(0.85) : const Color(0xFF7F1D1D), fontSize: 11),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),

              // Radar Gauge Card
              const RadarGaugeCard(),
              const SizedBox(height: 16),

              // Shift Status Card
              Container(
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  color: isDark ? const Color(0xFF161B22) : Colors.white,
                  borderRadius: BorderRadius.circular(16),
                  border: Border.all(color: isDark ? Colors.white.withOpacity(0.08) : const Color(0xFFE2E8F0)),
                ),
                child: Column(
                  children: [
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Text('Today Shift Status', style: TextStyle(color: isDark ? Colors.white70 : const Color(0xFF64748B), fontSize: 13, fontWeight: FontWeight.w600)),
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                          decoration: BoxDecoration(
                            color: isCheckedIn ? const Color(0xFF10B981).withOpacity(0.2) : (isDark ? Colors.white.withOpacity(0.08) : const Color(0xFFF1F5F9)),
                            borderRadius: BorderRadius.circular(12),
                            border: Border.all(color: isCheckedIn ? const Color(0xFF10B981) : (isDark ? Colors.white24 : const Color(0xFFCBD5E1))),
                          ),
                          child: Text(
                            isCheckedIn ? 'ACTIVE (CHECKED IN)' : (attProvider.currentPunchStatus == 'CHECKED_OUT' ? 'COMPLETED' : 'NOT CHECKED IN'),
                            style: TextStyle(
                              color: isCheckedIn ? const Color(0xFF10B981) : (isDark ? Colors.white70 : const Color(0xFF64748B)),
                              fontSize: 11,
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                        ),
                      ],
                    ),
                    Divider(color: isDark ? Colors.white12 : const Color(0xFFE2E8F0), height: 24),
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceAround,
                      children: [
                        _buildStatColumn('Check-In Time', attProvider.lastCheckInShort ?? '--:--', isDark),
                        Container(width: 1, height: 28, color: isDark ? Colors.white12 : const Color(0xFFE2E8F0)),
                        _buildStatColumn('Check-Out Time', attProvider.lastCheckOutShort ?? '--:--', isDark),
                        Container(width: 1, height: 28, color: isDark ? Colors.white12 : const Color(0xFFE2E8F0)),
                        _buildStatColumn('Perimeter Watch', isCheckedIn ? 'Active' : 'Standby', isDark),
                      ],
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 20),

              // Large 1-Tap Geofence Punch Button
              SizedBox(
                height: 54,
                child: ElevatedButton.icon(
                  style: ElevatedButton.styleFrom(
                    backgroundColor: isCheckedIn ? const Color(0xFFEA580C) : const Color(0xFF10B981),
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
                    elevation: 4,
                  ),
                  icon: Icon(isCheckedIn ? Icons.logout_rounded : Icons.login_rounded, color: Colors.white, size: 22),
                  label: Text(
                    isCheckedIn ? 'TAP TO CHECK-OUT' : 'TAP TO CHECK-IN',
                    style: const TextStyle(color: Colors.white, fontSize: 15, fontWeight: FontWeight.w800, letterSpacing: 0.5),
                  ),
                  onPressed: attProvider.checkInStatus == CheckInStatus.submitting ? null : _handlePunchAction,
                ),
              ),

              const SizedBox(height: 10),
              Center(
                child: Text(
                  attProvider.geofenceConfig?.mobileRequireFaceVerification == true
                      ? 'Policy: Live Front-Facing Camera Biometric + Strict GPS Geofence'
                      : 'Policy: Strict GPS Geofence + Live Biometric Face Verification',
                  style: TextStyle(color: isDark ? Colors.white.withOpacity(0.4) : const Color(0xFF94A3B8), fontSize: 11),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildStatColumn(String label, String value, bool isDark) {
    return Column(
      children: [
        Text(label, style: TextStyle(color: isDark ? Colors.white.withOpacity(0.5) : const Color(0xFF64748B), fontSize: 11)),
        const SizedBox(height: 4),
        Text(value, style: TextStyle(color: isDark ? Colors.white : const Color(0xFF0F172A), fontSize: 13, fontWeight: FontWeight.bold)),
      ],
    );
  }

  // --------------------------------------------------------------------------
  // Tab 2: Punches Timeline with Month & Year Filtering
  // --------------------------------------------------------------------------
  Widget _buildTimelineTab(AttendanceProvider attProvider) {
    final records = attProvider.filteredRecords;
    final isLoading = attProvider.isLoadingHistory;
    final isDark = Theme.of(context).brightness == Brightness.dark;

    return Column(
      children: [
        // Year & Month Filter Header
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
          margin: const EdgeInsets.fromLTRB(16, 12, 16, 6),
          decoration: BoxDecoration(
            color: isDark ? const Color(0xFF161B22) : Colors.white,
            borderRadius: BorderRadius.circular(12),
            border: Border.all(color: isDark ? const Color(0xFF30363D) : const Color(0xFFE2E8F0)),
          ),
          child: Row(
            children: [
              const Icon(Icons.filter_list_rounded, color: Color(0xFF818CF8), size: 18),
              const SizedBox(width: 8),
              // Month selector
              Expanded(
                flex: 3,
                child: DropdownButtonHideUnderline(
                  child: DropdownButton<int>(
                    value: _selectedPunchMonth,
                    isDense: true,
                    isExpanded: true,
                    dropdownColor: isDark ? const Color(0xFF161B22) : Colors.white,
                    style: TextStyle(color: isDark ? Colors.white : const Color(0xFF0F172A), fontSize: 13, fontWeight: FontWeight.w600),
                    icon: Icon(Icons.arrow_drop_down, color: isDark ? Colors.white70 : const Color(0xFF64748B), size: 20),
                    items: [
                      const DropdownMenuItem(value: 0, child: Text('All Months', overflow: TextOverflow.ellipsis)),
                      for (int m = 1; m <= 12; m++)
                        DropdownMenuItem(value: m, child: Text(_monthName(m), overflow: TextOverflow.ellipsis)),
                    ],
                    onChanged: (val) {
                      if (val != null) {
                        setState(() => _selectedPunchMonth = val);
                        _reloadAttendancePunches();
                      }
                    },
                  ),
                ),
              ),
              const SizedBox(width: 8),
              // Year selector
              Expanded(
                flex: 2,
                child: DropdownButtonHideUnderline(
                  child: DropdownButton<int>(
                    value: _selectedPunchYear,
                    isDense: true,
                    isExpanded: true,
                    dropdownColor: isDark ? const Color(0xFF161B22) : Colors.white,
                    style: const TextStyle(color: Color(0xFF818CF8), fontSize: 13, fontWeight: FontWeight.bold),
                    icon: Icon(Icons.arrow_drop_down, color: isDark ? Colors.white70 : const Color(0xFF64748B), size: 20),
                    items: [
                      for (int y = DateTime.now().year - 2; y <= DateTime.now().year + 1; y++)
                        DropdownMenuItem(value: y, child: Text('$y')),
                    ],
                    onChanged: (val) {
                      if (val != null) {
                        setState(() => _selectedPunchYear = val);
                        _reloadAttendancePunches();
                      }
                    },
                  ),
                ),
              ),
              const SizedBox(width: 8),
              // Refresh button
              IconButton(
                icon: Icon(Icons.refresh_rounded, color: isDark ? Colors.white70 : const Color(0xFF64748B), size: 19),
                tooltip: 'Refresh Punches',
                padding: EdgeInsets.zero,
                constraints: const BoxConstraints(),
                onPressed: _reloadAttendancePunches,
              ),
            ],
          ),
        ),

        // Punches List or Empty State
        Expanded(
          child: RefreshIndicator(
            onRefresh: _reloadAttendancePunches,
            child: isLoading
                ? const Center(child: CircularProgressIndicator(color: Color(0xFF6366F1)))
                : records.isEmpty
                    ? Center(
                        child: SingleChildScrollView(
                          physics: const AlwaysScrollableScrollPhysics(),
                          child: Column(
                            mainAxisAlignment: MainAxisAlignment.center,
                            children: [
                              Icon(Icons.history_rounded, size: 48, color: isDark ? Colors.white.withOpacity(0.2) : const Color(0xFFCBD5E1)),
                              const SizedBox(height: 12),
                              Text(
                                _selectedPunchMonth == 0
                                    ? 'No attendance punches found for $_selectedPunchYear.'
                                    : 'No punches for ${_monthName(_selectedPunchMonth)} $_selectedPunchYear.',
                                style: TextStyle(color: isDark ? Colors.white.withOpacity(0.6) : const Color(0xFF64748B), fontSize: 13),
                              ),
                              const SizedBox(height: 6),
                              Text(
                                'Punches appear here automatically after check-in/out.',
                                style: TextStyle(color: isDark ? Colors.white.withOpacity(0.35) : const Color(0xFF94A3B8), fontSize: 11),
                              ),
                            ],
                          ),
                        ),
                      )
                    : ListView.builder(
                        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                        itemCount: records.length,
                        itemBuilder: (ctx, idx) {
                          final rec = records[idx];
                          final isCheckOut = rec.punchType == 'CHECK_OUT';
                          final isLate = rec.shiftStatus.toUpperCase().contains('LATE');

                          return Card(
                            color: isDark ? const Color(0xFF161B22) : Colors.white,
                            elevation: isDark ? 1 : 0,
                            margin: const EdgeInsets.only(bottom: 10),
                            shape: RoundedRectangleBorder(
                              borderRadius: BorderRadius.circular(12),
                              side: BorderSide(
                                color: isDark
                                    ? (isCheckOut ? const Color(0xFFEA580C).withOpacity(0.3) : const Color(0xFF10B981).withOpacity(0.3))
                                    : const Color(0xFFE2E8F0),
                              ),
                            ),
                            child: Padding(
                              padding: const EdgeInsets.all(12),
                              child: Row(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  CircleAvatar(
                                    radius: 18,
                                    backgroundColor: isCheckOut
                                        ? const Color(0xFFEA580C).withOpacity(0.18)
                                        : const Color(0xFF10B981).withOpacity(0.18),
                                    child: Icon(
                                      isCheckOut ? Icons.logout_rounded : Icons.login_rounded,
                                      color: isCheckOut ? const Color(0xFFEA580C) : const Color(0xFF10B981),
                                      size: 19,
                                    ),
                                  ),
                                  const SizedBox(width: 12),
                                  Expanded(
                                    child: Column(
                                      crossAxisAlignment: CrossAxisAlignment.start,
                                      children: [
                                        Row(
                                          children: [
                                            Text(
                                              isCheckOut ? 'CHECK OUT' : 'CHECK IN',
                                              style: TextStyle(
                                                color: isCheckOut ? const Color(0xFFFB923C) : const Color(0xFF10B981),
                                                fontWeight: FontWeight.bold,
                                                fontSize: 13,
                                                letterSpacing: 0.5,
                                              ),
                                            ),
                                            const SizedBox(width: 8),
                                            Flexible(
                                              child: Container(
                                                padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                                                decoration: BoxDecoration(
                                                  color: isLate
                                                      ? const Color(0xFFEF4444).withOpacity(0.2)
                                                      : const Color(0xFF10B981).withOpacity(0.15),
                                                  borderRadius: BorderRadius.circular(4),
                                                ),
                                                child: Text(
                                                  rec.shiftStatus,
                                                  style: TextStyle(
                                                    color: isLate ? const Color(0xFFEF4444) : const Color(0xFF10B981),
                                                    fontSize: 10,
                                                    fontWeight: FontWeight.w600,
                                                  ),
                                                  overflow: TextOverflow.ellipsis,
                                                ),
                                              ),
                                            ),
                                            const SizedBox(width: 6),
                                            if (rec.workDurationFormatted != '--')
                                              Container(
                                                padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 2),
                                                decoration: BoxDecoration(
                                                  color: const Color(0xFF6366F1).withOpacity(0.15),
                                                  borderRadius: BorderRadius.circular(6),
                                                ),
                                                child: Text(
                                                  rec.workDurationFormatted,
                                                  style: const TextStyle(
                                                    color: Color(0xFF6366F1),
                                                    fontWeight: FontWeight.bold,
                                                    fontSize: 11,
                                                  ),
                                                ),
                                              ),
                                          ],
                                        ),
                                        const SizedBox(height: 6),
                                        Text(
                                          rec.timestamp,
                                          style: TextStyle(color: isDark ? Colors.white : const Color(0xFF0F172A), fontSize: 12, fontWeight: FontWeight.w500),
                                        ),
                                        const SizedBox(height: 4),
                                        Row(
                                          children: [
                                            Icon(
                                              rec.geoLatitude != null ? Icons.location_on_rounded : Icons.devices_rounded,
                                              size: 13,
                                              color: isDark ? Colors.white38 : const Color(0xFF94A3B8),
                                            ),
                                            const SizedBox(width: 4),
                                            Expanded(
                                              child: Text(
                                                rec.geoDistanceMeters != null
                                                    ? 'Geofence (${rec.geoDistanceMeters!.round()}m) • Node: ${rec.nodeId}'
                                                    : 'Node: ${rec.nodeId}',
                                                style: TextStyle(color: isDark ? Colors.white.withOpacity(0.4) : const Color(0xFF64748B), fontSize: 11),
                                                overflow: TextOverflow.ellipsis,
                                              ),
                                            ),
                                          ],
                                        ),
                                      ],
                                    ),
                                  ),
                                ],
                              ),
                            ),
                          );
                        },
                      ),
          ),
        ),
      ],
    );
  }

  // --------------------------------------------------------------------------
  // Tab 3: Wages, Structured CTC & Payslips
  // --------------------------------------------------------------------------
  Widget _buildWagesTab() {
    if (_isLoadingWages && _isLoadingCompensation && _isLoadingPayslips) {
      return const Center(child: CircularProgressIndicator(color: Color(0xFF6366F1)));
    }

    final isDark = Theme.of(context).brightness == Brightness.dark;
    final p = _payrollData ?? {};
    final currency = p['currency_symbol'] ?? '₹';
    final gross = p['gross_earnings'] ?? 0.0;
    final net = p['net_salary'] ?? p['estimated_net'] ?? gross;
    final punchHours = p['total_punch_hours'] ?? 0.0;
    final otHours = p['overtime_hours'] ?? 0.0;
    final daysCount = p['active_days_count'] ?? 0;
    final model = p['compensation_model'] ?? 'STRUCTURED_SALARY';

    final comp = _compensationData ?? {};
    final structure = comp['structure'] as Map<String, dynamic>? ?? {};
    final employeeInfo = comp['employee'] as Map<String, dynamic>? ?? {};

    return RefreshIndicator(
      onRefresh: () async {
        await Future.wait([
          _loadPayrollData(),
          _loadCompensationData(),
          _loadPayslips(),
        ]);
      },
      child: SingleChildScrollView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.all(16),
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 520),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                // Top Estimated Earnings Card
                Container(
                  padding: const EdgeInsets.all(20),
                  decoration: BoxDecoration(
                    gradient: const LinearGradient(colors: [Color(0xFF4F46E5), Color(0xFF7C3AED)]),
                    borderRadius: BorderRadius.circular(16),
                    boxShadow: [
                      BoxShadow(color: const Color(0xFF4F46E5).withOpacity(0.3), blurRadius: 12, offset: const Offset(0, 4)),
                    ],
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Text('ESTIMATED EARNINGS (THIS MONTH)', style: TextStyle(color: Colors.white.withOpacity(0.8), fontSize: 11, fontWeight: FontWeight.bold, letterSpacing: 0.5)),
                          Container(
                            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                            decoration: BoxDecoration(
                              color: Colors.white24,
                              borderRadius: BorderRadius.circular(6),
                            ),
                            child: Text(
                              model.replaceAll('_', ' '),
                              style: const TextStyle(color: Colors.white, fontSize: 10, fontWeight: FontWeight.bold),
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 8),
                      Text('$currency$net', style: const TextStyle(color: Colors.white, fontSize: 30, fontWeight: FontWeight.w900)),
                      const SizedBox(height: 4),
                      Text('Gross Earnings: $currency$gross • $daysCount active shift days', style: TextStyle(color: Colors.white.withOpacity(0.85), fontSize: 12)),
                    ],
                  ),
                ),
                const SizedBox(height: 14),

                // Metrics Row (Punch Hours & Overtime)
                Row(
                  children: [
                    Expanded(child: _buildMetricCard('Shift Hours', '$punchHours hrs', Icons.timelapse_rounded, const Color(0xFF38BDF8), isDark)),
                    const SizedBox(width: 12),
                    Expanded(child: _buildMetricCard('Overtime Hours', '$otHours hrs', Icons.more_time_rounded, const Color(0xFFF59E0B), isDark)),
                  ],
                ),
                const SizedBox(height: 20),

                // Active Compensation Structure Card
                Container(
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(
                    color: isDark ? const Color(0xFF161B22) : Colors.white,
                    borderRadius: BorderRadius.circular(14),
                    border: Border.all(color: isDark ? Colors.white.withOpacity(0.08) : const Color(0xFFE2E8F0)),
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          const Icon(Icons.account_balance_wallet_rounded, color: Color(0xFF6366F1), size: 18),
                          const SizedBox(width: 8),
                          Text('Active Compensation & CTC Structure', style: TextStyle(color: isDark ? Colors.white : const Color(0xFF0F172A), fontSize: 14, fontWeight: FontWeight.bold)),
                        ],
                      ),
                      Divider(color: isDark ? Colors.white12 : const Color(0xFFE2E8F0), height: 20),
                      if (structure.isNotEmpty) ...[
                        _buildCompRow('Compensation Model', structure['compensation_model']?.toString().replaceAll('_', ' ') ?? model, isDark: isDark),
                        if (structure['hourly_rate'] != null && (structure['hourly_rate'] as num) > 0)
                          _buildCompRow('Standard Hourly Rate', '$currency${structure['hourly_rate']} / hr', isDark: isDark),
                        if (structure['monthly_gross'] != null)
                          _buildCompRow('Monthly Gross Pay', '$currency${structure['monthly_gross']}', isDark: isDark),
                        if (structure['annual_ctc'] != null)
                          _buildCompRow('Annual CTC', '$currency${structure['annual_ctc']}', isDark: isDark),
                        if (structure['basic_salary'] != null && (structure['basic_salary'] as num) > 0)
                          _buildCompRow('Basic Salary', '$currency${structure['basic_salary']}', isDark: isDark),
                        if (structure['hra'] != null && (structure['hra'] as num) > 0)
                          _buildCompRow('House Rent Allowance (HRA)', '$currency${structure['hra']}', isDark: isDark),
                        if (structure['special_allowance'] != null && (structure['special_allowance'] as num) > 0)
                          _buildCompRow('Special Allowance', '$currency${structure['special_allowance']}', isDark: isDark),
                        if (structure['epf_employee'] != null && (structure['epf_employee'] as num) > 0)
                          _buildCompRow('Provident Fund (EPF)', '- $currency${structure['epf_employee']}', isDeduction: true, isDark: isDark),
                        if (structure['esi_employee'] != null && (structure['esi_employee'] as num) > 0)
                          _buildCompRow('ESI Contribution', '- $currency${structure['esi_employee']}', isDeduction: true, isDark: isDark),
                        if (structure['professional_tax'] != null && (structure['professional_tax'] as num) > 0)
                          _buildCompRow('Professional Tax (PT)', '- $currency${structure['professional_tax']}', isDeduction: true, isDark: isDark),
                      ] else ...[
                        Text('Compensation configured at standard base tier.', style: TextStyle(color: isDark ? Colors.white.withOpacity(0.6) : const Color(0xFF64748B), fontSize: 12)),
                      ],

                      // Statutory & Bank Details
                      if (employeeInfo['pan_number']?.toString().isNotEmpty == true || employeeInfo['bank_account_number']?.toString().isNotEmpty == true) ...[
                        Divider(color: isDark ? Colors.white12 : const Color(0xFFE2E8F0), height: 20),
                        if (employeeInfo['pan_number']?.toString().isNotEmpty == true)
                          _buildCompRow('PAN Number', employeeInfo['pan_number'], isDark: isDark),
                        if (employeeInfo['uan_number']?.toString().isNotEmpty == true)
                          _buildCompRow('PF UAN Number', employeeInfo['uan_number'], isDark: isDark),
                        if (employeeInfo['bank_name']?.toString().isNotEmpty == true)
                          _buildCompRow('Bank Name', employeeInfo['bank_name'], isDark: isDark),
                        if (employeeInfo['bank_account_number']?.toString().isNotEmpty == true)
                          _buildCompRow('Bank Account', employeeInfo['bank_account_number'], isDark: isDark),
                      ],
                    ],
                  ),
                ),
                const SizedBox(height: 20),

                // Itemized Payslips History Header
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Text('Monthly Payslips', style: TextStyle(color: isDark ? Colors.white : const Color(0xFF0F172A), fontSize: 15, fontWeight: FontWeight.bold)),
                    Text('${_payslips.length} published', style: TextStyle(color: isDark ? Colors.white.withOpacity(0.5) : const Color(0xFF64748B), fontSize: 12)),
                  ],
                ),
                const SizedBox(height: 10),

                if (_payslips.isEmpty)
                  Container(
                    padding: const EdgeInsets.all(20),
                    decoration: BoxDecoration(
                      color: isDark ? const Color(0xFF161B22) : Colors.white,
                      borderRadius: BorderRadius.circular(12),
                      border: isDark ? null : Border.all(color: const Color(0xFFE2E8F0)),
                    ),
                    child: Center(
                      child: Text(
                        'No published payslips found for this year.',
                        style: TextStyle(color: isDark ? Colors.white.withOpacity(0.5) : const Color(0xFF64748B), fontSize: 12),
                      ),
                    ),
                  )
                else
                  ..._payslips.map<Widget>((slip) {
                    final monthName = _getMonthName(slip['period_month']);
                    final year = slip['period_year'];
                    final sGross = slip['gross_earnings'] ?? 0.0;
                    final sNet = slip['net_salary'] ?? 0.0;
                    final sDays = slip['total_working_days'] ?? slip['present_days'] ?? 0;

                    return Card(
                      color: isDark ? const Color(0xFF161B22) : Colors.white,
                      elevation: isDark ? 1 : 0,
                      margin: const EdgeInsets.only(bottom: 10),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(12),
                        side: BorderSide(color: isDark ? const Color(0xFF30363D) : const Color(0xFFE2E8F0)),
                      ),
                      child: ListTile(
                        leading: Container(
                          padding: const EdgeInsets.all(10),
                          decoration: BoxDecoration(
                            color: const Color(0xFF6366F1).withOpacity(0.15),
                            borderRadius: BorderRadius.circular(8),
                          ),
                          child: const Icon(Icons.receipt_long_rounded, color: Color(0xFF818CF8), size: 20),
                        ),
                        title: Text('$monthName $year', style: TextStyle(color: isDark ? Colors.white : const Color(0xFF0F172A), fontWeight: FontWeight.bold, fontSize: 13)),
                        subtitle: Text('$sDays days • Gross: $currency$sGross', style: TextStyle(color: isDark ? Colors.white.withOpacity(0.5) : const Color(0xFF64748B), fontSize: 11)),
                        trailing: Column(
                          mainAxisAlignment: MainAxisAlignment.center,
                          crossAxisAlignment: CrossAxisAlignment.end,
                          children: [
                            Text('$currency$sNet', style: const TextStyle(color: Color(0xFF10B981), fontWeight: FontWeight.bold, fontSize: 14)),
                            Text('Net Salary', style: TextStyle(color: isDark ? Colors.white.withOpacity(0.4) : const Color(0xFF64748B), fontSize: 10)),
                          ],
                        ),
                      ),
                    );
                  }).toList(),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildCompRow(String label, String value, {bool isDeduction = false, bool isDark = true}) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(label, style: TextStyle(color: isDark ? Colors.white.withOpacity(0.6) : const Color(0xFF64748B), fontSize: 12)),
          Text(
            value,
            style: TextStyle(
              color: isDeduction ? const Color(0xFFEF4444) : (isDark ? Colors.white : const Color(0xFF0F172A)),
              fontSize: 12,
              fontWeight: FontWeight.w600,
            ),
          ),
        ],
      ),
    );
  }

  String _getMonthName(dynamic month) {
    if (month == null) return 'Month';
    const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    final m = int.tryParse(month.toString()) ?? 1;
    if (m >= 1 && m <= 12) return months[m - 1];
    return 'Month';
  }

  Widget _buildMetricCard(String title, String val, IconData icon, Color color, bool isDark) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: isDark ? const Color(0xFF161B22) : Colors.white,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: isDark ? Colors.white.withOpacity(0.08) : const Color(0xFFE2E8F0)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, color: color, size: 20),
          const SizedBox(height: 10),
          Text(val, style: TextStyle(color: isDark ? Colors.white : const Color(0xFF0F172A), fontSize: 18, fontWeight: FontWeight.bold)),
          const SizedBox(height: 2),
          Text(title, style: TextStyle(color: isDark ? Colors.white.withOpacity(0.5) : const Color(0xFF64748B), fontSize: 11)),
        ],
      ),
    );
  }

  // --------------------------------------------------------------------------
  // Tab 4: Leaves (Quotas & Application History)
  // --------------------------------------------------------------------------
  Widget _buildLeavesTab() {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    return Scaffold(
      backgroundColor: Colors.transparent,
      floatingActionButton: FloatingActionButton.extended(
        backgroundColor: const Color(0xFF6366F1),
        icon: const Icon(Icons.add_rounded, color: Colors.white),
        label: const Text('Apply Leave', style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
        onPressed: _showApplyLeaveModal,
      ),
      body: Column(
        children: [
          // Segmented sub-tab control (Quotas vs Applications)
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 12, 16, 8),
            child: Row(
              children: [
                Expanded(
                  child: InkWell(
                    onTap: () => setState(() => _leavesSubTabIndex = 0),
                    child: Container(
                      padding: const EdgeInsets.symmetric(vertical: 8),
                      decoration: BoxDecoration(
                        color: _leavesSubTabIndex == 0 ? const Color(0xFF6366F1) : (isDark ? const Color(0xFF161B22) : const Color(0xFFE2E8F0)),
                        borderRadius: BorderRadius.circular(8),
                      ),
                      alignment: Alignment.center,
                      child: Text(
                        'Leave Quotas (${_leaveBalances.length})',
                        style: TextStyle(
                          color: _leavesSubTabIndex == 0 ? Colors.white : (isDark ? Colors.white70 : const Color(0xFF64748B)),
                          fontSize: 12,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                    ),
                  ),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: InkWell(
                    onTap: () => setState(() => _leavesSubTabIndex = 1),
                    child: Container(
                      padding: const EdgeInsets.symmetric(vertical: 8),
                      decoration: BoxDecoration(
                        color: _leavesSubTabIndex == 1 ? const Color(0xFF6366F1) : (isDark ? const Color(0xFF161B22) : const Color(0xFFE2E8F0)),
                        borderRadius: BorderRadius.circular(8),
                      ),
                      alignment: Alignment.center,
                      child: Text(
                        'My Applications (${_leaveRequests.length})',
                        style: TextStyle(
                          color: _leavesSubTabIndex == 1 ? Colors.white : (isDark ? Colors.white70 : const Color(0xFF64748B)),
                          fontSize: 12,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                    ),
                  ),
                ),
              ],
            ),
          ),

          // Sub-Tab Content
          Expanded(
            child: RefreshIndicator(
              onRefresh: () async {
                await Future.wait([
                  _loadLeaveBalances(),
                  _loadLeaveRequests(),
                ]);
              },
              child: _leavesSubTabIndex == 0 ? _buildLeaveQuotasView(isDark) : _buildLeaveRequestsView(isDark),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildLeaveQuotasView(bool isDark) {
    if (_isLoadingLeaves) {
      return const Center(child: CircularProgressIndicator(color: Color(0xFF6366F1)));
    }

    if (_leaveBalances.isEmpty) {
      return Center(
        child: Text('No leave quotas configured for current year.', style: TextStyle(color: isDark ? Colors.white.withOpacity(0.5) : const Color(0xFF64748B))),
      );
    }

    return ListView.builder(
      padding: const EdgeInsets.all(16),
      itemCount: _leaveBalances.length,
      itemBuilder: (ctx, idx) {
        final b = _leaveBalances[idx];
        final name = b['leave_type_name'] ?? 'Leave';
        final remaining = b['remaining_days'] ?? 0.0;
        final total = b['total_allocated'] ?? 0.0;
        final used = b['used_days'] ?? 0.0;
        final pending = b['pending_days'] ?? 0.0;

        return Card(
          color: isDark ? const Color(0xFF161B22) : Colors.white,
          elevation: isDark ? 1 : 0,
          margin: const EdgeInsets.only(bottom: 12),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(12),
            side: BorderSide(color: isDark ? const Color(0xFF30363D) : const Color(0xFFE2E8F0)),
          ),
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Text(name, style: TextStyle(color: isDark ? Colors.white : const Color(0xFF0F172A), fontWeight: FontWeight.bold, fontSize: 14)),
                    Text('$remaining days left', style: const TextStyle(color: Color(0xFF10B981), fontWeight: FontWeight.bold, fontSize: 13)),
                  ],
                ),
                const SizedBox(height: 10),
                LinearProgressIndicator(
                  value: total > 0 ? (used / total).clamp(0.0, 1.0) : 0.0,
                  backgroundColor: isDark ? Colors.white10 : const Color(0xFFE2E8F0),
                  color: const Color(0xFF6366F1),
                  minHeight: 6,
                  borderRadius: BorderRadius.circular(3),
                ),
                const SizedBox(height: 8),
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Text('Allocated: ${total}d', style: TextStyle(color: isDark ? Colors.white.withOpacity(0.5) : const Color(0xFF64748B), fontSize: 11)),
                    Text('Used: ${used}d', style: TextStyle(color: isDark ? Colors.white.withOpacity(0.5) : const Color(0xFF64748B), fontSize: 11)),
                    if (pending > 0)
                      Text('Pending: ${pending}d', style: const TextStyle(color: Color(0xFFF59E0B), fontSize: 11, fontWeight: FontWeight.bold)),
                  ],
                ),
              ],
            ),
          ),
        );
      },
    );
  }

  Widget _buildLeaveRequestsView(bool isDark) {
    if (_isLoadingRequests) {
      return const Center(child: CircularProgressIndicator(color: Color(0xFF6366F1)));
    }

    if (_leaveRequests.isEmpty) {
      return Center(
        child: Text('No leave applications submitted yet.', style: TextStyle(color: isDark ? Colors.white.withOpacity(0.5) : const Color(0xFF64748B))),
      );
    }

    return ListView.builder(
      padding: const EdgeInsets.all(16),
      itemCount: _leaveRequests.length,
      itemBuilder: (ctx, idx) {
        final req = _leaveRequests[idx];
        final typeName = req['leave_type_name'] ?? 'Leave';
        final startDate = req['start_date'] ?? '';
        final endDate = req['end_date'] ?? '';
        final totalDays = req['total_days'] ?? 1.0;
        final isHalfDay = req['is_half_day'] ?? false;
        final halfDayPeriod = req['half_day_period'] ?? 'NONE';
        final status = (req['status'] ?? 'PENDING').toString().toUpperCase();
        final reason = req['reason'] ?? '';
        final id = req['id'];

        Color statusColor = const Color(0xFFF59E0B);
        if (status == 'APPROVED') statusColor = const Color(0xFF10B981);
        if (status == 'REJECTED') statusColor = const Color(0xFFEF4444);
        if (status == 'CANCELLED') statusColor = isDark ? Colors.white38 : const Color(0xFF94A3B8);

        return Card(
          color: isDark ? const Color(0xFF161B22) : Colors.white,
          elevation: isDark ? 1 : 0,
          margin: const EdgeInsets.only(bottom: 12),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(12),
            side: BorderSide(color: isDark ? const Color(0xFF30363D) : const Color(0xFFE2E8F0)),
          ),
          child: Padding(
            padding: const EdgeInsets.all(14),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Text(typeName, style: TextStyle(color: isDark ? Colors.white : const Color(0xFF0F172A), fontWeight: FontWeight.bold, fontSize: 14)),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                      decoration: BoxDecoration(
                        color: statusColor.withOpacity(0.18),
                        borderRadius: BorderRadius.circular(6),
                        border: Border.all(color: statusColor.withOpacity(0.4)),
                      ),
                      child: Text(
                        status,
                        style: TextStyle(color: statusColor, fontSize: 10, fontWeight: FontWeight.bold),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 6),
                Text(
                  '$startDate to $endDate (${totalDays}d${isHalfDay ? " - ${halfDayPeriod.replaceAll('_', ' ')}" : ""})',
                  style: TextStyle(color: isDark ? const Color(0xFF818CF8) : const Color(0xFF4F46E5), fontSize: 12, fontWeight: FontWeight.w600),
                ),
                const SizedBox(height: 4),
                Text('Reason: $reason', style: TextStyle(color: isDark ? Colors.white.withOpacity(0.7) : const Color(0xFF475569), fontSize: 12)),
                if (status == 'PENDING' && id != null) ...[
                  const SizedBox(height: 10),
                  Align(
                    alignment: Alignment.centerRight,
                    child: OutlinedButton.icon(
                      style: OutlinedButton.styleFrom(
                        foregroundColor: const Color(0xFFEF4444),
                        side: const BorderSide(color: Color(0xFFEF4444), width: 1),
                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                      ),
                      icon: const Icon(Icons.cancel_outlined, size: 14),
                      label: const Text('Cancel Request', style: TextStyle(fontSize: 11, fontWeight: FontWeight.bold)),
                      onPressed: () => _showCancelLeaveDialog(id),
                    ),
                  ),
                ],
              ],
            ),
          ),
        );
      },
    );
  }
}

// ============================================================================
// Live Front-Camera & Geofence Verification Modal for Attendance Punch
// ============================================================================
class _PunchCameraModal extends StatefulWidget {
  final String punchAction; // 'CHECK_IN' or 'CHECK_OUT'
  final VoidCallback onPunchSuccess;

  const _PunchCameraModal({
    Key? key,
    required this.punchAction,
    required this.onPunchSuccess,
  }) : super(key: key);

  @override
  State<_PunchCameraModal> createState() => _PunchCameraModalState();
}

class _PunchCameraModalState extends State<_PunchCameraModal> {
  final CameraWebService _cameraService = CameraWebService();
  bool _isCameraReady = false;
  bool _isSubmitting = false;
  String? _errorMessage;
  int _punchCountdown = 2;
  Timer? _punchCountdownTimer;
  bool _isAutoPunching = false;

  @override
  void initState() {
    super.initState();
    _startCamera();
  }

  Future<void> _startCamera() async {
    try {
      await _cameraService.initialize(useFrontCamera: true);
      if (mounted) {
        setState(() => _isCameraReady = true);
        _maybeStartAutoPunch();
      }
    } catch (e) {
      if (mounted) setState(() => _errorMessage = ErrorFormatter.format(e));
    }
  }

  void _maybeStartAutoPunch() {
    final isInside = context.read<AttendanceProvider>().isInsideGeofence;
    if (!isInside || _isSubmitting || !mounted) return;

    _punchCountdownTimer?.cancel();
    setState(() {
      _punchCountdown = 2;
      _isAutoPunching = true;
    });

    _punchCountdownTimer = Timer.periodic(const Duration(seconds: 1), (timer) {
      if (!mounted) {
        timer.cancel();
        return;
      }
      final insideNow = context.read<AttendanceProvider>().isInsideGeofence;
      if (!insideNow) {
        timer.cancel();
        setState(() => _isAutoPunching = false);
        return;
      }
      if (_punchCountdown > 1) {
        setState(() => _punchCountdown--);
      } else {
        timer.cancel();
        setState(() => _isAutoPunching = false);
        _executePunch();
      }
    });
  }

  @override
  void dispose() {
    _punchCountdownTimer?.cancel();
    _cameraService.dispose();
    super.dispose();
  }

  Future<void> _executePunch() async {
    _punchCountdownTimer?.cancel();
    setState(() => _isAutoPunching = false);
    final authProvider = context.read<AuthProvider>();
    final attProvider = context.read<AttendanceProvider>();
    final token = authProvider.currentUser?.token;
    if (token == null) return;

    setState(() {
      _isSubmitting = true;
      _errorMessage = null;
    });

    try {
      // 1. Capture live frame from front camera
      Uint8List? frameBytes;
      try {
        frameBytes = await _cameraService.captureFrame();
      } catch (e) {
        debugPrint('Frame capture notice: $e');
      }

      // 2. Transmit to backend with forced punch action (CHECK_IN or CHECK_OUT)
      final res = await attProvider.performMobilePunch(
        token: token,
        frameBytes: frameBytes,
        forcedAction: widget.punchAction,
      );

      if (!mounted) return;

      if (res != null) {
        final status = res['status'] ?? 'success';
        if (status == 'success') {
          Navigator.pop(context);
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text(res['message'] ?? '${widget.punchAction == 'CHECK_IN' ? 'Check-in' : 'Check-out'} recorded successfully!'),
              backgroundColor: const Color(0xFF10B981),
            ),
          );
          widget.onPunchSuccess();
        } else if (status == 'cooldown') {
          setState(() {
            _isSubmitting = false;
            _errorMessage = res['message'] ?? 'Cooldown active between punches.';
          });
        } else {
          setState(() {
            _isSubmitting = false;
            _errorMessage = res['message'] ?? 'Punch could not be logged.';
          });
        }
      } else {
        setState(() {
          _isSubmitting = false;
          _errorMessage = attProvider.statusDetail ?? 'Punch registration failed. Check GPS perimeter accuracy.';
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _isSubmitting = false;
          _errorMessage = ErrorFormatter.format(e);
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final attProvider = context.watch<AttendanceProvider>();
    final isCheckIn = widget.punchAction == 'CHECK_IN';
    final isInside = attProvider.isInsideGeofence;
    final isDark = Theme.of(context).brightness == Brightness.dark;

    return Container(
      decoration: BoxDecoration(
        color: isDark ? const Color(0xFF161B22) : Colors.white,
        borderRadius: const BorderRadius.vertical(top: Radius.circular(20)),
      ),
      padding: EdgeInsets.only(
        left: 20,
        right: 20,
        top: 20,
        bottom: MediaQuery.of(context).viewInsets.bottom + 24,
      ),
      child: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            // Header Bar
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Expanded(
                  child: Row(
                    children: [
                      Container(
                        padding: const EdgeInsets.all(8),
                        decoration: BoxDecoration(
                          color: isCheckIn ? const Color(0xFF10B981).withOpacity(0.15) : const Color(0xFFEA580C).withOpacity(0.15),
                          borderRadius: BorderRadius.circular(8),
                        ),
                        child: Icon(
                          isCheckIn ? Icons.login_rounded : Icons.logout_rounded,
                          color: isCheckIn ? const Color(0xFF10B981) : const Color(0xFFEA580C),
                          size: 20,
                        ),
                      ),
                      const SizedBox(width: 10),
                      Expanded(
                        child: Text(
                          isCheckIn ? 'Facial Verification Check-In' : 'Facial Verification Check-Out',
                          style: TextStyle(color: isDark ? Colors.white : const Color(0xFF0F172A), fontSize: 15, fontWeight: FontWeight.bold),
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                    ],
                  ),
                ),
                IconButton(
                  icon: Icon(Icons.close_rounded, color: isDark ? Colors.white54 : const Color(0xFF64748B)),
                  onPressed: () => Navigator.pop(context),
                ),
              ],
            ),
          const SizedBox(height: 12),

          // Geofence Distance Pill
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
            decoration: BoxDecoration(
              color: isInside ? const Color(0xFF10B981).withOpacity(0.15) : const Color(0xFFEF4444).withOpacity(0.15),
              borderRadius: BorderRadius.circular(20),
              border: Border.all(color: isInside ? const Color(0xFF10B981) : const Color(0xFFEF4444)),
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(
                  isInside ? Icons.check_circle_rounded : Icons.warning_rounded,
                  color: isInside ? const Color(0xFF10B981) : const Color(0xFFEF4444),
                  size: 14,
                ),
                const SizedBox(width: 6),
                Text(
                  attProvider.geofenceStatusMessage ?? (isInside ? 'Inside Authorized Campus' : 'Outside Office Perimeter'),
                  style: TextStyle(
                    color: isInside ? const Color(0xFF10B981) : const Color(0xFFEF4444),
                    fontSize: 11,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 14),

          // Embedded Live Front Camera Feed with Oval Reticle
          Container(
            width: double.infinity,
            height: 270,
            decoration: BoxDecoration(
              color: Colors.black,
              borderRadius: BorderRadius.circular(16),
              border: Border.all(color: Colors.white12),
            ),
            clipBehavior: Clip.antiAlias,
            child: Stack(
              alignment: Alignment.center,
              children: [
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
                  Center(
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        const CircularProgressIndicator(color: Color(0xFF6366F1)),
                        const SizedBox(height: 8),
                        Text('Starting front camera feed...', style: TextStyle(color: Colors.white.withOpacity(0.7), fontSize: 12)),
                      ],
                    ),
                  ),

                // Oval face reticle guide
                Container(
                  width: 150,
                  height: 195,
                  decoration: BoxDecoration(
                    borderRadius: BorderRadius.circular(75),
                    border: Border.all(
                      color: isInside
                          ? (_isAutoPunching ? const Color(0xFF10B981) : const Color(0xFF6366F1))
                          : const Color(0xFFEF4444).withOpacity(0.7),
                      width: 2.5,
                    ),
                  ),
                ),

                // Auto-Punch countdown or status badge
                if (_isAutoPunching && !_isSubmitting)
                  Positioned(
                    bottom: 12,
                    child: Container(
                      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
                      decoration: BoxDecoration(
                        color: Colors.black.withOpacity(0.8),
                        borderRadius: BorderRadius.circular(16),
                        border: Border.all(color: const Color(0xFF10B981)),
                      ),
                      child: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          const SizedBox(
                            width: 12,
                            height: 12,
                            child: CircularProgressIndicator(color: Color(0xFF10B981), strokeWidth: 2),
                          ),
                          const SizedBox(width: 8),
                          Text(
                            'Hold still • Auto-stamping punch in $_punchCountdown...',
                            style: const TextStyle(color: Colors.white, fontSize: 11, fontWeight: FontWeight.bold),
                          ),
                        ],
                      ),
                    ),
                  )
                else if (_isSubmitting)
                  Positioned(
                    bottom: 12,
                    child: Container(
                      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
                      decoration: BoxDecoration(
                        color: Colors.black.withOpacity(0.85),
                        borderRadius: BorderRadius.circular(16),
                      ),
                      child: const Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          SizedBox(
                            width: 12,
                            height: 12,
                            child: CircularProgressIndicator(color: Color(0xFF6366F1), strokeWidth: 2),
                          ),
                          SizedBox(width: 8),
                          Text(
                            'Verifying face vectors & geofence...',
                            style: TextStyle(color: Colors.white, fontSize: 11, fontWeight: FontWeight.w600),
                          ),
                        ],
                      ),
                    ),
                  )
                else
                  Positioned(
                    bottom: 10,
                    child: Container(
                      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
                      decoration: BoxDecoration(
                        color: Colors.black.withOpacity(0.7),
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: Text(
                        'Align face inside oval',
                        style: TextStyle(color: Colors.white.withOpacity(0.8), fontSize: 11),
                      ),
                    ),
                  ),
              ],
            ),
          ),

          // Error / Alert Message
          if (_errorMessage != null) ...[
            const SizedBox(height: 12),
            Container(
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(
                color: const Color(0xFFEF4444).withOpacity(0.15),
                borderRadius: BorderRadius.circular(8),
                border: Border.all(color: const Color(0xFFEF4444)),
              ),
              child: Row(
                children: [
                  const Icon(Icons.error_outline_rounded, color: Color(0xFFEF4444), size: 16),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      _errorMessage!,
                      style: const TextStyle(color: Color(0xFFEF4444), fontSize: 12, fontWeight: FontWeight.w600),
                    ),
                  ),
                ],
              ),
            ),
          ],
          const SizedBox(height: 16),

          // Action Buttons
          Row(
            children: [
              Expanded(
                child: SizedBox(
                  height: 46,
                  child: OutlinedButton(
                    style: OutlinedButton.styleFrom(
                      foregroundColor: isDark ? Colors.white70 : const Color(0xFF475569),
                      side: BorderSide(color: isDark ? Colors.white24 : const Color(0xFFCBD5E1)),
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                    ),
                    onPressed: () => Navigator.pop(context),
                    child: const Text('Cancel'),
                  ),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                flex: 2,
                child: SizedBox(
                  height: 46,
                  child: ElevatedButton(
                    style: ElevatedButton.styleFrom(
                      backgroundColor: isCheckIn ? const Color(0xFF10B981) : const Color(0xFFEA580C),
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                    ),
                    onPressed: (_isSubmitting || !isInside) ? null : _executePunch,
                    child: _isSubmitting
                        ? const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(color: Colors.white, strokeWidth: 2))
                        : Text(
                            _isAutoPunching
                                ? 'Punch Now ($_punchCountdown)'
                                : (isCheckIn ? 'Confirm & Check-In' : 'Confirm & Check-Out'),
                            style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold),
                          ),
                  ),
                ),
              ),
            ],
          ),
        ],
      ),
    ),
  );
}
}
