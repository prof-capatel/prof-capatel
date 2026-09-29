# Face Recognition Attendance System — Complete Product & Feature Showcase
### *Enterprise Multi-Tenant AI Biometric Attendance, Statutory Indian Payroll & Workforce Lifecycle Engine*

---

## 🌟 Executive Overview

The **Face Recognition Attendance System** is an enterprise-grade workforce automation and identity verification platform engineered for retail chains, corporate enterprises, multi-campus academic institutions, and manufacturing facilities.

By fusing **zero-hardware 1:N facial recognition**, **dynamic multi-shift scheduling**, **real-time server-sent biometric streaming (SSE)**, **100% compliant Indian statutory payroll (EPF, ESIC, PT, TDS)**, and **mobile-first self-service portals**, the system eliminates buddy punching, automates compliance reporting, and reduces monthly payroll processing time from days to minutes.

```
┌───────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                               FACE ATTENDANCE CLOUD ARCHITECTURE                                      │
├──────────────────────────┬──────────────────────────┬─────────────────────────────────────────────────┤
│ 🏢 Multi-Tenant SaaS     │ 👤 AI Facial Recognition │ 💰 Indian Statutory Payroll                     │
│    White-Label Branding  │    3-Angle Biometric Hub │    Multi-Model Compensation (CTC/Hourly/Daily)  │
├──────────────────────────┼──────────────────────────┼─────────────────────────────────────────────────┤
│ 🏖️ Statutory Time-Off    │ ⏱️ Multi-Shift Engine    │ 📱 Mobile Self-Service &                        │
│    Leave Quota Balances  │    Grace & Half-Day Rule │    GPS Geofence Perimeter Map                   │
└──────────────────────────┴──────────────────────────┴─────────────────────────────────────────────────┘
```

---

## 📸 Visual Walkthrough & Core System Modules

