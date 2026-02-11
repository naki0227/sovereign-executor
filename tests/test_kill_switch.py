import grpc
import sovereign_pb2
import sovereign_pb2_grpc

def run_test():
    # Rustサーバーに接続
    channel = grpc.insecure_channel('localhost:50051')
    stub = sovereign_pb2_grpc.ExecutorStub(channel)

    print("1️⃣ 普通に取引をリクエストしてみる...")
    req1 = sovereign_pb2.TradeRequest(side="BUY", price=150.0, expected_e=0.05)
    res1 = stub.ExecuteTrade(req1)
    print(f"結果: {res1.message} (Success: {res1.success})\n")

    print("2️⃣ 🆘 緊急停止（Kill-Switch）を発動！")
    stop_req = sovereign_pb2.StopRequest(reason="テスト：異常検知のシミュレーション")
    stop_res = stub.EmergencyStop(stop_req)
    print(f"結果: {stop_res.message}\n")

    print("3️⃣ 停止後にもう一度取引をリクエストしてみる...")
    res2 = stub.ExecuteTrade(req1)
    print(f"結果: {res2.message} (Success: {res2.success})")

    if not res2.success:
        print("\n✅ テスト成功！システムは完全にロックされています。")
    else:
        print("\n❌ テスト失敗。ロックが効いていません。")

if __name__ == "__main__":
    run_test()
