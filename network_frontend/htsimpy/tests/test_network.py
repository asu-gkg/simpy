"""
Unit tests for network.py - 验证与C++实现的功能对应

测试所有类和函数的行为是否与C++版本一致
"""

import pytest
import sys
from unittest.mock import Mock, MagicMock
from typing import Optional

# 导入被测试的模块
from network_frontend.htsimpy.core.network import (
    PacketType, PacketDirection, PacketPriority,
    DataReceiver, PacketFlow, VirtualQueue, PacketSink, Packet, PacketDB,
    DEFAULTDATASIZE, FLOW_ID_DYNAMIC_BASE, UINT32_MAX,
    print_route
)
from network_frontend.htsimpy.core.logger.core import Logged
from network_frontend.htsimpy.core.logger.traffic import TrafficLogger


class MockRoute:
    """模拟Route类用于测试"""
    def __init__(self, sinks):
        self._sinks = sinks
        self._reverse_route = None
    
    def size(self):
        return len(self._sinks)
    
    def at(self, index):
        return self._sinks[index]
    
    def reverse(self):
        if self._reverse_route is None:
            # 创建反向路由
            self._reverse_route = MockRoute(list(reversed(self._sinks)))
            self._reverse_route._reverse_route = self
        return self._reverse_route


class MockPacketSink(PacketSink):
    """模拟PacketSink用于测试"""
    def __init__(self, name="MockSink"):
        super().__init__()
        self._name = name
        self.received_packets = []
        self.received_with_queue = []
    
    def receivePacket(self, pkt: Packet, previousHop: Optional[VirtualQueue] = None):
        if previousHop is None:
            self.received_packets.append(pkt)
        else:
            self.received_with_queue.append((pkt, previousHop))
    
    def nodename(self) -> str:
        return self._name


class MockDataReceiver(DataReceiver):
    """模拟DataReceiver用于测试"""
    def __init__(self, name="MockReceiver"):
        super().__init__(name)
        self._cumulative_ack = 0
        self._drops = 0
    
    def cumulative_ack(self) -> int:
        return self._cumulative_ack
    
    def drops(self) -> int:
        return self._drops


class MockVirtualQueue(VirtualQueue):
    """模拟VirtualQueue用于测试"""
    def __init__(self):
        super().__init__()
        self.completed_packets = []
    
    def completedService(self, pkt: Packet) -> None:
        self.completed_packets.append(pkt)


class MockPacket(Packet):
    """模拟Packet用于测试"""
    def priority(self) -> PacketPriority:
        return PacketPriority.PRIO_LO


class TestPacketType:
    """测试PacketType枚举"""
    
    def test_packet_type_values(self):
        """验证所有枚举值与C++一致"""
        assert PacketType.IP == 0
        assert PacketType.TCP == 1
        assert PacketType.TCPACK == 2
        assert PacketType.TCPNACK == 3
        assert PacketType.SWIFT == 4
        assert PacketType.SWIFTACK == 5
        assert PacketType.STRACK == 6
        assert PacketType.STRACKACK == 7
        assert PacketType.NDP == 8
        assert PacketType.NDPACK == 9
        assert PacketType.NDPNACK == 10
        assert PacketType.NDPPULL == 11
        assert PacketType.NDPRTS == 12
        assert PacketType.NDPLITE == 13
        assert PacketType.NDPLITEACK == 14
        assert PacketType.NDPLITEPULL == 15
        assert PacketType.NDPLITERTS == 16
        assert PacketType.ETH_PAUSE == 17
        assert PacketType.TOFINO_TRIM == 18
        assert PacketType.ROCE == 19
        assert PacketType.ROCEACK == 20
        assert PacketType.ROCENACK == 21
        assert PacketType.HPCC == 22
        assert PacketType.HPCCACK == 23
        assert PacketType.HPCCNACK == 24
        assert PacketType.EQDSDATA == 25
        assert PacketType.EQDSPULL == 26
        assert PacketType.EQDSACK == 27
        assert PacketType.EQDSNACK == 28
        assert PacketType.EQDSRTS == 29


class TestPacketDirection:
    """测试PacketDirection枚举"""
    
    def test_packet_direction_values(self):
        """验证方向枚举值"""
        assert PacketDirection.NONE == 0
        assert PacketDirection.UP == 1
        assert PacketDirection.DOWN == 2


class TestPacketPriority:
    """测试PacketPriority枚举"""
    
    def test_packet_priority_values(self):
        """验证优先级枚举值"""
        assert PacketPriority.PRIO_LO == 0
        assert PacketPriority.PRIO_MID == 1
        assert PacketPriority.PRIO_HI == 2
        assert PacketPriority.PRIO_NONE == 3


