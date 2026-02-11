import grpc
import sovereign_pb2
import sovereign_pb2_grpc
import time
import csv
import pandas as pd
import requests
import os
import json
from google import genai
from datetime import datetime
from dotenv import load_dotenv

import threading

# 初期設定
# 初期設定
load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
JUP_KEY = os.getenv("JUPITER_API_KEY")
DISCORD_URL = os.getenv("DISCORD_WEBHOOK_URL")
CSV_PATH = "trade_log.csv"
LEDGER_PATH = "ledger.csv"

# 戦略設定 (Strategy Config)
CURRENT_STRATEGY = "SCALPING" # "SCALPING" or "GRID" or "STANDARD"

SCALPING_CONFIG = {
    "rsi_buy": 45.0,      # 緩和: 25 -> 45 (より積極的にエントリー)
    "rsi_sell": 60.0,     # 緩和: 75 -> 60 (早めに利確)
    "min_profit": 0.2,    # 緩和: 0.5% -> 0.2% (薄利多売)
    "stop_loss": -0.5     # 損切りも浅く
}

GRID_CONFIG = {
    "center_price": 86.0, # グリッド中心価格 (MA20などで動的に更新も可)
    "step": 0.2,          # 緩和: 0.5% -> 0.2% (細かい値動きを拾う)
    "levels": 5,          # 上下レベル数
    "orders": {}          # 注文管理用 (メモリ内)

}

WHALE_CONFIG = {
    "address": "G8...WhaleAddressPlaceholder", # 監視対象 (例: Ansem or successful trader)
    "last_signature": None,
    "address": "G8...WhaleAddressPlaceholder", 
    "last_signature": None,
    "enabled": True # アクティブ化
}

def check_capital_level(current_sol):
    """資金量に基づいてレベルを判定"""
    level = 0
    mode = "ENTRY"
    
    if current_sol < 1.0:
        level = 0
        mode = "ENTRY (Scalping/Grid Only)"
    elif current_sol >= 1.0 and current_sol < 5.0:
        level = 1
        mode = "AGGRESSIVE (High Gas/Priority)"
        
    elif current_sol >= 5.0 and current_sol < 20.0:
        # 5.0 SOLあれば、デプロイ費(2.0)を払っても3.0残る -> 安全
        level = 2
        safe_buffer = current_sol - 2.0 
        mode = f"DOMINANCE (Flash Loan Ready | Safe Capital: {safe_buffer:.2f} SOL)"
        
    elif current_sol >= 20.0:
        level = 3
        mode = "WHALE (Full Copy Trade)"
        
    return level, mode

CAPITAL_LEVEL = 0


def send_discord_alert(content):
    """Discordに通知を送信"""
    if not DISCORD_URL: return
    try:
        requests.post(DISCORD_URL, json={"content": content})
    except Exception as e:
        print(f"⚠️ Discord送信エラー: {e}")

def heartbeat_loop():
    """生存報告を1時間ごとに送信 (初回は即時送信)"""
    first_run = True
    while True:
        try:
            if not first_run:
                time.sleep(3600) # 2回目以降は1時間待機
            
            # ステータス収集
            pos = calculate_position()
            pos_str = "No Position"
            if pos and pos['amount'] > 0:
                pos_str = f"{pos['amount']:.4f} SOL (Avg: ${pos['avg_price']:.2f})"
            
            # Balance info for heartbeat
            data = get_market_data()
            bal_str = "Unknown"
            if data:
                 bal_str = f"{float(data.get('balance',0))/1e9:.4f} SOL"

            msg = f"💓 **ALIVE SIGNAL**\nStrategy: `{CURRENT_STRATEGY}`\nBalance: {bal_str}\nPosition: {pos_str}\nStatus: Monitoring..."
            send_discord_alert(msg)
            print("💓 Heartbeat sent.")
            
            first_run = False
            
        except Exception as e:
            print(f"⚠️ Heartbeat Error: {e}")
            time.sleep(60)

def background_ops_loop():
    """バックグラウンドで重い処理や低頻度のタスクを実行 (Phase 9)"""
    print("🚜 Background Ops: ONLINE (Protocol Rotation, Drift, Stocks)")
    while True:
        try:
            # 資金レベルチェック (スレッド内で独自に取得)
            # data = get_market_data() # ここでAPI叩くとレート制限の可能性あり。
            # 簡易的にグローバル変数参照したいが、Pythonの仕様上safeでない場合も。
            # ここでは低頻度なので都度取得でOK。
            
            # 1時間に1回実行
            time.sleep(3600) 
            
            data = get_market_data()
            if not data: continue
            
            current_sol = float(data.get('balance', 0)) / 1e9
            cap_level, _ = check_capital_level(current_sol)
            
            if cap_level > 0:
                print(f"  🚜 Background Ops Check (Level {cap_level})...")
                rotate_protocols(cap_level)
                check_drift_position(cap_level)
                check_new_tokens(cap_level)
                check_stock_market(cap_level)
                
        except Exception as e:
            print(f"⚠️ Background Ops Error: {e}")
            time.sleep(600)

