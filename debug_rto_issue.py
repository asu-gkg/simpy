#!/usr/bin/env python3
"""
调试为什么Python在RTT>RTO时没有触发重传
"""

import sys
sys.path.append('/Users/nancy/PycharmProjects/simpy')

from network_frontend.htsimpy.core.eventlist import EventList
from network_frontend.htsimpy.protocols.tcp import TcpSrc, TcpSink, TcpRtxTimerScanner
from network_frontend.htsimpy.core.pipe import Pipe
from network_frontend.htsimpy.queues.base_queue import Queue
from network_frontend.htsimpy.core.route import Route
from network_frontend.htsimpy.packets.tcp_packet import TcpPacket

def time_from_ms(ms):
    return ms * 1_000_000_000

def test_rto_scenario():
    """测试RTT>RTO的场景"""
    print("测试场景：RTT=10秒，RTO=3秒")
    print("=" * 60)
    
    # 创建事件列表
    eventlist = EventList()
    eventlist.set_endtime(time_from_ms(15000))  # 15秒
    
    # 创建TcpRtxTimerScanner - 10ms扫描周期
    rtx_scanner = TcpRtxTimerScanner(time_from_ms(10), eventlist)
    
    # 创建TCP源和接收端
    tcp_src = TcpSrc(None, None, eventlist)
    tcp_src.setName("TestTCP")
    tcp_sink = TcpSink()
    tcp_sink.setName("TestSink")
    
    # 注册到扫描器
    rtx_scanner.registerTcp(tcp_src)
    
    # 创建10秒延迟的管道（单向5秒）
    pipe_out = Pipe(time_from_ms(5000), eventlist)  # 5秒延迟
    pipe_out.setName("HighLatencyPipe")
    
    pipe_back = Pipe(time_from_ms(5000), eventlist)  # 5秒返回延迟
    pipe_back.setName("ReturnPipe")
    
    # 创建路由
    route_out = Route()
    route_out.push_back(pipe_out)
    route_out.push_back(tcp_sink)
    
    route_in = Route()
    route_in.push_back(pipe_back)
    route_in.push_back(tcp_src)
    
    # 检查初始状态
    print(f"初始RTO (原始值): {tcp_src._rto}")
    print(f"初始RTO (毫秒): {tcp_src._rto // 1_000_000}ms")
    print(f"单向延迟: 5000ms")
    print(f"总RTT: 10000ms")
    print(f"扫描周期: 10ms")
    
    # 连接并开始发送
    tcp_src.connect(route_out, route_in, tcp_sink, 0)
    
    # 添加调试钩子
    class DebugHook:
        def __init__(self):
            self.events = []
            self.last_rto_timeout = None
            self.retransmit_count = 0
            
        def check_state(self, time_ms, tcp_src):
            # 记录RTO超时状态
            current_rto = tcp_src._RFC2988_RTO_timeout
            if current_rto != self.last_rto_timeout:
                self.events.append(f"时间 {time_ms}ms: RTO超时设置为 {current_rto // 1_000_000}ms")
                self.last_rto_timeout = current_rto
            
            # 检查是否应该超时
            if current_rto != float('inf') and tcp_src._eventlist.now() > current_rto:
                self.events.append(f"时间 {time_ms}ms: 应该触发超时！当前时间 > RTO超时时间")
            
            # 检查重传标志
            if tcp_src._rtx_timeout_pending:
                self.events.append(f"时间 {time_ms}ms: 重传超时待处理")
    
    debug = DebugHook()
    
    # 运行仿真
    print("\n运行仿真...")
    print("-" * 60)
    
    events = 0
    last_time = 0
    important_times = [0, 10, 100, 1000, 3000, 3010, 3020, 3030, 3040, 6000, 9000, 10000, 12000]
    
    while eventlist.do_next_event():
        events += 1
        current_time = eventlist.now()
        time_ms = current_time // 1_000_000
        
        # 在关键时间点检查状态
        if time_ms in important_times and time_ms != last_time:
            debug.check_state(time_ms, tcp_src)
            print(f"\n时间: {time_ms}ms")
            print(f"  事件数: {events}")
            print(f"  最高发送序号: {tcp_src._highest_sent}")
            print(f"  最后确认序号: {tcp_src._last_acked}")
            print(f"  RTO超时时间: {tcp_src._RFC2988_RTO_timeout // 1_000_000}ms")
            print(f"  当前RTO值: {tcp_src._rto // 1_000_000}ms")
            print(f"  重传待处理: {tcp_src._rtx_timeout_pending}")
            print(f"  已建立连接: {tcp_src._established}")
            last_time = time_ms
    
    print(f"\n仿真完成，总事件数: {events}")
    
    # 输出调试事件
    print("\n调试事件记录:")
    print("-" * 60)
    for event in debug.events:
        print(event)
    
    # 分析问题
    print("\n问题分析:")
    print("-" * 60)
    if debug.retransmit_count == 0:
        print("❌ 没有检测到重传！")
        print("\n可能的原因:")
        print("1. rtx_timer_hook没有正确触发")
        print("2. do_next_event没有处理超时")
        print("3. 事件调度时序问题")
    else:
        print(f"✓ 检测到 {debug.retransmit_count} 次重传")

def check_timer_scanner_implementation():
    """检查TcpRtxTimerScanner的实现"""
    print("\n\n检查TcpRtxTimerScanner实现")
    print("=" * 60)
    
    # 检查扫描器是否正确工作
    eventlist = EventList()
    scanner = TcpRtxTimerScanner(time_from_ms(10), eventlist)
    
    print(f"扫描器创建成功")
    print(f"扫描周期: {scanner._scanPeriod // 1_000_000}ms")
    print(f"是否已注册到事件列表: {scanner._eventlist is not None}")

if __name__ == "__main__":
    test_rto_scenario()
    check_timer_scanner_implementation()