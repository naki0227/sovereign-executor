import requests

def get_balance(address):
    url = "https://api.mainnet-beta.solana.com"
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getBalance",
        "params": [address]
    }
    try:
        response = requests.post(url, json=payload)
        result = response.json()
        # lamports を SOL に変換
        balance_sol = result['result']['value'] / 10**9
        return balance_sol
    except Exception as e:
        return f"エラー: {e}"

address = "6Hhxv2YKngYXvW6T8zSCgah4h5U85HBaCHXGCyNZe1kz"
print(f"🧐 ウォレット {address} の残高を確認中...")
balance = get_balance(address)
print(f"💰 現在の残高: {balance} SOL")