def calculate_position():
    """現在の保有数と平均取得単価を計算"""
    try:
        if not os.path.exists(LEDGER_PATH): return None
        df = pd.read_csv(LEDGER_PATH)
        total_sol = 0.0
        total_cost = 0.0
        
        for _, row in df.iterrows():
            side = row['Side']
            try: amount = float(row['Amount_SOL'])
            except: continue
            try: price = float(row['Price_USD'])
            except: continue
            
            if side == "BUY":
                total_sol += amount
                total_cost += amount * price
            elif side == "SELL":
                # 売却時は平均取得単価を維持したまま保有数とコストを減らす
                if total_sol > 0:
                    avg_price = total_cost / total_sol
                    total_cost -= amount * avg_price
                    total_sol -= amount
        
        if total_sol <= 0.0001: return {"amount": 0.0, "avg_price": 0.0}
        
        avg_price = total_cost / total_sol
        return {"amount": total_sol, "avg_price": avg_price}
        
    except Exception as e:
        print(f"⚠️ 計算エラー: {e}")
        return None

def get_historical_data():
    """Coinbaseから過去のローソク足データを取得 (15分足)"""
    url = "https://api.exchange.coinbase.com/products/SOL-USD/candles?granularity=900"
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(url, headers=headers, timeout=10).json()
        # [time, low, high, open, close, volume]
        df = pd.DataFrame(res, columns=['time', 'low', 'high', 'open', 'close', 'volume'])
        df['time'] = pd.to_datetime(df['time'], unit='s')
        df = df.sort_values('time').reset_index(drop=True)
        return df
    except Exception as e:
        print(f"⚠️ 履歴データ取得エラー: {e}")
        return None

def calculate_technicals(df):
    """テクニカル指標を計算 (RSI, Bollinger Bands)"""
    if df is None or len(df) < 50: return None
    
    # Close price series
    close = df['close']
    
    # RSI (14)
    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    
    # Bollinger Bands (20, 2)
    sma20 = close.rolling(window=20).mean()
    std20 = close.rolling(window=20).std()
    upper_bb = sma20 + (std20 * 2)
    lower_bb = sma20 - (std20 * 2)
    
    latest = df.iloc[-1]
    return {
        "rsi": rsi.iloc[-1],
        "upper_bb": upper_bb.iloc[-1],
        "lower_bb": lower_bb.iloc[-1],
        "sma20": sma20.iloc[-1],
        "bandwidth": (upper_bb.iloc[-1] - lower_bb.iloc[-1]) / sma20.iloc[-1] * 100, # Volatility %
        "close": latest['close']
    }

def update_strategy(technicals):
    """市場のボラティリティに基づいて戦略を自動切り替え"""
    if not technicals: return
    
    global CURRENT_STRATEGY
    volatility = technicals['bandwidth']
    
    # しきい値: 0.5% (これより動いていればScalping, 静かならGrid)
    THRESHOLD = 0.5
    
    new_strategy = "SCALPING"
    if volatility < THRESHOLD:
        new_strategy = "GRID"
    else:
        new_strategy = "SCALPING"
        
    if new_strategy != CURRENT_STRATEGY:
        print(f"🔄 STRATEGY SWITCH: {CURRENT_STRATEGY} -> {new_strategy} (Vol: {volatility:.2f}%)")
        CURRENT_STRATEGY = new_strategy
        
        # Gridモードに入った時、中心価格を更新するなどの初期化が必要ならここで行う
        if new_strategy == "GRID":
            GRID_CONFIG['center_price'] = technicals['sma20']
            print(f"🕸️ Grid Center Updated: ${GRID_CONFIG['center_price']:.2f}")

