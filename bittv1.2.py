#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════╗
║  🚀 DATA EXTRACTOR PRO - REAL-TIME SAVING                ║
║  ──────────────────────────────────────────────────────────  ║
║  Version: 7.0.0-sith-realtime                             ║
╚══════════════════════════════════════════════════════════════╝

មុខងារ:
  ✓ ទាញយកទិន្នន័យទាំងអស់ពី API
  ✓ Multithreading សម្រាប់ល្បឿនលឿន
  ✓ រក្សាទុកជា CSV ភ្លាមៗពេលទាញយក
  ✓ រក្សាទុករៀងរាល់ 500 ជួរ
  ✓ ទម្រង់ CSV: ID,Email,Name,Account_Type,Phone,Gender,DateOfBirth,RegistrationNumber,Province,District,School,Grade,Class
"""

import requests
import json
import csv
import time
import os
import threading
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional

# ============================================================
# CONFIGURATION
# ============================================================

BASE_URL = "https://admin.fedrupp.org"
API_URL = f"{BASE_URL}/Table/users"

COOKIES = {
    "ci_session": "783996fd9100e70d56e3bc8743877fbada62f3da",
    "csrf_cookie_name": "a6b757ea5575c13e08d1a0d76a0b324c",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://admin.fedrupp.org/users",
    "X-Requested-With": "XMLHttpRequest",
    "Accept": "application/json, text/plain, */*",
}

# ============================================================
# SETTINGS
# ============================================================

LIMIT_PER_PAGE = 5000
MAX_WORKERS = 10
OUTPUT_DIR = "exported_data"
SAVE_INTERVAL = 5000  # រក្សាទុករៀងរាល់ 500 ជួរ

# ============================================================
# COLUMN MAPPING
# ============================================================

CSV_COLUMNS = [
    "ID",
    "Email",
    "Name",
    "Account_Type",
    "Phone",
    "Gender",
    "DateOfBirth",
    "RegistrationNumber",
    "Province",
    "District",
    "School",
    "Grade",
    "Class"
]

COLUMN_MAPPING = {
    "id": "ID",
    "email": "Email",
    "name": "Name",
    "account_type": "Account_Type",
    "mobile": "Phone",
    "gender": "Gender",
    "dob": "DateOfBirth",
    "enrollment_number": "RegistrationNumber",
    "province_name": "Province",
    "district_name": "District",
    "high_school_name": "School",
    "grade": "Grade",
    "class": "Class"
}

# ============================================================
# GLOBAL VARIABLES
# ============================================================

all_data = []
data_lock = threading.Lock()
csv_file_path = None
csv_writer = None
csv_file = None
total_saved = 0
emails_list = []

# ============================================================
# HELPER FUNCTIONS
# ============================================================

def create_session():
    session = requests.Session()
    session.cookies.update(COOKIES)
    session.headers.update(HEADERS)
    return session

def fetch_page(session, page: int, limit: int = LIMIT_PER_PAGE) -> tuple:
    params = {
        "page": page,
        "limit": limit,
        "sort": "id",
        "order": "desc",
    }
    
    try:
        response = session.get(API_URL, params=params, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        rows = data.get("rows", [])
        total = int(data.get("total", 0))
        
        return rows, total
    except Exception as e:
        print(f"[!] កំហុសទំព័រ {page}: {e}")
        return [], 0

def get_total_pages(session) -> int:
    _, total = fetch_page(session, 1, 1)
    return total

def clean_value(value):
    if value is None:
        return ""
    if isinstance(value, (int, float)):
        return str(value)
    return str(value).strip()

def extract_csv_row(row: Dict) -> Dict:
    result = {}
    for api_key, csv_key in COLUMN_MAPPING.items():
        value = row.get(api_key, "")
        result[csv_key] = clean_value(value)
    return result

def init_csv_file(output_dir: str):
    """បង្កើតឯកសារ CSV និងសរសេរ Header"""
    global csv_file_path, csv_file, csv_writer
    
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_file_path = os.path.join(output_dir, f"users_data_{timestamp}.csv")
    
    csv_file = open(csv_file_path, "w", newline="", encoding="utf-8-sig")
    csv_writer = csv.DictWriter(csv_file, fieldnames=CSV_COLUMNS)
    csv_writer.writeheader()
    csv_file.flush()
    
    print(f"[+] CSV: {csv_file_path}")
    return csv_file_path

def save_rows_to_csv(rows: List[Dict]):
    """រក្សាទុកជួរដេកទៅ CSV ភ្លាមៗ"""
    global csv_writer, csv_file, total_saved, emails_list
    
    if not rows:
        return
    
    with data_lock:
        for row in rows:
            csv_row = extract_csv_row(row)
            csv_writer.writerow(csv_row)
            
            # ប្រមូលអ៊ីមែល
            email = row.get("email", "")
            if email:
                emails_list.append(email)
        
        csv_file.flush()
        total_saved += len(rows)
        print(f"   💾 បានរក្សាទុក {len(rows)} ជួរ (សរុប: {total_saved:,})")

def save_emails(output_dir: str, timestamp: str):
    """រក្សាទុកអ៊ីមែល"""
    if emails_list:
        email_file = os.path.join(output_dir, f"emails_{timestamp}.txt")
        with open(email_file, "w", encoding="utf-8") as f:
            f.write("\n".join(emails_list))
        print(f"[+] Emails: {email_file} ({len(emails_list):,} អ៊ីមែល)")

def close_csv():
    """បិទឯកសារ CSV"""
    global csv_file
    if csv_file:
        csv_file.close()

# ============================================================
# FETCH ALL DATA WITH REAL-TIME SAVING
# ============================================================

def fetch_all_pages_parallel(output_dir: str = OUTPUT_DIR):
    global all_data, total_saved
    
    session = create_session()
    
    total_rows = get_total_pages(session)
    if total_rows == 0:
        print("[!] គ្មានទិន្នន័យ")
        return []
    
    total_pages = (total_rows + LIMIT_PER_PAGE - 1) // LIMIT_PER_PAGE
    
    # បង្កើតឯកសារ CSV
    init_csv_file(output_dir)
    
    print(f"[+] ទិន្នន័យសរុប: {total_rows:,} ជួរ")
    print(f"[+] ចំនួនទំព័រ: {total_pages:,}")
    print(f"[+] Threads: {MAX_WORKERS}")
    print(f"[+] Save interval: {SAVE_INTERVAL} ជួរ")
    print("="*60)
    
    all_data = []
    lock = threading.Lock()
    progress = {"count": 0, "saved_count": 0}
    
    def fetch_page_thread(page):
        session_local = create_session()
        rows, _ = fetch_page(session_local, page)
        
        with lock:
            progress["count"] += len(rows)
            
            # រក្សាទុកភ្លាមៗ
            save_rows_to_csv(rows)
            
            print(f"   បានទាញយកទំព័រ {page:4d} → {len(rows):,} ជួរ (សរុប: {progress['count']:,})")
        
        return rows
    
    print("[+] កំពុងទាញយក និងរក្សាទុកភ្លាមៗ...")
    start_time = time.time()
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(fetch_page_thread, page): page for page in range(1, total_pages + 1)}
        
        for future in as_completed(futures):
            try:
                rows = future.result()
                all_data.extend(rows)
            except Exception as e:
                page = futures[future]
                print(f"[!] កំហុសទំព័រ {page}: {e}")
    
    elapsed = time.time() - start_time
    
    # បិទឯកសារ CSV
    close_csv()
    
    print(f"\n[+] ទាញយករួចរាល់ក្នុង {elapsed:.2f} វិនាទី")
    print(f"[+] បានទាញយក {len(all_data):,} / {total_rows:,} ជួរ")
    print(f"[+] បានរក្សាទុក {total_saved:,} ជួរ ក្នុង CSV")
    
    # រក្សាទុកអ៊ីមែល
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    save_emails(output_dir, timestamp)
    
    return all_data

# ============================================================
# MAIN FUNCTION
# ============================================================

def main():
    print("="*60)
    print("  🚀 DATA EXTRACTOR PRO - REAL-TIME SAVING")
    print("="*60)
    print(f"[+] API: {API_URL}")
    print(f"[+] Limit per page: {LIMIT_PER_PAGE}")
    print(f"[+] Max threads: {MAX_WORKERS}")
    print(f"[+] Output: {OUTPUT_DIR}/")
    print("="*60)
    
    start_time = time.time()
    
    # 1. ទាញយក និងរក្សាទុកភ្លាមៗ
    data = fetch_all_pages_parallel()
    
    if not data:
        print("[!] គ្មានទិន្នន័យ")
        return
    
    elapsed = time.time() - start_time
    print("\n" + "="*60)
    print(f"  ✅ បានបញ្ចប់ក្នុង {elapsed:.2f} វិនាទី")
    print(f"  📊 ទិន្នន័យសរុប: {len(data):,} ជួរ")
    print(f"  📁 Output: {OUTPUT_DIR}/")
    print("="*60)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[!] អ្នកបានបញ្ឈប់កម្មវិធី")
        close_csv()