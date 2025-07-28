"""
FIFOQueue - First-In-First-Out Queue Implementation

对应文件: queue.h/cpp (Queue类实现)
功能: 先进先出队列，最基本的队列类型

主要类:
- FIFOQueue: 对应C++的Queue类实现

C++对应关系:
- Queue::receivePacket() -> FIFOQueue.receive_packet()
- Queue::doNextEvent() -> FIFOQueue.do_next_event()
- Queue::beginService() -> FIFOQueue.begin_service()
- Queue::completeService() -> FIFOQueue.complete_service()
- Queue::queuesize() -> FIFOQueue.queuesize()
- Queue::maxsize() -> FIFOQueue.maxsize()
- Queue::serviceTime() -> FIFOQueue.service_time()
- Queue::num_drops() -> FIFOQueue.num_drops()
- Queue::reset_drops() -> FIFOQueue.reset_drops()

关键实现对应:
- C++的CircularBuffer<Packet*> _enqueued对应Python的collections.deque
- C++的先进先出访问模式(_enqueued.push() + _enqueued.pop())对应Python的右端添加+左端取出
- C++的_maxsize, _queuesize, _num_drops成员变量完全对应
- C++的receivePacket(), beginService(), completeService()逻辑完全对应
"""

from typing import Optional
from collections import deque
from .base_queue import BaseQueue
from ..core.logger import TrafficLogger, QueueLogger


