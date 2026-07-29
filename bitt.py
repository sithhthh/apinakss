#!/usr/bin/env python3
"""
Data Extractor Pro - ទាញយកទិន្នន័យទាំងអស់ពី admin.fedrupp.org
ប្រើ Multithreading ដើម្បីទាញយកលឿន
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
# ការកំណត់រចនាសម្ព័ន្ធ
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
# ការកំណត់សម្រាប់ការទាញយក
# ============================================================

LIMIT_PER_PAGE = 5000          # ចំនួនក្នុងមួយសំណើ
MAX_WORKERS = 10               # ចំនួន Threads ស្របគ្នា
OUTPUT_DIR = "exported_data"   # ថតសម្រាប់រក្សាទុក

# ============================================================
# មុខងារជំនួយ
# ============================================================

def create_session():
    """បង្កើត Session"""
    session = requests.Session()
    session.cookies.update(COOKIES)
    session.headers.update(HEADERS)
    return session

def fetch_page(session, page: int, limit: int = LIMIT_PER_PAGE) -> tuple:
    """ទាញយកទិន្នន័យពីទំព័រមួយ"""
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
    """យកចំនួនទំព័រសរុប"""
    _, total = fetch_page(session, 1, 1)
    return total

def fetch_all_pages_parallel() -> List[Dict]:
    """ទាញយកទិន្នន័យទាំងអស់ដោយប្រើ Multithreading"""
    
    session = create_session()
    
    # 1. យកចំនួនសរុប
    total_rows = get_total_pages(session)
    if total_rows == 0:
        print("[!] គ្មានទិន្នន័យ")
        return []
    
    total_pages = (total_rows + LIMIT_PER_PAGE - 1) // LIMIT_PER_PAGE
    print(f"[+] ទិន្នន័យសរុប: {total_rows:,} ជួរ")
    print(f"[+] ចំនួនទំព័រ: {total_pages:,}")
    print(f"[+] Threads: {MAX_WORKERS}")
    print("="*60)
    
    all_data = []
    lock = threading.Lock()
    progress = {"count": 0}
    
    def fetch_page_thread(page):
        """មុខងារសម្រាប់ Thread"""
        session_local = create_session()
        rows, _ = fetch_page(session_local, page)
        
        with lock:
            progress["count"] += len(rows)
            print(f"   បានទាញយកទំព័រ {page:4d} → {len(rows):,} ជួរ (សរុប: {progress['count']:,})")
        
        return rows
    
    # 2. ទាញយកដោយប្រើ Threads
    print("[+] កំពុងទាញយក...")
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
    print(f"\n[+] ទាញយករួចរាល់ក្នុង {elapsed:.2f} វិនាទី")
    print(f"[+] បានទាញយក {len(all_data):,} / {total_rows:,} ជួរ")
    
    return all_data

# ============================================================
# មុខងាររក្សាទុក
# ============================================================

def save_data(data: List[Dict], output_dir: str = OUTPUT_DIR):
    """រក្សាទុកទិន្នន័យជា JSON, CSV, និង Emails"""
    if not data:
        print("[!] គ្មានទិន្នន័យ")
        return
    
    # បង្កើតថត
    os.makedirs(output_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # ============================================================
    # 1. រក្សាទុក JSON
    # ============================================================
    json_file = os.path.join(output_dir, f"users_data_{timestamp}.json")
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"[+] JSON: {json_file}")
    
    # ============================================================
    # 2. រក្សាទុក CSV (ពេញលេញ)
    # ============================================================
    if isinstance(data[0], dict):
        keys = set()
        for row in data:
            keys.update(row.keys())
        keys = sorted(keys)
        
        csv_file = os.path.join(output_dir, f"users_data_{timestamp}.csv")
        with open(csv_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            writer.writerows(data)
        print(f"[+] CSV: {csv_file}")
    
    # ============================================================
    # 3. រក្សាទុកអ៊ីមែល
    # ============================================================
    emails = []
    for row in data:
        if isinstance(row, dict):
            email = row.get("email", "")
            if email:
                emails.append(email)
    
    if emails:
        email_file = os.path.join(output_dir, f"emails_{timestamp}.txt")
        with open(email_file, "w", encoding="utf-8") as f:
            f.write("\n".join(emails))
        print(f"[+] Emails: {email_file} ({len(emails):,} អ៊ីមែល)")
    
    # ============================================================
    # 4. រក្សាទុកស្ថិតិ
    # ============================================================
    stats = {
        "export_date": timestamp,
        "total_rows": len(data),
        "total_emails": len(emails),
        "columns": list(keys) if isinstance(data[0], dict) else [],
    }
    
    stats_file = os.path.join(output_dir, f"stats_{timestamp}.json")
    with open(stats_file, "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2, ensure_ascii=False)
    print(f"[+] Stats: {stats_file}")

# ============================================================
# មុខងារសំខាន់
# ============================================================

def main():
    print("="*60)
    print("  🚀 DATA EXTRACTOR PRO")
    print("="*60)
    print(f"[+] API: {API_URL}")
    print(f"[+] Limit per page: {LIMIT_PER_PAGE}")
    print(f"[+] Max threads: {MAX_WORKERS}")
    print(f"[+] Output: {OUTPUT_DIR}/")
    print("="*60)
    
    start_time = time.time()
    
    # 1. ទាញយកទិន្នន័យ
    data = fetch_all_pages_parallel()
    
    if not data:
        print("[!] គ្មានទិន្នន័យ")
        return
    
    # 2. រក្សាទុក
    print("\n[+] កំពុងរក្សាទុក...")
    save_data(data)
    
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