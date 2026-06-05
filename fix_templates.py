"""
Run this from your project root:
  python fix_templates.py

It will fix all colon-style URL names across every template file.
"""

import os
import glob

REPLACEMENTS = [
    ("patient:dashboard",            "patient_dashboard"),
    ("patient:symptom_entry",        "patient_symptom_entry"),
    ("patient:visit_history",        "patient_visit_history"),
    ("patient:visit_detail",         "patient_visit_detail"),
    ("patient:facility_finder",      "patient_facility_finder"),
    ("patient:change_facility",      "patient_change_facility"),
    ("patient:emergency",            "patient_emergency"),
    ("reception:dashboard",          "reception_dashboard"),
    ("reception:register_visit",     "reception_register_visit"),
    ("nurse:dashboard",              "nurse_dashboard"),
    ("nurse:vitals_entry",           "nurse_vitals_entry"),
    ("doctor:dashboard",             "doctor_dashboard"),
    ("doctor:consultation",          "doctor_consultation"),
    ("doctor:patient_history",       "doctor_patient_history"),
    ("doctor:referral_form",         "doctor_referral_form"),
    ("lab:dashboard",                "lab_dashboard"),
    ("lab:results_entry",            "lab_results_entry"),
    ("pharmacy:dashboard",           "pharmacy_dashboard"),
    ("pharmacy:dispense",            "pharmacy_dispense"),
    ("billing:dashboard",            "billing_dashboard"),
    ("billing:invoice",              "billing_invoice"),
    ("supervisor:dashboard",         "supervisor_dashboard"),
    ("supervisor:stock_entry",       "supervisor_stock_entry"),
    ("supervisor:stock_report",      "supervisor_stock_report"),
    ("admin_panel:dashboard",        "admin_panel_dashboard"),
    ("admin_panel:manage_facilities","admin_panel_manage_facilities"),
]

files = glob.glob("templates/**/*.html", recursive=True) + \
        glob.glob("templates/*.html")

total_fixed = 0

for path in files:
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    original = content
    for old, new in REPLACEMENTS:
        content = content.replace(old, new)
    if content != original:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"  Fixed: {path}")
        total_fixed += 1

print(f"\nDone. {total_fixed} file(s) updated.")
