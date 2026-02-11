import requests
import csv
import os
from datetime import datetime

LEDGER_PATH = "test_ledger.csv"

def get_usd_jpy_rate():
    try:
        url = "https://api.exchangerate-api.com/v4/latest/USD"
        res = requests.get(url, timeout=5).json()
        rate = res['rates']['JPY']
        print(f"✅ USD/JPY Rate: {rate}")
        return rate
    except Exception as e:
        print(f"❌ Rate Error: {e}")
        return None

def get_coinbase_price():
    try:
        url = "https://api.coinbase.com/v2/prices/SOL-USD/spot"
        res = requests.get(url, timeout=5).json()
        price = float(res['data']['amount'])
        print(f"✅ SOL Price (Coinbase): ${price}")
        return price
    except Exception as e:
        print(f"❌ Price Error: {e}")
        return None

def test_ledger_logging():
    rate = get_usd_jpy_rate()
    price = get_coinbase_price()
    
    if not rate or not price:
        print("❌ Skipping ledger test due to API failure")
        return

    decision = "TEST_BUY"
    amount_sol = 0.005
    usd_val = amount_sol * price
    jpy_val = int(usd_val * rate)
    tx_sig = "test_signature_123"
    reason = "Unit Test"

    # Write header if not exists
    if not os.path.exists(LEDGER_PATH):
        with open(LEDGER_PATH, "w", newline="") as f:
            f.write("Date,Pair,Side,Amount_SOL,Price_USD,Rate_USDJPY,Value_JPY,Tx_Hash,Notes\n")

    # Write record
    with open(LEDGER_PATH, "a", newline="") as f:
         csv.writer(f).writerow([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "SOL/USD",
            decision,
            amount_sol,
            price,
            rate,
            jpy_val,
            tx_sig,
            reason
        ])
    
    print("✅ Ledger logging executed.")
    
    # Verify content
    with open(LEDGER_PATH, "r") as f:
        print(f"📄 Ledger Content:\n{f.read()}")

if __name__ == "__main__":
    test_ledger_logging()
    # Cleanup
    if os.path.exists(LEDGER_PATH):
        os.remove(LEDGER_PATH)
        print("🧹 Cleaned up test ledger.")