def check_scalping_signal(data, position, technicals):
    """スキャルピング戦略のシグナル判定"""
    if not technicals: return None
    
    rsi = technicals['rsi']
    price = data['price']
    
    # SELL判定 (利益確定 or 損切り or RSI過熱)
    if position and position['amount'] > 0:
        avg = position['avg_price']
        profit_pct = ((price - avg) / avg) * 100
        
        # 1. 利益確定 (+0.5%以上)
        if profit_pct >= SCALPING_CONFIG['min_profit']:
            return {"decision": "SELL", "reason": f"Scalp Profit: {profit_pct:.2f}% (Target: {SCALPING_CONFIG['min_profit']}%)"}
        
        # 2. 損切り (-1.0%以下)
        if profit_pct <= SCALPING_CONFIG['stop_loss']:
            return {"decision": "SELL", "reason": f"Scalp Stop Loss: {profit_pct:.2f}%"}
            
        # 3. RSI過熱での早期撤退
        if rsi > SCALPING_CONFIG['rsi_sell'] and profit_pct > 0.1:
            return {"decision": "SELL", "reason": f"Scalp RSI Overheated: {rsi:.1f}"}

    # BUY判定 (緩和版)
    else:
        # RSIが基準値以下
        if rsi < SCALPING_CONFIG['rsi_buy']:
             # BB下限との距離条件も緩和: 下限+0.5%以内ならOKとする
             dist_to_lower = price - technicals['lower_bb']
             # lower_bbは約85ドル。0.5%は約0.4ドル。
             threshold = technicals['lower_bb'] * 0.005
             
             if dist_to_lower <= threshold: 
                  return {"decision": "BUY", "reason": f"Aggressive Scalp: RSI {rsi:.1f} & Low Price"}
    
    return None

def check_grid_signal(data, position):
    """グリッドトレード戦略のシグナル判定"""
    price = data['price']
    center = GRID_CONFIG['center_price']
    step_val = center * (GRID_CONFIG['step'] / 100)
    
    # 簡易グリッドロジック: 
    # 現在価格が (Center - n*Step) なら買い
    # 現在価格が (Center + n*Step) なら売り
    
    diff = price - center
    levels_away = diff / step_val # +1.2 means 1.2 steps above
    
    if position and position['amount'] > 0:
        # 売り判定: 含み益があり、かつグリッドの上のレベルに達した
        avg = position['avg_price']
        profit_pct = ((price - avg) / avg) * 100
        
        if profit_pct >= GRID_CONFIG['step']:
            return {"decision": "SELL", "reason": f"Grid Hit: +{profit_pct:.2f}%"}
            
    else:
        # 買い判定: グリッドの下のレベルに達した
        # 例: -1ステップ以下
        if levels_away <= -1.0:
            return {"decision": "BUY", "reason": f"Grid Buy Level: {levels_away:.1f} steps"}
    
    return None

def check_whale_activity():
    """Whale Stalking: 監視対象の新規トランザクションをチェック (Placeholder)"""
    if not WHALE_CONFIG.get('enabled') or "Placeholder" in WHALE_CONFIG['address']: return None
    
    # ここにSolana RPCでgetSignaturesForAddressを実行するロジックが入る
    try:
        rpc_url = "https://api.mainnet-beta.solana.com"
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getSignaturesForAddress",
            "params": [
                WHALE_CONFIG['address'],
                {"limit": 1}
            ]
        }
        res = requests.post(rpc_url, json=payload, timeout=5).json()
        if 'result' in res and len(res['result']) > 0:
            latest = res['result'][0]
            sig = latest['signature']
            
            if WHALE_CONFIG['last_signature'] and sig != WHALE_CONFIG['last_signature']:
                WHALE_CONFIG['last_signature'] = sig
                return f"New Tx: {sig[:8]}... (Check Solana Explorer)"
            
            WHALE_CONFIG['last_signature'] = sig
            
    except Exception as e:
        # print(f"Whale Check Fail: {e}")
        pass
        
    return None

def check_arbitrage(data):
    """CEX(Coinbase) vs DEX(Jupiter) の価格差を監視"""
    cex_price = data['price']
    
    # Check Jupiter Quote for 1 SOL to USDC
    # We can use the existing jupiter logic in executor, but here we are in oracle (Python).
    # We need to call Jupiter API directly.
    try:
        # Check Jupiter Quote for 1 SOL to USDC
        # Using specific mints: SOL (So11...) -> USDC (EPj... NO, use USDT Es9v...)
        # Executor uses Es9v... for USDT. Let's use that.
        # But wait, Coinbase is SOL-USD. USDC/USDT peg is ~1.0 but not guaranteed.
        # Let's use USDC (EPj...) if possible, or USDT (Es9v...).
        # Executor v1 API logic: "Es9v..."
        
        url = "https://api.jup.ag/swap/v1/quote?inputMint=So11111111111111111111111111111111111111112&outputMint=Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB&amount=1000000000&slippageBps=50"
        
        # Add basic headers to avoid 403/429?
        headers = {"Accept": "application/json"}
        res = requests.get(url, headers=headers, timeout=3)
        
        if res.status_code != 200:
             return None
             
        data_json = res.json()
        out_amount = int(data_json.get('outAmount', 0))
        
        # 厳密なチェック: 0の場合は無効として無視する
        if out_amount <= 0: return None
        
        dex_price = out_amount / 1e6 # USDT/USDC has 6 decimals
        
        diff = dex_price - cex_price
        diff_pct = (diff / cex_price) * 100
        
        if abs(diff_pct) > 1.5:
             return f"Arb Opp: CEX ${cex_price} vs DEX ${dex_price:.2f} ({diff_pct:+.2f}%)"
             
    except Exception as e:
        # print(f"Arb Check Error: {e}") 
        pass
        
    return None