class TestPrintRoute:
    """测试print_route函数"""
    
    def test_print_route(self, capsys):
        """验证路由打印功能"""
        # 创建模拟路由
        sink1 = MockPacketSink("Sink1")
        sink2 = MockPacketSink("Sink2")
        sink3 = MockPacketSink("Sink3")
        route = MockRoute([sink1, sink2, sink3])
        
        # 调用print_route
        print_route(route)
        
        # 验证输出
        captured = capsys.readouterr()
        assert captured.out == "Sink1 -> Sink2 -> Sink3\n"


class TestDataReceiver:
    """测试DataReceiver抽象类"""
    
    def test_data_receiver_creation(self):
        """验证DataReceiver的创建和基本功能"""
        receiver = MockDataReceiver("TestReceiver")
        
        # 验证名称设置（继承自Logged）
        assert receiver._name == "TestReceiver"
        
        # 验证抽象方法
        assert receiver.cumulative_ack() == 0
        assert receiver.drops() == 0


class TestPacketFlow:
    """测试PacketFlow类"""
    
    def test_packet_flow_creation(self):
        """验证PacketFlow的创建和流ID分配"""
        # 重置静态计数器
        original_max_id = PacketFlow._max_flow_id
        PacketFlow._max_flow_id = FLOW_ID_DYNAMIC_BASE
        
        try:
            # 创建第一个流
            logger = Mock(spec=TrafficLogger)
            flow1 = PacketFlow(logger)
            
            assert flow1._logger == logger
            assert flow1.flow_id() == FLOW_ID_DYNAMIC_BASE
            assert flow1._name == "PacketFlow"
            
            # 创建第二个流，验证ID递增
            flow2 = PacketFlow(None)
            assert flow2.flow_id() == FLOW_ID_DYNAMIC_BASE + 1
            assert flow2._logger is None
            
        finally:
            # 恢复原始值
            PacketFlow._max_flow_id = original_max_id
    
    def test_set_flowid(self):
        """测试手动设置流ID"""
        flow = PacketFlow(None)
        
        # 设置合法的流ID
        flow.set_flowid(12345)
        assert flow.flow_id() == 12345
        
        # 设置非法的流ID（>= FLOW_ID_DYNAMIC_BASE）
        with pytest.raises(SystemExit):
            flow.set_flowid(FLOW_ID_DYNAMIC_BASE)
    
    def test_log_traffic(self):
        """测试流量日志功能"""
        logger = Mock(spec=TrafficLogger)
        flow = PacketFlow(logger)
        
        pkt = Mock()
        location = Mock(spec=Logged)
        event = "TEST_EVENT"
        
        # 有logger时应该调用
        flow.logTraffic(pkt, location, event)
        logger.logTraffic.assert_called_once_with(pkt, location, event)
        
        # 没有logger时不应该出错
        flow2 = PacketFlow(None)
        flow2.logTraffic(pkt, location, event)  # 不应该抛出异常
    
    def test_log_me(self):
        """测试log_me方法"""
        flow_with_logger = PacketFlow(Mock(spec=TrafficLogger))
        assert flow_with_logger.log_me() == True
        
        flow_without_logger = PacketFlow(None)
        assert flow_without_logger.log_me() == False


class TestVirtualQueue:
    """测试VirtualQueue抽象类"""
    
    def test_virtual_queue_creation(self):
        """验证VirtualQueue的创建"""
        queue = MockVirtualQueue()
        
        # 测试completedService方法
        pkt = MockPacket()
        queue.completedService(pkt)
        assert len(queue.completed_packets) == 1
        assert queue.completed_packets[0] == pkt


class TestPacketSink:
    """测试PacketSink抽象类"""
    
    def test_packet_sink_creation(self):
        """验证PacketSink的创建和初始化"""
        sink = MockPacketSink("TestSink")
        assert sink._remoteEndpoint is None
        assert sink.nodename() == "TestSink"
    
    def test_remote_endpoint(self):
        """测试远程端点设置"""
        sink1 = MockPacketSink("Sink1")
        sink2 = MockPacketSink("Sink2")
        
        # 测试setRemoteEndpoint
        sink1.setRemoteEndpoint(sink2)
        assert sink1.getRemoteEndpoint() == sink2
        assert sink2.getRemoteEndpoint() is None
        
        # 测试setRemoteEndpoint2（双向设置）
        sink3 = MockPacketSink("Sink3")
        sink4 = MockPacketSink("Sink4")
        sink3.setRemoteEndpoint2(sink4)
        assert sink3.getRemoteEndpoint() == sink4
        assert sink4.getRemoteEndpoint() == sink3
    
    def test_receive_packet(self):
        """测试接收数据包"""
        sink = MockPacketSink()
        pkt = MockPacket()
        
        # 测试普通接收
        sink.receivePacket(pkt)
        assert len(sink.received_packets) == 1
        
        # 测试带VirtualQueue的接收
        queue = MockVirtualQueue()
        sink.receivePacket(pkt, queue)
        assert len(sink.received_with_queue) == 1


