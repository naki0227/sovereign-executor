use dotenv::dotenv;
use std::env;
use magic_crypt::new_magic_crypt; // ← これを追加しました！
use magic_crypt::MagicCryptTrait;

fn main() {
    dotenv().ok();

    // 1. 現在の生データを取得
    let raw_key = env::var("SOLANA_PRIVATE_KEY")
        .expect("❌ .envに SOLANA_PRIVATE_KEY が見つかりません");

    // 2. パスワードを決める
    let password = env::var("SOVEREIGN_PASS").unwrap_or_else(|_| "sovereign-secure".to_string());

    println!("🔒 Locking Private Key with password: '{}'...", password);

    // 3. 暗号化 (AES-256)
    let mc = new_magic_crypt!(password, 256);
    let encrypted_base64 = mc.encrypt_str_to_base64(&raw_key);

    println!("\n✅ 暗号化完了！以下の文字列を .env に上書きしてください:\n");
    println!("SOLANA_PRIVATE_KEY=\"enc:{}\"", encrypted_base64);
    println!("\n⚠️ 注意: 先頭の 'enc:' を忘れないでください！");
}