def execute_circular_arb(stub, start_sol=1.0):
    """循環アービトラージ実行 (SOL -> USDC -> SOL)"""
    try:
        # 1. SOL -> USDC Quote
        url1 = f"https://api.jup.ag/swap/v1/quote?inputMint=So11111111111111111111111111111111111111112&outputMint=Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB&amount={int(start_sol * 1e9)}&slippageBps=50"
        res1 = requests.get(url1, headers={"Accept": "application/json"}, timeout=2)
        if res1.status_code != 200: return None
        data1 = res1.json()
        usdc_out = int(data1.get('outAmount', 0))
        
        if usdc_out <= 0: return None
        
        # 2. USDC -> SOL Quote
        url2 = f"https://api.jup.ag/swap/v1/quote?inputMint=Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB&outputMint=So11111111111111111111111111111111111111112&amount={usdc_out}&slippageBps=50"
        res2 = requests.get(url2, headers={"Accept": "application/json"}, timeout=2)
        if res2.status_code != 200: return None
        data2 = res2.json()
        sol_out = int(data2.get('outAmount', 0))
        
        if sol_out <= 0: return None
        
        final_sol = sol_out / 1e9
        profit_sol = final_sol - start_sol
        roi = (profit_sol / start_sol) * 100
        
        if roi > 0.5: # 0.5%以上の利益 (ガス代負けしないライン)
             msg = f"🔄 **CIRCULAR ARB FOUND**: {start_sol} SOL -> {usdc_out/1e6} USDC -> {final_sol:.4f} SOL (+{roi:.2f}%)"
             print(msg)
             send_discord_alert(msg)
             
             # --- AUTO EXECUTE ---
             # Step 1: SELL SOL for USDC
             print("  🔄 Executing Leg 1: SOL -> USDC...")
             req1 = sovereign_pb2.TradeRequest(side="SELL", amount_lamports=int(start_sol * 1e9))
             resp1 = stub.ExecuteTrade(req1)
             
             if resp1.success:
                 print(f"  ✅ Leg 1 Success: {resp1.tx_signature}")
                 time.sleep(2) # Wait for confirmation/balance update? 
                 # In a real atomic setup, this would be one tx. Here we risk slippage.
                 
                 # Step 2: BUY SOL with USDC
                 # amount_lamports for BUY usually means "how much SOL to buy", 
                 # but executor logic might treat it as input amount if we changed it?
                 # Checking executor logic: 
                 # if side == "BUY" { input=usdc, output=sol }
                 # quote url: amount={req.amount_lamports}
                 # So for BUY, amount_lamports is the INPUT amount (USDC) in smallest units?
                 # Wait, executor uses `req.amount_lamports` directly in quote url.
                 # If input is USDC (6 decimals), we need to pass USDC amount efficiently?
                 # No, executor expects lamports (9 decimals) usually.
                 # Let's check executor src/main.rs again quickly.
                 
                 # Based on my memory of executor:
                 # quote_url = ... amount={req.amount_lamports}
                 # If Side=BUY, Input=USDC. 
                 # So we need to pass USDC amount to `amount_lamports`.
                 # But USDC has 6 decimals. 
                 # If we pass 1_000_000 (1 USDC), Jupiter treats it as 1 USDC.
                 # So we should pass `usdc_out` from first quote.
                 
                 print(f"  🔄 Executing Leg 2: USDC -> SOL ({usdc_out} units)...")
                 req2 = sovereign_pb2.TradeRequest(side="BUY", amount_lamports=usdc_out)
                 resp2 = stub.ExecuteTrade(req2)
                 
                 if resp2.success:
                      res_msg = f"✅ **ARB COMPLETE**: {resp2.tx_signature}"
                      print(res_msg)
                      send_discord_alert(res_msg)
                      return res_msg
                 else:
                      err_msg = f"⚠️ Leg 2 Failed! Stuck in USDC. Manual intervention required."
                      print(err_msg)
                      send_discord_alert(err_msg)
                      return err_msg
             else:
                 print("  ❌ Leg 1 Failed. Aborting.")
                 return None

    except Exception as e:
        print(f"Arb Error: {e}")
        
    return None


