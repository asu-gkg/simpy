#!/usr/bin/env python3
"""
HTSimPy TCP协议示例

演示TCP协议的基本功能（对应tcp.h/cpp和tcppacket.h/cpp）
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../..'))

from network_frontend.htsimpy.core.eventlist import EventList
from network_frontend.htsimpy.core.network import PacketFlow
from network_frontend.htsimpy.queues.fifo_queue import FIFOQueue
from network_frontend.htsimpy.packets.tcp_packet import TCPPacket


class TCPReceiver:
    """TCP数据包接收器"""
    
    def __init__(self, name: str):
        self.name = name
        self.received_packets = []
    
    def receive_packet(self, packet):
        """接收TCP数据包"""
        self.received_packets.append(packet)
        print(f"[{self.name}] 接收到TCP数据包: 序列号={packet.seq_no}, 大小={packet.size}字节")
        packet.free()


def main():
    """主函数 - 演示TCP协议通信"""
    
    print("=== HTSimPy TCP协议示例 ===")
    
    # 1. 创建事件调度器（对应eventlist.h/cpp）
    eventlist = EventList()
    
    # 2. 创建TCP接收器
    receiver = TCPReceiver("TCP接收器")
    
    # 3. 创建FIFO队列（对应queue.h/cpp）
    queue = FIFOQueue(eventlist, "TCP链路队列", capacity=20, link_speed=10_000_000_000)
    
    # 4. 创建数据包流
    flow = PacketFlow(logger=None)
    flow.set_flow_id(100)
    
    # 5. 创建TCP数据包
    print("创建TCP数据包...")
    
    # SYN包
    syn_packet = TCPPacket()
    syn_packet.set(flow, 64, 1, 1000, 0, 65536, 0x02)
    syn_packet.set_syn(True)
    print(f"SYN包: 序列号={syn_packet.seq_no}")
    
    # 数据包
    data_packet = TCPPacket()  
    data_packet.set(flow, 1460, 2, 1001, 0, 65536, 0x18)
    data_packet.set_ack(True)
    print(f"数据包: 序列号={data_packet.seq_no}")
    
    print("=== TCP示例完成 ===")


if __name__ == "__main__":
    main()