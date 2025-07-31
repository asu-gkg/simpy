"""
RandomQueue - Random Drop Queue Implementation

对应文件: randomqueue.h/cpp  
功能: 简单的FIFO队列，在快满时随机丢包

主要类:
- RandomQueue: 随机丢包队列类，继承Queue

C++对应关系:
- RandomQueue::RandomQueue() -> RandomQueue.__init__()
- RandomQueue::receivePacket() -> RandomQueue.receivePacket()
- RandomQueue::set_packet_loss_rate() -> RandomQueue.set_packet_loss_rate()
"""

import random
from typing import Optional
from collections import deque
from .base_queue import Queue
from ..core.network import Packet
from ..core.logger import QueueLogger
from ..core.logger.traffic import TrafficLogger


class RandomQueue(Queue):
    """
    随机丢包队列实现 - 对应 randomqueue.h/cpp 中的 RandomQueue 类
    
    简单的FIFO队列，在快满时随机丢包
    对应 C++ class RandomQueue : public Queue
    """
    
    def __init__(self, bitrate: int, maxsize: int, eventlist, 
                 logger: Optional[QueueLogger] = None, 
                 drop: int = 0):
        """
        初始化随机队列 - 对应 C++ RandomQueue::RandomQueue(linkspeed_bps bitrate, mem_b maxsize, 
                                                            EventList& eventlist, QueueLogger* logger, mem_b drop)
        
        Args:
            bitrate: 链路速度（bps）- 对应 C++ 的 linkspeed_bps bitrate
            maxsize: 队列容量（字节）- 对应 C++ 的 mem_b maxsize  
            eventlist: 事件调度器 - 对应 C++ 的 EventList& eventlist
            logger: 队列日志记录器 - 对应 C++ 的 QueueLogger* logger
            drop: 随机丢包缓冲区大小 - 对应 C++ 的 mem_b drop
        """
        # 调用Queue构造器 - 对应 C++ : Queue(bitrate,maxsize,eventlist,logger)
        super().__init__(bitrate, maxsize, eventlist, logger)
        
        # RandomQueue 特有成员初始化 - 对应 C++ RandomQueue 成员
        self._drop = drop                    # mem_b _drop
        self._buffer_drops = 0               # int _buffer_drops
        self._drop_th = maxsize - drop       # mem_b _drop_th = _maxsize - _drop
        self._plr = 0.0                      # double _plr = 0.0
    
    def set_packet_loss_rate(self, l: float) -> None:
        """
        设置丢包率 - 对应 C++ void RandomQueue::set_packet_loss_rate(double l)
        
        Args:
            l: 丢包率
        """
        self._plr = l
    
    def receivePacket(self, pkt: Packet) -> None:
        """
        接收数据包 - 对应 C++ void RandomQueue::receivePacket(Packet& pkt)
        
        Args:
            pkt: 要接收的数据包
        """
        # 对应 C++ RandomQueue::receivePacket() 逻辑
        drop_prob = 0.0
        crt = self._queuesize + pkt.size()
        
        # 对应 C++ if (_plr > 0.0 && drand() < _plr)
        if self._plr > 0.0 and random.random() < self._plr:
            print("Random Drop")
            pkt.free()
            return
        
        # 对应 C++ if (crt > _drop_th) drop_prob = 0.1;
        if crt > self._drop_th:
            drop_prob = 0.1
        
        # 对应 C++ if (crt > _maxsize || drand() < drop_prob)
        if crt > self._maxsize or random.random() < drop_prob:
            # 丢包
            if self._logger:
                self._logger.logQueue(self, QueueLogger.QueueEvent.PKT_DROP, pkt)
            if pkt.flow() and pkt.flow().log_me():
                pkt.flow().logTraffic(pkt, self, TrafficLogger.TrafficEvent.PKT_DROP)
            
            if crt > self._maxsize:
                self._buffer_drops += 1
            
            pkt.free()
            return
        
        # 入队 - 对应 C++ 入队逻辑
        if pkt.flow() and pkt.flow().log_me():
            pkt.flow().logTraffic(pkt, self, TrafficLogger.TrafficEvent.PKT_ARRIVE)
        
        queueWasEmpty = self._enqueued.empty()
        self._enqueued.push(pkt)
        self._queuesize += pkt.size()
        
        if self._logger:
            self._logger.logQueue(self, QueueLogger.QueueEvent.PKT_ENQUEUE, pkt)
        
        if queueWasEmpty:
            # 调度出队事件
            assert self._enqueued.size() == 1
            self.beginService()
    
 