from solana.rpc.api import Client
from solders.pubkey import Pubkey
from solders.keypair import Keypair
from spl.token.instructions import close_account, CloseAccountParams
from spl.token.constants import TOKEN_PROGRAM_ID
from solders.transaction import Transaction
from solders.system_program import TransferParams, transfer
from dotenv import load_dotenv
import os
import base58
import base64
import hashlib
from cryptography.fernet import Fernet

# 設定
load_dotenv()
SOLANA_RPC = "https://api.mainnet-beta.solana.com"
ENCRYPTED_KEY = os.getenv("SOLANA_PRIVATE_KEY")
PASSWORD = os.getenv("SOVEREIGN_PASS")

def decrypt_key(encrypted_key, password):
    if not encrypted_key:
        print("DEBUG: SOLANA_PRIVATE_KEY is missing")
        return None
    if not password:
        print("DEBUG: SOVEREIGN_PASS is missing")
        return None
    try:
        if encrypted_key.startswith("enc:"):
            cipher_text = encrypted_key[4:]
        else:
            return encrypted_key # Not encrypted
            
        key = base64.urlsafe_b64encode(hashlib.sha256(password.encode()).digest())
        f = Fernet(key)
        return f.decrypt(cipher_text.encode()).decode()
    except Exception as e:
        print(f"🔓 Decryption Failed: {e}")
        return None

def main():
    print("🧹 DUST SWEEPER: Scanning for empty accounts...")
    
    # Decrypt Key
    private_key = decrypt_key(ENCRYPTED_KEY, PASSWORD)
    if not private_key:
        print("❌ Private Key Error: Check .env for SOLANA_PRIVATE_KEY and SOVEREIGN_PASSWORD")
        return

    # Client & Keypair
    client = Client(SOLANA_RPC)
    try:
        kp = Keypair.from_base58_string(private_key) 
    except Exception as e:
        print(f"⚠️ Key Error (Is it encrypted?): {e}")
        # Proceeding to explain we might need the decrypted key
        return

    wallet_pubkey = kp.pubkey()
    print(f"🔍 Wallet: {wallet_pubkey}")

    # TOKEN_PROGRAM_ID accounts
    opts = client.get_token_accounts_by_owner(
        wallet_pubkey, 
        {"programId": TOKEN_PROGRAM_ID}
    )
    
    accounts = opts.value
    if not accounts:
        print("✅ No token accounts found.")
        return

    print(f"found {len(accounts)} token accounts.")

    closed_count = 0
    reclaimed_lamports = 0

    for acc in accounts:
        pubkey = acc.pubkey
        # Get account info to check balance
        # solana-py 0.30+ structure might differ slightly, using standard approach
        data = acc.account.data
        # data layout: mint(32), owner(32), amount(8), ...
        # primitive parsing or use spl library layouts
        
        # Simplified: Check amount. 
        # The amount is at offset 64 in standard layout? No.
        # Let's use get_token_account_balance for simplicity (slower but safer)
        
        try:
            bal_resp = client.get_token_account_balance(pubkey)
            amount = int(bal_resp.value.amount)
            decimals = bal_resp.value.decimals
            ui_amount = bal_resp.value.ui_amount
            
            if amount == 0:
                print(f"🗑️  Empty Account found: {pubkey}")
                
                # Close it
                params = CloseAccountParams(
                    account=pubkey,
                    dest=wallet_pubkey,
                    owner=wallet_pubkey,
                    program_id=TOKEN_PROGRAM_ID
                )
                ix = close_account(params)
                
                tx = Transaction().add(ix)
                # Recent blockhash
                # solana-py requires explicit blockhash setting in newer versions
                latest_blockhash = client.get_latest_blockhash().value.blockhash
                tx.recent_blockhash = latest_blockhash
                
                # Sign and Send
                resp = client.send_transaction(tx, kp)
                print(f"   PLEASE CHECK: {resp.value}")
                
                closed_count += 1
                reclaimed_lamports += 2039280 # Approx rent
                
        except Exception as e:
            print(f"   ⚠️ Error checking {pubkey}: {e}")

    print(f"\n🧹 Sweep Complete.")
    print(f"   Closed: {closed_count} accounts")
    print(f"   Reclaimed: ~{reclaimed_lamports / 1e9:.4f} SOL")

if __name__ == "__main__":
    main()
