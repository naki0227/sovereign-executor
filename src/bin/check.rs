use reqwest::Client;
use std::time::Duration;
use tokio::time::sleep;
use chrono::Local;

// 色定数
const RED: &str = "\x1b[31m";
const GREEN: &str = "\x1b[32m";
const RESET: &str = "\x1b[0m";

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    // 画面クリア
    print!("\x1b[2J\x1b[1;1H");
    println!("🏥 Jupiter API Health Monitor Started...");
    println!("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");

    let client = Client::builder()
        .user_agent("Mozilla/5.0")
        .timeout(Duration::from_secs(5))
        .build()?;

    // ターゲット: Jupiter V6 Quote API
    let url = "https://quote-api.jup.ag/v6/quote";
    // 予備ターゲット (Public)
    // let url = "https://public.jupiterapi.com/v6/quote";

    let params = [
        ("inputMint", "So11111111111111111111111111111111111111112"), // SOL
        ("outputMint", "EPjFW36Wy29zCW9E5G96awqD49sfFull1ndWcGCFZ6w"), // USDC
        ("amount", "100000000"), // 0.1 SOL
    ];

    loop {
        let now = Local::now().format("%H:%M:%S");
        print!("[{}] Pinging Jupiter... ", now);
        
        // リクエスト送信
        match client.get(url).query(&params).send().await {
            Ok(resp) => {
                let status = resp.status();
                if status.is_success() {
                    // 200 OK なら復活！
                    println!("{}✅ ALIVE (Status: {}){}", GREEN, status, RESET);
                    println!("{}🎉 Jupiter API is BACK ONLINE! You can swap now!{}", GREEN, RESET);
                    // 音を鳴らす（ベル文字）
                    print!("\x07"); 
                } else {
                    // 4xx, 5xx ならまだダウン中
                    println!("{}❌ DOWN (Status: {}){}", RED, status, RESET);
                }
            }
            Err(e) => {
                // 接続エラー (DNSエラーなど)
                println!("{}❌ CONNECTION FAILED ({}){}", RED, e, RESET);
            }
        }

        // 30秒待機
        sleep(Duration::from_secs(30)).await;
    }
}