All capabilities documented below are fully verified and cross-referenced with production screenshots from our active corporate tenant walkthrough (`Demo Store` on [curiosityhub.co.in](https://curiosityhub.co.in)).

---

### Module 1: Dedicated Tenant Portal & Unified Authentication

Each registered enterprise or institution receives an isolated, vanity-slug URL (e.g., `/login/demo-store`) that dynamically adapts its branding, color palette, logo, and permitted role selection.

![Tenant Portal Login](file:///d:/Attendance%20System/screenshots/walkthrough/01_login_portal.png)

#### Key Highlights:
- **Tenant-Scoped Vanity Routing:** Custom portal slugs ensure employees and managers land directly in their organization workspace without cross-tenant exposure.
- **Dual Authentication Modes:** 
  - Direct credentials sign-in with role-targeted access (`Tenant Administrator`, `Faculty/Supervisor`, `Employee/Student`).
  - Biometric face scan login with optical alignment guides and shutter confirmation.
- **Branded Security Badges:** Displays dynamic institution title, subtitle, and tier badge (e.g., *Corporate Enterprise Portal - Pro Edition*).
- **Session Tokens & Cookie Hygiene:** Issues secure, encrypted JWT tokens with automatic expiry and browser state preservation.

---

### Module 2: Live Operational Dashboard & Real-Time Biometric HUD

The central command dashboard delivers instant visibility into daily floor activity, workforce availability, shift compliance, and live camera streams.

![Live Dashboard Overview](file:///d:/Attendance%20System/screenshots/walkthrough/02_dashboard_live.png)

#### Key Highlights:
- **Consolidated KPI Metrics Bar:**
  - **Today's Attendance:** Real-time counter of total checked-in staff, active floor members, and completed check-outs.
  - **Workforce & Shifts:** Enrolled active profiles and currently scheduled operating shift windows (e.g., `10:30 – 18:00 Standard Window`).
  - **Leaves & Approvals:** Staff members on approved leave today and pending time-off request counter.
- **Draggable & Dockable Camera Kiosk Card:**
  - Desktop-draggable live scanner card with perimeter flash indicator on successful detection.
  - Automatic standby detection with 1-click camera feed toggle and camera switch selector.
- **Real-Time Recognition Feed (SSE Powered):**
  - Instant live event stream powered by Server-Sent Events (`EventSource`) without page refresh.
  - Displays recognized employee avatar, name, staff code, detection confidence percentage (e.g., `61.7% Match`), ingestion node, and exact timestamp.
- **Biometric Terminal Gateway Status:** Real-time health indicator confirming ingestion readiness for mobile clients and Raspberry Pi edge nodes.

---

### Module 3: Employee Directory & Dynamic Profile Lifecycle

A structured master directory for managing staff profiles, corporate designations, branch location assignments, and compensation blueprints.

![Employee Directory](file:///d:/Attendance%20System/screenshots/walkthrough/03_employee_directory.png)

![Employee Profile Edit Modal](file:///d:/Attendance%20System/screenshots/walkthrough/04_employee_edit_modal.png)

#### Key Highlights:
- **Comprehensive Staff Catalog:** Displays enrolled employees with profile thumbnails, staff IDs, department badges, assigned work shifts, wage models, and employment status.
- **Granular Multi-Criteria Filtering:** Filter staff by Department (*Accounts, Operations, Sales*), Designation (*Store Manager, Clerk, Associate*), and assigned Work Shifts.
- **Interactive Profile Edit Modal:**
  - **3-Angle Enrolled Face Inspection:** View registered Frontal, Left-angle, and Right-angle reference photos.
  - **Organizational Hierarchy:** Reassign branch locations, reporting departments, and linked corporate designations.
  - **Shift & Date of Joining (DOJ):** Configurable DOJ calendar with automatic shift assignment inheritance.
  - **Compensation & Wage Blueprint:** Real-time salary structure configuration supporting Monthly Basic, Daily Wage Rate, or Hourly Billed Rate.

---

### Module 4: 3-Angle Facial Recognition Enrollment Kiosk

High-accuracy biometric enrollment that captures multi-angle face samples to ensure reliable recognition across varying lighting conditions, angles, and facial expressions.

![Register New Employee Enrollment](file:///d:/Attendance%20System/screenshots/walkthrough/05_register_new_employee.png)

#### Key Highlights:
- **Interactive Camera Guide Oval:** Live camera viewport with dashed biometric alignment framing and laser-sweep scanning animation.
- **Automated 3-Angle Photo Pipeline:** Guides the user through capturing three high-resolution perspectives: Frontal (0°), Left Angle (~15°), and Right Angle (~15°).
- **Auto-Generated Employee Codes:** Automatically provisions sequential corporate roll numbers (e.g., `EMP-1857`).
- **Cascading Master Pickers:** Selecting a Department dynamically filters and populates applicable Designations and default salary structures.
- **Vector Feature Extraction:** Real-time generation of 128-dimensional mathematical embeddings stored directly in RAM cache and database vectors.

---

### Module 5: Attendance Auditing, Ingestion Logs & Safe Soft-Delete

An immutable, searchable audit log capturing every biometric punch, manual administrative override, and shift state transition across the organization.

![Active Attendance Logs](file:///d:/Attendance%20System/screenshots/walkthrough/06_attendance_logs_active.png)

![Attendance Soft Delete Modal](file:///d:/Attendance%20System/screenshots/walkthrough/07_attendance_logs_soft_delete_modal.png)

#### Key Highlights:
- **Detailed Punch Ledger:** Records Log ID, Employee Name, Staff Code, Department, Ingestion Node, Check-In Time, Check-Out Time, Active Working Hours, and Shift Status (*ON_TIME, LATE_CHECKIN, EARLY_DEPARTURE*).
- **Date Range & Status Filters:** Custom calendar date pickers with single-click filtering for active, late, or incomplete records.
- **Audit-Safe Soft Delete System:**
  - Administrative soft-delete option with confirmation modal displaying Record ID, Member, Timestamp, and Ingestion details.
  - Automatically excludes deleted entries from live KPI metrics, export reports, and monthly payroll batches.
  - Full trash ledger allows reviewing soft-deleted logs and restoring them at any time with complete audit accountability.
- **Manual Punch Override Modal:** Authorized administrative fallback tool to force-mark check-in or check-out with mandatory justification notes.

---

### Module 6: Executive Analytics, Workforce Punctuality & Compliance Reports

High-level data visualization turning raw clock-in timestamps into actionable workforce productivity metrics and compliance analytics.

![Analytics and Reports](file:///d:/Attendance%20System/screenshots/walkthrough/08_analytics_and_reports.png)

#### Key Highlights:
- **Punctuality & Trend Charts:** Visualizes on-time arrival percentages, recurring tardiness patterns, and average daily shift completion rates.
- **Departmental Comparison:** Compares attendance consistency and active headcount across organizational departments.
- **Defaulter & Exception Tracking:** Highlights unclosed shifts (*MISSED_CHECKOUT*), frequent latecomers, and unsanctioned absences.
- **1-Click Compliance Export:** Instant CSV and Excel export formats pre-formatted for statutory labor audit filings.

---

### Module 7: Complete Indian Statutory Payroll & Multi-Model Compensation Engine

A full-featured payroll calculation engine tailored specifically for Indian corporate labor compliance, supporting structured CTC, daily wages, and hourly contracts.

![Payroll Monthly Batches](file:///d:/Attendance%20System/screenshots/walkthrough/09_payroll_monthly_batches.png)

![Payroll Employee Structures](file:///d:/Attendance%20System/screenshots/walkthrough/10_payroll_employee_structures.png)

![Payroll Salary Templates](file:///d:/Attendance%20System/screenshots/walkthrough/11_payroll_salary_templates.png)

![Payroll Masters](file:///d:/Attendance%20System/screenshots/walkthrough/12_payroll_masters.png)

![Payroll Wage Estimator](file:///d:/Attendance%20System/screenshots/walkthrough/13_payroll_wage_estimator.png)

#### Sub-Tab 1: Monthly Payroll Cycles & Batches
- **KPI Summary Cards:** Processed Monthly Cycles, Latest Net Outlay (₹), Statutory Liabilities (EPF + ESIC + PT), and Employer Total CTC Outlay.
- **Lifecycle Batch Processing:** Full workflow progression: `Draft` &rarr; `Verified` &rarr; `Approved` &rarr; `Disbursed`.
- **Automated Bank Advice Export:** Generates consolidated Excel and CSV bank disbursement files with IFSC and account numbers.

#### Sub-Tab 2: Employee Salary Structures
- **Individual Structure Assignment:** Assign and modify employee compensation profiles with custom monthly basic, HRA %, DA %, conveyance, medical, and special allowances.
- **Statutory Opt-in Controls:** Individual toggles for EPF (with ₹15,000 statutory wage ceiling cap), ESIC, and State Professional Tax (PT).

#### Sub-Tab 3: Reusable Salary Templates Master
- **Multi-Model Compensation Support:**
  - **Structured Salary (CTC):** Monthly basic percentage, HRA, DA, fixed conveyance, medical allowance, and other perks.
  - **Hourly Operative:** Billed strictly against biometric active hours with overtime premium rules.
  - **Daily Wage Staff:** Flat daily compensation per present day and authorized paid leave.
  - **Intern Stipend:** Fixed monthly stipend with zero statutory deduction overhead.
- **Transparent Parameter Breakdown:** Payslips dynamically output `"NA"` for non-applicable parameters on hourly and daily templates, ensuring transparency.

#### Sub-Tab 4: Component & Statutory Masters
- **Statutory Slabs:** Configurable Employee PF (12%), Employer PF (3.67%), EPS (8.33%), ESIC Employee (0.75%), ESIC Employer (3.25%), and state PT brackets.

#### Sub-Tab 5: Attendance Wage Estimator
- **Real-Time Projections:** Continuously computes projected month-to-date earnings from daily biometric punches, factoring in late arrival penalties and approved paid leaves.

---

### Module 8: Statutory Leave Management, Quotas & Time-Off Approvals

A centralized leave management portal balancing employee time-off requests against annual statutory entitlements and biometric records.

![Leave Management](file:///d:/Attendance%20System/screenshots/walkthrough/14_leave_management.png)

#### Key Highlights:
- **Statutory Quota Summary:** Dedicated entitlement cards for Casual Leave (CL), Sick Leave (SL), and Earned / Privilege Leave (PL).
- **Automated Balance Tracking:** Deducts approved leaves in real time and automatically credits paid leaves toward monthly payroll calculations.
- **Leave Application & Approval Workflow:** Staff and managers can apply, review, approve, or reject time-off requests with administrative audit tags.

---

### Module 9: Enterprise White-Labeling, Theming & Organizational Settings

A comprehensive administrative settings suite allowing complete white-label customization of branding, shifts, security policies, and geofenced perimeters.

![Settings Organization Profile](file:///d:/Attendance%20System/screenshots/walkthrough/15_settings_organization_profile.png)

![Settings Themes & Appearance](file:///d:/Attendance%20System/screenshots/walkthrough/16_settings_themes_appearance.png)

![Settings Departments](file:///d:/Attendance%20System/screenshots/walkthrough/17_settings_departments.png)

![Settings Designations](file:///d:/Attendance%20System/screenshots/walkthrough/18_settings_designations.png)

![Settings Shifts & Rules](file:///d:/Attendance%20System/screenshots/walkthrough/19_settings_shifts_rules.png)

![Settings Attendance & Security](file:///d:/Attendance%20System/screenshots/walkthrough/20_settings_attendance_security.png)

![Settings Geofencing & Portals](file:///d:/Attendance%20System/screenshots/walkthrough/21_settings_geofencing_portals.png)

#### Settings Capabilities:
1. **Organization Profile (`Tab 1`):** Configure institutional name, acronym code, branding tagline, upload custom logo, and set header badge text.
2. **Themes & Appearance (`Tab 2`):** Pre-built theme engine with live switching: *Warm Academic (Terracotta), Light Modern, Slate Corporate, Dark Mode, Emerald Forest, Midnight Blue*.
3. **Departments (`Tab 3`):** Create and manage operational departments (*Operations, Accounts, IT, Billing*).
4. **Designations & Role Masters (`Tab 4`):** Define organizational designations and bind them to default salary blueprints for instant employee onboarding.
5. **Shifts & Rules (`Tab 5`):** Multi-shift scheduler defining shift start time, end time, grace minutes (e.g., 15 mins), half-day thresholds (e.g., 4.0 hours), and break durations.
6. **Attendance & Security (`Tab 6`):** Precision biometric parameters including match confidence distance threshold, anti-spoofing liveness sensitivity, and continuous capture cooldown timers.
7. **Geofencing & Portals (`Tab 7`):** Interactive **Leaflet.js map engine** allowing administrators to define store coordinates, authorized perimeter radius (in meters), and manage tokenized employee self-attendance URLs.

---

## 👥 Role-Based Access Control (RBAC) & Personas

The system features strict separation of duties across four distinct operational personas:

| Role | Target Portal | Key Permissions & Responsibilities |
| :--- | :--- | :--- |
| **Super Administrator** | `/super-admin` | Platform owner. Manages all tenant organizations, provisions SaaS subscription editions (Basic, Smart, Pro), and oversees global system health. |
| **Tenant Administrator** | `/` (Dashboard) | Organization HR/Operations Manager. Manages employees, configures shifts, oversees live camera feeds, runs monthly payroll, and approves leaves. |
| **Teacher / Supervisor** | `/teacher-portal` | Academic faculty or floor supervisor. Takes session attendance, monitors assigned shift teams, and reviews daily roster punctuality. |
| **Employee / Student** | `/portal/{slug}` | End-user. Clock in/out via face scan, view personal attendance logs, download PDF payslips, and submit leave requests. |

---

## 💎 SaaS Subscription Tiers Matrix

The platform dynamically adapts its navigation menus, feature cards, and database constraints based on the tenant's subscribed SaaS edition:

```
┌────────────────────────────┬────────────────────────────┬────────────────────────────┐
│       BASIC EDITION        │       SMART EDITION        │        PRO EDITION         │
│   (Attendance Essentials)  │   (Attendance + Leaves)    │      (Full Enterprise)     │
├────────────────────────────┼────────────────────────────┼────────────────────────────┤
│ • AI Facial Recognition    │ • All Basic Features       │ • All Smart Features       │
│ • Employee Directory       │ • Multi-Shift Scheduling   │ • Indian Statutory Payroll │
│ • Live Operational HUD     │ • Leave Quota Management   │ • Salary Template Masters  │
│ • Attendance Audit Logs    │ • Time-Off Request Workflow│ • Automated Bank Advice    │
│ • Edge Node Frame Capture  │ • Advanced Analytics       │ • PDF Payslip Generator    │
│ • 1-Location Geofence      │ • Multi-Location Hierarchy │ • Custom CTC Structures    │
└────────────────────────────┴────────────────────────────┴────────────────────────────┘
```

---

## 🛠️ Technology Stack & Architecture

- **Backend:** Python 3.10+ / FastAPI / Starlette / Uvicorn ASGI
- **Biometric Core:** 128-dimensional Euclidean Vector Embeddings, dlib C++ models, OpenCV, Temporal Motion Anti-Spoofing
- **Database Engine:** MySQL 8.0+ with SQLAlchemy 2.0 ORM, connection pooling, and automated schema migration gates
- **Frontend Layer:** Semantic HTML5, Vanilla CSS Design System with custom CSS tokens, Leaflet.js Mapping Engine, Font Awesome 6.4
- **Real-Time Streaming:** Server-Sent Events (SSE / `text/event-stream`) with zero-latency proxy bypass
- **Deployment Platform:** Ubuntu Linux on AWS EC2, Nginx reverse proxy with TLS 1.3 / HTTP/2 SSL by Let's Encrypt
