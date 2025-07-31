#!/usr/bin/env python3
"""
详细对比Python和C++实现的异同
"""

import os
import subprocess
import re

def analyze_tcp_connection_sequence():
    """分析TCP连接建立序列"""
    print("=== TCP连接建立序列对比 ===\n")
    
    # 1. 检查connect方法
    print("1. TCP connect方法对比:")
    print("-" * 60)
    
    # C++ connect
    print("C++实现 (tcp.cpp):")
    result = subprocess.run(
        ['grep', '-A20', 'TcpSrc::connect', '/Users/nancy/PycharmProjects/simpy/csg-htsim/sim/tcp.cpp'],
        capture_output=True, text=True
    )
    if result.stdout:
        lines = result.stdout.split('\n')[:25]
        for line in lines:
            if 'connect' in line or 'SYN' in line or '_state' in line or 'established' in line:
                print(f"  {line.strip()}")
    
    # Python connect
    print("\nPython实现 (tcp.py):")
    result = subprocess.run(
        ['grep', '-A20', 'def connect', '/Users/nancy/PycharmProjects/simpy/network_frontend/htsimpy/protocols/tcp.py'],
        capture_output=True, text=True
    )
    if result.stdout:
        lines = result.stdout.split('\n')[:25]
        for line in lines:
            if 'connect' in line or 'SYN' in line or '_state' in line or 'established' in line:
                print(f"  {line.strip()}")

def analyze_syn_sending():
    """分析SYN发送逻辑"""
    print("\n\n=== SYN发送逻辑对比 ===\n")
    
    # 1. 检查send_syn
    print("1. send_syn方法对比:")
    print("-" * 60)
    
    # C++
    print("C++ send_syn:")
    result = subprocess.run(
        ['grep', '-B5', '-A15', 'send_syn()', '/Users/nancy/PycharmProjects/simpy/csg-htsim/sim/tcp.cpp'],
        capture_output=True, text=True
    )
    if result.stdout:
        for line in result.stdout.split('\n'):
            if any(keyword in line for keyword in ['send_syn', 'new_syn_pkt', 'sendOn', '_RFC2988_RTO_timeout']):
                print(f"  {line.strip()}")
    
    # Python
    print("\nPython send_syn:")
    result = subprocess.run(
        ['grep', '-B5', '-A15', 'def send_syn', '/Users/nancy/PycharmProjects/simpy/network_frontend/htsimpy/protocols/tcp.py'],
        capture_output=True, text=True
    )
    if result.stdout:
        for line in result.stdout.split('\n'):
            if any(keyword in line for keyword in ['send_syn', 'new_syn_pkt', 'sendOn', '_RFC2988_RTO_timeout']):
                print(f"  {line.strip()}")

def analyze_timer_mechanism():
    """分析定时器机制"""
    print("\n\n=== 定时器机制对比 ===\n")
    
    print("1. RTO超时检查机制:")
    print("-" * 60)
    
    # C++ rtx_timer_hook
    print("C++ rtx_timer_hook逻辑:")
    result = subprocess.run(
        ['grep', '-B5', '-A20', 'rtx_timer_hook', '/Users/nancy/PycharmProjects/simpy/csg-htsim/sim/tcp.cpp'],
        capture_output=True, text=True
    )
    if result.stdout:
        lines = result.stdout.split('\n')
        for i, line in enumerate(lines):
            if 'rtx_timer_hook' in line:
                # 打印函数定义和关键逻辑
                for j in range(i, min(i+20, len(lines))):
                    if any(keyword in lines[j] for keyword in ['RFC2988_RTO_timeout', 'rtx_timeout_pending', 'doNextEvent', 'retransmit']):
                        print(f"  {lines[j].strip()}")
    
    # Python rtx_timer_hook
    print("\nPython rtx_timer_hook逻辑:")
    with open('/Users/nancy/PycharmProjects/simpy/network_frontend/htsimpy/protocols/tcp.py', 'r') as f:
        content = f.read()
        if 'def rtx_timer_hook' in content:
            start = content.find('def rtx_timer_hook')
            end = content.find('\n    def ', start + 1)
            if end == -1:
                end = start + 500
            method = content[start:end]
            for line in method.split('\n')[:20]:
                if any(keyword in line for keyword in ['rtx_timer_hook', 'RFC2988_RTO_timeout', 'rtx_timeout_pending', 'source_is_pending', 'retransmit']):
                    print(f"  {line.strip()}")

