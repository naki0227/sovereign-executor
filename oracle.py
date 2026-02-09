import os
import json
import psycopg2
import requests
import grpc
import re
from google import genai
from dotenv import load_dotenv

import sovereign_pb2
import sovereign_pb2_grpc

load_dotenv()

def get_clean_env(key):
    val = os.getenv(key, "")
    return re.sub(r"['\"\s\t\n\r]", "", val)

GEMINI_KEY = get_clean_env("GEMINI_API_KEY")
JUPITER_KEY = get_clean_env("JUPITER_API_KEY")
DATABASE_URL = get_clean_env("DATABASE_URL")
EXECUTOR_ADDR = "127.0.0.1:50051"

client = genai.Client(api_key=GEMINI_KEY)
MODEL_ID = "gemini-3-flash-preview"

def get_jupiter_quote():
    url = "https://api.jup.ag/swap/v1/quote"
    USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
    SOL_MINT  = "So11111111111111111111111111111111111111112"
    params = {"inputMint": USDC_MINT, "outputMint": SOL_MINT, "amount": "1000000", "slippageBps": 50}
    headers = {"x-api-key": JUPITER_KEY}
    try:
        res = requests.get(url, params=params, headers=headers, timeout=10)
        if res.status_code != 200:
            res = requests.get("https://lite-api.jup.ag/swap/v1/quote", params=params, timeout=10)
        return res.json() if res.status_code == 200 else None
    except: return None

def consult_oracle(quote_data):
    print(f"🔮 Sovereign Oracle: Analyzing for Expected Value (E)...")
    prompt = f"""
    System: あなたは 'Sovereign' の最高リスク管理責任者です。
    計画書に基づき、期待値 E = (W*P)-(L*Q)-C を最大化する判断を下せ。
    感情を排除し、データのみに基づいて BUY か HOLD を決定せよ。

    【取引データ】
    {json.dumps(quote_data, indent=2)}

    【出力形式: JSON】
    {{ "decision": "BUY" | "HOLD", "expected_value_e": float, "reasoning": "期待値とリスクの観点から簡潔に(80文字)" }}
    """
    try:
        response = client.models.generate_content(
            model=MODEL_ID, contents=prompt,
            config={"response_mime_type": "application/json"}
        )
        return json.loads(response.text.strip())
    except: return None

def send_to_executor(decision_data, price):
    try:
        with grpc.insecure_channel(EXECUTOR_ADDR) as channel:
            stub = sovereign_pb2_grpc.ExecutorStub(channel)
            request = sovereign_pb2.TradeRequest(
                side=decision_data['decision'],
                price=float(price),
                expected_e=float(decision_data.get('expected_value_e', 0))
            )
            response = stub.ExecuteTrade(request, timeout=5)
            print(f"⚡ Executor: {response.message}")
            return response.tx_signature
    except: return None

def record_to_vault(decision_data, price, tx_sig=None):
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO trades (side, price, expected_value_e, ai_reasoning, tx_signature)
            VALUES (%s, %s, %s, %s, %s);
        """, (decision_data['decision'], price, decision_data.get('expected_value_e', 0), 
              decision_data.get('reasoning', ''), tx_sig))
        conn.commit()
        cur.close(); conn.close()
        print("🏛️ Vault updated.")
    except Exception as e: print(f"❌ DB Error: {e}")

if __name__ == "__main__":
    print("🔬 Sovereign Engine: Operating...")
    quote = get_jupiter_quote()
    if quote:
        price = 1 / (int(quote.get('outAmount', 0)) / 10**9)
        print(f"✅ Live Price: ${price:.2f}")
        decision = consult_oracle(quote)
        if decision:
            print(f"🧠 AI Decision: {decision['decision']} (E={decision['expected_value_e']})")
            tx_sig = send_to_executor(decision, price) if decision['decision'] == 'BUY' else None
            record_to_vault(decision, price, tx_sig)
