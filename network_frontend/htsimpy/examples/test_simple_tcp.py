#!/usr/bin/env python3
"""
简单的TCP测试 - 用于调试TCP连接问题
"""

import sys
from network_frontend.htsimpy.core.eventlist import EventList
from network_frontend.htsimpy.core.network import Packet
from network_frontend.htsimpy.core.route import Route
from network_frontend.htsimpy.core.pipe import Pipe
from network_frontend.htsimpy.queues.base_queue import Queue
from network_frontend.htsimpy.protocols.tcp import TcpSrc, TcpSink, TcpRtxTimerScanner


def time_from_ms(ms: int) -> int:
    """毫秒转换为皮秒"""
    return ms * 1_000_000_000_000


def main():
    print("=== 简单TCP连接测试 ===")
    
    # 创建事件调度器
    eventlist = EventList()
    eventlist.set_endtime(time_from_ms(1000))  # 1秒
    
    # 创建网络组件
    queue_out = Queue(
        bitrate=10_000_000,  # 10Mbps
        maxsize=100_000,     # 100KB
        eventlist=eventlist
    )
    queue_out.setName("queue_out")
    
    pipe_out = Pipe(time_from_ms(10), eventlist)  # 10ms延迟
    pipe_out.setName("pipe_out")
    
    queue_back = Queue(
        bitrate=10_000_000,  # 10Mbps
        maxsize=100_000,     # 100KB
        eventlist=eventlist
    )
    queue_back.setName("queue_back")
    
    pipe_back = Pipe(time_from_ms(10), eventlist)  # 10ms延迟
    pipe_back.setName("pipe_back")
    
    # 创建TCP源和接收端
    tcp_src = TcpSrc(None, None, eventlist)
    tcp_src.setName("tcp_src")
    tcp_src._ssthresh = 100 * 1500  # 设置慢启动阈值
    
    tcp_sink = TcpSink()
    tcp_sink.setName("tcp_sink")
    
    # 创建重传定时器
    rtx_scanner = TcpRtxTimerScanner(time_from_ms(10), eventlist)
    rtx_scanner.registerTcp(tcp_src)
    
    # 建立路由
    route_out = Route()
    route_out.push_back(queue_out)
    route_out.push_back(pipe_out)
    route_out.push_back(tcp_sink)
    
    route_back = Route()
    route_back.push_back(queue_back)
    route_back.push_back(pipe_back)
    route_back.push_back(tcp_src)
    
    print(f"路由出: {route_out}")
    print(f"路由回: {route_back}")
    
    # 连接TCP
    tcp_src.connect(route_out, route_back, tcp_sink, 0)
    
    # 运行仿真
    print("\n开始仿真...")
    event_count = 0
    
    try:
        while eventlist.do_next_event() and event_count < 100:
            event_count += 1
            sim_time = eventlist.now() / 1e12
            print(f"事件 {event_count}: 时间={sim_time:.6f}s")
    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()
    
    print(f"\n仿真结束，总事件数: {event_count}")
    print(f"TCP状态:")
    print(f"  已建立: {tcp_src._established}")
    print(f"  最高发送: {tcp_src._highest_sent}")
    print(f"  最后确认: {tcp_src._last_acked}")
    print(f"  包发送数: {tcp_src._packets_sent}")


if __name__ == "__main__":
    main()