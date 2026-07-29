#!/usr/bin/env python3
"""
Data Extractor Pro - ជាមួយ Save/Load (Resume) និង Custom Limit
ទាញយកទិន្នន័យពី admin.fedrupp.org/Table/users
"""

import requests
import json
import csv
import time
import os
import sys
from datetime import datetime

# ============================================================
# ការកំណត់រចនាសម្ព័ន្ធ (CONFIGURATION)
# ============================================================

BASE_URL = "https://admin.fedrupp.org"
API_URL = f"{BASE_URL}/Table/users"

# COOKIES (ចម្លងពី cookies.txt របស់អ្នក)
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
# ការកំណត់អ្នកប្រើ (USER SETTINGS)
# ============================================================

LIMIT = 5000              # ចំនួនជួរក្នុងមួយទំព័រ (1000, 2000, 5000, 10000)
TOTAL_ROWS = 421274       # ចំនួនទិន្នន័យសរុប
CHECKPOINT_INTERVAL = 5   # រក្សាទុកបណ្តោះអាសន្នរៀងរាល់ 5 ទំព័រ
CHECKPOINT_FILE = "checkpoint.json"   # ឯកសារបណ្តោះអាសន្ន
OUTPUT_JSON = "users_data_final.json"  # ឯកសារចុងក្រោយ JSON
OUTPUT_CSV = "users_data_final.csv"    # ឯកសារចុងក្រោយ CSV

# ============================================================
# មុខងារជំនួយ
# ============================================================

def create_session():
    """បង្កើត Session ជាមួយ Cookies និង Headers"""
    session = requests.Session()
    session.cookies.update(COOKIES)
    session.headers.update(HEADERS)
    return session

def fetch_page(session, page, limit):
    """ទាញយកទិន្នន័យពី API តាមទំព័រ"""
    params = {
        "page": page,
        "limit": limit,
        "sort": "id",
        "order": "desc",
    }
    
    print(f"[+] កំពុងទាញយកទំព័រ {page} (limit={limit})...")
    
    try:
        response = session.get(API_URL, params=params, timeout=60)
        response.raise_for_status()
        
        data = response.json()
        
        if "rows" in data:
            rows = data["rows"]
        elif "data" in data:
            rows = data["data"]
        else:
            rows = data
        
        if isinstance(rows, dict) and "rows" in rows:
            rows = rows["rows"]
        
        total = data.get("total", len(rows) if isinstance(rows, list) else 0)
        
        if isinstance(rows, list):
            print(f"[+] បានទាញយក {len(rows)} ជួរ (សរុប: {total})")
            return rows, int(total)
        else:
            print(f"[!] ទិន្នន័យមិនមែនជាបញ្ជី: {type(rows)}")
            return [], 0
            
    except requests.exceptions.Timeout:
        print("[!] Timeout! ព្យាយាមបន្ថយ limit")
        return [], 0
    except requests.exceptions.RequestException as e:
        print(f"[!] កំហុសសំណើ: {e}")
        return [], 0
    except json.JSONDecodeError:
        print(f"[!] កំហុស JSON (អាច limit ធំពេក)")
        return [], 0

def save_checkpoint(data, page, filename=CHECKPOINT_FILE):
    """រក្សាទុកទិន្នន័យបណ្តោះអាសន្ន (Checkpoint)"""
    checkpoint = {
        "timestamp": datetime.now().isoformat(),
        "page": page,
        "total_rows": len(data),
        "data": data
    }
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(checkpoint, f, indent=2, ensure_ascii=False)
    print(f"[+] 💾 បានរក្សាទុក Checkpoint (ទំព័រ {page}, {len(data)} ជួរ)")

def load_checkpoint(filename=CHECKPOINT_FILE):
    """ផ្ទុកទិន្នន័យបណ្តោះអាសន្នពី Checkpoint"""
    if os.path.exists(filename):
        try:
            with open(filename, "r", encoding="utf-8") as f:
                checkpoint = json.load(f)
            print(f"[+] 📂 បានផ្ទុក Checkpoint (ទំព័រ {checkpoint.get('page', 0)}, {len(checkpoint.get('data', []))} ជួរ)")
            return checkpoint.get("data", []), checkpoint.get("page", 0)
        except Exception as e:
            print(f"[!] កំហុសពេលផ្ទុក Checkpoint: {e}")
            return [], 0
    return [], 0

def save_final_json(data, filename=OUTPUT_JSON):
    """រក្សាទុកទិន្នន័យចុងក្រោយជា JSON"""
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"[+] 💾 បានរក្សាទុក {len(data)} ជួរ ក្នុង {filename}")

def save_final_csv(data, filename=OUTPUT_CSV):
    """រក្សាទុកទិន្នន័យចុងក្រោយជា CSV"""
    if not data or not isinstance(data[0], dict):
        print("[!] មិនអាចរក្សាទុក CSV (ទិន្នន័យមិនមែនជា dict)")
        return
    
    keys = set()
    for row in data:
        keys.update(row.keys())
    keys = sorted(keys)
    
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(data)
    
    print(f"[+] 💾 បានរក្សាទុក {len(data)} ជួរ ក្នុង {filename}")

