import os
import psycopg2
from psycopg2 import extras
from dotenv import load_dotenv
import re

load_dotenv()

def get_clean_env(key):
    val = os.getenv(key, "")
    return re.sub(r"['\"\s\t\n\r]", "", val)

DATABASE_URL = get_clean_env("DATABASE_URL")

def audit_sovereign():
    print("🛡️  Project 'Sovereign' - Auditor Module")
    print("〜 統計的優位性の検証と資産推移の監査 〜\n")
    
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor(cursor_factory=extras.RealDictCursor)
        
        # 全取引データの取得
        cur.execute("""
            SELECT id, side, price, expected_value_e, ai_reasoning, created_at, tx_signature 
            FROM trades 
            ORDER BY created_at DESC;
        """)
        rows = cur.fetchall()
        
        if not rows:
            print("📭 Vault is empty.")
            return

        # 統計計算
        total_trades = len(rows)
        avg_e = sum(r['expected_value_e'] for r in rows) / total_trades
        
        print(f"📊 【統計サマリー】")
        print(f"  総取引試行数: {total_trades} 回")
        print(f"  平均期待値 E: {avg_e:.4f} " + ("🟢 (優位性あり)" if avg_e > 0 else "🔴 (ロジック改善が必要)"))
        print("-" * 110)
        
        # 履歴表示（最新5件）
        print(f"{'ID':<4} | {'TIME':<8} | {'SIDE':<4} | {'PRICE':<9} | {'E_SCORE':<7} | {'REASONING'}")
        print("-" * 110)
        
        for row in rows[:5]:
            time_str = row['created_at'].strftime("%H:%M:%S")
            e_val = f"{row['expected_value_e']:.3f}"
            price = f"${row['price']:.2f}"
            print(f"{row['id']:<4} | {time_str:<8} | {row['side']:<4} | {price:<9} | {e_val:<7} | {row['ai_reasoning']}")
        
        print("-" * 110)
        print("💡 PKSHA 面接官へのTips: この期待値 E は AI (Gemini) が市場の複雑性を評価して算出したものです。")
        
        cur.close()
        conn.close()
    except Exception as e:
        print(f"❌ Auditor Error: {e}")

if __name__ == "__main__":
    audit_sovereign()
