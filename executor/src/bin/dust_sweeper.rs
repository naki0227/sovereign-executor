use solana_client::rpc_client::RpcClient;
use solana_sdk::{
    commitment_config::CommitmentConfig,
    pubkey::Pubkey,
    signature::{Keypair, Signer},
    transaction::Transaction,
    program_pack::Pack,
};
use spl_token::{
    instruction::close_account,
    state::Account as TokenAccount,
};
use std::env;
use dotenv::dotenv;
use magic_crypt::{new_magic_crypt, MagicCryptTrait};
use bs58;

// Reusing key loading logic
fn get_payer() -> Keypair {
    dotenv().ok();
    let key_str = env::var("SOLANA_PRIVATE_KEY").expect("SOLANA_PRIVATE_KEY not set");
    let secret_string = if key_str.starts_with("enc:") {
        let encrypted_part = &key_str[4..];
        let password = env::var("SOVEREIGN_PASS").expect("SOVEREIGN_PASS required");
        let mc = new_magic_crypt!(password, 256);
        mc.decrypt_base64_to_string(encrypted_part).expect("Decryption failed")
    } else { key_str };
    let bytes = bs58::decode(&secret_string).into_vec().expect("Invalid Base58");
    Keypair::from_bytes(&bytes).expect("Invalid Keypair")
}

fn main() {
    println!("🧹 Dust Sweeper (Rust Edition) Starting...");
    
    let payer = get_payer();
    let rpc_url = "https://api.mainnet-beta.solana.com";
    let client = RpcClient::new_with_commitment(rpc_url.to_string(), CommitmentConfig::confirmed());
    
    let wallet_pubkey = payer.pubkey();
    println!("🔍 Wallet: {}", wallet_pubkey);
    
    // Get all token accounts
    // spl_token::id() is Token Program ID
    let accounts = client.get_token_accounts_by_owner(
        &wallet_pubkey,
        solana_client::rpc_request::TokenAccountsFilter::ProgramId(spl_token::id()),
    ).expect("Failed to get token accounts");
    
    println!("Found {} token accounts.", accounts.len());
    
    let mut closed_count = 0;
    
    for account in accounts {
        let pubkey_str = account.pubkey;
        let pubkey = pubkey_str.parse::<Pubkey>().unwrap();
        
        // Parse data
        let split_data: Vec<u8> = match account.account.data {
             solana_account_decoder::UiAccountData::Binary(data, _) => base64::decode(data).unwrap(),
             _ => continue, 
        };
        if let Ok(token_acc) = TokenAccount::unpack(&split_data) {
            // Check if amount is 0
            if token_acc.amount == 0 {
                // Check if it is not a wrapped SOL account we are actively using? 
                // Wrapped SOL (wSOL) with 0 balance is fine to close, but we might want to keep it if we used it frequently.
                // However, usually we unwrap in Jupiter swaps. 
                // Let's close everything 0 balance for now.
                
                println!("🗑️  Empty Account: {}", pubkey);
                println!("   Mint: {}", token_acc.mint);
                
                // Create Close Instruction
                let ix = close_account(
                    &spl_token::id(),
                    &pubkey,
                    &wallet_pubkey, // dest (receive rent)
                    &wallet_pubkey, // owner
                    &[],            // signers
                ).unwrap();
                
                let latest_blockhash = client.get_latest_blockhash().unwrap();
                let tx = Transaction::new_signed_with_payer(
                    &[ix],
                    Some(&wallet_pubkey),
                    &[&payer],
                    latest_blockhash,
                );
                
                match client.send_and_confirm_transaction(&tx) {
                    Ok(sig) => {
                        println!("   ✅ Closed! Sig: {}", sig);
                        closed_count += 1;
                    },
                    Err(e) => println!("   ⚠️ Failed: {}", e),
                }
            }
        }
    }
    
    println!("🧹 Done. Closed {} accounts.", closed_count);
    // Rough calculation: 0.00203928 SOL per account
    let recovered = closed_count as f64 * 0.002039;
    println!("💰 Est. Recovered: {} SOL", recovered);
}
