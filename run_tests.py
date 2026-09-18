#!/usr/bin/env python3
"""
Targeted & Selective Test Runner for Attendance System
Enables modular, fast feedback loops during daily development with automatic post-test hygiene.

Usage Examples:
  python run_tests.py --suite payroll          # Run all payroll tests (~8-10s)
  python run_tests.py --suite attendance       # Run all attendance & shift tests (~7-9s)
  python run_tests.py --suite masters          # Run company locations & designations (~5-7s)
  python run_tests.py --quick                  # Run all fast modular tests (~15-20s)
  python run_tests.py --file location          # Run any test file matching 'location'
  python run_tests.py --failfast               # Stop execution immediately on first error
  python run_tests.py --full                   # Full 136-test pre-deployment gate
  python run_tests.py --list                   # List all available suites and descriptions
"""

import sys
import os
import time
import argparse
import unittest
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from tests.suites import SUITES, SUITE_DESCRIPTIONS
from src.database.session import SessionLocal
from src.database.models import (
    Tenant, Student, CompanyLocation, DesignationMaster, SalaryTemplate, 
    SalaryComponent, PayrollBatch, EmployeeSalaryStructure, AttendanceRecord
)

def purge_test_database_records(verbose: bool = True):
    """Purges any temporary test records created during test runs."""
    db = SessionLocal()
    try:
        purged_counts = {"locations": 0, "templates": 0, "tenants": 0}
        
        # 1. Test Company Locations
        test_locs = db.query(CompanyLocation).filter(
            CompanyLocation.name.ilike("%test%") | CompanyLocation.code.ilike("%test%")
        ).all()
        purged_counts["locations"] = len(test_locs)
        for loc in test_locs:
            db.delete(loc)

        # 2. Test Salary Templates
        test_tpls = db.query(SalaryTemplate).filter(
            SalaryTemplate.name.ilike("%test%") | SalaryTemplate.code.ilike("%test%")
        ).all()
        purged_counts["templates"] = len(test_tpls)
        for tpl in test_tpls:
            db.delete(tpl)

        # 3. Test Tenants
        test_tenants = db.query(Tenant).filter(
            Tenant.slug.in_(["testcorp_refine", "test_corporate_sub", "temp_test_tenant"])
        ).all()
        purged_counts["tenants"] = len(test_tenants)
        for t in test_tenants:
            db.delete(t)

        db.commit()
        total = sum(purged_counts.values())
        if verbose:
            if total > 0:
                print(f"[DB Hygiene] Purged {total} temporary test record(s) ({purged_counts['locations']} locations, {purged_counts['templates']} templates, {purged_counts['tenants']} tenants).")
            else:
                print("[DB Hygiene] Database is clean. 0 leftover test records found.")
    except Exception as e:
        db.rollback()
        if verbose:
            print(f"[DB Hygiene Warning] Purge failed: {e}")
    finally:
        db.close()


def print_suite_list():
    """Prints all available suites and their descriptions."""
    print("=" * 70)
    print("  AVAILABLE TARGETED TEST SUITES")
    print("=" * 70)
    for suite_name, desc in SUITE_DESCRIPTIONS.items():
        files = SUITES.get(suite_name, [])
        file_count = len(files)
        print(f"\n  * {suite_name.upper():<12} ({file_count} test files)")
        print(f"    Description: {desc}")
        if suite_name not in ["quick", "full", "pre-deploy"]:
            print(f"    Files: {', '.join(files)}")
    print("\n" + "=" * 70)


def build_test_suite(test_files: list, failfast: bool = False):
    """Builds a unittest.TestSuite from a list of test files."""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    tests_dir = PROJECT_ROOT / "tests"

    for file_name in test_files:
        clean_name = str(file_name).replace("/", ".").replace("\\", ".")
        if clean_name.endswith(".py"):
            clean_name = clean_name[:-3]

        if not clean_name.startswith("tests."):
            target_py = tests_dir / f"{file_name}"
            if not target_py.exists():
                found = list(tests_dir.glob(f"**/{Path(file_name).name}"))
                if found:
                    rel_path = found[0].relative_to(PROJECT_ROOT)
                    clean_name = str(rel_path.with_suffix("")).replace("/", ".").replace("\\", ".")
                else:
                    clean_name = f"tests.{clean_name}"
            else:
                rel_path = target_py.relative_to(PROJECT_ROOT)
                clean_name = str(rel_path.with_suffix("")).replace("/", ".").replace("\\", ".")

        module_name = clean_name
        try:
            mod_suite = loader.loadTestsFromName(module_name)
            suite.addTest(mod_suite)
        except Exception as e:
            print(f"[!] Error loading test module '{module_name}': {e}")
            raise e

    return suite


