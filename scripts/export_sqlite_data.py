#!/usr/bin/env python3
"""
Export SQLite data to JSON files for DynamoDB migration
Run this script to extract all data from your current SQLite database
"""

import sqlite3
import json
import uuid
import os
from datetime import datetime
from pathlib import Path

# Database path
DATABASE_PATH = "test.db"  # Update this if your database is elsewhere
OUTPUT_DIR = "migration_data"

def ensure_output_dir():
    """Create output directory if it doesn't exist"""
    Path(OUTPUT_DIR).mkdir(exist_ok=True)

def export_users():
    """Export users table to JSON"""
    print("Exporting users...")
    
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT * FROM users")
        users = []
        
        for row in cursor.fetchall():
            user = {
                "user_id": f"usr_{uuid.uuid4()}",
                "email": row["email"],
                "username": row["username"],
                "password_hash": row["password_hash"],
                "first_name": row["first_name"] or "",
                "last_name": row["last_name"] or "",
                "phone_number": row["phone_number"] or "",
                "role": row["role"],
                "is_active": bool(row["is_active"]),
                "is_verified": bool(row["is_verified"]),
                "created_at": row["created_at"] or datetime.utcnow().isoformat() + "Z",
                "updated_at": row["updated_at"] or datetime.utcnow().isoformat() + "Z",
                "last_login": row["last_login"] or "",
                "original_id": row["id"]  # Keep for reference mapping
            }
            users.append(user)
        
        with open(f"{OUTPUT_DIR}/users.json", "w") as f:
            json.dump(users, f, indent=2)
        
        print(f"Exported {len(users)} users")
        return users
        
    except sqlite3.Error as e:
        print(f"Error exporting users: {e}")
        return []
    finally:
        conn.close()

def export_lab_tests():
    """Export lab_tests table to JSON"""
    print("Exporting lab tests...")
    
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT * FROM lab_tests")
        tests = []
        
        for row in cursor.fetchall():
            test = {
                "test_id": f"test_{uuid.uuid4()}",
                "name": row["name"],
                "code": row["code"],
                "description": row["description"] or "",
                "category": row["category"],
                "sub_category": row["sub_category"] or "",
                "sample_type": row["sample_type"] or "",
                "requirements": row["requirements"] or "",
                "procedure": row["procedure"] or "",
                "price": int(float(row["price"]) * 100),  # Convert to paisa
                "duration_minutes": row["duration_minutes"] or 30,
                "report_delivery_hours": row["report_delivery_hours"] or 24,
                "is_active": bool(row["is_active"]),
                "is_home_collection_available": bool(row["is_home_collection_available"]),
                "minimum_age": row["minimum_age"] or 0,
                "maximum_age": row["maximum_age"] or 120,
                "reference_ranges": row["reference_ranges"] or "{}",
                "units": row["units"] or "",
                "created_at": row["created_at"] or datetime.utcnow().isoformat() + "Z",
                "updated_at": row["updated_at"] or datetime.utcnow().isoformat() + "Z",
                "original_id": row["id"]  # Keep for reference mapping
            }
            tests.append(test)
        
        with open(f"{OUTPUT_DIR}/lab_tests.json", "w") as f:
            json.dump(tests, f, indent=2)
        
        print(f"Exported {len(tests)} lab tests")
        return tests
        
    except sqlite3.Error as e:
        print(f"Error exporting lab tests: {e}")
        return []
    finally:
        conn.close()

