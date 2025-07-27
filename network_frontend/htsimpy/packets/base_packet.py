"""
BasePacket - Base Packet Class

对应文件: 各种 *packet.h 文件的基类
功能: 定义所有数据包类型的基类

主要类:
- BasePacket: 数据包基类

C++对应关系:
- 各种Packet类的基类 -> BasePacket
- Packet::set() -> BasePacket.set()
- Packet::free() -> BasePacket.free()
"""

from abc import ABC, abstractmethod
from typing import Optional, Any
from ..core.network import Packet, PacketSink
from ..core.packet import PacketType, PacketDirection, PacketPriority
from ..core.route import Route


class BasePacket(Packet):
    """
    数据包基类 - 对应各种 *packet.h 文件中Packet类的基类
    
    所有具体的数据包类型都应该继承此类
    """
    
    def __init__(self):
        super().__init__()
        # 数据包特定属性
        self._payload = None
        self._header_size = 0
        self._payload_size = 0
    
    def set(self, flow: 'PacketFlow', pkt_size: int, pkt_id: int) -> None:
        """
        对应 C++ 中的 Packet::set()
        设置数据包的基本属性
        
        Args:
            flow: 数据包流
            pkt_size: 数据包大小
            pkt_id: 数据包ID
        """
        # TODO: 实现数据包设置逻辑
        pass
    
    def set_payload(self, payload: Any) -> None:
        """
        设置数据包负载
        
        Args:
            payload: 负载数据
        """
        self._payload = payload
        if payload:
            self._payload_size = len(payload)
        else:
            self._payload_size = 0
    
    def get_payload(self) -> Any:
        """
        获取数据包负载
        
        Returns:
            负载数据
        """
        return self._payload
    
    def set_header_size(self, header_size: int) -> None:
        """
        设置头部大小
        
        Args:
            header_size: 头部大小
        """
        self._header_size = header_size
    
    @property
    def header_size(self) -> int:
        """获取头部大小"""
        return self._header_size
    
    @property
    def payload_size(self) -> int:
        """获取负载大小"""
        return self._payload_size
    
    def total_size(self) -> int:
        """
        获取数据包总大小
        
        Returns:
            头部大小 + 负载大小
        """
        return self._header_size + self._payload_size
    
    def is_data_packet(self) -> bool:
        """
        判断是否为数据包（非控制包）
        
        Returns:
            如果是数据包返回True，否则返回False
        """
        # TODO: 实现数据包类型判断
        return True
    
    def is_control_packet(self) -> bool:
        """
        判断是否为控制包
        
        Returns:
            如果是控制包返回True，否则返回False
        """
        return not self.is_data_packet()
    
    def clone(self) -> 'BasePacket':
        """
        克隆数据包
        
        Returns:
            克隆的数据包副本
        """
        # TODO: 实现数据包克隆逻辑
        pass
    
    def __str__(self) -> str:
        """字符串表示"""
        return f"{self.__class__.__name__}(id={self.id}, size={self.size}, type={self.type.name})"
    
    def __repr__(self) -> str:
        """详细字符串表示"""
        return (f"{self.__class__.__name__}(id={self.id}, size={self.size}, "
                f"type={self.type.name}, dst={self.dst}, flow_id={self.flow_id})")