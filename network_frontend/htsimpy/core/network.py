"""
Network - Network Abstraction Layer

对应文件: network.h/cpp
功能: 网络基础抽象类，定义数据包、接收器、流等核心概念

主要类:
- Packet: 数据包基类
- PacketSink: 数据包接收器
- PacketFlow: 数据包流
- DataReceiver: 数据接收器
- VirtualQueue: 虚拟队列

C++对应关系:
- Packet::sendOn() -> Packet.send_on()
- PacketSink::receivePacket() -> PacketSink.receive_packet()
- PacketFlow::set_flowid() -> PacketFlow.set_flow_id()
"""

from abc import ABC, abstractmethod
from typing import Optional, List, Any
from enum import Enum
from .packet import PacketType, PacketDirection, PacketPriority

# 对应 C++ 中的类型定义
PacketId = int  # packetid_t
FlowId = int    # flowid_t


class DataReceiver(ABC):
    """
    数据接收器 - 对应 network.h/cpp 中的 DataReceiver 类
    
    所有能够接收数据的组件都应该实现此接口
    """
    
    def __init__(self, name: str):
        self._name = name
    
    @abstractmethod
    def cumulative_ack(self) -> int:
        """
        对应 C++ 中的 DataReceiver::cumulative_ack()
        返回累积确认号
        """
        pass
    
    @abstractmethod
    def drops(self) -> int:
        """
        对应 C++ 中的 DataReceiver::drops()
        返回丢包数量
        """
        pass


class PacketFlow:
    """
    数据包流 - 对应 network.h/cpp 中的 PacketFlow 类
    
    管理数据包的流信息和日志记录
    """
    
    _max_flow_id = 0  # 对应 C++ 中的 static packetid_t _max_flow_id
    
    def __init__(self, logger=None):
        self._logger = logger
        self._flow_id = None
        self._max_flow_id += 1
        self._flow_id = self._max_flow_id
    
    def set_logger(self, logger) -> None:
        """对应 C++ 中的 PacketFlow::set_logger()"""
        self._logger = logger
    
    def log_traffic(self, packet: 'Packet', location: Any, event_type: str) -> None:
        """
        对应 C++ 中的 PacketFlow::logTraffic()
        记录流量日志
        """
        # TODO: 实现流量日志记录
        pass
    
    def set_flow_id(self, flow_id: FlowId) -> None:
        """对应 C++ 中的 PacketFlow::set_flowid()"""
        self._flow_id = flow_id
    
    @property
    def flow_id(self) -> FlowId:
        """对应 C++ 中的 PacketFlow::flow_id()"""
        return self._flow_id
    
    def log_me(self) -> bool:
        """对应 C++ 中的 PacketFlow::log_me()"""
        return self._logger is not None


class VirtualQueue(ABC):
    """
    虚拟队列 - 对应 network.h/cpp 中的 VirtualQueue 类
    
    队列的抽象接口
    """
    
    @abstractmethod
    def completed_service(self, packet: 'Packet') -> None:
        """
        对应 C++ 中的 VirtualQueue::completedService()
        数据包服务完成时的回调
        """
        pass


