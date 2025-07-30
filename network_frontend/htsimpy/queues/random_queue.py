"""
RandomQueue - Random Drop Queue Implementation

对应文件: randomqueue.h/cpp  
功能: 随机丢包队列实现，对应C++的RandomQueue

主要类:
- RandomQueue: 随机丢包队列类，继承BaseQueue

C++对应关系:
- RandomQueue::RandomQueue() -> RandomQueue.__init__()
- RandomQueue::receivePacket() -> RandomQueue.receive_packet()
- RandomQueue::completeService() -> RandomQueue.complete_service()
- RandomQueue::setRandomDrop() -> RandomQueue.set_random_drop()
"""

import random
from typing import Optional
from collections import deque
from .base_queue import BaseQueue
from ..core.network import Packet
from ..core.logger import QueueLogger


class RandomQueue(BaseQueue):
    """
    随机丢包队列实现 - 对应 randomqueue.h/cpp 中的 RandomQueue 类
    
    在队列满时随机丢弃数据包，模拟网络拥塞情况
    """
    
    def __init__(self, bitrate: int, maxsize: int, eventlist, 
                 logger: Optional[QueueLogger] = None, 
                 random_drop_size: int = 0):
        """
        初始化随机队列 - 对应 C++ RandomQueue::RandomQueue()
        
        Args:
            bitrate: 链路速度（bps）- 对应 C++ 的 linkspeed_bps bitrate
            maxsize: 队列容量（字节）- 对应 C++ 的 mem_b maxsize  
            eventlist: 事件调度器 - 对应 C++ 的 EventList& eventlist
            logger: 队列日志记录器 - 对应 C++ 的 QueueLogger* logger
            random_drop_size: 随机丢包缓冲区大小 - 对应 C++ 的 mem_b random_drop_size
        """
        # 调用BaseQueue构造器 - 对应 C++ RandomQueue::RandomQueue() : BaseQueue()
        super().__init__(bitrate, eventlist, logger)
        
        # RandomQueue 特有成员初始化 - 对应 C++ RandomQueue 成员
        self._maxsize = maxsize  # mem_b _maxsize
        self._queuesize_bytes = 0  # mem_b _queuesize = 0
        self._num_drops = 0  # int _num_drops = 0
        self._random_drop_size = random_drop_size  # mem_b _random_drop_size
        self._enqueued = deque()  # CircularBuffer<Packet*> _enqueued
        
        # 生成节点名称 - 对应 C++ RandomQueue 构造器中的 stringstream 逻辑
        # ss << "randomqueue(" << bitrate/1000000 << "Mb/s," << maxsize << "bytes)";
        self._nodename = f"randomqueue({bitrate//1000000}Mb/s,{maxsize}bytes)"
    
    # 实现BaseQueue的抽象方法
    
    def queuesize(self) -> int:
        """
        获取队列字节大小 - 对应 C++ RandomQueue::queuesize()
        
        Returns:
            队列中数据的字节数
        """
        return self._queuesize_bytes
    
    def maxsize(self) -> int:
        """
        获取队列最大容量 - 对应 C++ RandomQueue::maxsize()
        
        Returns:
            队列最大容量（字节）
        """
        return self._maxsize
    
    def set_random_drop(self, random_drop_size: int) -> None:
        """
        设置随机丢包大小 - 对应 C++ RandomQueue::setRandomDrop()
        
        Args:
            random_drop_size: 随机丢包缓冲区大小
        """
        self._random_drop_size = random_drop_size
    
    def receive_packet(self, packet: Packet) -> None:
        """
        接收数据包 - 对应 C++ RandomQueue::receivePacket()
        
        Args:
            packet: 要接收的数据包
        """
        # 对应 C++ RandomQueue::receivePacket() 逻辑
        
        # 检查是否在随机丢包区域内 - 对应 C++ 随机丢包逻辑
        if (self._random_drop_size > 0 and 
            self._queuesize_bytes >= (self._maxsize - self._random_drop_size)):
            # 在随机丢包区域，随机决定是否丢包
            # 对应 C++ 中的随机丢包概率计算
            drop_probability = (self._queuesize_bytes - (self._maxsize - self._random_drop_size)) / self._random_drop_size
            if random.random() < drop_probability:
                # 丢包 - 对应 C++ 中的包丢弃
                self._num_drops += 1
                packet.free()  # 释放数据包
                if self._logger:
                    self._logger.logQueue(self, QueueLogger.QueueEvent.PKT_DROP, packet)
                return
        
        # 检查队列是否已满 - 对应 C++ 中的队列满检查
        if self._queuesize_bytes + packet.size() > self._maxsize:
            # 队列满，丢包 - 对应 C++ 中的队列满丢包
            self._num_drops += 1
            packet.free()  # 释放数据包
            if self._logger:
                self._logger.logQueue(self, QueueLogger.QueueEvent.PKT_DROP, packet)
            return
        
        # 入队 - 对应 C++ RandomQueue::receivePacket() 中的入队逻辑
        self._enqueued.append(packet)
        self._queuesize_bytes += packet.size()
        
        # 记录入队事件
        if self._logger:
            self._logger.logQueue(self, QueueLogger.QueueEvent.PKT_ENQUEUE, packet)
        
        # 如果队列之前为空，开始服务 - 对应 C++ 逻辑
        if len(self._enqueued) == 1:
            self._start_service()
    
    def _start_service(self) -> None:
        """
        开始服务队列中的数据包 - 对应 C++ RandomQueue 的服务逻辑
        """
        if not self._enqueued:
            return
            
        # 计算服务时间 - 对应 C++ 中的服务时间计算
        packet = self._enqueued[0]
        service_time = packet.size() * self._ps_per_byte
        
        # 调度完成服务事件 - 使用相对时间调度
        self._eventlist.source_is_pending_rel(self, service_time)
    
    def do_next_event(self) -> None:
        """
        处理下一个事件（完成服务）- 对应 C++ RandomQueue::doNextEvent()
        """
        self.complete_service()
    
    def complete_service(self) -> None:
        """
        完成服务 - 对应 C++ RandomQueue::completeService()
        """
        if not self._enqueued:
            return
        
        # 出队 - 对应 C++ RandomQueue::completeService() 中的出队逻辑
        packet = self._enqueued.popleft()
        self._queuesize_bytes -= packet.size()
        
        # 记录出队事件
        if self._logger:
            self._logger.logQueue(self, QueueLogger.QueueEvent.PKT_UNQUEUE, packet)
        
        # 发送到下一跳 - 对应 C++ 中的数据包转发
        if self._next_sink:
            self._next_sink.receive_packet(packet)
        else:
            # 使用路由系统传递包
            print(f"📦 Queue {self.nodename()} forwarding packet via routing")
            packet.send_on()
        
        # 如果队列还有数据包，继续服务 - 对应 C++ 逻辑
        if self._enqueued:
            self._start_service()
    
    def num_drops(self) -> int:
        """
        获取丢包数量 - 对应 C++ RandomQueue::numDrops()
        
        Returns:
            总丢包数量
        """
        return self._num_drops
    
    def is_empty(self) -> bool:
        """
        检查队列是否为空 - 对应 C++ RandomQueue::empty()
        
        Returns:
            队列是否为空
        """
        return len(self._enqueued) == 0
    
    def nodename(self) -> str:
        """
        获取节点名称 - 对应 C++ RandomQueue::nodename()
        
        Returns:
            节点名称字符串
        """
        return self._nodename 