def main():
    parser = argparse.ArgumentParser(
        description="Selective & Targeted Test Runner for Attendance System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "-s", "--suite",
        choices=list(SUITES.keys()),
        help="Run a predefined test suite (payroll, attendance, masters, auth, ui, cv, unit, integration, quick, system, full)",
    )
    parser.add_argument(
        "-f", "--file",
        help="Run a specific test file or substring pattern (e.g. 'location' or 'test_indian_payroll.py')",
    )
    parser.add_argument(
        "-x", "--failfast",
        action="store_true",
        help="Stop test execution immediately upon first failure",
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Run all fast modular test suites (~15-20s)",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Run the complete 136-test pre-deployment verification gate (~70-90s)",
    )
    parser.add_argument(
        "-l", "--list",
        action="store_true",
        help="List all available test suites and exit",
    )
    parser.add_argument(
        "--no-purge",
        action="store_true",
        help="Skip automatic post-test database record purging",
    )
    parser.add_argument(
        "-v", "--verbose",
        type=int,
        default=2,
        choices=[1, 2],
        help="Test runner verbosity level (1=normal, 2=verbose)",
    )

    args = parser.parse_args()

    if args.list:
        print_suite_list()
        return 0

    # Determine target files
    target_files = []
    suite_label = "CUSTOM"

    if args.full:
        target_files = SUITES["full"]
        suite_label = "FULL PRE-DEPLOYMENT GATE"
    elif args.quick:
        target_files = SUITES["quick"]
        suite_label = "QUICK MODULAR SUITE"
    elif args.suite:
        target_files = SUITES[args.suite]
        suite_label = f"SUITE: {args.suite.upper()}"
    elif args.file:
        pattern = args.file.lower().replace(".py", "")
        tests_dir = PROJECT_ROOT / "tests"
        all_test_files = [str(f.relative_to(tests_dir)).replace("\\", "/") for f in tests_dir.glob("**/test_*.py")]
        matching = [f for f in all_test_files if pattern in f.lower()]
        if not matching:
            print(f"[!] No test files found matching pattern: '{args.file}'")
            print(f"    Available test files: {', '.join(all_test_files)}")
            return 1
        target_files = matching
        suite_label = f"FILE PATTERN: '{args.file}'"
    else:
        # Default action: run quick suite
        target_files = SUITES["quick"]
        suite_label = "QUICK MODULAR SUITE (Default)"

    print("=" * 70)
    print(f"  ATTENDANCE SYSTEM TEST RUNNER: {suite_label}")
    print(f"  Files to execute: {len(target_files)} test module(s)")
    if args.failfast:
        print("  Fast-Fail Mode: ENABLED (Stops on first error)")
    print("=" * 70)
    for i, tf in enumerate(target_files, 1):
        print(f"  [{i:02d}] {tf}")
    print("=" * 70 + "\n")

    start_time = time.time()

    # Load and build test suite
    test_suite = build_test_suite(target_files, failfast=args.failfast)
    runner = unittest.TextTestRunner(
        verbosity=args.verbose,
        failfast=args.failfast,
    )
    result = runner.run(test_suite)
    elapsed = time.time() - start_time

    # Print Summary Card
    print("\n" + "=" * 70)
    print("  TEST RUN SUMMARY REPORT")
    print("=" * 70)
    print(f"  Status:       {'[PASS] SUCCESS' if result.wasSuccessful() else '[FAIL] FAILED'}")
    print(f"  Tests Run:    {result.testsRun}")
    print(f"  Failures:     {len(result.failures)}")
    print(f"  Errors:       {len(result.errors)}")
    print(f"  Skipped:      {len(result.skipped)}")
    print(f"  Total Time:   {elapsed:.2f} seconds")
    print("=" * 70)

    # Post-Test Database Purge
    if not args.no_purge:
        purge_test_database_records(verbose=True)

    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
