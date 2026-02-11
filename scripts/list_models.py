import os
from google import genai

api_key = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=api_key)

print("利用可能なモデル一覧:")
for model in client.models.list():
    if 'generateContent' in model.supported_actions:
        print(f"- {model.name}")
