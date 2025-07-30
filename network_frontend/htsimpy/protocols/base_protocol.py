"""
BaseProtocol - Base Protocol Class

对应文件: 各种协议文件的基类
功能: 定义所有网络协议的通用接口

主要类:
- BaseProtocol: 协议基类

C++对应关系:
- 各种协议类的基类 -> BaseProtocol
- 协议的基本方法 -> BaseProtocol的抽象方法
"""

from abc import ABC, abstractmethod
from typing import Optional, Any
from ..core.network import PacketSink, PacketFlow, DataReceiver
from ..core.eventlist import EventSource
from ..core.logger import Logged
from ..core.route import Route


class BaseProtocol(EventSource, PacketSink, DataReceiver):
    """
    协议基类 - 对应各种协议文件的基类
    
    所有网络协议都应该继承此类
    """
    
    def __init__(self, eventlist, name: str):
        # 明确调用每个基类的__init__，避免重复调用Logged.__init__
        EventSource.__init__(self, eventlist, name)  # 这会调用Logged.__init__
        PacketSink.__init__(self, name)
        # 跳过DataReceiver.__init__以避免重复调用Logged.__init__
        # 但我们需要初始化DataReceiver特有的属性（如果有的话）
        
        # 协议状态
        self._connected = False
        self._flow = None
        self._route = None
        self._remote_endpoint = None
        
        # 统计信息
        self._bytes_sent = 0
        self._bytes_received = 0
        self._packets_sent = 0
        self._packets_received = 0
        self._packets_dropped = 0
    
    @abstractmethod
    def receive_packet(self, packet: 'Packet') -> None:
        """
        对应 C++ 中的协议::receivePacket()
        接收数据包
        
        Args:
            packet: 接收的数据包
        """
        pass
    
    @abstractmethod
    def do_next_event(self) -> None:
        """
        对应 C++ 中的协议::doNextEvent()
        执行下一个事件
        """
        pass
    
    @abstractmethod
    def cumulative_ack(self) -> int:
        """
        对应 C++ 中的协议::cumulative_ack()
        获取累积确认号
        
        Returns:
            累积确认号
        """
        pass
    
    @abstractmethod
    def drops(self) -> int:
        """
        对应 C++ 中的协议::drops()
        获取丢包数量
        
        Returns:
            丢包数量
        """
        pass
    
    # 连接管理
    def connect(self, route: Route) -> None:
        """
        建立连接
        
        Args:
            route: 连接路由
        """
        self._route = route
        self._connected = True
    
    def disconnect(self) -> None:
        """断开连接"""
        self._connected = False
        self._route = None
    
    def is_connected(self) -> bool:
        """
        检查是否已连接
        
        Returns:
            如果已连接返回True，否则返回False
        """
        return self._connected
    
    # 数据发送
    def send_data(self, data: bytes, size: int = None) -> bool:
        """
        发送数据
        
        Args:
            data: 要发送的数据
            size: 数据大小，如果为None则使用data的长度
            
        Returns:
            如果成功发送返回True，否则返回False
        """
        if not self._connected:
            return False
        
        if size is None:
            size = len(data)
        
        # TODO: 实现数据发送逻辑
        self._bytes_sent += size
        self._packets_sent += 1
        
        return True
    
    def send_packet(self, packet: 'Packet') -> bool:
        """
        发送数据包
        
        Args:
            packet: 要发送的数据包
            
        Returns:
            如果成功发送返回True，否则返回False
        """
        if not self._connected:
            return False
        
        # TODO: 实现数据包发送逻辑
        self._bytes_sent += packet.size
        self._packets_sent += 1
        
        return True
    
    # 流管理
    def set_flow(self, flow: PacketFlow) -> None:
        """
        设置数据流
        
        Args:
            flow: 数据流
        """
        self._flow = flow
    
    @property
    def flow(self) -> Optional[PacketFlow]:
        """获取数据流"""
        return self._flow
    
    @property
    def flow_id(self) -> int:
        """获取流ID"""
        return self._flow.flow_id if self._flow else 0
    
    # 路由管理
    def set_route(self, route: Route) -> None:
        """
        设置路由
        
        Args:
            route: 路由路径
        """
        self._route = route
    
    @property
    def route(self) -> Optional[Route]:
        """获取路由"""
        return self._route
    
    # 统计信息
    @property
    def bytes_sent(self) -> int:
        """获取发送字节数"""
        return self._bytes_sent
    
    @property
    def bytes_received(self) -> int:
        """获取接收字节数"""
        return self._bytes_received
    
    @property
    def packets_sent(self) -> int:
        """获取发送数据包数"""
        return self._packets_sent
    
    @property
    def packets_received(self) -> int:
        """获取接收数据包数"""
        return self._packets_received
    
    @property
    def packets_dropped(self) -> int:
        """获取丢包数"""
        return self._packets_dropped
    
    def reset_stats(self) -> None:
        """重置统计信息"""
        self._bytes_sent = 0
        self._bytes_received = 0
        self._packets_sent = 0
        self._packets_received = 0
        self._packets_dropped = 0
    
    def get_stats(self) -> dict:
        """
        获取统计信息
        
        Returns:
            统计信息字典
        """
        return {
            'name': self._name,
            'connected': self._connected,
            'flow_id': self.flow_id,
            'bytes_sent': self._bytes_sent,
            'bytes_received': self._bytes_received,
            'packets_sent': self._packets_sent,
            'packets_received': self._packets_received,
            'packets_dropped': self._packets_dropped,
            'cumulative_ack': self.cumulative_ack(),
            'drops': self.drops(),
        }
    
    def __str__(self) -> str:
        """字符串表示"""
        return (f"{self.__class__.__name__}(name={self._name}, "
                f"connected={self._connected}, flow_id={self.flow_id})")
    
    def __repr__(self) -> str:
        """详细字符串表示"""
        return (f"{self.__class__.__name__}(name={self._name}, "
                f"connected={self._connected}, flow_id={self.flow_id}, "
                f"route={self._route is not None})")