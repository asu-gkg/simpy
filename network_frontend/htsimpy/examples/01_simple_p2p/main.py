#!/usr/bin/env python3
"""
HTSimPy 简单点对点通信示例

演示最基本的HTSimPy功能：
1. 创建事件调度器
2. 创建简单的点对点链路  
3. 使用NDP协议发送数据包
4. 基础日志输出

对应的htsim概念：
- EventList (eventlist.h/cpp)
- NDP协议 (ndp.h/cpp)  
- 基础队列 (queue.h/cpp)
- Pipe网络链路 (pipe.h/cpp)
"""

import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../..'))
import rich
from network_frontend.htsimpy.core.eventlist import EventList
from network_frontend.htsimpy.core.network import PacketFlow, PacketSink
from network_frontend.htsimpy.core.route import Route
from network_frontend.htsimpy.core.pipe import Pipe
from network_frontend.htsimpy.queues.fifo_queue import FIFOQueue
from network_frontend.htsimpy.packets.ndp_packet import NDPPacket
from network_frontend.htsimpy.core.logger import Logger


class SimpleReceiver(PacketSink):
    """简单的数据包接收器 - 实现PacketSink接口"""
    
    def __init__(self, name: str):
        super().__init__(name)  # 调用PacketSink构造函数
        self.name = name
        self.received_packets = []
    
    def receive_packet(self, packet, virtual_queue=None):
        """接收数据包 - 实现PacketSink的抽象方法"""
        self.received_packets.append(packet)
        print(f"[{self.name}] 接收到数据包: {packet}")
        
        # 释放数据包
        packet.free()
    
    def nodename(self) -> str:
        """返回节点名称 - 实现PacketSink的抽象方法"""
        return self.name


