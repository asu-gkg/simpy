#!/usr/bin/env python3
"""
调试TCP行为，特别是重传机制
"""

import sys
sys.path.append('/Users/nancy/PycharmProjects/simpy')

from network_frontend.htsimpy.core.eventlist import EventList
from network_frontend.htsimpy.protocols.tcp import TcpSrc, TcpSink
from network_frontend.htsimpy.core.pipe import Pipe
from network_frontend.htsimpy.queues.base_queue import Queue
from network_frontend.htsimpy.core.route import Route
from network_frontend.htsimpy.core.logger.logfile import Logfile

def time_from_ms(ms):
    return ms * 1_000_000_000

def test_tcp_timeout():
    """测试TCP超时和重传机制"""
    print("测试TCP超时和重传机制...")
    
    # 创建事件列表
    eventlist = EventList()
    eventlist.set_endtime(time_from_ms(20000))  # 20秒
    
    # 创建日志文件
    logfile = Logfile("debug_tcp.log", eventlist)
    
    # 创建TCP源和接收端
    tcp_src = TcpSrc(None, None, eventlist)
    tcp_src.setName("TestTCP")
    tcp_sink = TcpSink()
    tcp_sink.setName("TestSink")
    
    # 创建一个高延迟的管道来触发超时
    pipe_out = Pipe(time_from_ms(5000), eventlist)  # 5秒延迟
    pipe_out.setName("HighLatencyPipe")
    
    pipe_back = Pipe(time_from_ms(10), eventlist)  # 10ms返回延迟
    pipe_back.setName("ReturnPipe")
    
    # 创建路由
    route_out = Route()
    route_out.push_back(pipe_out)
    route_out.push_back(tcp_sink)
    
    route_in = Route()
    route_in.push_back(pipe_back)
    route_in.push_back(tcp_src)
    
    # 设置初始RTO为3秒（应该会触发重传）
    tcp_src._rto = time_from_ms(3000)
    
    print(f"初始RTO: {tcp_src._rto // 1_000_000}ms")
    print(f"管道延迟: {5000}ms (单向)")
    print("预期: 应该看到重传，因为RTT(10秒) > RTO(3秒)")
    
    # 连接并开始发送
    tcp_src.connect(route_out, route_in, tcp_sink, 0)
    
    # 运行仿真
    print("\n运行仿真...")
    events = 0
    retransmits = 0
    last_time = 0
    
    while eventlist.do_next_event():
        events += 1
        current_time = eventlist.now()
        
        # 检查TCP源的状态
        if events % 100 == 0:
            time_ms = current_time // 1_000_000
            if hasattr(tcp_src, '_last_acked'):
                print(f"时间: {time_ms}ms, 事件: {events}, "
                      f"最后确认: {tcp_src._last_acked}, "
                      f"已发送: {tcp_src._highest_sent}, "
                      f"CWND: {tcp_src._cwnd}")
            
            # 检查是否有重传
            if hasattr(tcp_src, '_retransmit_cnt'):
                if tcp_src._retransmit_cnt > retransmits:
                    retransmits = tcp_src._retransmit_cnt
                    print(f"  *** 检测到重传! 总重传次数: {retransmits}")
    
    print(f"\n仿真完成:")
    print(f"  总事件数: {events}")
    print(f"  总重传次数: {retransmits}")
    
    # 检查TCP源的最终状态
    if hasattr(tcp_src, '_last_acked'):
        print(f"  最终确认序号: {tcp_src._last_acked}")
    if hasattr(tcp_src, '_highest_sent'):
        print(f"  最高发送序号: {tcp_src._highest_sent}")
    if hasattr(tcp_src, '_cwnd'):
        print(f"  最终拥塞窗口: {tcp_src._cwnd}")

def check_tcp_implementation():
    """检查TCP实现中的重传相关代码"""
    print("\n检查TCP重传实现...")
    
    # 导入TCP模块
    from network_frontend.htsimpy.protocols import tcp
    
    # 检查TcpSrc类中是否有重传相关的方法
    tcp_methods = [method for method in dir(tcp.TcpSrc) if not method.startswith('_')]
    retransmit_methods = [m for m in tcp_methods if 'retransmit' in m.lower() or 'timeout' in m.lower()]
    
    print(f"TCP源端方法总数: {len(tcp_methods)}")
    print(f"重传相关方法: {retransmit_methods}")
    
    # 检查私有方法和属性
    all_attrs = dir(tcp.TcpSrc)
    private_retransmit = [a for a in all_attrs if ('retransmit' in a.lower() or 'timeout' in a.lower() or 'rto' in a.lower())]
    print(f"所有重传/超时相关属性和方法: {private_retransmit}")

if __name__ == "__main__":
    # 只运行实现检查，避免EventList单例问题
    # test_tcp_timeout()
    check_tcp_implementation()