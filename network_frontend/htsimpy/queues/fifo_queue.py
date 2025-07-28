"""
FIFOQueue - First-In-First-Out Queue Implementation

对应文件: queue.h/cpp (基础FIFO实现)
功能: 先进先出队列，最基本的队列类型

主要类:
- FIFOQueue: FIFO队列实现

C++对应关系:
- Queue::receivePacket() -> FIFOQueue.receive_packet()
- Queue::doNextEvent() -> FIFOQueue.do_next_event()
"""

from typing import Optional, List, Any
from .base_queue import BaseQueue


class FIFOQueue(BaseQueue):
    """
    FIFO队列实现 - 对应 queue.h/cpp 中的基础Queue类
    
    实现先进先出的队列调度策略
    """
    
    def __init__(self, eventlist, name: str, capacity: int = 1000, 
                link_speed: int = 100_000_000_000):  # 默认100Gbps
        """
        初始化FIFO队列
        
        Args:
            eventlist: 事件调度器
            name: 队列名称
            capacity: 队列容量（包数）
            link_speed: 链路速度（bps）
        """
        super().__init__(eventlist, name, capacity)
        self._link_speed = link_speed  # bits per second
        
        # 计算服务时间（皮秒/bit）
        # 1秒 = 10^12皮秒
        self._ps_per_bit = 1_000_000_000_000 // link_speed
    
    def do_next_event(self) -> None:
        """
        对应 C++ 中的 Queue::doNextEvent()
        处理队列服务事件
        """
        if self.is_empty:
            self._busy = False
            return
        
        # 取出队列头部数据包
        packet = self.dequeue_packet()
        if packet is None:
            self._busy = False
            return
        
        # 发送数据包到下一跳
        next_hop = packet.send_on()
        if next_hop:
            next_hop.receive_packet(packet)
        else:
            # 没有下一跳，丢弃数据包
            packet.free()
        
        # 如果队列中还有数据包，调度下一个服务事件
        if not self.is_empty:
            self.schedule_service()
        else:
            self._busy = False
    
    def schedule_service(self) -> None:
        """
        调度队列服务
        
        计算当前数据包的传输时间并调度下一个服务事件
        """
        if self.is_empty:
            return
        
        # 获取队列头部数据包
        packet = self.peek_packet()
        if packet is None:
            return
        
        # 计算传输时间（皮秒）
        # 传输时间 = 数据包大小(bits) * 每bit传输时间(ps/bit)
        packet_size_bits = packet.size * 8  # 字节转位
        transmission_time = packet_size_bits * self._ps_per_bit
        
        # 调度下一个服务事件
        self._eventlist.source_is_pending(
            self, 
            self._eventlist.now() + transmission_time
        )
    
    def set_link_speed(self, speed: int) -> None:
        """
        设置链路速度
        
        Args:
            speed: 链路速度（bps）
        """
        self._link_speed = speed
        self._ps_per_bit = 1_000_000_000_000 // speed
    
    @property
    def link_speed(self) -> int:
        """获取链路速度"""
        return self._link_speed
    
    @property
    def transmission_delay(self) -> int:
        """获取当前数据包的传输延迟（皮秒）"""
        if self.is_empty:
            return 0
        
        packet = self.peek_packet()
        if packet is None:
            return 0
        
        packet_size_bits = packet.size * 8
        return packet_size_bits * self._ps_per_bit
    
    def __str__(self) -> str:
        """字符串表示"""
        return (f"FIFOQueue(name={self._name}, "
                f"size={len(self._queue)}/{self._capacity}, "
                f"speed={self._link_speed/1e9:.1f}Gbps, "
                f"busy={self._busy})")
    
    def __repr__(self) -> str:
        """详细字符串表示"""
        return (f"FIFOQueue(name={self._name}, "
                f"capacity={self._capacity}, size={len(self._queue)}, "
                f"link_speed={self._link_speed}, busy={self._busy}, "
                f"total_packets={self._total_packets}, "
                f"dropped_packets={self._dropped_packets})") 