class FIFOQueue(BaseQueue):
    """
    FIFO队列实现 - 对应 queue.h/cpp 中的Queue类
    
    严格按照C++实现的FIFO（先进先出）行为：
    - 入队：append()到队尾
    - 出队：popleft()从队头取出
    """
    
    def __init__(self, bitrate: int, maxsize: int, eventlist, 
                logger: Optional[QueueLogger] = None):
        """
        初始化队列 - 对应 C++ Queue::Queue(linkspeed_bps bitrate, mem_b maxsize, EventList& eventlist, QueueLogger* logger)
        
        Args:
            bitrate: 链路速度（bps）- 对应 C++ 的 linkspeed_bps bitrate
            maxsize: 队列容量（字节）- 对应 C++ 的 mem_b maxsize
            eventlist: 事件调度器 - 对应 C++ 的 EventList& eventlist
            logger: 队列日志记录器 - 对应 C++ 的 QueueLogger* logger
        """
        # 调用BaseQueue构造器 - 对应 C++ Queue::Queue() : BaseQueue(bitrate, eventlist, logger)
        super().__init__(bitrate, eventlist, logger)
        
        # Queue 特有成员初始化 - 对应 C++ Queue::Queue()
        self._maxsize = maxsize  # mem_b _maxsize
        self._queuesize_bytes = 0  # mem_b _queuesize = 0
        self._num_drops = 0  # int _num_drops = 0
        self._enqueued = deque()  # CircularBuffer<Packet*> _enqueued
        
        # 生成节点名称 - 对应 C++ Queue::Queue() 中的 stringstream 逻辑
        # ss << "queue(" << bitrate/1000000 << "Mb/s," << maxsize << "bytes)";
        self._nodename = f"queue({bitrate//1000000}Mb/s,{maxsize}bytes)"
    
    # 实现BaseQueue的抽象方法
    
    def queuesize(self) -> int:
        """
        获取队列字节大小 - 对应 C++ Queue::queuesize()
        
        Returns:
            队列中数据的字节数
        """
        return self._queuesize_bytes
    
    def maxsize(self) -> int:
        """
        获取队列最大字节容量 - 对应 C++ Queue::maxsize()
        
        Returns:
            队列最大容量（字节）
        """
        return self._maxsize
    
    # Queue特有的方法
    
    def num_drops(self) -> int:
        """
        获取丢包数量 - 对应 C++ 的 num_drops()
        
        Returns:
            丢包数量
        """
        return self._num_drops
    
    def reset_drops(self) -> None:
        """
        重置丢包计数 - 对应 C++ 的 reset_drops()
        """
        self._num_drops = 0
    
    def service_time(self) -> int:
        """
        获取队列服务时间 - 对应 C++ Queue::serviceTime()
        
        Returns:
            服务时间（皮秒）
        """
        return self._queuesize_bytes * self._ps_per_byte
    
    # 核心事件处理方法 - 对应 C++ Queue 类的核心功能
    
    def do_next_event(self) -> None:
        """
        对应 C++ 中的 Queue::doNextEvent()
        处理队列服务事件 - 直接调用 complete_service
        """
        self.complete_service()
    
    def receive_packet(self, packet) -> None:
        """
        接收数据包 - 对应 C++ 的 Queue::receivePacket()
        
        Args:
            packet: 要接收的数据包
        """
        # 检查容量限制 - 对应 C++ 的 if (_queuesize+pkt.size() > _maxsize)
        if self._queuesize_bytes + packet.size > self._maxsize:
            # 数据包不能放入队列，丢弃它
            if self._logger:
                # 对应 C++ 的 _logger->logQueue(*this, QueueLogger::PKT_DROP, pkt)
                self._logger.logQueue(self, QueueLogger.QueueEvent.PKT_DROP, packet)
            
            # 对应 C++ 的 pkt.flow().logTraffic(pkt, *this, TrafficLogger::PKT_DROP)
            if hasattr(packet, 'flow') and packet.flow():
                packet.flow().log_traffic(packet, self, TrafficLogger.TrafficEvent.PKT_DROP)
            
            packet.free()
            self._num_drops += 1
            return
        
        # 记录数据包到达 - 对应 C++ 的 pkt.flow().logTraffic(pkt, *this, TrafficLogger::PKT_ARRIVE)
        if hasattr(packet, 'flow') and packet.flow():
            packet.flow().log_traffic(packet, self, TrafficLogger.TrafficEvent.PKT_ARRIVE)
        
        # 入队数据包 - 对应 C++ 的入队逻辑
        queue_was_empty = len(self._enqueued) == 0
        
        # 对应 C++ 的 _enqueued.push(pkt_p); _queuesize += pkt.size();
        self._enqueued.append(packet)  # 推到队尾（右端）
        self._queuesize_bytes += packet.size
        
        # 记录入队日志 - 对应 C++ 的 _logger->logQueue(*this, QueueLogger::PKT_ENQUEUE, pkt)
        if self._logger:
            self._logger.logQueue(self, QueueLogger.QueueEvent.PKT_ENQUEUE, packet)
        
        # 如果队列之前为空，开始服务 - 对应 C++ 的服务调度
        if queue_was_empty:
            # 对应 C++ 的 assert(_enqueued.size() == 1); beginService();
            assert len(self._enqueued) == 1
            self.begin_service()
    
    def begin_service(self) -> None:
        """
        开始服务 - 对应 C++ 的 Queue::beginService()
        
        调度下一个出队事件
        """
        # 对应 C++ 的 assert(!_enqueued.empty());
        assert len(self._enqueued) > 0
        
        # 获取队头数据包（对应 C++ 的 _enqueued.back()访问最早入队的包）
        # 注意：C++的CircularBuffer.back()返回最早入队的包，对应Python的[0]
        packet = self._enqueued[0]
        
        # 计算传输时间（皮秒）- 对应 C++ 的 drainTime(_enqueued.back())
        transmission_time = self.drainTime(packet)
        
        # 调度下一个服务事件 - 对应 C++ 的 eventlist().sourceIsPendingRel(*this, drainTime(_enqueued.back()));
        self._eventlist.source_is_pending_rel(self, transmission_time)
    
    def complete_service(self) -> None:
        """
        完成服务 - 对应 C++ 的 Queue::completeService()
        
        出队数据包并发送到下一跳
        """
        # 对应 C++ 的 assert(!_enqueued.empty());
        assert len(self._enqueued) > 0
        
        # 从队头取出数据包 - 对应 C++ 的 Packet* pkt = _enqueued.pop();
        # C++的CircularBuffer.pop()从back取出（最早入队的），对应Python的popleft()
        packet = self._enqueued.popleft()  # FIFO：从左端（队头）取出
        
        # 更新队列字节大小 - 对应 C++ 的 _queuesize -= pkt->size();
        self._queuesize_bytes -= packet.size
        
        # 记录数据包出发 - 对应 C++ 的 pkt->flow().logTraffic(*pkt, *this, TrafficLogger::PKT_DEPART)
        if hasattr(packet, 'flow') and packet.flow():
            packet.flow().log_traffic(packet, self, TrafficLogger.TrafficEvent.PKT_DEPART)
        
        # 记录服务日志 - 对应 C++ 的 if (_logger) _logger->logQueue(*this, QueueLogger::PKT_SERVICE, *pkt);
        if self._logger:
            self._logger.logQueue(self, QueueLogger.QueueEvent.PKT_SERVICE, packet)
        
        # 记录数据包传输时间用于利用率统计 - 对应 C++ 的 log_packet_send(drainTime(pkt));
        transmission_time = self.drainTime(packet)
        self.log_packet_send(transmission_time)
        
        # 发送数据包到下一跳 - 对应 C++ 的 pkt->sendOn()
        packet.send_on()
        
        # 如果队列中还有数据包，调度下一个服务事件 - 对应 C++ 的服务调度逻辑
        if len(self._enqueued) > 0:
            self.begin_service()
    
    # 便利方法和属性
    
    @property
    def is_empty(self) -> bool:
        """检查队列是否为空"""
        return len(self._enqueued) == 0
    
    @property
    def packet_count(self) -> int:
        """获取队列中的数据包数量"""
        return len(self._enqueued)
    
    @property
    def transmission_delay(self) -> int:
        """获取当前数据包的传输延迟（皮秒）"""
        if self.is_empty:
            return 0
        
        packet = self.peek_packet()
        if packet is None:
            return 0
        
        return packet.size * self._ps_per_byte
    
    def peek_packet(self):
        """查看队头数据包但不移除"""
        if self.is_empty:
            return None
        return self._enqueued[0]
    
    # 向后兼容的别名方法
    
    def queuesize_bytes(self) -> int:
        """为了向后兼容保留的别名"""
        return self.queuesize()
    
    def maxsize_bytes(self) -> int:
        """为了向后兼容保留的别名"""
        return self.maxsize()
    
    @property
    def link_speed(self) -> int:
        """获取链路速度"""
        return self._bitrate
    
    def set_link_speed(self, speed: int) -> None:
        """
        设置链路速度
        
        Args:
            speed: 链路速度（bps）
        """
        self._bitrate = speed
        self._ps_per_byte = int((10**12 * 8) / speed)
    
    def __repr__(self) -> str:
        """详细字符串表示"""
        return (f"FIFOQueue(maxsize={self._maxsize}, queuesize={self._queuesize_bytes}, "
                f"packet_count={len(self._enqueued)}, link_speed={self._bitrate}, "
                f"num_drops={self._num_drops})") 