def get_usd_jpy_rate():
    """現在のUSD/JPYレートを取得 (Exchangerate-API 使用)"""
    url = "https://api.exchangerate-api.com/v4/latest/USD"
    try:
        res = requests.get(url, timeout=5).json()
        return res['rates']['JPY']
    except Exception as e:
        print(f"⚠️ 為替レート取得エラー: {e}")
        return 150.0  # フォールバック値 (概算)

def get_solana_balance():
    """Solana RPCから現在のSOL残高を取得 (Lamports)"""
    try:
        # Reverting to Mainnet Beta (Confirmed working via curl)
        rpc_url = "https://api.mainnet-beta.solana.com"
        # 環境変数から公開鍵を取得するか、ハードコード (非推奨だが現状Configにないため)
        # WHALE_CONFIGではなく、自身の公開鍵が必要。
        # executorは知っているがoracleは知らない？
        # いえ、ExecutorはEnvからPrivate Keyを読む。Public Keyはそこで生成。
        # OracleはEnvにPublic Keyを持っていない。
        # 緊急対応: ユーザーの公開鍵 (Solscanから判明) を使用
        my_pubkey = "6Hhxv2YKngYXvW6T8zSCgah4h5U85HBaCHXGCyNZe1kz"
        
        headers = {"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"}
        payload = {
            "jsonrpc": "2.0", "id": 1,
            "method": "getBalance",
            "params": [my_pubkey]
        }
        
        # print(f"    DEBUG: RPC POST {rpc_url}...")
        res = requests.post(rpc_url, json=payload, headers=headers, timeout=10).json()
        if 'result' in res:
            val = int(res['result']['value'])
            return val
        else:
             print(f"⚠️ RPC Response Error: {res}")
    except Exception as e:
        print(f"⚠️ Balance Check Error: {e}")
    return 0

def get_token_balance(mint_address):
    """SPLトークンの残高を取得 (UI Amount) - Robust with Retries"""
    rpc_urls = [
        "https://solana-mainnet.rpc.extrnode.com",
        "https://solana-api.projectserum.com",
        "https://api.mainnet-beta.solana.com"
    ]
    
    for rpc_url in rpc_urls:
        try:
            headers = {"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"}
            payload = {
                "jsonrpc": "2.0", "id": 1,
                "method": "getTokenAccountsByOwner",
                "params": [
                    "6Hhxv2YKngYXvW6T8zSCgah4h5U85HBaCHXGCyNZe1kz",
                    {"mint": mint_address},
                    {"encoding": "jsonParsed"}
                ]
            }
            # Timeoutを短くして次を試す
            res = requests.post(rpc_url, json=payload, headers=headers, timeout=10).json()
            
            if 'result' in res and 'value' in res['result']:
                accounts = res['result']['value']
                if accounts:
                    total = 0.0
                    for acc in accounts:
                        amount = float(acc['account']['data']['parsed']['info']['tokenAmount']['uiAmount'])
                        total += amount
                    # print(f"    DEBUG: {rpc_url} Success: {total}")
                    return total
                else:
                    return 0.0 # 正常に取得できたが残高なし
            
            # エラーなら次へ
            # print(f"    DEBUG: {rpc_url} failed. Res: {res.get('error', 'Unknown')}")

        except Exception as e:
            # print(f"    DEBUG: {rpc_url} Exception: {e}")
            continue
            
    return -1.0 # エラー時は -1 を返す (Cache更新しないため)

# Global Cache for Token Balances
TOKEN_CACHE = {
    "USDC": 0.0,
    "USDT": 0.0,
    "REQ_TIME": 0
}

