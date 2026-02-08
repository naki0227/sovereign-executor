use dotenv::dotenv;
use reqwest::Client;
use serde_json::Value;
use solana_client::rpc_client::RpcClient;
use solana_sdk::{
    signature::{read_keypair_file, Signer},
    system_instruction,
    transaction::Transaction,
};
use std::time::{Duration, Instant};
use tokio::time::sleep;
use chrono::Local;
use std::sync::{Arc, Mutex};
use std::fs::OpenOptions;
use std::io::{self, Write}; // 【修正】selfを追加して io::stdout を使えるようにした
use std::collections::VecDeque;

// 色定数
const RED: &str = "\x1b[31m";
const GREEN: &str = "\x1b[32m";
const CYAN: &str = "\x1b[36m";
const YELLOW: &str = "\x1b[33m";
const RESET: &str = "\x1b[0m";
const BOLD: &str = "\x1b[1m";

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    dotenv().ok();
    print!("\x1b[2J\x1b[1;1H");
    println!("{}⚔️  Sovereign Executor: Auto-Trading Mode{}", BOLD, RESET);
    println!("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
    println!(" [Strategy] Mean Reversion (Drop > 0.05%)");
    println!(" [Limit]    Max 3 trades (Safety Lock)");
    println!("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");

    // 1. ウォレット準備
    let keypair_path = dirs::home_dir().unwrap().join(".config/solana/id.json");
    let keypair = read_keypair_file(&keypair_path).or_else(|_| {
        read_keypair_file("id.json")
    }).expect("鍵が見つかりません！");
    let wallet_address = keypair.pubkey();
    let rpc_url = "https://api.mainnet-beta.solana.com";

    // 共有メモリ
    let shared_price = Arc::new(Mutex::new(0.0));
    let monitor_price = Arc::clone(&shared_price);

    // 2. 監視タスク (裏側)
    tokio::spawn(async move {
        let client = Client::builder()
            .user_agent("Mozilla/5.0")
            .timeout(Duration::from_secs(3))
            .build()
            .unwrap();

        let url = "https://api.exchange.coinbase.com/products/SOL-USD/ticker";
        
        loop {
            match client.get(url).send().await {
                Ok(res) => {
                    if let Ok(json) = res.json::<Value>().await {
                        if let Some(price_str) = json["price"].as_str() {
                            let p: f64 = price_str.parse().unwrap_or(0.0);
                            if let Ok(mut lock) = monitor_price.lock() {
                                *lock = p;
                            }
                        }
                    }
                }
                Err(_) => {}
            }
            sleep(Duration::from_millis(500)).await; // 0.5秒更新
        }
    });

    // 3. 自動売買ロジック (メインブレイン)
    let mut history: VecDeque<f64> = VecDeque::new(); // 価格履歴
    let window_size = 30; // 30サンプル(約15~30秒分)の平均を見る
    let mut last_trade_time = Instant::now() - Duration::from_secs(999); // 初期化
    let mut trade_count = 0;
    let max_trades = 3; // 安全のため3回で終了

    println!("Waiting for data accumulation...");

    loop {
        // 現在価格を取得
        let current_price = *shared_price.lock().unwrap();
        
        if current_price == 0.0 {
            sleep(Duration::from_millis(100)).await;
            continue;
        }

        // 履歴に追加
        history.push_back(current_price);
        if history.len() > window_size {
            history.pop_front();
        }

        // データが溜まったら分析開始
        if history.len() == window_size {
            // 平均値 (SMA) 計算
            let sum: f64 = history.iter().sum();
            let avg = sum / window_size as f64;
            
            // 乖離率 (%)
            let deviation = (current_price - avg) / avg * 100.0;

            let now = Local::now().format("%H:%M:%S");
            
            // ログ表示 (\r で上書き表示)
            print!("\r[{}] Price: ${:.3} | SMA: ${:.3} | Dev: {:+.4}%   ", 
                now, current_price, avg, deviation);
            io::stdout().flush()?;

            // 🔥【エントリー条件】
            // 1. 平均より 0.05% 以上安くなっている (急落)
            // 2. クールダウン (60秒) が終わっている
            // 3. 取引回数が上限以下
            if deviation < -0.05 
               && last_trade_time.elapsed().as_secs() > 60 
               && trade_count < max_trades 
            {
                println!("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
                println!("{}🚨 SIGNAL DETECTED! Drop {:.4}% (Price ${}){}", RED, deviation, current_price, RESET);
                println!("🚀 Executing Buy Logic...");

                // トランザクション実行
                let client = RpcClient::new(rpc_url.to_string());
                let instruction = system_instruction::transfer(
                    &wallet_address, &wallet_address, 1000
                );
                
                // ブロックハッシュ取得
                if let Ok(latest_blockhash) = client.get_latest_blockhash() {
                    let tx = Transaction::new_signed_with_payer(
                        &[instruction], Some(&wallet_address), &[&keypair], latest_blockhash
                    );

                    match client.send_and_confirm_transaction(&tx) {
                        Ok(sig) => {
                            println!("{}✅ EXECUTION SUCCESS: https://solscan.io/tx/{}{}", GREEN, sig, RESET);
                            
                            // CSV記録
                            if let Ok(mut file) = OpenOptions::new().create(true).append(true).open("trade_log.csv") {
                                writeln!(file, "{},{},BUY,{}", Local::now(), current_price, sig).unwrap();
                            }
                            
                            trade_count += 1;
                            last_trade_time = Instant::now();
                            println!("💤 Entering Cooldown (60s)... Trades: {}/{}", trade_count, max_trades);
                        },
                        Err(e) => println!("❌ Tx Failed: {}", e),
                    }
                } else {
                     println!("❌ Network Error (Blockhash)");
                }
                println!("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
            }
        }

        // 制限に達したら終了
        if trade_count >= max_trades {
            println!("\n\n{}🛑 Daily Limit Reached (3/3). Stopping bot for safety.{}", YELLOW, RESET);
            break;
        }

        sleep(Duration::from_millis(1000)).await; // 1秒間隔で思考
    }

    Ok(())
}
