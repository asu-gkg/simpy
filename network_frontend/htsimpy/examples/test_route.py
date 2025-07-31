#!/usr/bin/env python3
"""
测试路由问题
"""

from network_frontend.htsimpy.core.eventlist import EventList
from network_frontend.htsimpy.core.network import Packet, PacketFlow, PacketSink
from network_frontend.htsimpy.core.route import Route
from network_frontend.htsimpy.packets.tcp_packet import TcpAck


class DummySink(PacketSink):
    def __init__(self, name):
        super().__init__()
        self.name = name
        self.received = []
    
    def receivePacket(self, pkt, previousHop=None):
        print(f"{self.name} received packet, nexthop={pkt._nexthop}, route.size()={pkt._route.size() if pkt._route else 'None'}")
        self.received.append(pkt)
        # 不再继续发送
    
    def nodename(self):
        return self.name


def main():
    print("=== 路由测试 ===")
    
    # 创建事件调度器
    eventlist = EventList()
    
    # 创建网络节点
    sink1 = DummySink("sink1")
    sink2 = DummySink("sink2")
    
    # 创建路由：sink1 -> sink2
    route = Route()
    route.push_back(sink1)
    route.push_back(sink2)
    
    print(f"路由: {route}, size={route.size()}")
    
    # 创建数据包
    flow = PacketFlow(None)
    ack = TcpAck.newpkt(flow, route, 0, 1, 0)
    
    print(f"\n发送数据包...")
    print(f"初始 nexthop={ack._nexthop}")
    
    # 第一次sendOn - 应该到达sink1
    print(f"\n第一次sendOn:")
    ack.sendOn()
    
    print(f"sendOn后 nexthop={ack._nexthop}")
    
    # 第二次sendOn - 应该到达sink2
    print(f"\n第二次sendOn:")
    try:
        ack.sendOn()
        print(f"sendOn后 nexthop={ack._nexthop}")
    except AssertionError as e:
        print(f"错误: {e}")
        print(f"当前 nexthop={ack._nexthop}, route.size()={ack._route.size()}")
    
    # 尝试第三次sendOn - 应该失败
    print(f"\n第三次sendOn:")
    try:
        ack.sendOn()
    except AssertionError as e:
        print(f"预期的错误: nexthop超出路由范围")
        print(f"当前 nexthop={ack._nexthop}, route.size()={ack._route.size()}")


if __name__ == "__main__":
    main()