class Packet(ABC):
    """
    数据包基类 - 对应 network.h/cpp 中的 Packet 类
    
    所有数据包类型的基类，定义了数据包的基本属性和行为
    """
    
    def __init__(self):
        # 对应 C++ 构造函数中的初始化
        self._is_header = False
        self._bounced = False
        self._type = PacketType.IP
        self._flags = 0
        self._refcount = 0
        self._dst = 0xFFFFFFFF  # UINT32_MAX
        self._pathid = 0xFFFFFFFF  # UINT32_MAX
        self._direction = PacketDirection.NONE
        self._ingress_queue = None
        
        # 路由相关
        self._route = None
        self._nexthop = 0
        self._next_routed_hop = None
        
        # 数据包属性
        self._size = 0
        self._id = 0
        self._flow = None
        self._path_len = 0
    
    def free(self) -> None:
        """
        对应 C++ 中的 Packet::free()
        释放数据包资源
        """
        # TODO: 实现数据包释放逻辑
        pass
    
    @classmethod
    def set_packet_size(cls, packet_size: int) -> None:
        """
        对应 C++ 中的 Packet::set_packet_size()
        设置默认数据包大小
        """
        # TODO: 实现包大小设置逻辑
        pass
    
    @classmethod
    def data_packet_size(cls) -> int:
        """
        对应 C++ 中的 Packet::data_packet_size()
        获取数据包大小
        """
        # TODO: 实现包大小获取逻辑
        return 1500  # 默认值
    
    @abstractmethod
    def send_on(self) -> 'PacketSink':
        """
        对应 C++ 中的 Packet::sendOn()
        发送数据包到下一跳
        """
        pass
    
    def previous_hop(self) -> Optional['PacketSink']:
        """对应 C++ 中的 Packet::previousHop()"""
        if self._nexthop >= 2 and self._route:
            return self._route[self._nexthop - 2]
        return None
    
    def current_hop(self) -> Optional['PacketSink']:
        """对应 C++ 中的 Packet::currentHop()"""
        if self._nexthop >= 1 and self._route:
            return self._route[self._nexthop - 1]
        return None
    
    def strip_payload(self) -> None:
        """
        对应 C++ 中的 Packet::strip_payload()
        移除数据包负载，只保留头部
        """
        assert not self._is_header
        self._is_header = True
    
    def bounce(self) -> None:
        """
        对应 C++ 中的 Packet::bounce()
        数据包反弹
        """
        # TODO: 实现数据包反弹逻辑
        pass
    
    def unbounce(self, pkt_size: int) -> None:
        """
        对应 C++ 中的 Packet::unbounce()
        取消数据包反弹
        """
        # TODO: 实现取消反弹逻辑
        pass
    
    def go_up(self) -> None:
        """对应 C++ 中的 Packet::go_up()"""
        if self._direction == PacketDirection.NONE:
            self._direction = PacketDirection.UP
        elif self._direction == PacketDirection.DOWN:
            raise RuntimeError("Invalid direction transition")
    
    def go_down(self) -> None:
        """对应 C++ 中的 Packet::go_down()"""
        if self._direction == PacketDirection.UP:
            self._direction = PacketDirection.DOWN
        elif self._direction == PacketDirection.NONE:
            raise RuntimeError("Invalid direction transition")
    
    def set_direction(self, direction: PacketDirection) -> None:
        """对应 C++ 中的 Packet::set_direction()"""
        self._direction = direction
    
    @abstractmethod
    def priority(self) -> PacketPriority:
        """
        对应 C++ 中的 Packet::priority()
        获取数据包优先级
        """
        pass
    
    def inc_ref_count(self) -> None:
        """对应 C++ 中的 Packet::inc_ref_count()"""
        self._refcount += 1
    
    def dec_ref_count(self) -> None:
        """对应 C++ 中的 Packet::dec_ref_count()"""
        self._refcount -= 1
        if self._refcount <= 0:
            self.free()
    
    @property
    def ref_count(self) -> int:
        """对应 C++ 中的 Packet::ref_count()"""
        return self._refcount
    
    def set_route(self, route: 'Route') -> None:
        """
        对应 C++ 中的 Packet::set_route()
        设置数据包路由
        """
        self._route = route
        self._nexthop = 0
        if route:
            self._path_len = len(route)
    
    # 属性访问器
    @property
    def size(self) -> int:
        """对应 C++ 中的 Packet::size()"""
        return self._size
    
    @size.setter
    def size(self, value: int) -> None:
        """对应 C++ 中的 Packet::set_size()"""
        self._size = value
    
    @property
    def type(self) -> PacketType:
        """对应 C++ 中的 Packet::type()"""
        return self._type
    
    @property
    def header_only(self) -> bool:
        """对应 C++ 中的 Packet::header_only()"""
        return self._is_header
    
    @property
    def bounced(self) -> bool:
        """对应 C++ 中的 Packet::bounced()"""
        return self._bounced
    
    @property
    def id(self) -> PacketId:
        """对应 C++ 中的 Packet::id()"""
        return self._id
    
    @property
    def flow_id(self) -> FlowId:
        """对应 C++ 中的 Packet::flow_id()"""
        return self._flow.flow_id if self._flow else 0
    
    @property
    def dst(self) -> int:
        """对应 C++ 中的 Packet::dst()"""
        return self._dst
    
    @dst.setter
    def dst(self, value: int) -> None:
        """对应 C++ 中的 Packet::set_dst()"""
        self._dst = value
    
    @property
    def pathid(self) -> int:
        """对应 C++ 中的 Packet::pathid()"""
        return self._pathid
    
    @pathid.setter
    def pathid(self, value: int) -> None:
        """对应 C++ 中的 Packet::set_pathid()"""
        self._pathid = value
    
    @property
    def direction(self) -> PacketDirection:
        """对应 C++ 中的 Packet::get_direction()"""
        return self._direction
    
    @property
    def flags(self) -> int:
        """对应 C++ 中的 Packet::flags()"""
        return self._flags
    
    @flags.setter
    def flags(self, value: int) -> None:
        """对应 C++ 中的 Packet::set_flags()"""
        self._flags = value
    
    @property
    def nexthop(self) -> int:
        """对应 C++ 中的 Packet::nexthop()"""
        return self._nexthop
    
    @property
    def path_len(self) -> int:
        """对应 C++ 中的 Packet::path_len()"""
        return self._path_len


class PacketSink(ABC):
    """
    数据包接收器 - 对应 network.h/cpp 中的 PacketSink 类
    
    所有能够接收数据包的组件都应该继承此类
    """
    
    def __init__(self, name: str):
        self._name = name
        self._remote_endpoint = None
    
    @abstractmethod
    def receive_packet(self, packet: Packet) -> None:
        """
        对应 C++ 中的 PacketSink::receivePacket()
        接收数据包
        """
        pass
    
    def set_remote_endpoint(self, endpoint: 'PacketSink') -> None:
        """
        对应 C++ 中的 PacketSink::setRemoteEndpoint()
        设置远程端点
        """
        self._remote_endpoint = endpoint
    
    def set_remote_endpoint2(self, endpoint: 'PacketSink') -> None:
        """
        对应 C++ 中的 PacketSink::setRemoteEndpoint2()
        双向设置远程端点
        """
        self._remote_endpoint = endpoint
        endpoint.set_remote_endpoint(self)
    
    @property
    def remote_endpoint(self) -> Optional['PacketSink']:
        """获取远程端点"""
        return self._remote_endpoint