def main():
    """主函数 - 演示简单的点对点通信"""
    
    print("=== HTSimPy 简单点对点通信示例 ===")
    print()
    
    # 1. 创建事件调度器（对应EventList）
    print("1. 创建事件调度器...")
    eventlist = EventList()
    
    # 2. 创建接收器
    print("2. 创建接收器...")
    receiver = SimpleReceiver("接收器_1")
    
    # 3. 创建FIFO队列（对应queue.h/cpp）
    print("3. 创建FIFO队列...")
    queue = FIFOQueue(
        bitrate=1_000_000_000,  # 1Gbps链路速度
        maxsize=10*1500,  # 队列容量（字节）：10个1500字节的包
        eventlist=eventlist
    )
    
    # 4. 创建网络链路Pipe（对应pipe.h/cpp）
    print("4. 创建网络链路...")
    pipe = Pipe(
        delay=1000000,  # 1ms延迟（1,000,000皮秒）
        eventlist=eventlist
    )
    
    # 5. 创建数据包流
    print("5. 创建数据包流...")
    flow = PacketFlow(logger=None)
    flow.set_flow_id(1)
    
    # 6. 使用正确的Route类创建路由：pipe -> receiver
    print("6. 设置路由...")
    route = Route()
    # 注意：路由不包括源队列，只包括后续的跳数
    route.push_back(pipe)      # 添加网络链路到路由路径  
    route.push_back(receiver)  # 添加接收器到路由路径
    print(f"   路由设置: pipe -> receiver (共{route.size()}跳)")
    
    # 7. 设置组件间的连接
    print("7. 设置组件连接...")
    # 设置队列输出到管道
    queue.setNext(pipe)        # 队列的下一跳是pipe 
    pipe.set_next(receiver)    # pipe的下一跳是receiver
    print(f"   连接链: 队列 -> {pipe} -> {receiver.nodename()}")
    
    # 8. 创建并发送NDP数据包
    print("8. 创建并发送NDP数据包...")
    
    for i in range(3):
        # 创建NDP数据包
        seqno = i * 1500  # 序列号
        pacerno = i       # 包序号
        packet = NDPPacket.newpkt(
            flow=flow,
            seqno=seqno,
            pacerno=pacerno,
            size=1500,        # 1500字节数据包大小
            retransmitted=False,
            last_packet=(i == 2)  # 最后一个包
        )
        
        # 设置路由
        packet.set_route(route)
        
        print(f"   发送数据包 {i+1}: {packet}")
        
        # 发送到队列
        print(f"   当前仿真时间: {eventlist.now():,}ps, 队列中数据包: {queue.packet_count}")
        queue.receive_packet(packet)
        print(f"   发送后队列状态: {queue.packet_count}个包, {queue.queuesize()}字节")
    
    # 9. 运行仿真
    print()
    print("9. 运行仿真...")
    
    # 设置仿真结束时间（可选）
    sim_end_time = 20_000_000 *1000  # 20ms（20,000,000皮秒）
    eventlist.set_endtime(sim_end_time)
    print(f"   设置仿真结束时间: {sim_end_time:,}ps ({sim_end_time/1_000_000:.1f}ms)")
    
    # 运行事件循环
    print("   开始执行事件循环...")
    event_count = 0
    max_events = 10  # 防止无限循环
    
    while event_count < max_events and eventlist.do_next_event():
        event_count += 1
        current_time = eventlist.now()
        current_ms = current_time / 1_000_000
        pending_events = len(eventlist._pendingsources)
        
        print(f"   执行事件 #{event_count}: 时间={current_time:,}ps ({current_ms:.3f}ms), 剩余事件={pending_events}")
        
        # 如果时间超过结束时间，停止
        if current_time >= sim_end_time:
            print(f"   达到仿真结束时间，停止执行")
            break
    
    if event_count >= max_events:
        print(f"   达到最大事件数量限制({max_events})，停止执行")
    elif event_count == 0:
        print("   没有事件可以执行")
    else:
        print(f"   仿真完成！共执行了 {event_count} 个事件")
    
    # 10. 输出结果
    print()
    print("10. 仿真结果:")
    print(f"    队列状态: {queue}")
    print(f"      - 队列长度: {queue.queuesize()} 字节")
    print(f"      - 队列中数据包数: {queue.packet_count}")
    print(f"      - 队列是否为空: {queue.is_empty}")
    print(f"    网络链路: {pipe}")
    print(f"      - 延迟: {pipe._delay//1000000}ms")
    print(f"      - 传输中数据包: {pipe._count}")
    print(f"    路由信息: 路径长度={route.size()}, 跳数={route.hop_count()}")
    print(f"    网络拓扑: 队列 -> 链路({pipe._delay//1000000}ms) -> 接收器")
    print(f"    事件调度器详细状态:")
    print(f"      - 当前仿真时间: {eventlist.now():,} 皮秒 ({eventlist.now()/1_000_000:.3f} ms)")
    print(f"      - 最后事件时间: {eventlist._lasteventtime:,} 皮秒")
    print(f"      - 结束时间设置: {eventlist._endtime:,} 皮秒")
    print(f"      - 实例计数: {eventlist._instance_count}")
    print(f"      - 待处理事件源: {len(eventlist._pendingsources)} 个")
    
    if eventlist._pendingsources:
        print("      - 待处理事件详情:")
        for i, (when, source) in enumerate(eventlist._pendingsources[:5]):  # 只显示前5个
            time_ms = when / 1_000_000
            print(f"        [{i+1}] 时间: {when:,}ps ({time_ms:.3f}ms), 源: {source}")
        if len(eventlist._pendingsources) > 5:
            print(f"        ... 还有 {len(eventlist._pendingsources) - 5} 个事件")
    
    print(f"      - 待处理触发器: {len(eventlist._pending_triggers)} 个")
    
    if eventlist._pending_triggers:
        print("      - 触发器详情:")
        for i, trigger in enumerate(eventlist._pending_triggers[:3]):  # 只显示前3个
            print(f"        [{i+1}] {trigger}")
        if len(eventlist._pending_triggers) > 3:
            print(f"        ... 还有 {len(eventlist._pending_triggers) - 3} 个触发器")
    
    # 还可以用rich显示对象概览
    print(f"      - 对象概览:")
    rich.inspect(eventlist)
    print(f"    接收器状态:")
    print(f"      - 节点名称: {receiver.nodename()}")
    print(f"      - 已接收数据包数量: {len(receiver.received_packets)}")
    
    if receiver.received_packets:
        print("      - 接收到的数据包详情:")
        for i, pkt in enumerate(receiver.received_packets):
            print(f"        [{i+1}] {pkt}")
    else:
        print("      - 尚未接收到任何数据包（可能需要完善数据包路由流程）")
    
    print()
    print("=== 示例完成 ===")
    print("这个示例展示了完整的HTSimPy网络拓扑：队列-链路-接收器")


if __name__ == "__main__":
    main() 