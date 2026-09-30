# AI SYSTEM KNOWLEDGE BASE: MULTI-TENANT FACE ATTENDANCE & PAYROLL ENTERPRISE PLATFORM

> **Purpose**: Feed this document to Gemini (as a System Prompt, Custom GPT Instruction, or Project Knowledge File) to generate precise, production-grade prompts and technical specifications for the Antigravity AI engineering agent.

---

## 1. System Overview & Tech Stack

| Layer | Technologies & Libraries |
| :--- | :--- |
| **Backend Framework** | Python 3.10+, FastAPI, Uvicorn, Starlette |
| **Database & ORM** | MySQL 8.0+ (`face_system` DB on localhost:3306) with SQLite fallback / SQLAlchemy ORM / PyMySQL |
| **Face Recognition & Vision** | OpenCV (`cv2`), `face_recognition` (dlib 128-d Euclidean vector embeddings), NumPy, Pillow |
| **Security & Anti-Spoofing** | 2D FFT Spectral Texture Analysis, Specular Reflection Detection, Temporal Micro-motion (1-5 frame analysis) |
| **Authentication & RBAC** | JWT (HS256) stored in HTTP-only cookies (`access_token`, `active_role`, `active_tenant_id`), Passlib (bcrypt) |
| **Frontend Architecture** | Server-rendered Jinja2 templates (`src/server/templates/`), Vanilla JavaScript (ES6+), Vanilla CSS (`dashboard.css`) |
| **Design System & UI Tokens** | 3 Dynamic Themes (`light`, `dark`, `warm` / `academic`), CSS Custom Properties (`--bg-card`, `--accent-primary`, etc.), Font Awesome 6.4.0, Google Fonts (Plus Jakarta Sans, Inter) |
| **Reporting & Export** | `openpyxl` (Excel .xlsx generation), CSV export, PDF payslips |

---

## 2. Multi-Tenant Dual-Mode Architecture

The platform operates under a **Single-Database, Multi-Tenant Shared Schema** model using tenant scoping (`tenant_id` foreign key on all business entities). The system dynamically shifts terminology and workflows based on `tenant.tenant_type`:

### A. Educational Mode (`tenant_type = 'educational'`)
- **Entities**: Students, Teachers, Classes/Semesters, Divisions, Academic Years.
- **Key Routes**: `/students`, `/academic-management`, `/login/{slug}`, `/portal/{slug}`.
- **Onboarding/Self-Service**: Student Self-Registration Portal.

### B. Corporate Mode (`tenant_type = 'corporate' | 'company' | 'enterprise'`)
- **Entities**: Employees, Managers, Departments, Designations, Work Shifts, Office Locations.
- **Key Routes**: `/employees`, `/payroll`, `/leave-management`, `/settings`, `/login/{slug}`, `/employee/{slug}`.
- **Onboarding/Self-Service**: Employee Self-Enrollment Portal (`/onboard/{uuid}/{token}`), Facial Self-Attendance Check-In (`/check-in/{uuid}/{token}`).
- **Role/Designation De-duplication Principle**: Corporate tenants do NOT use school-style `student/teacher` roles. Visible corporate title is managed exclusively via **Designation** (`DesignationMaster`), while backend `user_role` is standard `employee` (hidden in UI).

---

## 3. Core Database Models & Invariants

All models reside in `src/database/models.py`.

