#!/usr/bin/env python3
"""
测试MPTCP示例运行脚本
用于验证05_mptcp_example是否能正确运行
"""

import subprocess
import sys
import os

def run_test(algorithm, rate2=400, rtt2=10, rwnd=None, run_paths=2):
    """运行MPTCP示例测试"""
    cmd = [
        sys.executable,
        "network_frontend/htsimpy/examples/05_mptcp_example/main.py",
        algorithm
    ]
    
    # 如果是COUPLED_EPSILON，添加epsilon参数
    if algorithm == "COUPLED_EPSILON":
        cmd.append("1.0")  # epsilon值
    
    # 添加其他参数
    cmd.append(str(rate2))
    cmd.append(str(rtt2))
    
    if rwnd is not None:
        cmd.append(str(rwnd))
    
    print(f"运行命令: {' '.join(cmd)}")
    print("-" * 50)
    
    try:
        # 运行命令
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        # 输出结果
        print("标准输出:")
        print(result.stdout)
        
        if result.stderr:
            print("\n标准错误:")
            print(result.stderr)
        
        return result.returncode
    except Exception as e:
        print(f"运行出错: {e}")
        return -1

def main():
    """主函数"""
    print("=== 测试HTSimPy MPTCP示例 ===")
    print()
    
    # 切换到项目根目录
    os.chdir("/Users/nancy/PycharmProjects/simpy")
    
    # 测试不同的算法
    algorithms = ["UNCOUPLED", "COUPLED_INC", "FULLY_COUPLED", "COUPLED_EPSILON"]
    
    for algo in algorithms:
        print(f"\n\n{'='*60}")
        print(f"测试算法: {algo}")
        print(f"{'='*60}\n")
        
        # 运行短时间测试（5秒）
        returncode = run_test(algo, rate2=400, rtt2=10)
        
        if returncode != 0:
            print(f"\n{algo} 测试失败！返回码: {returncode}")
            # 继续测试其他算法
        else:
            print(f"\n{algo} 测试成功！")

if __name__ == "__main__":
    main()