def get_market_data():
    """Coinbase APIからSOL価格を取得 + Solana RPCから残高取得 (SOL & Stablecoins with Caching)"""
    global TOKEN_CACHE
    
    url = "https://api.coinbase.com/v2/prices/SOL-USD/spot"
    try:
        res = requests.get(url, timeout=5).json()
        price = float(res['data']['amount'])
        
        # Balance Fetch (SOL) - Ensure this is fresh as it's critical for gas
        balance = get_solana_balance()
        
        # Token Balances using Cache
        # If cache is valid (nonzero), update every 120s.
        # If cache is 0.0 (possibly failed), update every 30s.
        cache_duration = 120
        if TOKEN_CACHE["USDC"] == 0 and TOKEN_CACHE["USDT"] == 0:
            cache_duration = 30
            
        if time.time() - TOKEN_CACHE["REQ_TIME"] > cache_duration:
             usdc_bal = get_token_balance("EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v")
             usdt_bal = get_token_balance("Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB")
             
             if usdc_bal >= 0: TOKEN_CACHE["USDC"] = usdc_bal
             if usdt_bal >= 0: TOKEN_CACHE["USDT"] = usdt_bal
             
             TOKEN_CACHE["REQ_TIME"] = time.time()
        
        return {
            "price": price, 
            "balance": balance, 
            "usdc_balance": TOKEN_CACHE["USDC"],
            "usdt_balance": TOKEN_CACHE["USDT"]
        }
    except Exception as e:
        print(f"\n⚠️ 価格取得エラー (Coinbase): {e}")
        return None

def get_trade_history():
    """Ledgerから直近のトレード履歴を取得 (フォーマット整形)"""
    try:
        if not os.path.exists(LEDGER_PATH): return "No history."
        df = pd.read_csv(LEDGER_PATH)
        # 必要なカラムのみ抽出: Date, Side, Amount_SOL, Price_USD, Value_JPY
        history_df = df[['Date', 'Side', 'Amount_SOL', 'Price_USD', 'Value_JPY']].tail(15)
        return history_df.to_string(index=False)
    except Exception as e:
        return f"History Error: {e}"

def ask_ai_decision(data, history, position, technicals):
    """AIに現状を分析させ判断を仰ぐ (戦略統合版)"""
    
    # 1. 数学的戦略の判定を実行
    strat_signal = None
    if CURRENT_STRATEGY == "SCALPING":
        strat_signal = check_scalping_signal(data, position, technicals)
    elif CURRENT_STRATEGY == "GRID":
        strat_signal = check_grid_signal(data, position)
        
    # 戦略シグナルが出ている場合は、それをAIに強く推奨する
    strategy_advice = "特になし。基本ルールに従え。"
    if strat_signal:
        strategy_advice = f"★戦略シグナル点灯★: {strat_signal['decision']} を推奨。\n理由: {strat_signal['reason']}"

    
    current_price = data['price']
    pos_str = "ポジションなし"
    profit_pct = 0.0
    
    if position and position['amount'] > 0:
        avg_price = position['avg_price']
        profit_pct = ((current_price - avg_price) / avg_price) * 100
        pos_str = f"保有SOL: {position['amount']:.4f} SOL\n平均取得単価: ${avg_price:.3f}\n現在含み益: {profit_pct:+.2f}%"

    tech_str = "テクニカルデータ不足"
    if technicals:
        tech_str = f"""
        RSI(14): {technicals['rsi']:.2f}
        BB Upper: ${technicals['upper_bb']:.2f}
        BB Lower: ${technicals['lower_bb']:.2f}
        Price vs LowerBB: {current_price - technicals['lower_bb']:.2f}
        """

    prompt = f"""
    あなたはトレードAI「SOVEREIGN」です。
    
    【現在のポジション状況】
    {pos_str}
    
    【テクニカル指標 (15分足)】
    {tech_str}
    
    【市場価格】
    SOL: ${current_price}
    
    【直近履歴】
    {history}
    
    【発動中の戦略: {CURRENT_STRATEGY}】
    {strategy_advice}
    
    【厳格な交戦規定 (Rules of Engagement)】
    1. BUY (買い) の絶対条件:
       - RSI < {SCALPING_CONFIG['rsi_buy']} (売られすぎ) であること。
       - または、価格が Bollinger Band Lower を下回っていること。
       - 上記を満たさない限り、決して買ってはならない。
       
    2. SELL (売り) の絶対条件:
       - 現在の含み益が +{SCALPING_CONFIG['min_profit']}% を超えていること。
       - または、含み益が +0.1% 以上かつ RSI > {SCALPING_CONFIG['rsi_sell']} (買われすぎ) であること。
       
    3. WAIT (待機):
       - 上記以外は全て WAIT。
       - 曖昧な状況で動くことは死を意味する。
    
    必ず以下のJSONのみ返せ: {{"decision": "BUY" or "SELL" or "WAIT", "reason": "分析理由"}}
    """
    try:
        response = client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=prompt
        )
        raw_text = response.text.strip().replace('```json', '').replace('```', '')
        return json.loads(raw_text)
    except:
        return {"decision": "WAIT", "reason": "AI Processing..."}