```
[Tenant] (id, name, slug, tenant_type, is_active, is_deleted)
  ├── [TenantBranding] (theme, accent_color, logo_url, liveness_mode, cooldown_minutes, shift rules, statutory rules)
  ├── [User] (id, username, hashed_password, role: SUPER_ADMIN | TENANT_ADMIN | TEACHER | STUDENT, tenant_id)
  ├── [Department] (id, name, code, description, tenant_id)
  ├── [DesignationMaster] (id, title, code, department_id, salary_template_id, is_active, tenant_id)
  ├── [OfficeLocation] (id, name, code, city, state, latitude, longitude, tenant_id)
  ├── [WorkShift] (id, name, code, start_time, end_time, grace_period_minutes, is_default, tenant_id)
  ├── [Student] (id, roll_number, name, user_role, department_id, designation_id, shift_id, location_id, monthly_base_salary, hourly_rate, face_encoding_status, tenant_id)
  │     ├── [FaceEncoding] (id, student_id, sample_angle: frontal | left | right, vector_blob)
  │     ├── [AttendanceLog] (id, student_id, timestamp, status, verification_type: WEBCAM | SELF_MOBILE | GEOFENCED)
  │     ├── [EmployeeCompensationStructure] (id, student_id, compensation_model, annual_ctc, monthly_gross, monthly_basic, monthly_hra, etc.)
  │     ├── [EmployeeBankingDetail] (id, student_id, pan_number, uan_number, esic_number, bank_account, ifsc_code)
  │     └── [LeaveQuota] / [LeaveApplication]
  ├── [SalaryTemplate] (id, name, code, compensation_model: STRUCTURED_SALARY | MONTHLY_FIXED | HOURLY | DAILY_WAGE | STIPEND, basic_pct, hra_pct, enable_pf, enable_esi, enable_pt)
  └── [PayrollBatch] (id, period_month, period_year, status: DRAFT | VERIFIED | APPROVED | PAID)
        └── [PayrollRecord] (id, batch_id, student_id, gross_earnings, epf_deduction, esic_deduction, pt_deduction, net_pay)
```

---

## 4. Protected Core Infrastructure & Tenants (NEVER DELETE)

The database contains **6 Core Tenants** and **9 Core Administrative Users** that are vital to automated test suites, demo environments, and system stability:

### Preserved Core Tenants:
1. `default` (ID 1, Educational - FaceAttendance Campus)
2. `pulin1` (ID 106, Corporate)
3. `ssec` (ID 115, Corporate)
4. `gecm` (ID 155, Corporate)
5. `raymond-store-1` (ID 292, Corporate)
6. `the-retail-store` (ID 750, Corporate - Flagship Ahmedabad)

