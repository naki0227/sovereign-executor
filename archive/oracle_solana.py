import os
import requests
from google import genai
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=api_key)

def get_sol_price():
    """CoinGeckoのパブリックAPIからSOL価格を取得（認証不要）"""
    url = "https://api.coingecko.com/api/v3/simple/price?ids=solana&vs_currencies=usd"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            return data['solana']['usd']
        else:
            print(f"⚠️ APIエラー (Status {response.status_code}): {response.text}")
            return None
    except Exception as e:
        print(f"❌ 通信エラー: {e}")
        return None

def analyze_market(price):
    """Gemini 3-flash-preview による分析"""
    prompt = f"""
    【Solana 市場データ】
    現在のSOL価格: ${price}

    あなたはニューヨークの伝説的トレーダー『Sovereign』です。
    この価格を見て、現在の相場における『期待値』を100点満点でスコア化し、
    BUY/HOLD/SELLのいずれかの判断とその理由を1文で述べてください。
    """
    try:
        response = client.models.generate_content(
            model='gemini-3-flash-preview', 
            contents=prompt
        )
        return response.text
    except Exception as e:
        return f"AI分析エラー: {e}"

if __name__ == "__main__":
    print("🔮 The Oracle: CoinGecko経由でSolana市場をスキャン中...")
    price = get_sol_price()
    
    if price:
        print(f"📈 現在のSOL価格: ${price}")
        print("\n--- Sovereign Core の深層思考 ---")
        print(analyze_market(price))
    else:
        print("❌ 価格取得に失敗しました。")
