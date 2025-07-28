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
"""

import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../..'))

from network_frontend.htsimpy.core.eventlist import EventList
from network_frontend.htsimpy.core.network import PacketFlow
from network_frontend.htsimpy.queues.fifo_queue import FIFOQueue
from network_frontend.htsimpy.packets.ndp_packet import NDPPacket
from network_frontend.htsimpy.core.logger import Logger


class SimpleReceiver:
    """简单的数据包接收器"""
    
    def __init__(self, name: str):
        self.name = name
        self.received_packets = []
    
    def receive_packet(self, packet):
        """接收数据包"""
        self.received_packets.append(packet)
        print(f"[{self.name}] 接收到数据包: {packet}")
        
        # 释放数据包
        packet.free()


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
        eventlist=eventlist,
        name="链路队列",
        capacity=10,  # 队列容量10个包
        link_speed=1_000_000_000  # 1Gbps链路
    )
    
    # 4. 创建数据包流
    print("4. 创建数据包流...")
    flow = PacketFlow(logger=None)
    flow.set_flow_id(1)
    
    # 5. 创建路由：队列 -> 接收器
    print("5. 设置路由...")
    route = [queue, receiver]
    
    # 6. 创建并发送NDP数据包
    print("6. 创建并发送NDP数据包...")
    
    for i in range(3):
        # 创建NDP数据包
        packet = NDPPacket()
        packet.set(
            flow=flow,
            pkt_size=1500,  # 1500字节数据包
            pkt_id=i,
            seq_no=i * 1500,
            ack_no=0,
            window_size=65536
        )
        
        # 设置路由
        packet.set_route(route)
        
        print(f"   发送数据包 {i+1}: {packet}")
        
        # 发送到队列
        queue.receive_packet(packet)
    
    # 7. 运行仿真
    print()
    print("7. 运行仿真...")
    print("   注意：目前仅演示数据结构创建，完整的事件仿真需要更多组件实现")
    
    # 8. 输出结果
    print()
    print("8. 仿真结果:")
    print(f"   队列状态: {queue}")
    print(f"   事件调度器状态: {eventlist}")
    print(f"   接收器状态: 准备接收数据包")
    
    print()
    print("=== 示例完成 ===")
    print("这个示例展示了HTSimPy的基本组件创建和配置过程")


if __name__ == "__main__":
    main() 