def test_limit(session, limit):
    """សាកល្បង limit មុនពេលទាញយកទាំងអស់"""
    print(f"\n[*] 🔍 កំពុងសាកល្បង limit={limit}...")
    rows, total = fetch_page(session, 1, limit)
    
    if rows:
        print(f"[+] ✅ limit={limit} ដំណើរការ! (បាន {len(rows)} ជួរ)")
        return True
    else:
        print(f"[+] ❌ limit={limit} មិនដំណើរការ")
        return False

# ============================================================
# មុខងារសំខាន់
# ============================================================

def main():
    print("="*70)
    print("  🚀 DATA EXTRACTOR PRO - ជាមួយ Save/Load (Resume)")
    print("="*70)
    print(f"[+] Limit: {LIMIT}")
    print(f"[+] Total rows: {TOTAL_ROWS}")
    print(f"[+] Checkpoint: {CHECKPOINT_FILE}")
    print(f"[+] Output JSON: {OUTPUT_JSON}")
    print(f"[+] Output CSV: {OUTPUT_CSV}")
    print("="*70)
    
    # បង្កើត Session
    session = create_session()
    
    # សាកល្បង Limit
    if not test_limit(session, LIMIT):
        print("\n[!] ❌ Limit នេះមិនដំណើរការ! សូមព្យាយាមបន្ថយតម្លៃ")
        print("[!] ឧទាហរណ៍: LIMIT = 2000 ឬ LIMIT = 1000")
        sys.exit(1)
    
    # ============================================================
    # ព្យាយាមផ្ទុក Checkpoint (បន្តពីកន្លែងឈប់)
    # ============================================================
    
    all_data, last_page = load_checkpoint()
    start_page = last_page + 1 if last_page > 0 else 1
    
    if all_data:
        print(f"[+] 📂 បន្តពីទំព័រ {start_page} (បានទាញយក {len(all_data)} ជួររួចហើយ)")
    else:
        print("[+] 🆕 ចាប់ផ្តើមថ្មី")
    
    # ============================================================
    # ទាញយកទិន្នន័យ
    # ============================================================
    
    page = start_page
    total_pages = (TOTAL_ROWS // LIMIT) + 1
    
    while True:
        rows, total = fetch_page(session, page, LIMIT)
        
        if not rows:
            print("[!] ⚠️ គ្មានទិន្នន័យ ឬកំហុស")
            break
        
        all_data.extend(rows)
        print(f"[+] 📊 បានទាញយក {len(all_data)}/{TOTAL_ROWS} ជួរ")
        
        # ============================================================
        # រក្សាទុក Checkpoint (រៀងរាល់ CHECKPOINT_INTERVAL ទំព័រ)
        # ============================================================
        
        if page % CHECKPOINT_INTERVAL == 0:
            save_checkpoint(all_data, page)
        
        # ============================================================
        # ពិនិត្យលក្ខខណ្ឌបញ្ចប់
        # ============================================================
        
        if len(all_data) >= TOTAL_ROWS:
            print("[+] ✅ បានបញ្ចប់! ទាញយកទិន្នន័យទាំងអស់ហើយ")
            break
        
        if len(rows) < LIMIT:
            print("[+] ✅ គ្មានទិន្នន័យបន្ថែម")
            break
        
        page += 1
        time.sleep(0.5)  # ការពារ Rate Limiting
    
    # ============================================================
    # រក្សាទុកចុងក្រោយ
    # ============================================================
    
    if all_data:
        # រក្សាទុក JSON
        save_final_json(all_data)
        
        # រក្សាទុក CSV
        save_final_csv(all_data)
        
        # លុប Checkpoint (ប្រសិនបើចង់)
        # if os.path.exists(CHECKPOINT_FILE):
        #     os.remove(CHECKPOINT_FILE)
        #     print(f"[+] 🗑️ បានលុបឯកសារ Checkpoint")
        
        print("="*70)
        print(f"[+] ✅ បានបញ្ចប់! ទាញយកបាន {len(all_data)} ជួរ")
        print(f"[+] 📁 ឯកសារ: {OUTPUT_JSON} និង {OUTPUT_CSV}")
        print("="*70)
    else:
        print("[-] ❌ គ្មានទិន្នន័យ")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n[!] ⏹️ អ្នកបានបញ្ឈប់កម្មវិធី (Ctrl+C)")
        print("[!] 💾 ទិន្នន័យបណ្តោះអាសន្នត្រូវបានរក្សាទុកក្នុង checkpoint.json")
        print("[!] 🔄 អាចបន្តដោយរត់កម្មវិធីម្តងទៀត")
        
        # រក្សាទុក Checkpoint ចុងក្រោយ
        if 'all_data' in locals() and all_data:
            save_checkpoint(all_data, page if 'page' in locals() else 0)