import grpc
import sovereign_pb2
import sovereign_pb2_grpc

def test_swap():
    channel = grpc.insecure_channel('localhost:50051')
    stub = sovereign_pb2_grpc.ExecutorStub(channel)
    
    print("Sending Trade Request...")
    # 0.005 SOL
    req = sovereign_pb2.TradeRequest(side="SELL", amount_lamports=5000000)
    try:
        resp = stub.ExecuteTrade(req)
        print(f"Response: {resp}")
    except grpc.RpcError as e:
        print(f"RPC Error: {e.details()}")

if __name__ == "__main__":
    test_swap()
