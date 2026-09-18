"""
Test Suites Categorization and Mapping for Attendance System.
Enables fast, targeted, selective test execution across modularized test packages.
"""

SUITES = {
    "payroll": [
        "payroll/test_indian_payroll_system.py",
        "payroll/test_payroll_structure_and_template_mapping.py",
        "payroll/test_designation_and_payroll_workflow.py",
        "payroll/test_corporate_payroll_and_date_ranges.py",
    ],
    "attendance": [
        "attendance/test_corporate_checkin_checkout.py",
        "attendance/test_multi_shift_management.py",
        "attendance/test_smart_override_and_doj.py",
    ],
    "masters": [
        "masters/test_masters_crud_and_salary_templates.py",
        "masters/test_ui_refinements_and_location_fix.py",
        "masters/test_offboarding_and_leave_management.py",
    ],
    "auth": [
        "auth/test_decoupled_auth_portals.py",
        "auth/test_tenant_login_routing.py",
        "auth/test_tokenized_gateways.py",
        "auth/test_tenant_scoped_employee_edit.py",
        "auth/test_tenant_portal_face_login_and_relieve.py",
        "auth/test_employee_auth_and_camera_visibility.py",
    ],
    "ui": [
        "ui/test_corporate_dashboard_layout.py",
        "ui/test_corporate_routes_and_non_camera_logout.py",
        "ui/test_corporate_subheaders_cleanup.py",
        "ui/test_streamlined_navigation_and_core_protection.py",
        "ui/test_settings_universal_employee_portal_link.py",
        "ui/test_employee_portal_tenant_theming.py",
    ],
    "cv": [
        "unit/test_face_detection.py",
    ],
    "unit": [
        "unit/test_face_detection.py",
    ],
    "integration": [
        "integration/test_system.py",
    ],
    "system": [
        "integration/test_system.py",
    ],
}

# Derived compound suites
SUITES["quick"] = (
    SUITES["payroll"]
    + SUITES["attendance"]
    + SUITES["masters"]
    + SUITES["auth"]
    + SUITES["ui"]
    + SUITES["cv"]
)

SUITES["full"] = SUITES["quick"] + SUITES["system"]
SUITES["pre-deploy"] = SUITES["full"]

SUITE_DESCRIPTIONS = {
    "payroll": "Salary templates, EPF/ESIC/PT compliance, wage batches, and payslips (~8-10s)",
    "attendance": "Check-in/out, multi-shift scheduling, night shifts, and manual overrides (~7-9s)",
    "masters": "Company locations, designations, departments, and leave allocations (~5-7s)",
    "auth": "Tenant isolation, magic token gateways, portal login, and user roles (~6-8s)",
    "ui": "Dashboard layout, navigation controls, and static template rendering (~3-5s)",
    "cv": "Computer vision face detection and dlib HOG encodings (~3-5s)",
    "unit": "Fast pure algorithmic and CV unit tests (~3-5s)",
    "integration": "End-to-end multi-tenant integration test suite (~35-45s)",
    "quick": "All fast modular unit and component test suites (~15-20s)",
    "system": "Monolithic end-to-end multi-tenant system integration suite (~35-45s)",
    "full": "Complete 136-test pre-deployment test gate (~70-90s)",
}