### Preserved Core Users (Password: `admin123`):
- `superadmin` (SUPER_ADMIN)
- `admin` (TENANT_ADMIN for default #1)
- `teacher1`, `student1` (default #1)
- `admin` (TENANT_ADMIN for pulin1 #106)
- `ssec` (TENANT_ADMIN for ssec #115)
- `gecm` (TENANT_ADMIN for gecm #155)
- `raymond` (TENANT_ADMIN for raymond-store-1 #292)
- `admin_retail` (TENANT_ADMIN for the-retail-store #750)

> **Database Purge Script**: All automated tests or maintenance scripts must run `scripts/purge_test_records.py` which safely cleans temporary test records while preserving these core entities.

---

## 5. Directory & File Structure Map

```
D:\Attendance System\
├── .agents\
│   └── skills\
│       └── attendance-system\
│           └── SKILL.md           # Antigravity Persistent Skill (Architecture, Tokens, Maps)
├── src\
│   ├── database\
│   │   ├── models.py              # Core SQLAlchemy models (Tenant, User, Student, Shifts, etc.)
│   │   ├── session.py             # DB connection, engine, init_db, default seeds
│   ├── face_engine\
│   │   ├── recognition.py         # 128-d embedding extraction, in-memory matrix matcher
│   │   ├── anti_spoof.py          # 2D FFT spectral texture & liveness verification
│   ├── server\
│   │   ├── app.py                 # FastAPI initialization, middleware, route mounting
│   │   ├── rbac_middleware.py     # Auth dependencies, token creation, role gates
│   │   ├── tenant_middleware.py   # Domain / header / slug multi-tenant scoping
│   │   ├── services\
│   │   │   ├── __init__.py        # Business logic & view services export
│   │   │   └── view_service.py    # Consolidated template context, tenant branding, role resolution
│   │   ├── routes\
│   │   │   ├── views_public.py    # Public landing page (/), SEO sitemap/robots, demo logins
│   │   │   ├── views_auth.py      # SaaS login, tenant portals, token logins, onboarding
│   │   │   ├── views_employee.py  # Employee self-service dashboard, mobile check-in
│   │   │   ├── views_dashboard.py # Admin views (/dashboard, /employees, /payroll, /settings)
│   │   │   ├── api_auth.py        # /api/v1/auth (login, logout, session check)
│   │   │   ├── api_demo.py        # /api/v1/demo (AWS SES OTP verification, trial provisioning)
│   │   │   ├── api_enrollment.py  # /api/v1/enroll (webcam stream capture, batch 3-photo)
│   │   │   ├── api_attendance.py  # /api/v1/attendance (clock-in, clock-out, records, live HUD)
│   │   │   ├── api_payroll.py     # /api/v1/payroll (salary templates, masters, batches)
│   │   │   ├── api_leave.py       # /api/v1/leaves (quotas, applications, approval)
│   │   │   ├── api_nodes.py       # /api/v1/nodes (mobile check-in, edge ingestion)
│   │   │   └── api_academic.py    # /api/v1/academic (departments, classes, divisions)
│   │   ├── templates\             # Jinja2 HTML Templates
│   │   │   ├── base.html          # Global sidebar, topbar, theme switcher, mobile drawer
│   │   │   ├── landing.html       # Marketing showcase (compacted with partials)
│   │   │   ├── enroll.html        # Register New Employee (Webcam Guided & Batch 3-Photo)
│   │   │   ├── students.html      # Employee / Student Directory with Edit Profile Modals
│   │   │   ├── settings.html      # Org Settings, Themes, Departments, Designations, Shifts, Geofencing
│   │   │   ├── payroll.html       # Payroll Batches, Salary Templates, Statutory Rules, Payslips
│   │   │   ├── login.html         # Unified & Tenant-specific Clean Login Portal
│   │   │   ├── self_attendance.html # Mobile facial scan check-in portal with GPS geofencing
│   │   │   └── components\        # Reusable Jinja2 Component Partials
│   │   │       ├── demo_modal.html       # Free Demo modal & 6-digit OTP dialog
│   │   │       ├── guide_modal.html      # 10-step Quick Onboarding Guide modal
│   │   │       ├── lightbox_modal.html   # Screenshot zoom lightbox
│   │   │       ├── settings_modals.html  # Modals for departments, designations, shifts, locations
│   │   │       ├── payroll_modals.html   # Modals for batch generation, salary blueprints
│   │   │       └── academic_modals.html  # Modals for department & class editing
│   │   └── static\
│   │       ├── css\
│   │       │   ├── landing.css    # Extracted Curiosity HUB landing page styling (~2300 lines)
│   │       │   └── dashboard.css  # Core design system, responsive grid, theme variables
│   │       └── js\
│   │           ├── landing.js             # Onboarding walkthrough, modal controllers & demo logic
│   │           ├── settings.js            # Leaflet map, geofencing, shift rules & master CRUD
│   │           ├── payroll.js             # Salary template modals, batch runner & payslips
│   │           ├── academic_management.js # Bulk Excel parser & class promotion handlers
│   │           └── dashboard.js           # Live SSE stream, toast alerts & audio feedback
│   └── utils\
│       ├── timezone.py            # IST (Asia/Kolkata) timezone helpers (get_ist_now)
│       └── auth_utils.py          # Password hashing, JWT token validation
├── scripts\
│   ├── purge_test_records.py      # Database hygiene script (preserves 6 core tenants)
│   └── run_server.py              # Local server launcher (FastAPI / Uvicorn on port 8000)
└── tests\
    ├── auth\                      # Authentication & RBAC test suites
    ├── attendance\                # Check-in, check-out, multi-shift test suites
    ├── ui\                        # Integration & UI rendering test suites
    ├── payroll\                   # Indian statutory payroll & compensation tests
    └── integration\               # End-to-end API workflows
```

---

## 6. Prompt Engineering Directives for Gemini (Meta-Instructions)

When asking Gemini to generate a task prompt for Antigravity, tell Gemini to follow this **Prompt Construction Blueprint**:

### Standard Prompt Format:
```markdown
**System [UI / Architecture / API] Prompt: [Concise Feature Title]**

You are an autonomous engineering agent working inside `D:\Attendance System`. We need to [clear 1-2 sentence high-level goal], followed by purging any test records generated during this update.

**CRITICAL DIRECTIVES:**
1. Do not write code immediately. Output a concise implementation plan and ask essential clarifying questions before coding.
2. **Do not upload or push changes** to GitHub or production unless instructed.
3. Preserve all 6 core tenants and 9 core users without modifying core referential integrity.

**Required Architectural / UI Upgrades:**
1. **[Component / Page Name]:**
   * [Specific requirement with exact field names, routes, and styling tokens]
2. **[Backend / Database / API Name]:**
   * [Specific endpoints, schemas, service logic, and database migrations if needed]
3. **Automated Verification:**
   * Create or update unit/integration tests under `tests/ui/` or `tests/auth/`.
   * Run `scripts/purge_test_records.py` at the end to ensure database hygiene.
```

---

## 7. Key Code & UI Conventions

1. **Vanilla CSS & Design System Tokens**:
   - Use CSS custom properties: `var(--bg-card)`, `var(--bg-subtle)`, `var(--text-heading)`, `var(--text-muted)`, `var(--accent-primary)`, `var(--accent-emerald)`, `var(--radius-sm)`, `var(--border-color)`.
   - Never use TailwindCSS unless explicitly instructed.
2. **Auto-Generated & Editable Form Fields**:
   - Auto-generate IDs/codes on load (e.g. `generateRandomEmployeeCode()`), with an inline reload button (`<button class="auto-code-refresh-btn">`), keeping input fully editable by user.
3. **Tenant Routing & Permissions**:
   - Always resolve tenant context via `get_current_tenant` dependency.
   - For routes that apply across both Corporate and Educational tiers, avoid restrictive module guards (like requiring full paid payroll flags for basic designation or department listings).
4. **Idempotent Testing**:
   - Test suites in `tests/` must clean up any created entities by code pattern in `tearDown` or pre-creation to allow repetitive test execution without 400 Duplicate errors.

---

## 8. Database Schema Reference (`src/database/models.py`)

Primary relational tables mapped in MySQL (`DATABASE_URL = mysql+pymysql://root:@localhost:3306/face_system`):

| Table Name | Model Class | Primary & Key Columns |
| :--- | :--- | :--- |
| `tenants` | `Tenant` | `id` (PK), `slug` (Unique), `name`, `tenant_type` (`educational`/`corporate`), `subscription_plan`, `subscription_status`, `is_active`, `uuid`, `admin_token`, `onboarding_token`, `attendance_slug` |
| `users` | `User` | `id` (PK), `tenant_id` (FK), `username`, `email`, `password_hash`, `role` (`SUPER_ADMIN`/`TENANT_ADMIN`/`TEACHER`/`STUDENT`), `full_name`, `phone_number`, `is_active` |
| `students` | `Student` | `id` (PK), `tenant_id` (FK), `roll_number`, `name`, `gender`, `department_id` (FK), `email`, `phone_number`, `user_role` (`employee`/`student`), `joining_date`, `is_active` |
| `face_encodings` | `FaceEncoding` | `id` (PK), `tenant_id` (FK), `student_id` (FK), `sample_angle` (`Front`/`Left`/`Right`), `vector_json` (Text 128-d/512-d), `photo_path` |
| `attendance_records` | `AttendanceRecord` | `id` (PK), `tenant_id` (FK), `student_id` (FK), `node_id`, `timestamp` (IST), `confidence_distance`, `status` (`PRESENT`/`LATE`/`HALF_DAY`), `snapshot_path`, `is_manual_override` |
| `node_devices` | `NodeDevice` | `node_id` (PK), `tenant_id` (FK), `name`, `location`, `last_heartbeat`, `is_online`, `fps` |
| `departments` | `Department` | `id` (PK), `tenant_id` (FK), `name`, `code`, `description` |
| `work_shifts` | `WorkShift` | `id` (PK), `tenant_id` (FK), `name`, `code`, `start_time`, `end_time`, `grace_period_minutes`, `break_duration_minutes` |
| `company_locations` | `CompanyLocation` | `id` (PK), `tenant_id` (FK), `name`, `code`, `latitude`, `longitude`, `geofence_radius_meters` |
| `leave_types` | `LeaveType` | `id` (PK), `tenant_id` (FK), `name`, `code`, `is_paid`, `default_days_per_year` |
| `leave_requests` | `LeaveRequest` | `id` (PK), `tenant_id` (FK), `student_id` (FK), `leave_type_id` (FK), `start_date`, `end_date`, `status` (`PENDING`/`APPROVED`/`REJECTED`) |
| `salary_templates` | `SalaryTemplate` | `id` (PK), `tenant_id` (FK), `name`, `code`, `compensation_model`, `basic_percentage`, `hra_percentage` |
| `payroll_batches` | `PayrollBatch` | `id` (PK), `tenant_id` (FK), `batch_number`, `period_month`, `period_year`, `status` (`DRAFT`/`CALCULATED`/`FINALIZED`) |
| `payroll_payslips` | `PayrollPayslip` | `id` (PK), `tenant_id` (FK), `batch_id` (FK), `student_id` (FK), `gross_salary`, `net_salary`, `status` |

