use dotenv::dotenv;
use reqwest::Client;
use serde_json::json;
use std::env;
use std::time::Duration;
use tokio::time::sleep;
use chrono::Local;

// 色定数
const RED: &str = "\x1b[31m";
const GREEN: &str = "\x1b[32m";
const RESET: &str = "\x1b[0m";

// 🔔 Discord通知関数
async fn send_discord_alert(client: &Client, message: &str) {
    // .env から URL を読み込む
    if let Ok(url) = env::var("DISCORD_WEBHOOK_URL") {
        let payload = json!({ "content": message });
        // 送信しても結果は待たずに次へ (Fire and Forget)
        let _ = client.post(&url).json(&payload).send().await;
    }
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    dotenv().ok(); // .env読み込み
    
    print!("\x1b[2J\x1b[1;1H");
    println!("🏥 Jupiter Monitor with Discord Alert Started...");
    println!("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");

    let client = Client::builder()
        .user_agent("Mozilla/5.0")
        .timeout(Duration::from_secs(5))
        .build()?;

    // 起動テスト通知
    println!("🔔 Sending Test Alert...");
    send_discord_alert(&client, "🏥 **Health Monitor Started.** Waiting for Jupiter to revive...").await;

    let url = "https://quote-api.jup.ag/v6/quote"; // 本番API
    // let url = "https://public.jupiterapi.com/v6/quote"; // 予備API
    
    let params = [
        ("inputMint", "So11111111111111111111111111111111111111112"), // SOL
        ("outputMint", "EPjFW36Wy29zCW9E5G96awqD49sfFull1ndWcGCFZ6w"), // USDC
        ("amount", "100000000"), // 0.1 SOL
    ];

    let mut was_alive = false; 

    loop {
        let now = Local::now().format("%H:%M:%S");
        print!("[{}] Pinging Jupiter... ", now);
        
        match client.get(url).query(&params).send().await {
            Ok(resp) => {
                let status = resp.status();
                if status.is_success() {
                    // ✅ 復活！
                    println!("{}ALIVE (Status: {}){}", GREEN, status, RESET);
                    
                    if !was_alive {
                        println!("🎉 Sending Recovery Alert!");
                        send_discord_alert(&client, "🎉 **Jupiter API Resurrected!** (200 OK)\nSystem is ready to swap.").await;
                        was_alive = true;
                    }
                } else {
                    // ❌ まだダウン中
                    println!("{}DOWN (Status: {}){}", RED, status, RESET);
                    
                    if was_alive {
                        send_discord_alert(&client, "💀 **Jupiter API went DOWN.** (Status: 5xx/4xx)").await;
                        was_alive = false;
                    }
                }
            }
            Err(e) => {
                println!("{}CONNECTION FAILED ({}){}", RED, e, RESET);
                 if was_alive {
                    was_alive = false;
                }
            }
        }

        // 60秒待機
        sleep(Duration::from_secs(60)).await;
    }
}
