import os
import base64
import hashlib
from cryptography.fernet import Fernet
from dotenv import load_dotenv

# .envを読み込む
load_dotenv()

# パスワードと暗号化された鍵を取得
password = os.getenv("SOVEREIGN_PASSWORD")
encrypted_key_str = os.getenv("SOLANA_PRIVATE_KEY")

print(f"DEBUG: Password exists? {bool(password)}")
print(f"DEBUG: Encrypted Key starts with enc? {encrypted_key_str.startswith('enc:') if encrypted_key_str else False}")

if not password or not encrypted_key_str:
    print("❌ Error: SOVEREIGN_PASSWORD または SOLANA_PRIVATE_KEY が見つかりません。")
    exit()

# 'enc:' を取り除く
if encrypted_key_str.startswith("enc:"):
    cipher_text = encrypted_key_str[4:]
else:
    cipher_text = encrypted_key_str

# パスワードを32バイトのBase64鍵に変換する (SHA256ハッシュ)
# これが「普通のパスワード」を「Fernetの鍵」に変える魔法です
key = base64.urlsafe_b64encode(hashlib.sha256(password.encode()).digest())

try:
    f = Fernet(key)
    decrypted_key = f.decrypt(cipher_text.encode()).decode()
    print("\n🎉 解読成功！以下の秘密鍵をコピーして .env に貼り付けてください:\n")
    print(decrypted_key)
    print("\n------------------------------------------------")
except Exception as e:
    print(f"\n❌ 解読失敗: {e}")
    print("パスワードが間違っているか、データが壊れている可能性があります。")