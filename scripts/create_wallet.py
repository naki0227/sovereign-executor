from solders.keypair import Keypair
import json
import os

# ウォレットファイルの保存先
wallet_path = os.path.expanduser("~/sovereign/id.json")

# 新しいキーペアを作成
kp = Keypair()

# CLI互換の [byte, byte, ...] 形式で保存
with open(wallet_path, "w") as f:
    # 秘密鍵の全64バイトを取得してリスト化
    secret_bytes = list(bytes(kp))
    json.dump(secret_bytes, f)

print(f"✅ ウォレット作成成功: {wallet_path}")
print(f"🔑 公開鍵（あなたのアドレス）: {kp.pubkey()}")
print("\n⚠️ この id.json は秘密鍵そのものです。絶対に外部に漏らさないでください。")