def analyze_doNextEvent():
    """分析doNextEvent差异"""
    print("\n\n=== doNextEvent处理对比 ===\n")
    
    print("1. TCP源端的doNextEvent:")
    print("-" * 60)
    
    # C++
    print("C++ TcpSrc::doNextEvent:")
    result = subprocess.run(
        ['grep', '-B2', '-A15', 'TcpSrc::doNextEvent', '/Users/nancy/PycharmProjects/simpy/csg-htsim/sim/tcp.cpp'],
        capture_output=True, text=True
    )
    if result.stdout:
        for line in result.stdout.split('\n')[:20]:
            if any(keyword in line for keyword in ['doNextEvent', 'established', 'rtx_timeout_pending', 'retransmit', 'receivePacket']):
                print(f"  {line.strip()}")
    
    # Python
    print("\nPython TcpSrc.do_next_event:")
    with open('/Users/nancy/PycharmProjects/simpy/network_frontend/htsimpy/protocols/tcp.py', 'r') as f:
        content = f.read()
        if 'def do_next_event' in content:
            start = content.find('def do_next_event')
            end = content.find('\n    def ', start + 1)
            if end == -1:
                end = start + 300
            method = content[start:end]
            for line in method.split('\n')[:15]:
                if any(keyword in line for keyword in ['do_next_event', 'established', 'rtx_timeout_pending', 'retransmit', 'receivePacket']):
                    print(f"  {line.strip()}")

def analyze_route_structure():
    """分析路由结构差异"""
    print("\n\n=== 路由结构对比 ===\n")
    
    print("1. 路由创建方式:")
    print("-" * 60)
    
    # 检查Python路由
    print("Python路由创建 (05_mptcp_example):")
    result = subprocess.run(
        ['grep', '-B2', '-A5', 'Route()', '/Users/nancy/PycharmProjects/simpy/network_frontend/htsimpy/examples/05_mptcp_example/main.py'],
        capture_output=True, text=True
    )
    if result.stdout:
        print(result.stdout)
    
    # 检查C++路由
    print("\nC++路由创建 (main.cpp):")
    result = subprocess.run(
        ['grep', '-B2', '-A5', 'route_t()', '/Users/nancy/PycharmProjects/simpy/csg-htsim/sim/tests/main.cpp'],
        capture_output=True, text=True
    )
    if result.stdout:
        print(result.stdout)

def check_initial_state():
    """检查初始状态设置"""
    print("\n\n=== 初始状态设置对比 ===\n")
    
    print("1. TCP源端初始化:")
    print("-" * 60)
    
    # C++初始化
    print("C++ TcpSrc构造函数关键变量:")
    result = subprocess.run(
        ['grep', '-A30', 'TcpSrc::TcpSrc', '/Users/nancy/PycharmProjects/simpy/csg-htsim/sim/tcp.cpp'],
        capture_output=True, text=True
    )
    if result.stdout:
        for line in result.stdout.split('\n')[:40]:
            if any(keyword in line for keyword in ['_established', '_state', '_highest_sent', '_last_acked', '_rto =', '_RFC2988']):
                print(f"  {line.strip()}")
    
    # Python初始化
    print("\nPython TcpSrc.__init__关键变量:")
    with open('/Users/nancy/PycharmProjects/simpy/network_frontend/htsimpy/protocols/tcp.py', 'r') as f:
        content = f.read()
        init_start = content.find('def __init__(self,')
        init_end = content.find('\n    def ', init_start + 1)
        if init_end == -1:
            init_end = init_start + 1500
        init_method = content[init_start:init_end]
        for line in init_method.split('\n'):
            if any(keyword in line for keyword in ['_established', '_state', '_highest_sent', '_last_acked', '_rto =', '_RFC2988']):
                print(f"  {line.strip()}")

def main():
    print("Python vs C++ HTSim实现详细对比分析")
    print("=" * 80)
    
    analyze_tcp_connection_sequence()
    analyze_syn_sending()
    analyze_timer_mechanism()
    analyze_doNextEvent()
    analyze_route_structure()
    check_initial_state()
    
    print("\n\n=== 关键发现总结 ===")
    print("=" * 80)
    print("""
1. 连接建立流程:
   - 两者都使用send_syn()发送SYN包
   - 都设置了RTO定时器
   
2. 定时器机制:
   - C++和Python都使用rtx_timer_hook检查超时
   - 都通过TcpRtxTimerScanner定期扫描
   
3. 可能的差异点:
   - 事件调度的时机
   - 路由结构的细节
   - 初始状态的设置
   
需要进一步检查:
   - Pipe组件的延迟处理
   - 事件调度器的实现细节
   - 包的路由过程
""")

if __name__ == "__main__":
    main()