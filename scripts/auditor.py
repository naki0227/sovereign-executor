import csv
import os

CSV_FILE = "trades.csv"

def audit():
    if not os.path.exists(CSV_FILE):
        print("📭 No trade records found yet.")
        return

    total_buy_usd = 0.0
    total_sell_usd_approx = 0.0
    trade_count = 0
    
    print("\n📊 --- Sovereign Auditor Report ---")
    print(f"{'Time':<20} | {'Side':<4} | {'Price':<8} | {'Amount'}")
    print("-" * 50)

    try:
        with open(CSV_FILE, mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                trade_count += 1
                ts = row['Timestamp']
                side = row['Side']
                price = float(row['Price'])
                amount = float(row['Amount'])
                
                print(f"{ts:<20} | {side:<4} | ${price:<7.2f} | {amount}")

                if side == "BUY":
                    total_buy_usd += amount # USDCを使った
                elif side == "SELL":
                    # 売ったSOL * その時の価格 = USDC換算の受取額
                    total_sell_usd_approx += (amount * price)

        print("-" * 50)
        print(f"✅ Total Trades: {trade_count}")
        print(f"📉 Total Invested (BUY): ${total_buy_usd:.2f}")
        print(f"📈 Total Revenue (SELL): ${total_sell_usd_approx:.2f}")
        
        # 簡易的な損益計算（在庫分を無視したキャッシュフローのみ）
        net_cashflow = total_sell_usd_approx - total_buy_usd
        color = "\033[92m" if net_cashflow > 0 else "\033[91m" # 緑 or 赤
        reset = "\033[0m"
        
        print(f"💰 Net Cashflow: {color}${net_cashflow:.4f}{reset}")
        print("-----------------------------------")

    except Exception as e:
        print(f"⚠️ Error reading audit log: {e}")

if __name__ == "__main__":
    audit()
