# Attendance System — Complete Feature Catalog & 2-Minute Onboarding Guide
### *Enterprise Biometric Attendance, Statutory Indian Payroll & Employee Self-Service Platform*
**Demonstration Showcase:** *The Retail Store (Flagship Ahmedabad)*

---

## 🌟 Executive Summary

The **Attendance System** is an all-in-one, cloud-ready workforce management platform designed for modern retail chains, corporate offices, and educational institutions. It unifies **AI-powered facial recognition attendance**, **automated Indian statutory payroll**, **time-off management**, and **mobile-first employee self-service** into a single, cohesive dashboard that takes **less than 2 minutes** to set up.

---

## 📦 Part 1: Comprehensive Feature & Module Catalog

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           ATTENDANCE SYSTEM CORE PLATFORM                       │
├───────────────────────┬────────────────────────┬────────────────────────────────┤
│ 🏢 Organization &     │ 👤 Biometric & AI Face │ 💰 Smart Indian Payroll        │
│    Multi-Tenancy      │    Recognition Engine  │    & Wage Calculator           │
├───────────────────────┼────────────────────────┼────────────────────────────────┤
│ 🏖️ Leave & Quota      │ ⏱️ Shift Scheduling   │ 📱 Employee Self-Service       │
│    Management         │    & Geofence Rules    │    Mobile Portal               │
└───────────────────────┴────────────────────────┴────────────────────────────────┘
```

### Module 1: Multi-Tenant Enterprise Administration & Branding
*Manage multiple branches, stores, or campuses from a unified command center.*

- **Instant Tenant Provisioning**: Create dedicated, isolated environments for stores or companies with unique URLs (`/portal/{company-name}`).
- **Custom Brand Identity**: 
  - Match your company's visual identity with pre-built themes (*Warm Academic / Terracotta, Slate Corporate, Indigo Tech, Dark Mode*).
  - Upload custom company logos, set institutional badges, and configure localized time zones and currency symbols (e.g. ₹ INR).
- **Multi-Location Hierarchy**: Organize staff across physical branch locations (e.g., *Ahmedabad Flagship Store, S.G. Highway*) with store addresses and emergency contact numbers.
- **Department & Designation Masters**: Create structured departments (*Store Operations, Inventory & Logistics, Customer Billing*) and role tiers (*Store Manager, Cashier, Associate*).
- **Granular Role-Based Security**: Built-in access levels for *Superadmin, Tenant Admin, Shift Manager,* and *Staff*.
- **Comprehensive Audit Trail**: Every administrative action, manual attendance override, and salary change is logged with an immutable timestamp and user sign-off.

---

### Module 2: AI Facial Recognition Attendance Engine
*Zero-hardware, touchless biometric check-in with millisecond precision.*

- **1:N Face Recognition**: Identifies staff instantly from a crowd without requiring ID cards, PINs, or fingerprint touching.
- **Zero-Hardware Thin-Client Mode**: Runs directly inside any modern web browser using standard laptops, tablets, or mobile webcams.
- **RTSP & IP Camera Network Support**: Connect existing ceiling-mounted CCTV cameras or smart edge nodes (`/api/v1/nodes/frame`) for passive walk-through attendance.
- **Continuous Live Attendance Kiosk**:
  - Live attendance scanner runs continuously in the background across tab switches and window minimizing.
  - Automatic stream interruption detection and 1-click feed restart.
- **Intelligent Deduplication Cooldown**: Configurable cooldown window (e.g., 1 to 3 minutes) prevents duplicate punch registrations when staff stand near the camera.
- **Real-Time Recognition Alerts**:
  - Instant visual HUD toast notifications display the employee's name, ID, match confidence percentage, and check-in/out status.
  - Audio chime feedback confirms successful punches.
- **Authorized Manual Punch Override**: Admin tool to force-mark attendance with justification presets (*Medical Exception, Hardware Maintenance, Field Duty*).

---

### Module 3: Smart Indian Payroll & Wage Engine
*100% compliant Indian statutory payroll calculated automatically from daily biometric attendance.*

> [!TIP]
> **No Confusion for First-Time Users**: You do not need to memorize tax formulas. Simply assign a salary template, and the system handles the rest with 1 click at the end of each month.

- **4 Flexible Compensation Models**:
  1. **Structured Salary (Monthly CTC Breakdown)**: Standard corporate pay structured into Basic, HRA, Conveyance, and Allowances.
  2. **Monthly Fixed**: Fixed monthly remuneration for full-time store staff.
  3. **Daily Wage**: Pay-per-day rate ideal for daily contract staff and security.
  4. **Hourly Rate**: Pay calculated strictly by approved working hours and shifts.
- **Built-in Indian Statutory Deductions**:
  - **EPF (Employees' Provident Fund)**: 12% employee and employer contribution with optional ₹15,000 statutory wage ceiling cap.
  - **ESIC (Employee State Insurance)**: Automatic 0.75% employee and 3.25% employer deduction applied for monthly gross under ₹21,000.
  - **Professional Tax (PT)**: Built-in state slabs (e.g., Gujarat ₹200/month for gross salaries above ₹12,000).
  - **TDS (Income Tax Deduction)**: Direct monthly tax withholding support.
- **Automated Attendance Linkage**:
  - Automatically calculates payable days, unpaid absences (LWP), approved paid leaves, and overtime hours.
  - **Overtime Calculations**: Customizable multipliers (1.5x for standard overtime, 2.0x for Sunday/holiday overtime).
- **1-Click Monthly Batch Processing**: Generate payroll for all store employees in seconds with a complete audit summary.
- **Digital Itemized Payslips**:
  - Clear breakdown of Gross Earnings, Statutory Deductions, Net Pay in words & numbers, and employer statutory contributions.
  - Crisp, printable PDF format for paper distribution or digital archiving.

---

### Module 4: Leave & Time-Off Management
*Frictionless leave tracking that automatically synchronizes with month-end payroll.*

- **Pre-Configured Statutory Leave Policies**:
  - **Casual Leave (CL)**: 12 Days/Year for short-term personal needs.
  - **Medical Leave (ML)**: 10 Days/Year for health recovery.
  - **Earned / Privilege Leave (EL)**: 15 Days/Year for annual planned vacations.
  - **Leave Without Pay (LWP)**: Unpaid absence tracked and deducted from payroll.
- **Real-Time Quota Tracking**: Visual quota progress bars show total, utilized, and remaining leave balances.
- **Self-Service Leave Applications**: Staff submit requests with date pickers and reason fields directly from their phones.
- **Administrative Approval Queue**: Store managers review, approve, or reject pending leave requests with 1 tap.

---

### Module 5: Shift Scheduling & Store Location Rules
*Tailored work shifts with flexible grace periods and attendance policies.*

- **Multi-Shift Scheduling**: Create overlapping or rotating shifts (e.g., *Morning Shift: 08:00 – 16:00, Evening Shift: 12:00 – 22:00*).
- **Late Arrival Grace Periods**: Configurable grace window (e.g. 15 minutes) before marking late check-in.
- **Half-Day Attendance Rules**: Automatically marks half-day if working hours fall below threshold (e.g., 4.0 hours).
- **Missed Punch Policies**: Auto-resolves forgotten check-outs with Half-Day or Standard Shift assumptions.
- **Optional GPS Geofencing**: Restricts mobile self-attendance strictly within the physical store coordinates (e.g. 150-meter radius).

---

### Module 6: Mobile-First Employee Self-Service Portal
*A private, passwordless smartphone portal for every staff member.*

- **Passwordless Face Login (`/employee/{company-slug}`)**: Staff simply scan their face on their smartphone to log in — no forgotten passwords or PINs.
- **Clean, Compact Mobile Layout**: Designed from the ground up for modern iOS and Android smartphones without excessive whitespace or duplicate headers.
- **Daily Attendance Timeline**: Real-time log of check-in times, check-out times, total active hours, and shift status.
- **Wages & CTC Breakdown Tab**: Full transparency into Basic pay, HRA, Allowances, PF eligibility, and monthly take-home estimate.
- **Instant Leave Application Tab**: Apply for time-off and check live approval status in seconds.
- **Digital Payslip Vault**: Instant view and download of itemized monthly salary slips.

---

## ⚡ Part 2: The 2-Minute Rapid Tenant Onboarding Guide

*How "The Retail Store" went from zero to live face recognition and automated payroll in 120 seconds.*

```
 ⏱️ 0:00 ────────────── 0:30 ────────────── 1:00 ────────────── 1:30 ────────────── 2:00
    │                      │                      │                      │              │
    ▼                      ▼                      ▼                      ▼              ▼
 [Stage 1]              [Stage 2]              [Stage 3]              [Stage 4]     [🚀 LIVE]
  Store Profile          Shifts & Pay           Face Enrollment        Terminal      Active System
  & Branding             Templates              (10 Staff)             Activation
