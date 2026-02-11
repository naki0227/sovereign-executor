import csv
import os
from datetime import datetime

TRADE_LOG = "trade_log.csv"
LEDGER = "ledger.csv"
DEFAULT_JPY_RATE = 150.0

def migrate():
    if not os.path.exists(TRADE_LOG):
        print(f"No {TRADE_LOG} found.")
        return

    # Read existing ledger hashes to avoid duplicates
    existing_hashes = set()
    if os.path.exists(LEDGER):
        with open(LEDGER, "r") as f:
            reader = csv.reader(f)
            next(reader, None) # Skip header
            for row in reader:
                if len(row) > 7:
                    existing_hashes.add(row[7]) # Tx_Hash is index 7

    # Prepare new rows
    new_rows = []
    
    with open(TRADE_LOG, "r") as f:
        reader = csv.reader(f)
        for row in reader:
            if not row: continue
            
            # Parse row based on length
            date_str = row[0]
            price = float(row[1])
            side = "UNKNOWN"
            amount_sol = 0.0
            tx_hash = ""
            
            if len(row) == 5:
                # Date, Price, Side, Amount, Hash
                side = row[2]
                amount_sol = float(row[3]) / 1e9 # Lamports to SOL? 
                # Wait, line 15 in trade_log has 5000000. oracle.py writes amount_lamports? 
                # Let's check oracle.py codes... yes `amount` variable is passed. 
                # `amount = 5000000` in oracle.py. So it is lamports.
                # But wait, ledger.csv line 2 suggests Amount_SOL is 0.005.
                # So I need to convert.
                tx_hash = row[4]
                
            elif len(row) == 4:
                # Date, Price, Side, Hash (Missing Amount)
                if row[2] in ["BUY", "SELL"]:
                    side = row[2]
                    tx_hash = row[3]
                    # Estimate amount? Most were 0.005 SOL (5000000 lamports) typically? 
                    # Checking line 1: 1000? line 1 is weird. 
                    # Let's assume 0 for unknown amount to be safe, or 0.005 if it was the standard.
                    amount_sol = 0.0
                else:
                    # Date, Price, Amount, Hash (Old format?)
                    side = "UNKNOWN"
                    try:
                        amount_sol = float(row[2]) / 1e9
                    except: amount_sol = 0
                    tx_hash = row[3]
            
            if tx_hash in existing_hashes:
                print(f"Skipping duplicate: {tx_hash}")
                continue

            # Calculate Values
            # amount_sol is already in SOL
            # If amount > 1000, it's probably lamports not converted? 
            # In line 15: 5000000. So if > 1, assume lamports.
            if amount_sol > 1:
                amount_sol /= 1e9

            usd_val = amount_sol * price
            jpy_val = int(usd_val * DEFAULT_JPY_RATE)
            
            # Date,Pair,Side,Amount_SOL,Price_USD,Rate_USDJPY,Value_JPY,Tx_Hash,Notes
            new_row = [
                date_str,
                "SOL/USD",
                side,
                amount_sol,
                price,
                DEFAULT_JPY_RATE,
                jpy_val,
                tx_hash,
                "Migrated from trade_log.csv"
            ]
            new_rows.append(new_row)

    # Append to Ledger
    if new_rows:
        mode = "a" if os.path.exists(LEDGER) else "w"
        with open(LEDGER, mode, newline="") as f:
            writer = csv.writer(f)
            if mode == "w":
                writer.writerow(["Date","Pair","Side","Amount_SOL","Price_USD","Rate_USDJPY","Value_JPY","Tx_Hash","Notes"])
            writer.writerows(new_rows)
        print(f"Migrated {len(new_rows)} rows to {LEDGER}")
    else:
        print("No new rows to migrate.")

if __name__ == "__main__":
    migrate()
