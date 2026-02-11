import os
import base64
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad
from hashlib import sha256
from dotenv import load_dotenv

load_dotenv()

def decrypt_magic_crypt(encrypted_base64, password):
    # MagicCrypt (Rust) の 256ビット版は、パスワードの SHA256 ハッシュをキーに使う
    key = sha256(password.encode('utf-8')).digest()
    
    # MagicCrypt は IV (初期化ベクトル) にキーの最初の 16バイトを使う仕様
    iv = key[:16]
    
    # Base64デコード
    encrypted_bytes = base64.b64decode(encrypted_base64)
    
    # AES-256-CBC で復号
    cipher = AES.new(key, AES.MODE_CBC, iv)
    decrypted_bytes = unpad(cipher.decrypt(encrypted_bytes), AES.block_size)
    
    return decrypted_bytes.decode('utf-8')

# 設定取得
raw_key = os.getenv("SOLANA_PRIVATE_KEY", "")
password = os.getenv("SOVEREIGN_PASS") or os.getenv("SOVEREIGN_PASSWORD")

if not raw_key.startswith("enc:"):
    print("❌ SOLANA_PRIVATE_KEY が 'enc:' で始まっていません。")
    exit()

if not password:
    print("❌ パスワード(SOVEREIGN_PASS)が設定されていません。")
    exit()

encrypted_part = raw_key[4:]

print(f"🔑 試行パスワード: {password}")
print(f"🔒 対象データ: {encrypted_part[:20]}...")

try:
    result = decrypt_magic_crypt(encrypted_part, password)
    print("\n🎉 成功しました！これがあなたの生の秘密鍵です:\n")
    print(result)
    print("\n--------------------------------------------------")
    print("これを .env の SOLANA_PRIVATE_KEY に貼り付けてください。")
except Exception as e:
    print(f"\n❌ 復号失敗: {e}")
    print("パスワードが1文字でも違うと解除できません。大文字小文字などを確認してください。")