```

### Stage 1: Store Profile & Brand Setup (0:00 – 0:30)
1. **Enter Business Name**: Enter `"The Retail Store"` and unique store slug (`the-retail-store`).
2. **Select Brand Theme**: Choose the **Warm Academic / Terracotta** theme (`#c2410c`) to match store interior branding.
3. **Set Store Location**: Add flagship address (*Titanium Square, S.G. Highway, Thaltej, Ahmedabad*).

### Stage 2: Shifts, Leaves & Salary Templates (0:30 – 1:00)
1. **Create Work Shifts**:
   - *Morning Shift*: `08:00 AM – 04:00 PM` (15 min grace period).
   - *Evening Shift*: `12:00 PM – 10:00 PM` (15 min grace period).
2. **Confirm Leave Quotas**: Standard 12 CL, 10 ML, 15 EL pre-loaded automatically.
3. **Assign Salary Templates**: Choose *Store Management (Structured)* for leadership and *Floor Sales (Monthly Fixed)* for team members.

### Stage 3: Instant Biometric Employee Enrollment (1:00 – 1:30)
1. **Add Staff Profiles**: Input staff names, roll numbers, and designations.
2. **Capture 3 Reference Photos**: Using the built-in webcam or employee self-onboarding link, capture Front, Left, and Right angles.
3. **AI Vector Generation**: The system extracts 128-d biometric embeddings in < 200 milliseconds per person.

