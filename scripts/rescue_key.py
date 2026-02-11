import os
import base64
import hashlib
from cryptography.fernet import Fernet
from dotenv import load_dotenv

load_dotenv()

# 入力データを取得
raw_password = os.getenv("SOVEREIGN_PASSWORD", "")
raw_key = os.getenv("SOLANA_PRIVATE_KEY", "")

print(f"🔑 入力されたパスワード: '{raw_password}'")
print(f"🔒 暗号化データ（先頭10文字）: '{raw_key[:10]}...'")

if not raw_password or not raw_key:
    print("❌ エラー: パスワードか鍵が空っぽです！ export SOVEREIGN_PASSWORD=... しましたか？")
    exit()

# 鍵のクリーニング（enc: 除去、スペース除去）
clean_key = raw_key.replace("enc:", "").strip().strip('"').strip("'")

# 試行パターン作成
passwords_to_try = [
    raw_password,                 # そのまま
    raw_password.strip(),         # 前後の空白削除
    raw_password.lower(),         # 全部小文字
    raw_password.upper(),         # 全部大文字
    raw_password.capitalize(),    # 先頭だけ大文字
]

found = False

print("\n🕵️‍♂️ 解読を開始します...\n")

for pwd in set(passwords_to_try): # 重複を除いて試行
    try:
        # パスワードを鍵に変換 (SHA256 -> Base64)
        key = base64.urlsafe_b64encode(hashlib.sha256(pwd.encode()).digest())
        f = Fernet(key)
        
        # 復号化トライ
        decrypted_data = f.decrypt(clean_key.encode()).decode()
        
        print(f"🎉 成功しました！ (パスワード: '{pwd}')")
        print("--------------------------------------------------")
        print("以下の文字列をコピーして、.env の SOLANA_PRIVATE_KEY に貼り付けてください（enc: なしで）")
        print("\n" + decrypted_data + "\n")
        print("--------------------------------------------------")
        found = True
        break
    except Exception as e:
        print(f"❌ 失敗: '{pwd}' では解けませんでした。")

if not found:
    print("\n⚠️ 全パターン失敗しました。パスワードが間違っている可能性が高いです。")
    print("昨日のメモを確認するか、大文字小文字を思い出してください。")