#!/usr/bin/env python3
"""
对比分析Python和C++ TCP重传实现
"""

import os
import re

def analyze_cpp_retransmit():
    """分析C++ TCP重传实现"""
    print("分析C++ TCP重传实现...")
    print("=" * 60)
    
    # 查找C++中的重传相关代码
    cpp_tcp_file = "/Users/nancy/PycharmProjects/simpy/csg-htsim/sim/tcp.cpp"
    cpp_tcp_h = "/Users/nancy/PycharmProjects/simpy/csg-htsim/sim/tcp.h"
    
    # 查找RTO相关
    print("\n1. C++ RTO相关代码:")
    os.system(f'grep -n "RTO\\|rto\\|retransmit\\|timeout" {cpp_tcp_file} | head -20')
    
    # 查找超时处理
    print("\n2. C++ 超时处理:")
    os.system(f'grep -n "timedOut\\|timeout" {cpp_tcp_file} | head -10')
    
    # 查找SYN重传
    print("\n3. C++ SYN重传:")
    os.system(f'grep -n "SYN.*RTO\\|Resending SYN" {cpp_tcp_file} | head -10')

def analyze_python_retransmit():
    """分析Python TCP重传实现"""
    print("\n\n分析Python TCP重传实现...")
    print("=" * 60)
    
    py_tcp_file = "/Users/nancy/PycharmProjects/simpy/network_frontend/htsimpy/protocols/tcp.py"
    
    # 查找重传相关
    print("\n1. Python 重传相关代码:")
    os.system(f'grep -n "retransmit\\|timeout\\|rto\\|RTO" {py_tcp_file} | head -20')
    
    # 查找定时器相关
    print("\n2. Python 定时器相关:")
    os.system(f'grep -n "timer\\|Timer" {py_tcp_file} | head -10')
    
    # 查找事件调度
    print("\n3. Python 事件调度 (source_is_pending):")
    os.system(f'grep -n "source_is_pending\\|sourceIsPending" {py_tcp_file} | head -10')

def compare_initial_rto():
    """对比初始RTO设置"""
    print("\n\n对比初始RTO设置...")
    print("=" * 60)
    
    # C++ RTO初始化
    print("\n1. C++ 初始RTO:")
    os.system('grep -n "_rto.*=" /Users/nancy/PycharmProjects/simpy/csg-htsim/sim/tcp.cpp | grep -v "//" | head -5')
    
    # Python RTO初始化
    print("\n2. Python 初始RTO:")
    os.system('grep -n "_rto.*=" /Users/nancy/PycharmProjects/simpy/network_frontend/htsimpy/protocols/tcp.py | head -5')

def check_syn_handling():
    """检查SYN处理逻辑"""
    print("\n\n检查SYN处理逻辑...")
    print("=" * 60)
    
    # C++ SYN状态
    print("\n1. C++ SYN状态处理:")
    os.system('grep -B2 -A2 "SYNSENT" /Users/nancy/PycharmProjects/simpy/csg-htsim/sim/tcp.cpp | head -20')
    
    # Python SYN状态
    print("\n2. Python SYN状态处理:")
    os.system('grep -B2 -A2 "SYNSENT\\|SYN_SENT" /Users/nancy/PycharmProjects/simpy/network_frontend/htsimpy/protocols/tcp.py | head -20')

def main():
    analyze_cpp_retransmit()
    analyze_python_retransmit()
    compare_initial_rto()
    check_syn_handling()
    
    print("\n\n关键发现:")
    print("=" * 60)
    print("1. C++在发送SYN时会设置重传定时器")
    print("2. Python可能缺少SYN重传机制")
    print("3. 需要检查Python的retransmit_packet实现是否正确处理SYN")

if __name__ == "__main__":
    main()