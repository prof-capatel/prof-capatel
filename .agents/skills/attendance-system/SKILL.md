---
name: attendance-system
description: "Comprehensive architecture, routing, authentication, multi-tenant dual-mode, and UI/UX design reference for the Curiosity HUB Multi-Tenant Face Recognition Attendance & Automated Payroll SaaS platform."
---

# Curiosity HUB — Multi-Tenant Face Recognition Attendance & Payroll SaaS

A centralized, zero-hardware, AI-powered biometric workforce and academic management platform built with FastAPI, MySQL, OpenCV, and dlib 128-dimensional Euclidean vector embeddings.

---

## 1. System Architecture & Tech Stack

| Layer | Technologies & Implementations |
| :--- | :--- |
| **Backend Framework** | Python 3.10+, FastAPI, Starlette, Uvicorn (ASGI) |
| **Database & ORM** | MySQL 8.0 (`face_system` DB on `localhost:3306`) with SQLite fallback, SQLAlchemy ORM, PyMySQL |
| **Face Recognition & Vision** | OpenCV (`cv2`), `face_recognition` (dlib ResNet 128-d Euclidean vector matching with in-memory RAM cache) |
| **Anti-Spoofing & Liveness** | 2D FFT Spectral Texture Analysis, Specular Reflection, Temporal Micro-motion (1–5 frame analysis) |
| **Authentication & RBAC** | JWT (HS256) stored in HTTP-only cookies (`access_token`, `active_role`, `active_tenant_id`, `emp_session_token`), Passlib (bcrypt) |
| **Email & Communications** | AWS SES SMTP (`smtp-credentials.csv`) with TLS 587, automated 6-digit OTP verification & credential delivery |
| **Frontend Architecture** | Jinja2 Server-Rendered HTML (`src/server/templates/`), Vanilla JavaScript (ES6+), Vanilla CSS (`landing.css`, `dashboard.css`) |
| **Design System & Tokens** | 3 Themes (`light`, `dark`, `warm`/academic), CSS Custom Properties (`--bg-card`, `--accent-primary`, etc.), Font Awesome 6.4.0, Plus Jakarta Sans & Inter |
| **Reporting & Export** | `openpyxl` (Excel .xlsx), CSV export, PDF payslips |

---

## 2. Multi-Tenant Dual-Mode Operational Invariants

The database follows a **Single-Database, Multi-Tenant Shared Schema** model partitioned by `tenant_id`:

### A. Corporate Mode (`tenant.tenant_type in ['corporate', 'company', 'enterprise']`)
- **Key Entities**: Employees ([`Student`](file:///d:/Attendance%20System/src/database/models.py) model with `user_role != 'student'`), Departments, Designations ([`DesignationMaster`](file:///d:/Attendance%20System/src/database/models.py)), Work Shifts ([`WorkShift`](file:///d:/Attendance%20System/src/database/models.py)), Office Locations ([`CompanyLocation`](file:///d:/Attendance%20System/src/database/models.py)).
- **Primary Pages**: `/dashboard`, `/employees`, `/payroll`, `/leave-management`, `/settings`, `/login/{slug}`, `/employee/{slug}`.
- **Self-Service Portals**:
  - Employee Self-Onboarding: `/onboard/{tenant_uuid}/{onboarding_token}`
  - Permanent Daily Mobile Check-In: `/check-in/{tenant_uuid}/{attendance_slug}`
  - Passwordless Employee Portal: `/employee/{tenant_slug}` → `/employee/{tenant_slug}/dashboard`
- **Role/Designation Decoupling**: Visible corporate rank is stored in `designation_id` (`DesignationMaster`), while backend `user_role` remains `'employee'` or `'manager'`.

### B. Educational Mode (`tenant.tenant_type == 'educational'`)
- **Key Entities**: Students, Teachers, Classes/Courses ([`ClassModel`](file:///d:/Attendance%20System/src/database/models.py)), Divisions ([`Division`](file:///d:/Attendance%20System/src/database/models.py)), Academic Years ([`AcademicYear`](file:///d:/Attendance%20System/src/database/models.py)).
- **Primary Pages**: `/dashboard`, `/students`, `/academic-management`, `/teacher-portal`, `/enroll`, `/login/{slug}`, `/portal/{slug}`.

---

## 3. Protected Core Infrastructure (NEVER PURGE OR DELETE)

The system relies on **6 Core Tenants** and **9 Core Administrative Users** that MUST NEVER be deleted by test fixtures or migration scripts:

### Protected Core Tenants:
1. `default` (ID 1, Educational — FaceAttendance Campus)
2. `pulin1` (ID 106, Corporate — Pulin Enterprise)
3. `ssec` (ID 115, Corporate — SSEC Technologies)
4. `gecm` (ID 155, Corporate — GECM Corporate)
5. `raymond-store-1` (ID 292, Corporate — Raymond Retail)
6. `the-retail-store` (ID 750, Corporate — Flagship Ahmedabad Store)

### Protected Core Users (Default Password: `admin123`):
- `superadmin` (Role: `SUPER_ADMIN`)
- `admin` (Role: `TENANT_ADMIN` for tenant #1 `default`)
- `teacher1`, `student1` (tenant #1 `default`)
- `admin` (Role: `TENANT_ADMIN` for tenant #106 `pulin1`)
- `ssec` (Role: `TENANT_ADMIN` for tenant #115 `ssec`)
- `gecm` (Role: `TENANT_ADMIN` for tenant #155 `gecm`)
- `raymond` (Role: `TENANT_ADMIN` for tenant #292 `raymond-store-1`)
- `admin_retail` (Role: `TENANT_ADMIN` for tenant #750 `the-retail-store`)

> **Database Hygiene**: All test routines must run [`scripts/purge_test_records.py`](file:///d:/Attendance%20System/scripts/purge_test_records.py) which cleans temporary test records while preserving these core entities.

---

## 4. Complete System Routing Architecture

```
                    ┌─────────────────────────┐
                    │       FastAPI App       │
                    └────────────┬────────────┘
         ┌───────────────────────┼───────────────────────┐
         │                       │                       │
┌────────▼────────┐     ┌────────▼────────┐     ┌────────▼────────┐
│  Public Views   │     │   Auth Views    │     │ Employee Views  │
│ (views_public)  │     │  (views_auth)   │     │(views_employee) │
├─────────────────┤     ├─────────────────┤     ├─────────────────┤
│ /               │     │ /saas, /login   │     │ /employee/{slug}│
│ /robots.txt     │     │ /super-admin/   │     │ /self-attendance│
│ /sitemap.xml    │     │   login         │     │ /check-in/{u}/  │
│ /demo-login     │     │ /portal/{u}/{t} │     │   {slug}        │
│ /demo           │     │ /login/{slug}   │     │ /mobile-capture │
└─────────────────┘     │ /auth/token-    │     │ /face-demo      │
                        │   login/{u}/{t} │     └─────────────────┘
                        │ /onboard/{u}/   │
                        │   {token}       │
                        └─────────────────┘
                                 │
                        ┌────────▼────────┐
                        │   Admin Views   │
                        │(views_dashboard)│
                        ├─────────────────┤
                        │ /dashboard      │
                        │ /employees      │
                        │ /students       │
                        │ /enroll         │
                        │ /logs           │
                        │ /nodes          │
                        │ /analytics      │
                        │ /settings       │
                        │ /payroll        │
                        │ /payroll/payslip│
                        │ /leave-mgt      │
                        │ /super-admin    │
                        │ /academic-mgt   │
                        │ /teacher-portal │
                        └─────────────────┘
```

### Core API Endpoints (`/api/v1/`):
- `/api/v1/auth`: `/login`, `/logout`, `/me`, `/tenant-roles/{slug}`
- `/api/v1/demo`: `/request-otp`, `/verify-and-provision` (AWS SES SMTP automated onboarding)
- `/api/v1/enroll`: `/student`, `/capture-sample`, `/batch-upload`, `/student/{id}`
- `/api/v1/attendance`: `/log`, `/records`, `/stats`, `/verify-face`
- `/api/v1/payroll`: `/templates`, `/batches`, `/payslips`, `/calculate`
- `/api/v1/leave`: `/types`, `/requests`, `/balances`, `/apply`, `/approve`, `/reject`
- `/api/v1/nodes`: `/heartbeat`, `/register`, `/list`
- `/api/v1/academic`: `/departments`, `/classes`, `/divisions`, `/students/bulk-import`

---

## 5. Modular Server Directory & Template Hierarchy

```
d:\Attendance System\
├── src\server\
│   ├── app.py                         # FastAPI app setup, static mounts, route registration
│   ├── tenant_middleware.py           # Tenant resolution from subdomain, slug, or header
│   ├── rbac_middleware.py             # JWT verification, cookie parsing, role-based guards
│   ├── services\
│   │   ├── __init__.py
│   │   └── view_service.py            # Consolidated template rendering, tenant context & roles
│   ├── routes\
│   │   ├── views_public.py            # Public landing, SEO sitemap/robots, demo shortcuts
│   │   ├── views_auth.py              # SaaS login, tenant portals, token logins, onboarding
│   │   ├── views_employee.py          # Employee self-service dashboard, mobile check-in
│   │   ├── views_dashboard.py         # Administrative views (/dashboard, /employees, /payroll, etc.)
│   │   ├── api_auth.py
│   │   ├── api_demo.py
│   │   ├── api_enrollment.py
│   │   ├── api_attendance.py
│   │   ├── api_payroll.py
│   │   ├── api_leave.py
│   │   └── api_nodes.py
│   ├── static\
│   │   ├── css\
│   │   │   ├── landing.css            # Extracted landing page design system & typography
│   │   │   └── dashboard.css          # Core administrative dashboard theme system
│   │   └── js\
│   │       ├── landing.js             # Onboarding walkthrough, modal controllers & demo logic
│   │       ├── settings.js            # Leaflet map, geofencing, shift rules & master CRUD
│   │       ├── payroll.js             # Salary template modals, batch runner & payslips
│   │       ├── academic_management.js # Bulk Excel parser & class promotion handlers
│   │       └── dashboard.js           # Live SSE stream, toast alerts & audio feedback
│   └── templates\
│       ├── base.html                  # Core admin layout with sidebar, navbar, and theme engine
│       ├── landing.html               # Public marketing showcase (compacted with partials)
│       ├── settings.html              # Consolidated settings view
│       ├── payroll.html               # Payroll management dashboard
│       ├── academic_management.html   # Academic hierarchy
│       └── components\                # Reusable Jinja2 partials
│           ├── demo_modal.html        # 7-day Pro trial registration & OTP dialog
│           ├── guide_modal.html       # Interactive 10-step Quick Onboarding Guide modal
│           ├── lightbox_modal.html    # Screenshot zoom viewer
│           ├── settings_modals.html   # Designation, department, shift, location dialogs
│           ├── payroll_modals.html    # Batch generation & salary template dialogs
│           └── academic_modals.html   # Department & class edit dialogs
```

---

## 6. Authentication, Sessions & Cookie Protocol

| Cookie Name | Scope / Flags | Description |
| :--- | :--- | :--- |
| `access_token` | `HttpOnly`, `Path=/`, `Max-Age=30d` | JWT signed HS256 containing `sub` (user_id), `role`, `tenant_id`, and `exp` |
| `active_role` | `Path=/`, `Max-Age=30d` | Active user role string (`SUPER_ADMIN`, `TENANT_ADMIN`, `TEACHER`, `STUDENT`) |
| `active_tenant_id` | `Path=/`, `Max-Age=30d` | Currently selected tenant integer ID |
| `emp_session_token`| `HttpOnly`, `Path=/`, `Max-Age=30d` | Dedicated employee session JWT containing `student_id` and `tenant_id` |

---

## 7. UI/UX Design System & Branding Tokens

* **Rule**: Always use **Vanilla CSS** with CSS Custom Properties. **Never use TailwindCSS** unless explicitly requested.
* **Core Tokens**:
  - Backgrounds: `var(--bg-page)` (`#F8FAFC`), `var(--bg-card)` (`#FFFFFF`), `var(--bg-subtle)` (`#F1F5F9`)
  - Typography: `var(--text-heading)` (`#0F172A`), `var(--text-body)` (`#334155`), `var(--text-muted)` (`#64748B`)
  - Primary Brand Accent: `var(--accent-primary)` (`#EA580C` sunset orange), `var(--accent-gradient)`
  - Secondary Tech Accent: `var(--tech-indigo)` (`#4F46E5`), `var(--tech-indigo-soft)` (`#EEF2FF`)
  - Success/Status: `var(--accent-emerald)` (`#10B981`)
  - Radii & Shadows: `var(--radius-sm)` (`6px`), `var(--radius-md)` (`12px`), `var(--shadow-md)`
* **Typography**: Plus Jakarta Sans for executive headers, Inter for tabular numbers and forms.

---

## 8. Verification & Database Hygiene Protocol

1. **Lightweight Test Commands**:
   ```powershell
   .\venv\Scripts\python.exe -m unittest tests.auth.test_tenant_login_routing
   .\venv\Scripts\python.exe -m unittest tests.auth.test_free_demo_provisioning
   .\venv\Scripts\python.exe -m unittest tests.attendance.test_corporate_checkin_checkout
   .\venv\Scripts\python.exe -m unittest tests.ui.test_landing_page_curiosity_hub
   ```
2. **Purge Test Records**:
   ```powershell
   .\venv\Scripts\python.exe scripts/purge_test_records.py
   ```
3. **Git Hygiene**:
   - Never commit `.pem` files or `smtp-credentials.csv`.
   - Never push to GitHub or EC2 production server unless explicitly instructed.

---

## 9. Database Schema Reference (`src/database/models.py`)

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

---

## 10. SEO Architecture, Super Admin SEO Hub & Public Website Standards

### A. Dynamic SEO Engine (`src/server/services/seo_service.py`)
- **Storage**: Persistent JSON file `data/seo_settings.json` with fallback defaults in `DEFAULT_SEO`. No database migration required; changes apply immediately on next page render.
- **Dynamic Endpoints**:
  - `GET /robots.txt` → Served dynamically from `seo_service.get_robots_txt()`.
  - `GET /sitemap.xml` → Served dynamically from `seo_service.get_sitemap_xml()`.
  - `GET /` → Injects `seo` dict into `landing.html` Jinja2 context for dynamic `<title>`, `<meta description>`, `<meta keywords>`, `<link rel="canonical">`, OpenGraph, and Twitter tags.

### B. Super Admin Control Plane SEO Hub
- **UI Location**: Integrated into `src/server/templates/super_admin.html` as `#seoManagementCard` with handlers in `src/server/static/js/super_admin.js`.
- **APIs**:
  - `GET /api/v1/super-admin/seo`: Computes technical SEO health score (0–100), audit parameters, SERP snippet preview, and social sharing card preview.
  - `POST /api/v1/super-admin/seo`: Saves updated title, canonical URL, meta description, keywords, OG image, and robots rules.
  - `POST /api/v1/super-admin/seo/sitemap-regenerate`: Rebuilds XML sitemap with active canonical URL.

### C. Public Website Mobile-First Design & Layout Standards
- **Hero Whitespace Constraint**: `.hero-section` padding strictly kept at `24px 0 32px` on desktop and `14px 0 20px` on mobile to avoid empty gaps between the sticky navbar and the hero headline.
- **Touch Target Compliance**: Mobile navigation buttons (`.btn-nav-demo`, `.btn-nav-signin`, `.mobile-toggle`) enforce `min-height: 44px; min-width: 44px` for mobile usability.
- **Narrative Guidelines**: Professional enterprise tone without promotional gimmicks (e.g. no "fastest onboarding", "zero dedicated hardware", or metric ribbons).


