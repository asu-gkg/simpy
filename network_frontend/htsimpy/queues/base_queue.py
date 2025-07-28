"""
BaseQueue - Base Queue Implementation

对应文件: queue.h/cpp
功能: 基础队列抽象类

主要类:
- BaseQueue: 队列基类

C++对应关系:
- Queue::receivePacket() -> BaseQueue.receive_packet()
- Queue::doNextEvent() -> BaseQueue.do_next_event()
- Queue::setName() -> BaseQueue.set_name()
"""

from abc import ABC, abstractmethod
from typing import Optional, List, Any
from ..core.network import Packet, PacketSink
from ..core.eventlist import EventSource
from ..core.logger import Logged


class BaseQueue(PacketSink, EventSource, Logged):
    """
    队列基类 - 对应 queue.h/cpp 中的 Queue 类
    
    所有队列类型都应该继承此类
    """
    
    def __init__(self, eventlist, name: str, capacity: int = 1000):
        PacketSink.__init__(self, name)
        EventSource.__init__(self, eventlist, name)
        Logged.__init__(self, name)
        
        # 队列属性
        self._capacity = capacity
        self._queue: List[Packet] = []
        self._busy = False
        self._service_time = 0
        
        # 统计信息
        self._total_packets = 0
        self._dropped_packets = 0
        self._total_bytes = 0
        self._dropped_bytes = 0
    
    def receive_packet(self, packet: Packet) -> None:
        """
        对应 C++ 中的 Queue::receivePacket()
        接收数据包
        
        Args:
            packet: 接收的数据包
        """
        self._total_packets += 1
        self._total_bytes += packet.size
        
        if len(self._queue) >= self._capacity:
            # 队列满，丢包
            self._dropped_packets += 1
            self._dropped_bytes += packet.size
            packet.free()
            return
        
        # 添加到队列
        self._queue.append(packet)
        
        # 如果队列空闲，开始服务
        if not self._busy:
            self._busy = True
            self.schedule_service()
    
    @abstractmethod
    def do_next_event(self) -> None:
        """
        对应 C++ 中的 Queue::doNextEvent()
        执行下一个事件
        
        子类必须实现此方法来处理队列服务逻辑
        """
        pass
    
    def schedule_service(self) -> None:
        """
        调度队列服务
        
        计算服务时间并调度下一个服务事件
        """
        # TODO: 实现服务调度逻辑
        pass
    
    def dequeue_packet(self) -> Optional[Packet]:
        """
        从队列中取出一个数据包
        
        Returns:
            取出的数据包，如果队列为空返回None
        """
        if self._queue:
            return self._queue.pop(0)
        return None
    
    def peek_packet(self) -> Optional[Packet]:
        """
        查看队列头部的数据包但不取出
        
        Returns:
            队列头部的数据包，如果队列为空返回None
        """
        if self._queue:
            return self._queue[0]
        return None
    
    def enqueue_packet(self, packet: Packet) -> bool:
        """
        将数据包加入队列
        
        Args:
            packet: 要加入的数据包
            
        Returns:
            如果成功加入返回True，否则返回False
        """
        if len(self._queue) >= self._capacity:
            return False
        
        self._queue.append(packet)
        return True
    
    def set_capacity(self, capacity: int) -> None:
        """
        设置队列容量
        
        Args:
            capacity: 新的队列容量
        """
        self._capacity = capacity
    
    def set_service_time(self, service_time: int) -> None:
        """
        设置服务时间
        
        Args:
            service_time: 服务时间（皮秒）
        """
        self._service_time = service_time
    
    # 属性访问器
    @property
    def capacity(self) -> int:
        """获取队列容量"""
        return self._capacity
    
    @property
    def size(self) -> int:
        """获取当前队列大小"""
        return len(self._queue)
    
    @property
    def is_empty(self) -> bool:
        """检查队列是否为空"""
        return len(self._queue) == 0
    
    @property
    def is_full(self) -> bool:
        """检查队列是否已满"""
        return len(self._queue) >= self._capacity
    
    @property
    def busy(self) -> bool:
        """检查队列是否忙碌"""
        return self._busy
    
    @property
    def service_time(self) -> int:
        """获取服务时间"""
        return self._service_time
    
    # 统计信息
    @property
    def total_packets(self) -> int:
        """获取总数据包数"""
        return self._total_packets
    
    @property
    def dropped_packets(self) -> int:
        """获取丢包数"""
        return self._dropped_packets
    
    @property
    def total_bytes(self) -> int:
        """获取总字节数"""
        return self._total_bytes
    
    @property
    def dropped_bytes(self) -> int:
        """获取丢包字节数"""
        return self._dropped_bytes
    
    @property
    def drop_rate(self) -> float:
        """获取丢包率"""
        if self._total_packets == 0:
            return 0.0
        return self._dropped_packets / self._total_packets
    
    @property
    def utilization(self) -> float:
        """获取队列利用率"""
        return len(self._queue) / self._capacity
    
    def reset_stats(self) -> None:
        """重置统计信息"""
        self._total_packets = 0
        self._dropped_packets = 0
        self._total_bytes = 0
        self._dropped_bytes = 0
    
    def __str__(self) -> str:
        """字符串表示"""
        return (f"{self.__class__.__name__}(name={self._name}, "
                f"size={len(self._queue)}/{self._capacity}, "
                f"busy={self._busy})")
    
    def __repr__(self) -> str:
        """详细字符串表示"""
        return (f"{self.__class__.__name__}(name={self._name}, "
                f"capacity={self._capacity}, size={len(self._queue)}, "
                f"busy={self._busy}, service_time={self._service_time})")