def export_reports(users, lab_tests):
    """Export reports table to JSON"""
    print("Exporting reports...")
    
    # Create mapping dictionaries
    user_id_map = {user["original_id"]: user["user_id"] for user in users}
    test_id_map = {test["original_id"]: test["test_id"] for test in lab_tests}
    
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT * FROM reports")
        reports = []
        
        for row in cursor.fetchall():
            report = {
                "report_id": f"rpt_{uuid.uuid4()}",
                "user_id": user_id_map.get(row["user_id"], f"usr_{uuid.uuid4()}"),
                "lab_test_id": test_id_map.get(row["lab_test_id"], f"test_{uuid.uuid4()}"),
                "report_number": row["report_number"],
                "status": row["status"],
                "scheduled_at": row["scheduled_at"] or "",
                "collected_at": row["collected_at"] or "",
                "tested_at": row["tested_at"] or "",
                "reviewed_at": row["reviewed_at"] or "",
                "delivered_at": row["delivered_at"] or "",
                "sample_collected_by": row["sample_collected_by"] or "",
                "collection_location": row["collection_location"] or "",
                "collection_notes": row["collection_notes"] or "",
                "results": row["results"] or "{}",
                "observations": row["observations"] or "",
                "recommendations": row["recommendations"] or "",
                "s3_file_key": row["file_path"] or "",
                "file_original_name": row["file_original_name"] or "",
                "file_size": row["file_size"] or 0,
                "file_type": row["file_type"] or "",
                "is_shared": bool(row["is_shared"]),
                "shared_at": row["shared_at"] or "",
                "shared_with": row["shared_with"] or "",
                "is_verified": bool(row["is_verified"]),
                "verified_by": row["verified_by"] or "",
                "verified_at": row["verified_at"] or "",
                "amount_charged": row["amount_charged"] or 0,
                "payment_status": row["payment_status"] or "pending",
                "payment_reference": row["payment_reference"] or "",
                "notes": row["notes"] or "",
                "priority": row["priority"] or "normal",
                "created_at": row["created_at"] or datetime.utcnow().isoformat() + "Z",
                "updated_at": row["updated_at"] or datetime.utcnow().isoformat() + "Z",
                "original_id": row["id"]  # Keep for reference mapping
            }
            reports.append(report)
        
        with open(f"{OUTPUT_DIR}/reports.json", "w") as f:
            json.dump(reports, f, indent=2)
        
        print(f"Exported {len(reports)} reports")
        return reports
        
    except sqlite3.Error as e:
        print(f"Error exporting reports: {e}")
        return []
    finally:
        conn.close()

def export_bookings(users, lab_tests):
    """Export bookings table to JSON"""
    print("Exporting bookings...")
    
    # Create mapping dictionaries
    user_id_map = {user["original_id"]: user["user_id"] for user in users}
    test_id_map = {test["original_id"]: test["test_id"] for test in lab_tests}
    
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT * FROM bookings")
        bookings = []
        
        for row in cursor.fetchall():
            booking = {
                "booking_id": f"book_{uuid.uuid4()}",
                "user_id": user_id_map.get(row["user_id"], f"usr_{uuid.uuid4()}"),
                "test_id": test_id_map.get(row["test_id"], f"test_{uuid.uuid4()}"),
                "booking_reference": row["booking_reference"],
                "patient_name": row["patient_name"],
                "patient_age": row["patient_age"],
                "patient_gender": row["patient_gender"],
                "appointment_date": row["appointment_date"],
                "home_collection": bool(row["home_collection"]),
                "address": row["address"] or "",
                "phone_number": row["phone_number"],
                "special_instructions": row["special_instructions"] or "",
                "status": row["status"],
                "admin_notes": row["admin_notes"] or "",
                "cancellation_reason": row["cancellation_reason"] or "",
                "created_at": row["created_at"] or datetime.utcnow().isoformat() + "Z",
                "updated_at": row["updated_at"] or datetime.utcnow().isoformat() + "Z",
                "cancelled_at": row["cancelled_at"] or "",
                "completed_at": row["completed_at"] or "",
                "original_id": row["id"]  # Keep for reference mapping
            }
            bookings.append(booking)
        
        with open(f"{OUTPUT_DIR}/bookings.json", "w") as f:
            json.dump(bookings, f, indent=2)
        
        print(f"Exported {len(bookings)} bookings")
        return bookings
        
    except sqlite3.Error as e:
        print(f"Error exporting bookings: {e}")
        return []
    finally:
        conn.close()

def main():
    """Main export function"""
    print("Starting SQLite to DynamoDB data export...")
    
    if not os.path.exists(DATABASE_PATH):
        print(f"Database file {DATABASE_PATH} not found!")
        print("Please update the DATABASE_PATH variable in this script.")
        return
    
    ensure_output_dir()
    
    # Export data in dependency order
    users = export_users()
    lab_tests = export_lab_tests()
    reports = export_reports(users, lab_tests)
    bookings = export_bookings(users, lab_tests)
    
    # Create ID mapping file for reference
    id_mappings = {
        "users": {user["original_id"]: user["user_id"] for user in users},
        "lab_tests": {test["original_id"]: test["test_id"] for test in lab_tests},
        "reports": {report["original_id"]: report["report_id"] for report in reports},
        "bookings": {booking["original_id"]: booking["booking_id"] for booking in bookings}
    }
    
    with open(f"{OUTPUT_DIR}/id_mappings.json", "w") as f:
        json.dump(id_mappings, f, indent=2)
    
    print(f"\nExport completed!")
    print(f"Data exported to {OUTPUT_DIR}/ directory")
    print(f"Total records: Users={len(users)}, Tests={len(lab_tests)}, Reports={len(reports)}, Bookings={len(bookings)}")
    print("\nNext step: Run the upload script to migrate data to DynamoDB")

if __name__ == "__main__":
    main()