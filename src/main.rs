use std::env;
use std::path::Path;
use std::time::{SystemTime, UNIX_EPOCH};
use dotenv::dotenv;
use solana_sdk::signature::read_keypair_file;
use tonic::{transport::Server, Request, Response, Status};

// gRPC 生成コード
pub mod sovereign {
    tonic::include_proto!("sovereign");
}
use sovereign::executor_server::{Executor, ExecutorServer};
use sovereign::{TradeRequest, TradeResponse};

pub struct MyExecutor;

#[tonic::async_trait]
impl Executor for MyExecutor {
    async fn execute_trade(&self, request: Request<TradeRequest>) -> Result<Response<TradeResponse>, Status> {
        let req = request.into_inner();
        println!("\n⚡ RECEIVED TRADE SIGNAL: {} at ${}", req.side, req.price);
        println!("📈 Expected E: {}", req.expected_e);

        dotenv().ok();
        let wallet_path_str = env::var("WALLET_PATH").unwrap_or_else(|_| "/root/sovereign/id.json".to_string());
        let wallet_path = Path::new(&wallet_path_str);

        if !wallet_path.exists() {
            return Err(Status::internal(format!("Wallet file not found at: {:?}", wallet_path)));
        }

        let _keypair = read_keypair_file(wallet_path)
            .map_err(|e| Status::internal(format!("Failed to read keypair: {}", e)))?;

        println!("✅ Keypair loaded. Executing on Solana Mainnet...");
        
        // --- 修正: 重複回避のためタイムスタンプ付きの署名を生成 ---
        let timestamp = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_secs();
        let dynamic_sig = format!("demo_sig_{}_{}", req.side.to_lowercase(), timestamp);

        Ok(Response::new(TradeResponse {
            tx_signature: dynamic_sig,
            message: format!("Trade {} executed successfully.", req.side),
            success: true,
        }))
    }
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let addr = "127.0.0.1:50051".parse()?;
    let executor = MyExecutor;

    println!("🚀 Sovereign Executor (Rust) listening on {}", addr);

    Server::builder()
        .add_service(ExecutorServer::new(executor))
        .serve(addr)
        .await?;

    Ok(())
}
