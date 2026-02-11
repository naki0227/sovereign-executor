import subprocess
import os
import sys

def kill_process(name):
    try:
        # pkill -f でコマンド名に一致するプロセスを強制終了
        # -9 は SIGKILL (強制停止)
        subprocess.run(["pkill", "-9", "-f", name], check=False)
        print(f"💀 Killed: {name}")
    except Exception as e:
        print(f"⚠️ Error killing {name}: {e}")

if __name__ == "__main__":
    print("\n🚨🚨 SOVEREIGN KILL SWITCH ACTIVATED 🚨🚨")
    print("Stopping all engines immediately...\n")
    
    # PythonのOracle (脳) を殺す
    kill_process("oracle.py")
    
    # RustのExecutor (筋肉) を殺す
    kill_process("executor")
    
    print("\n✅ System Halted. All positions are frozen.")
    print("Please check your wallet manually.")
