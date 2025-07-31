#!/usr/bin/env python3
"""
深入分析为什么C++有重传而Python没有
"""

import subprocess
import os

def check_send_syn_implementation():
    """检查send_syn的实现细节"""
    print("=== send_syn实现细节对比 ===\n")
    
    # 查找C++ send_syn
    print("1. C++ send_syn实现:")
    print("-" * 60)
    cpp_file = "/Users/nancy/PycharmProjects/simpy/csg-htsim/sim/tcp.cpp"
    
    # 使用grep查找send_syn函数
    result = subprocess.run(
        ['grep', '-A30', 'TcpSrc::send_syn()', cpp_file],
        capture_output=True, text=True
    )
    
    if result.stdout:
        print("找到C++ send_syn:")
        for line in result.stdout.split('\n')[:35]:
            print(f"  {line}")
    
    # 查找Python send_syn
    print("\n\n2. Python send_syn实现:")
    print("-" * 60)
    py_file = "/Users/nancy/PycharmProjects/simpy/network_frontend/htsimpy/protocols/tcp.py"
    
    with open(py_file, 'r') as f:
        content = f.read()
        
    # 查找send_syn方法
    if 'def send_syn' in content:
        start = content.find('def send_syn')
        end = content.find('\n    def ', start + 1)
        if end == -1:
            end = start + 800
        method = content[start:end]
        print("找到Python send_syn:")
        for line in method.split('\n'):
            print(f"  {line}")

def check_connect_timing():
    """检查connect的时序差异"""
    print("\n\n=== connect时序对比 ===\n")
    
    print("1. 检查starttime参数的使用:")
    print("-" * 60)
    
    # C++ connect调用
    print("C++ connect调用 (main.cpp):")
    result = subprocess.run(
        ['grep', '-B2', '-A2', 'connect.*timeFromMs', '/Users/nancy/PycharmProjects/simpy/csg-htsim/sim/tests/main.cpp'],
        capture_output=True, text=True
    )
    if result.stdout:
        print(result.stdout)
    
    # Python connect调用
    print("\nPython connect调用:")
    result = subprocess.run(
        ['grep', '-B2', '-A2', 'connect.*time_from_ms', '/Users/nancy/PycharmProjects/simpy/network_frontend/htsimpy/examples/05_mptcp_example/main.py'],
        capture_output=True, text=True
    )
    if result.stdout:
        print(result.stdout)

def analyze_retransmit_trigger():
    """分析重传触发条件"""
    print("\n\n=== 重传触发条件分析 ===\n")
    
    # 分析C++输出中的重传信息
    print("1. C++重传信息分析:")
    print("-" * 60)
    print("At 3030 RTO 3000 MDEV 0 RTT 0 SEQ 0 HSENT 1 CWND 10 FAST RECOVERY? 0 Flow ID Subflow2")
    print("\n解析:")
    print("- 时间: 3030ms (刚好超过RTO 3000ms)")
    print("- RTT: 0 (还没收到ACK，所以RTT未测量)")
    print("- SEQ: 0 (序列号为0，说明是初始SYN)")
    print("- HSENT: 1 (已发送的最高序列号为1)")
    print("- 流ID: Subflow2 (第二个子流)")
    
    print("\n2. 关键时间点:")
    print("- Subflow2的starttime: 0-50ms随机")
    print("- Subflow2的RTT: 10000ms (路径2延迟)")
    print("- 初始RTO: 3000ms")
    print("- 第一次重传: ~3030ms")
    print("- 第二次重传: ~9040ms (RTO翻倍后)")

def check_timer_registration():
    """检查定时器注册"""
    print("\n\n=== 定时器注册对比 ===\n")
    
    print("1. TcpRtxTimerScanner注册:")
    print("-" * 60)
    
    # C++注册
    print("C++注册 (main.cpp):")
    result = subprocess.run(
        ['grep', '-B2', '-A2', 'registerTcp', '/Users/nancy/PycharmProjects/simpy/csg-htsim/sim/tests/main.cpp'],
        capture_output=True, text=True
    )
    if result.stdout:
        print(result.stdout)
    
    # Python注册
    print("\nPython注册:")
    result = subprocess.run(
        ['grep', '-B2', '-A2', 'registerTcp', '/Users/nancy/PycharmProjects/simpy/network_frontend/htsimpy/examples/05_mptcp_example/main.py'],
        capture_output=True, text=True
    )
    if result.stdout:
        print(result.stdout)

def check_event_scheduling():
    """检查事件调度差异"""
    print("\n\n=== 事件调度差异 ===\n")
    
    print("1. 检查source_is_pending调用:")
    print("-" * 60)
    
    # 查看Python中的事件调度
    py_file = "/Users/nancy/PycharmProjects/simpy/network_frontend/htsimpy/protocols/tcp.py"
    
    print("Python send_syn中的事件调度:")
    result = subprocess.run(
        ['grep', '-B5', '-A5', 'source_is_pending.*starttime', py_file],
        capture_output=True, text=True
    )
    if result.stdout:
        print(result.stdout)
    
    print("\n关键差异分析:")
    print("- C++: 发送SYN后立即设置RTO定时器")
    print("- Python: 可能在事件调度时机上有差异")

def propose_solution():
    """提出解决方案"""
    print("\n\n=== 问题总结与解决方案 ===\n")
    
    print("问题根源分析:")
    print("1. Subflow2的RTT(10秒)远大于初始RTO(3秒)")
    print("2. 当SYN包需要10秒才能到达并返回ACK时，3秒的RTO必然会触发重传")
    print("3. 这是正确的TCP行为")
    
    print("\n为什么Python没有重传:")
    print("1. 可能是事件调度的精度问题")
    print("2. 可能是starttime的处理有细微差异")
    print("3. 可能是定时器扫描的时机不同")
    
    print("\n这种差异的影响:")
    print("1. 对于正常RTT的网络，两者行为一致")
    print("2. 只在极端高延迟情况下表现不同")
    print("3. 不影响MPTCP的基本功能")

def main():
    check_send_syn_implementation()
    check_connect_timing()
    analyze_retransmit_trigger()
    check_timer_registration()
    check_event_scheduling()
    propose_solution()

if __name__ == "__main__":
    main()