class TestPacket:
    """测试Packet类"""
    
    def test_static_members(self):
        """验证静态成员变量"""
        assert Packet._data_packet_size == DEFAULTDATASIZE
        assert Packet._packet_size_fixed == False
        assert Packet._defaultFlow is not None
    
    def test_packet_creation(self):
        """测试Packet的创建和初始化"""
        pkt = MockPacket()
        
        # 验证初始值
        assert pkt._is_header == False
        assert pkt._bounced == False
        assert pkt._type == PacketType.IP
        assert pkt._flags == 0
        assert pkt._refcount == 0
        assert pkt._dst == UINT32_MAX
        assert pkt._pathid == UINT32_MAX
        assert pkt._direction == PacketDirection.NONE
        assert pkt._ingressqueue is None
    
    def test_packet_size_management(self):
        """测试数据包大小管理"""
        # 保存原始值
        original_size = Packet._data_packet_size
        original_fixed = Packet._packet_size_fixed
        
        try:
            # 重置状态
            Packet._packet_size_fixed = False
            
            # 设置新大小
            Packet.set_packet_size(9000)
            assert Packet._data_packet_size == 9000
            
            # 获取大小会锁定它
            size = Packet.data_packet_size()
            assert size == 9000
            assert Packet._packet_size_fixed == True
            
            # 尝试在锁定后设置应该失败
            with pytest.raises(AssertionError):
                Packet.set_packet_size(1500)
        
        finally:
            # 恢复原始值
            Packet._data_packet_size = original_size
            Packet._packet_size_fixed = original_fixed
    
    def test_send_on(self):
        """测试sendOn方法"""
        pkt = MockPacket()
        
        # 创建路由
        sink1 = MockPacketSink("Sink1")
        sink2 = MockPacketSink("Sink2")
        sink3 = MockPacketSink("Sink3")
        route = MockRoute([sink1, sink2, sink3])
        
        # 设置路由
        pkt.set_route(route)
        
        # 第一跳
        next_sink = pkt.sendOn()
        assert next_sink == sink1
        assert pkt._nexthop == 1
        assert len(sink1.received_packets) == 1
        
        # 第二跳
        next_sink = pkt.sendOn()
        assert next_sink == sink2
        assert pkt._nexthop == 2
    
    def test_bounce_unbounce(self):
        """测试bounce和unbounce功能"""
        pkt = MockPacket()
        
        # 创建路由
        sinks = [MockPacketSink(f"Sink{i}") for i in range(4)]
        route = MockRoute(sinks)
        pkt.set_route(route)
        
        # 前进几步
        pkt.sendOn()  # nexthop = 1
        pkt.sendOn()  # nexthop = 2
        
        # Bounce
        pkt.bounce()
        assert pkt._bounced == True
        assert pkt._is_header == True
        assert pkt._nexthop == 2  # route.size() - nexthop = 4 - 2 = 2
        
        # 发送应该使用反向路由
        next_sink = pkt.sendOn()
        # 反向路由是 [Sink3, Sink2, Sink1, Sink0]
        # nexthop=2 意味着获取反向路由的第2个元素（索引2），即Sink1
        assert next_sink == sinks[1]
        
        # Unbounce
        pkt.unbounce(1500)
        assert pkt._bounced == False
        assert pkt._is_header == False
        assert pkt._size == 1500
        assert pkt._nexthop == 0
    
    def test_direction_management(self):
        """测试方向管理"""
        pkt = MockPacket()
        
        # 初始为NONE，可以设置为UP
        pkt.go_up()
        assert pkt._direction == PacketDirection.UP
        
        # UP状态可以变为DOWN
        pkt.go_down()
        assert pkt._direction == PacketDirection.DOWN
        
        # DOWN状态不能再go_up
        with pytest.raises(SystemExit):
            pkt.go_up()
        
        # 测试set_direction
        pkt2 = MockPacket()
        pkt2.set_direction(PacketDirection.UP)
        assert pkt2._direction == PacketDirection.UP
        
        # 相同方向不会改变
        pkt2.set_direction(PacketDirection.UP)
        assert pkt2._direction == PacketDirection.UP
        
        # UP可以变为DOWN
        pkt2.set_direction(PacketDirection.DOWN)
        assert pkt2._direction == PacketDirection.DOWN
    
    def test_reference_counting(self):
        """测试引用计数"""
        pkt = MockPacket()
        assert pkt.ref_count() == 0
        
        pkt.inc_ref_count()
        assert pkt.ref_count() == 1
        
        pkt.inc_ref_count()
        assert pkt.ref_count() == 2
        
        pkt.dec_ref_count()
        assert pkt.ref_count() == 1
    
    def test_packet_str(self):
        """测试str方法，包括C++中的bug"""
        pkt = MockPacket()
        
        # 测试正常类型
        pkt._type = PacketType.TCP
        assert pkt.str() == "TCP"
        
        pkt._type = PacketType.NDP
        assert pkt.str() == "NDP"
        
        # 测试C++中的bug：STRACK返回"SWIFT"
        pkt._type = PacketType.STRACK
        assert pkt.str() == "SWIFT"  # 这是C++中的bug！
        
        # 测试C++中的bug：STRACKACK返回"SWIFTACK"
        pkt._type = PacketType.STRACKACK
        assert pkt.str() == "SWIFTACK"  # 这是C++中的bug！
    
    def test_set_attrs(self):
        """测试set_attrs方法"""
        pkt = MockPacket()
        flow = PacketFlow(None)
        
        pkt.set_attrs(flow, 1500, 12345)
        
        assert pkt._flow == flow
        assert pkt._size == 1500
        assert pkt._oldsize == 1500
        assert pkt._id == 12345
        assert pkt._nexthop == 0
        assert pkt._oldnexthop == 0
        assert pkt._route is None
        assert pkt._is_header == False
        assert pkt._flags == 0
        assert pkt._next_routed_hop is None
    
    def test_set_route_overloads(self):
        """测试set_route的多个重载版本"""
        pkt = MockPacket()
        
        # 测试单参数版本 - set_route(route)
        route1 = MockRoute([MockPacketSink()])
        pkt.set_route(route1)
        assert pkt._route == route1
        assert pkt._nexthop == 0
        
        # 测试四参数版本 - set_route(flow, route, pkt_size, id)
        flow = PacketFlow(None)
        route2 = MockRoute([MockPacketSink(), MockPacketSink()])
        pkt.set_route(flow, route2, 2000, 54321)
        
        assert pkt._flow == flow
        assert pkt._route == route2
        assert pkt._size == 2000
        assert pkt._oldsize == 2000
        assert pkt._id == 54321
        assert pkt._nexthop == 0
        assert pkt._is_header == False
        assert pkt._flags == 0


