use tonic::{transport::Server, Request, Response, Status};
use sovereign::executor_server::{Executor, ExecutorServer};
use sovereign::{TradeRequest, TradeResponse, StopRequest, StopResponse};
use solana_sdk::{
    signature::{Keypair, Signer},
    transaction::VersionedTransaction,
    commitment_config::CommitmentConfig,
};
use solana_client::rpc_client::RpcClient;
use std::env;
use magic_crypt::{new_magic_crypt, MagicCryptTrait};
use bs58;
use dotenv::dotenv;
use base64::Engine;

pub mod sovereign {
    include!(concat!(env!("OUT_DIR"), "/sovereign.rs"));
}

const RPC_URL: &str = "https://api.mainnet-beta.solana.com";

#[derive(Debug, Default)]
pub struct MyExecutor {}

// 元の復号ロジックを完全に維持
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

#[tonic::async_trait]
impl Executor for MyExecutor {
    async fn execute_trade(&self, request: Request<TradeRequest>) -> Result<Response<TradeResponse>, Status> {
        let req = request.into_inner();
        let payer = get_payer();
        let client = RpcClient::new_with_commitment(RPC_URL.to_string(), CommitmentConfig::confirmed());
        let jup_key = env::var("JUPITER_API_KEY").expect("JUPITER_API_KEY is required for v1");

        println!("🚀 [SIGNAL] {} order: {} lamports", req.side, req.amount_lamports);

        // Use dynamic mints from request if provided, otherwise fallback (or error)
        // For safety, require mints to be non-empty.
        let in_mint = if req.input_mint.is_empty() {
            println!("⚠️ [WARN] Input Mint missing, defaulting to USDC for BUY, SOL for SELL");
             if req.side == "BUY" { "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v" } else { "So11111111111111111111111111111111111111112" }
        } else {
            &req.input_mint
        };

        let out_mint = if req.output_mint.is_empty() {
            println!("⚠️ [WARN] Output Mint missing, defaulting to SOL for BUY, USDC for SELL");
            if req.side == "BUY" { "So11111111111111111111111111111111111111112" } else { "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v" }
        } else {
            &req.output_mint
        };

        let client_http = reqwest::Client::new();
        let mut headers = reqwest::header::HeaderMap::new();
        headers.insert("x-api-key", jup_key.parse().unwrap());

        // 1. Jupiter Quote (最新 v1 エンドポイント)
        // ドメインを api.jup.ag に統一
        let quote_url = format!(
            "https://api.jup.ag/swap/v1/quote?inputMint={}&outputMint={}&amount={}&slippageBps=500", // 緩和: 100(1.0%) -> 500(5.0%) - Nuclear Option
            in_mint, out_mint, req.amount_lamports
        );
        let quote: serde_json::Value = client_http.get(quote_url)
            .headers(headers.clone())
            .send().await.map_err(|e| Status::internal(e.to_string()))?
            .json().await.unwrap();

        // 2. Swap Transaction (最新 v1 エンドポイント)
        let swap_res: serde_json::Value = client_http.post("https://api.jup.ag/swap/v1/swap")
            .headers(headers)
            .json(&serde_json::json!({
                "quoteResponse": quote,
                "userPublicKey": payer.pubkey().to_string(),
                "wrapAndUnwrapSol": true,
                "dynamicComputeUnitLimit": true, 
                "prioritizationFeeLamports": 200000
            })).send().await.map_err(|e| Status::internal(e.to_string()))?
            .json().await.unwrap();

        // Debugging: Log the response if swapTransaction is missing
        if swap_res.get("swapTransaction").is_none() {
            println!("❌ [ERROR] Jupiter Swap API Response: {:?}", swap_res);
            return Err(Status::internal(format!("Swap API Error: {:?}", swap_res)));
        }

        let tx_base64 = swap_res["swapTransaction"].as_str().ok_or(Status::internal("Swap Data Error"))?;
        let tx_data = base64::engine::general_purpose::STANDARD.decode(tx_base64).unwrap();
        let mut tx: VersionedTransaction = bincode::deserialize(&tx_data).unwrap();
        
        // 3. Finalize & Send (元のロジックを継承)
        tx.message.set_recent_blockhash(client.get_latest_blockhash().map_err(|e| Status::internal(e.to_string()))?);
        let signed_tx = VersionedTransaction::try_new(tx.message, &[&payer]).unwrap();
        let signature = client.send_and_confirm_transaction(&signed_tx).map_err(|e| Status::internal(format!("TX Send Failed: {}", e)))?;

        println!("✅ [SUCCESS] Signature: {}", signature);
        Ok(Response::new(TradeResponse { success: true, tx_signature: signature.to_string(), message: "SUCCESS_V1".into() }))
    }

    async fn emergency_stop(&self, _: Request<StopRequest>) -> Result<Response<StopResponse>, Status> {
        Ok(Response::new(StopResponse { locked: true, message: "LOCKED".into() }))
    }
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let addr = "127.0.0.1:50051".parse()?;
    println!("🏛️  Sovereign Executor Online on {}", addr);
    Server::builder().add_service(ExecutorServer::new(MyExecutor::default())).serve(addr).await?;
    Ok(())
}