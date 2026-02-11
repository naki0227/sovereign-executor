import os
import subprocess
import time
from datetime import datetime

def check_service(name):
    try:
        res = subprocess.run(["systemctl", "is-active", name], capture_output=True, text=True)
        status = res.stdout.strip()
        print(f"✅ Service {name}: {status}")
        return status == "active"
    except Exception as e:
        print(f"❌ Service {name} Check Failed: {e}")
        return False

def check_file_freshness(path, max_age_seconds=120):
    if not os.path.exists(path):
        print(f"❌ File Missing: {path}")
        return False
    
    mtime = os.path.getmtime(path)
    age = time.time() - mtime
    if age < max_age_seconds:
        print(f"✅ File {path} is Fresh (Last modified {int(age)}s ago)")
        return True
    else:
        print(f"⚠️ File {path} is Stale (Last modified {int(age)}s ago)")
        return False

def check_dust_sweeper():
    path = "/root/sovereign/executor/target/release/dust_sweeper"
    if os.path.exists(path):
        print(f"✅ Dust Sweeper Binary Exists")
        # Dry run check
        try:
            res = subprocess.run([path], capture_output=True, text=True)
            if "Dust Sweeper" in res.stdout:
                print("✅ Dust Sweeper Execution: OK")
                return True
        except Exception as e:
             print(f"❌ Dust Sweeper Exec Failed: {e}")
    else:
        print(f"❌ Dust Sweeper Binary Not Found at {path}")
    return False

def check_logs_for_keywords(path, keywords):
    if not os.path.exists(path): return False
    with open(path, 'r') as f:
        # Read last 100 lines
        lines = f.readlines()[-100:]
        content = "".join(lines)
        
        for k in keywords:
            if k in content:
                print(f"✅ Log contains '{k}'")
            else:
                print(f"⚠️ Log missing recent '{k}' (Might be normal if no signal)")

def main():
    print("🛡️ SOVEREIGN SYSTEM VERIFICATION 🛡️\n")
    
    all_good = True
    
    # 1. Services
    if not check_service("sovereign-oracle"): all_good = False
    
    # 2. Logs
    if not check_file_freshness("/root/sovereign/oracle.log"): all_good = False
    
    # 3. Binaries
    if not check_dust_sweeper(): all_good = False
    
    # 4. Log Content Analysis
    print("\n🔍 Analyzing Oracle Logs...")
    check_logs_for_keywords("/root/sovereign/oracle.log", [
        "SOVEREIGN ORACLE: ONLINE",
        "監視中",
        "RSI", # Confirm technicals running
        "Whale" # Confirm whale check running (if logging enabled)
    ])
    
    # 5. Ledger
    if os.path.exists("/root/sovereign/ledger.csv"):
        print(f"✅ Ledger exists.")
    else:
        print(f"⚠️ Ledger missing (Normal if no trades yet)")

    print("\n" + ("="*30))
    if all_good:
        print("🎉 SYSTEM STATUS: GREEN (Ready for Combat)")
    else:
        print("⚠️ SYSTEM STATUS: YELLOW/RED (Check issues above)")
    print("="*30)

if __name__ == "__main__":
    main()