class TestPacketDB:
    """测试PacketDB模板类"""
    
    def test_packet_db_allocation(self):
        """测试数据包分配和释放"""
        db = PacketDB[MockPacket]()
        
        # 初始状态
        assert db._alloc_count == 0
        assert len(db._freelist) == 0
        
        # 分配第一个数据包
        pkt1 = db.allocPacket(MockPacket)
        assert db._alloc_count == 1
        assert pkt1.ref_count() == 1
        assert len(db._freelist) == 0
        
        # 分配第二个数据包
        pkt2 = db.allocPacket(MockPacket)
        assert db._alloc_count == 2
        assert pkt2.ref_count() == 1
        
        # 释放第一个数据包
        db.freePacket(pkt1)
        assert pkt1.ref_count() == 0
        assert len(db._freelist) == 1
        
        # 再次分配应该重用释放的数据包
        pkt3 = db.allocPacket(MockPacket)
        assert pkt3 == pkt1  # 应该是同一个对象
        assert db._alloc_count == 2  # 计数不应增加
        assert pkt3.ref_count() == 1
        assert len(db._freelist) == 0
    
    def test_packet_db_ref_counting(self):
        """测试引用计数管理"""
        db = PacketDB[MockPacket]()
        
        pkt = db.allocPacket(MockPacket)
        assert pkt.ref_count() == 1
        
        # 增加引用计数
        pkt.inc_ref_count()
        assert pkt.ref_count() == 2
        
        # 第一次释放不应该放入freelist
        db.freePacket(pkt)
        assert pkt.ref_count() == 1
        assert len(db._freelist) == 0
        
        # 第二次释放才放入freelist
        db.freePacket(pkt)
        assert pkt.ref_count() == 0
        assert len(db._freelist) == 1


class TestCppBugs:
    """专门测试C++代码中的bug是否被正确复现"""
    
    def test_strack_string_bug(self):
        """验证STRACK和STRACKACK的字符串返回bug"""
        pkt = MockPacket()
        
        # STRACK应该返回"SWIFT"而不是"STRACK"
        pkt._type = PacketType.STRACK
        assert pkt.str() == "SWIFT"
        assert pkt.str() != "STRACK"  # 确认不是正确的值
        
        # STRACKACK应该返回"SWIFTACK"而不是"STRACKACK"
        pkt._type = PacketType.STRACKACK
        assert pkt.str() == "SWIFTACK"
        assert pkt.str() != "STRACKACK"  # 确认不是正确的值


if __name__ == "__main__":
    pytest.main([__file__, "-v"])