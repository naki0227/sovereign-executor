import os
import google.generativeai as genai

# APIキーの設定
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    print("Error: GEMINI_API_KEY が設定されていません。")
    exit()

genai.configure(api_key=api_key)

# 2026年最新の gemini-1.5-flash (または gemini-2.0-flash-exp) を使用
# ※ 環境によってモデル名が異なる場合があるため、汎用的な 2.5-flash を指定します
model = genai.GenerativeModel('gemini-2.5-flash')

try:
    response = model.generate_content("あなたはニューヨークのサーバーで起動した資産運用ボット『Sovereign』のコアAIです。最初の一言をお願いします。")
    print("\n" + "="*50)
    print("Gemini 応答成功:")
    print(response.text)
    print("="*50 + "\n")
except Exception as e:
    print(f"エラーが発生しました: {e}")
