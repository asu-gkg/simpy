#!/usr/bin/env python3
"""
测试MPTCP示例是否正确显示重传
特别关注第二条路径（10秒RTT）
"""

import subprocess
import sys
import time

def run_mptcp_example():
    """运行MPTCP示例并捕获输出"""
    print("运行MPTCP示例...")
    print("=" * 60)
    
    # 运行命令，使用更长的仿真时间来捕获重传
    cmd = [
        sys.executable,
        "network_frontend/htsimpy/examples/05_mptcp_example/main.py",
        "UNCOUPLED",  # 算法
        "400",        # rate2
        "10000",      # rtt2 (10秒)
        "254",        # rwnd
        "2"           # run_paths
    ]
    
    print(f"命令: {' '.join(cmd)}")
    print("-" * 60)
    
    # 运行并捕获输出
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        cwd="/Users/nancy/PycharmProjects/simpy"
    )
    
    output_lines = []
    retransmission_found = False
    
    # 实时读取输出
    for line in process.stdout:
        output_lines.append(line.strip())
        
        # 检查是否包含重传信息
        if "RTO" in line and "HSENT" in line and "Subflow" in line:
            print(f"\n>>> 发现重传信息: {line.strip()}")
            retransmission_found = True
        
        # 打印关键信息
        if any(keyword in line for keyword in ["路径", "RTT=", "Outputting", "仿真完成"]):
            print(line.strip())
    
    process.wait()
    
    return output_lines, retransmission_found

def analyze_output(output_lines):
    """分析输出查找重传模式"""
    print("\n\n分析输出...")
    print("=" * 60)
    
    # 查找所有包含时间戳和重传相关信息的行
    retransmission_lines = []
    
    for line in output_lines:
        # C++格式: "At 3030 RTO 3000 MDEV 0 RTT 0 SEQ 0 HSENT 1 CWND 10 FAST RECOVERY? 0 Flow ID Subflow2"
        if "At" in line and "RTO" in line and "Subflow" in line:
            retransmission_lines.append(line)
    
    if retransmission_lines:
        print(f"\n找到 {len(retransmission_lines)} 条重传记录:")
        for line in retransmission_lines:
            print(f"  {line}")
            # 解析重传信息
            parts = line.split()
            if len(parts) >= 14:
                time_ms = parts[1]
                rto = parts[3]
                flow_id = parts[-1]
                print(f"    -> 时间: {time_ms}ms, RTO: {rto}ms, 流: {flow_id}")
    else:
        print("\n❌ 未找到重传记录")
        print("\n可能的原因:")
        print("1. Python输出格式与C++不同")
        print("2. 需要添加额外的日志来捕获重传事件")
        print("3. 仿真时间太短")

def check_log_files():
    """检查生成的日志文件"""
    print("\n\n检查日志文件...")
    print("=" * 60)
    
    import os
    import glob
    
    # 查找data目录下的日志文件
    log_pattern = "data/logout.400pktps.10000ms.*.txt"
    log_files = glob.glob(log_pattern)
    
    if log_files:
        print(f"找到 {len(log_files)} 个日志文件:")
        for log_file in log_files:
            print(f"  {log_file}")
            # 检查文件大小
            size = os.path.getsize(log_file)
            print(f"    大小: {size} 字节")
            
            # 读取前几行
            try:
                with open(log_file, 'r') as f:
                    lines = f.readlines()[:10]
                    if any("TCPSRC" in line and "rtx_timeout" in line for line in lines):
                        print("    ✓ 包含重传超时信息")
            except:
                pass
    else:
        print(f"未找到匹配的日志文件: {log_pattern}")

def main():
    """主函数"""
    print("=== 测试MPTCP重传行为 ===")
    print(f"当前时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # 运行MPTCP示例
    output_lines, retransmission_found = run_mptcp_example()
    
    # 分析输出
    analyze_output(output_lines)
    
    # 检查日志文件
    check_log_files()
    
    # 总结
    print("\n\n=== 总结 ===")
    print("=" * 60)
    if retransmission_found:
        print("✓ MPTCP示例正确显示了重传行为")
    else:
        print("❌ MPTCP示例未显示预期的重传行为")
        print("\n建议:")
        print("1. 在TcpSrc中添加重传日志输出")
        print("2. 确保TcpLoggerSimple正确记录重传事件")
        print("3. 验证C++和Python的日志格式是否一致")

if __name__ == "__main__":
    main()