### Stage 4: Activate Live Terminal & Go Live! (1:30 – 2:00)
1. **Launch Live Camera Feed**: Click **"Start Attendance Capture"** on the admin dashboard.
2. **Share Employee Portal**: Distribute `/employee/the-retail-store` to staff for one-tap mobile face login.
3. **🎉 System Ready**: Staff can now mark attendance, managers monitor live feeds, and payroll calculates automatically.

---

## 🏬 Part 3: "The Retail Store" Real-World Demonstration Proof

### 1. Store Master Configuration

| Parameter | Demonstration Value | Purpose / Benefit |
| :--- | :--- | :--- |
| **Business Name** | The Retail Store | Brand Header & Portal Title |
| **Store Slug** | `the-retail-store` | Unique URL: `/employee/the-retail-store` |
| **Flagship Location** | Titanium Square, S.G. Highway, Ahmedabad - 380054 | Store Geofence & Location Master |
| **Color Scheme** | Warm Academic Terracotta (`#c2410c`) | Dynamic Tenant Theme Inheritance |
| **Attendance Cooldown** | 1 Minute Sliding Window | Zero duplicate punches |
| **Overtime Multiplier** | 1.5x Regular / 2.0x Holiday | Automated OT calculation |
| **Indian Statutory Rules** | EPF (₹15,000 cap), ESIC (< ₹21,000 gross), Gujarat PT (₹200) | 100% Tax & Labor Law Compliance |

---

### 2. Seeded 10-Employee Roster & Payroll Breakdown

| ID | Employee Name | Designation | Department | Monthly CTC | Net Take-Home | Key Statutory Coverage |
| :---: | :--- | :--- | :--- | :---: | :---: | :--- |
| **#1765** | **Chirag Patel** | Store Manager | Store Operations | ₹65,000 | **₹59,200** | EPF Capped (₹1,800), Gujarat PT (₹200) |
| **#1766** | **Dhaval Shah** | Assistant Manager | Store Operations | ₹45,000 | **₹41,000** | EPF Capped (₹1,800), Gujarat PT (₹200) |
| **#1767** | **Pranshu Patel** | Visual Merchandiser | Store Operations | ₹32,000 | **₹29,100** | EPF Capped (₹1,800), Gujarat PT (₹200) |
| **#1768** | **Hiren Parmar** | Inventory Lead | Inventory & Logistics | ₹28,000 | **₹25,400** | EPF Capped (₹1,800), Gujarat PT (₹200) |
| **#1769** | **Mayur Patel** | Logistics Coordinator | Inventory & Logistics | ₹22,000 | **₹19,900** | EPF Capped (₹1,800), Gujarat PT (₹200) |
| **#1770** | **Sachin Dave** | Senior Cashier | Customer Billing | ₹19,500 | **₹17,450** | ESIC Active (0.75%), EPF, Gujarat PT |
| **#1771** | **Vijay Patel** | Customer Care Specialist | Customer Billing | ₹18,000 | **₹16,100** | ESIC Active (0.75%), EPF, Gujarat PT |
| **#1772** | **Sagar Patel** | Senior Sales Specialist | Store Operations | ₹20,000 | **₹17,900** | ESIC Active (0.75%), EPF, Gujarat PT |
| **#1773** | **Het Patel** | Store Associate | Store Operations | ₹16,500 | **₹14,750** | ESIC Active (0.75%), EPF, Gujarat PT |
| **#1774** | **Anand Parekh** | Security Lead | Store Operations | ₹17,000 | **₹15,200** | ESIC Active (0.75%), EPF, Gujarat PT |

---

### 3. August 2026 Processed Payroll Summary

- **Total Staff Processed**: 10 Employees
- **Gross Payroll Disbursed**: ₹3,02,500
- **Total Employee Statutory Deductions (EPF + ESIC + PT)**: ₹26,500
- **Total Net Salaries Disbursed**: ₹2,76,000
- **Employer Statutory Contributions (EPF + ESIC)**: ₹28,150
- **Payslips Generated**: 10 Itemized Digital & Printable Payslips

---

## 🎯 Key Takeaways for Prospective Clients

1. **Zero Hardware Investment**: Start immediately with existing store webcams or mobile phones.
2. **Zero Payroll Calculation Headaches**: Attendance automatically turns into fully compliant payslips with EPF, ESIC, and PT.
3. **Frictionless 2-Minute Onboarding**: No complex multi-week implementations — launch your store in under 120 seconds.
4. **Delightful Employee Experience**: Touchless face check-in and private mobile self-service portals staff love using.