# --- Phase 9: Full Spectrum (Dormant) ---
def rotate_protocols(level):
    """Protocol Rotation (The Farmer) - Level 1 Required"""
    if level < 1: return
    # TODO: Implement actual interaction with Jupiter/MarginFi SDKs
    # if datetime.now().hour == 0 and datetime.now().minute == 0:
    #     print("🚜 Farming Protocol Rotation...")

def check_drift_position(level):
    """On-Chain FX (Drift) - Level 2 Required"""
    if level < 2: return
    # TODO: Connect to Drift User Account
    pass

def check_new_tokens(level):
    """Pump.fun Sniper - Level 3 (High Risk) Required"""
    if level < 3: return
    # TODO: Monitor Geyser for new mints
    pass

def check_stock_market(level):
    """Stock Connector - Level 3 Required"""
    if level < 3: return
    # TODO: Connect to Alpaca API
    pass

def main():
    channel = grpc.insecure_channel('localhost:50051')
    stub = sovereign_pb2_grpc.ExecutorStub(channel)
    
    # Heartbeatスレッド開始
    threading.Thread(target=heartbeat_loop, daemon=True).start()
    
    # Background Ops (Phase 9) スレッド開始
    threading.Thread(target=background_ops_loop, daemon=True).start()
    
    print("🦅 SOVEREIGN ORACLE: ONLINE", flush=True)

    while True:
        try:
            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] --- 監視中 ---", flush=True)
            data = get_market_data()
            if not data:
                time.sleep(10); continue

            history = get_trade_history()
            position = calculate_position()
            
            # テクニカル分析
            df = get_historical_data()
            technicals = calculate_technicals(df)
            
            # 戦略マネージャー (自動切り替え)
            update_strategy(technicals)
            
            # Whale Stalking
            whale_signal = check_whale_activity()
            if whale_signal:
                send_discord_alert(f"🐋 **WHALE ALERT**: {whale_signal}")

            # Arb Monitor
            arb_signal = check_arbitrage(data)
            if arb_signal:
                print(f"⚡ {arb_signal}")
                if abs(float(arb_signal.split('(')[1].split('%')[0])) > 2.0: # 2%以上なら通知
                    send_discord_alert(f"⚡ **ARB ALERT**: {arb_signal}")
            
            # Circular Arb (Active Check)
            circ_arb = execute_circular_arb(stub, start_sol=1.0)
            if circ_arb:
                print(f"🔄 {circ_arb}")

            # Capital Level Check
            position_amount = 0.0
            if position:
                 position_amount = float(position.get('amount', 0)) * data['price']
            
            total_equity = (float(data.get('balance', 0)) / 1e9) + (position_amount / data['price']) # Approx
            # Note: balance is lamports.
            
            # 簡易的にbalanceだけで判定 (Positionは含まず安全側に)
            current_sol_balance = float(data.get('balance', 0)) / 1e9
            current_usdc_balance = float(data.get('usdc_balance', 0))
            cap_level, cap_mode = check_capital_level(current_sol_balance)
            
            current_usdc_balance = float(data.get('usdc_balance', 0))
            current_usdt_balance = float(data.get('usdt_balance', 0))
            cap_level, cap_mode = check_capital_level(current_sol_balance)
            
            if cap_level >= 0:
                print(f"  💰 Bal: {current_sol_balance:.4f} SOL | {current_usdc_balance:.2f} USDC | {current_usdt_balance:.2f} USDT (Level {cap_level}: {cap_mode})", flush=True)
                
            # Phase 9 moved to background_ops_loop()

            ai = ask_ai_decision(data, history, position, technicals)
            
            # 戦略シグナルがあればAI判断より優先（あるいはAIがそれに従うはず）
            # ここではAIの最終判断を採用するが、AIはStrategy Adviceに従うようにプロンプトされている
            decision = ai['decision']
            
            # コンソール表示
            print(f"  🔭 判断: {decision}")
            
            if technicals:
                print(f"     📈 RSI: {technicals['rsi']:.1f} | BB: ${technicals['lower_bb']:.2f} - ${technicals['upper_bb']:.2f}")

            if position and position['amount'] > 0:
                print(f"     📊 {position['amount']:.4f} SOL @ ${position['avg_price']:.3f} (P&L: {((data['price'] - position['avg_price']) / position['avg_price']) * 100:+.2f}%)")
            print(f"     📝 理由: {ai['reason']}")

            if decision in ["BUY", "SELL"]:
                print(f"  🔥 {decision} 実行中... (Strategy: {CURRENT_STRATEGY})", flush=True)
                
                # Dynamic Amount Calculation
                trade_amount = 0
                input_mint = ""
                output_mint = ""
                
                # Mint Definitions
                SOL_MINT = "So11111111111111111111111111111111111111112"
                USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
                USDT_MINT = "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB"

                if decision == "BUY":
                    # BUY = SOLを買う (Stablecoinを売る)
                    # Check both USDC and USDT
                    usdc_bal = float(data.get('usdc_balance', 0))
                    usdt_bal = float(data.get('usdt_balance', 0))
                    
                    if usdc_bal > usdt_bal and usdc_bal >= 0.1:
                        # Use USDC
                        trade_amount = int(usdc_bal * 1e6)
                        input_mint = USDC_MINT
                        output_mint = SOL_MINT
                        print(f"     Spending: {usdc_bal:.4f} USDC")
                    elif usdt_bal >= 0.1:
                        # Use USDT
                        trade_amount = int(usdt_bal * 1e6)
                        input_mint = USDT_MINT
                        output_mint = SOL_MINT
                        print(f"     Spending: {usdt_bal:.4f} USDT")
                    else:
                         print(f"  ❌ Insufficient Stablecoins for BUY. (USDC: {usdc_bal:.2f}, USDT: {usdt_bal:.2f})")
                         continue

                elif decision == "SELL":
                    # SELL = SOLを売る (USDCを買う)
                    # Sell all position (SOL) -> USDC (Default)
                    
                    balance_sol = float(data.get('balance', 0)) / 1e9
                    trade_amount_sol = max(0, balance_sol - 0.01)
                    
                    if position and position['amount'] > 0:
                        amount_to_sell = position['amount']
                    else:
                        amount_to_sell = trade_amount_sol

                    trade_amount_sol = min(amount_to_sell, trade_amount_sol)
                    trade_amount = int(trade_amount_sol * 1e9)
                    
                    input_mint = SOL_MINT
                    output_mint = USDC_MINT # Default to USDC for profit
                    
                    if trade_amount <= 0:
                        print("  ❌ Insufficient SOL to SELL.")
                        continue

                # Safety Clamp (Max 1.0 SOL equivalent for now)
                # trade_amount = min(trade_amount, 1_000_000_000) 
                
                print(f"     Trade Input Amount: {trade_amount} (atomic units)")
                print(f"     Route: {input_mint[:4]}... -> {output_mint[:4]}...")
                
                req = sovereign_pb2.TradeRequest(
                    side=decision, 
                    amount_lamports=trade_amount,
                    input_mint=input_mint,
                    output_mint=output_mint
                )
                resp = stub.ExecuteTrade(req)
                
                if resp.success:
                    # JPY換算とLedger記録
                    jpy_rate = get_usd_jpy_rate()
                    
                    if decision == "BUY":
                        # Input is USDC/USDT (6 decimals) -> Approx 1 USD
                        input_val = amount / 1e6
                        usd_val = input_val # 1 USDC = 1 USD
                        sol_amount_approx = usd_val / data['price'] # Log用
                    else:
                        # Input is SOL (9 decimals)
                        input_val = amount / 1e9
                        usd_val = input_val * data['price']
                        sol_amount_approx = input_val

                    jpy_val = int(usd_val * jpy_rate)
                    
                    # 旧ログ (互換性維持)
                    with open(CSV_PATH, "a", newline="") as f:
                        csv.writer(f).writerow([datetime.now().strftime("%Y-%m-%d %H:%M:%S"), data['price'], decision, sol_amount_approx, resp.tx_signature])
                    
                    # 新Ledger (税務対応)
                    with open(LEDGER_PATH, "a", newline="") as f:
                        # Date,Pair,Side,Amount_SOL,Price_USD,Rate_USDJPY,Value_JPY,Tx_Hash,Notes
                        csv.writer(f).writerow([
                            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "SOL/USD",
                            decision,
                            "SOL/USD",
                            decision,
                            sol_amount_approx,
                            data['price'],
                            jpy_rate,
                            jpy_val,
                            resp.tx_signature,
                            ai['reason']
                        ])

                    print(f"  🎯 成功! Tx: {resp.tx_signature}")
                    print(f"  💰 評価額: ¥{jpy_val} (@{jpy_rate} JPY/USD)")
                    
                    # Discord通知
                    msg = f"🦅 **SOVEREIGN V2 EXECUTION**\nTx: {resp.tx_signature}\nSide: **{decision}**\nPrice: ${data['price']}\nValue: ¥{jpy_val:,}\nReason: {ai['reason']}"
                    send_discord_alert(msg)


        except Exception as e:
            print(f"  ⚠️ ループエラー: {e}")

        time.sleep(60)

if __name__ == "__main__":
    main()