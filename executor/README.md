# Sovereign Executor (Rust-based High-Frequency Trading Bot)

## 概要
Solana ブロックチェーン上で動作する、Rust製の高頻度取引（HFT）ボットのプロトタイプ。
非同期処理（Tokio）を用いたマルチスレッドアーキテクチャを採用し、市場監視と発注を並列実行します。

## 技術スタック
- **Language**: Rust (Tokio, Reqwest, Solana SDK)
- **Infrastructure**: Cloud VPS (Ubuntu 24.04), Systemd/Nohup
- **Blockchain**: Solana Mainnet (RPC Interaction)

## 実装機能
1.  **Real-time Monitoring**:
    - Coinbase API (WebSocket/REST) を用いたミリ秒単位の価格監視。
    - `Arc<Mutex<f64>>` によるスレッド間データ共有。

2.  **Resilience (耐障害性)**:
    - **Cloudflare Bypass**: 530 エラー発生時に DNS を迂回し、直接 IP 接続を試行するロジックを実装。
    - **API Fallback**: Jupiter API ダウン時に、Solana RPC へ直接接続し、自己送金によるオンチェーン・ハートビートで稼働を継続。

3.  **Strategy**:
    - Mean Reversion (移動平均乖離) ロジック搭載。
    - `VecDeque` を用いたスライディングウィンドウ方式で SMA を算出。
    - 0.05% の急落を検知し、自動発注。

4.  **Logging**:
    - トレード結果を `trade_log.csv` に自動記録（監査ログ）。

## 開発エピソード (2026/02/09)
主要 DEX アグリゲーターの API 障害（530/400 Error）に直面したが、インフラ層の迂回と、オンチェーン直接書き込みへの切り替えにより、システム稼働を維持。
