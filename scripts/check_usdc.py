import os
import json
import base58
import requests
from dotenv import load_dotenv

load_dotenv()

# 設定
USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
RPC_URL = os.getenv("RPC_URL", "https://api.mainnet-beta.solana.com")
PRIVATE_KEY = os.getenv("SOLANA_PRIVATE_KEY")

def get_my_address():
    # 秘密鍵から公開鍵を復元
    secret_bytes = base58.b58decode(PRIVATE_KEY)
    # 最初の32バイトが秘密鍵のシード、次の32バイトが公開鍵
    # 多くのライブラリで共通の仕様
    import nacl.signing
    signing_key = nacl.signing.SigningKey(secret_bytes[:32])
    verify_key = signing_key.verify_key
    return base58.b58encode(bytes(verify_key)).decode('utf-8')

def check_usdc_balance():
    my_address = get_my_address()
    print(f"📦 Wallet: {my_address}")

    # 直接 JSON-RPC を叩く (ライブラリの型エラーを回避)
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getTokenAccountsByOwner",
        "params": [
            my_address,
            {"mint": USDC_MINT},
            {"encoding": "jsonParsed"}
        ]
    }

    response = requests.post(RPC_URL, json=payload).json()

    if "result" not in response or not response["result"]["value"]:
        print("❌ USDCアカウントが見つかりません（残高 0）。")
        return 0

    # 残高の抽出
    token_info = response["result"]["value"][0]["account"]["data"]["parsed"]["info"]
    amount = token_info["tokenAmount"]["uiAmount"]

    print(f"💰 USDC残高: {amount} USDC")
    return amount

if __name__ == "__main__":
    try:
        check_usdc_balance()
    except Exception as e:
        print(f"❌ エラーが発生しました: {e}")
