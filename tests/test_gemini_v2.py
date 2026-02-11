import os
from google import genai

api_key = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=api_key)

try:
    # 一覧にあった最新のプレビューモデルを指定
    response = client.models.generate_content(
        model='gemini-3-flash-preview', 
        contents="ニューヨークのサーバーで『gemini-3-flash-preview』として目覚めました。これからの市場攻略に向けた覚悟を短く述べてください。"
    )
    
    print("\n" + "💎" * 15)
    print("Sovereign Core Online:")
    print(response.text)
    print("💎" * 15 + "\n")
    
except Exception as e:
    print(f"エラーが発生しました: {e}")
