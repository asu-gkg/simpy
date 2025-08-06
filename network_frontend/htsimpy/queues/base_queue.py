"""
BaseQueue - Base Queue Implementation

对应文件: queue.h/cpp (BaseQueue类)
功能: 基础队列抽象类，对应C++的BaseQueue

主要类:
- BaseQueue: 队列基类，对应C++的BaseQueue

C++对应关系:
- BaseQueue::setLogger() -> BaseQueue.set_logger()
- BaseQueue::setName() -> BaseQueue.set_name()
- BaseQueue::forceName() -> BaseQueue.force_name()
- BaseQueue::setNext() -> BaseQueue.set_next()
- BaseQueue::next() -> BaseQueue.next()
- BaseQueue::nodename() -> BaseQueue.nodename()
- BaseQueue::queuesize() -> BaseQueue.queuesize() [抽象方法]
- BaseQueue::maxsize() -> BaseQueue.maxsize() [抽象方法]
- BaseQueue::drainTime() -> BaseQueue.drain_time()
- BaseQueue::serviceCapacity() -> BaseQueue.service_capacity()
- BaseQueue::log_packet_send() -> BaseQueue.log_packet_send()
- BaseQueue::average_utilization() -> BaseQueue.average_utilization()
- BaseQueue::quantized_utilization() -> BaseQueue.quantized_utilization()
- BaseQueue::quantized_queuesize() -> BaseQueue.quantized_queuesize()
"""

from abc import ABC, abstractmethod
from typing import Optional, List
from collections import deque
from ..core.circular_buffer import CircularBuffer
from ..core.network import PacketSink, Packet
from ..core.eventlist import EventSource, EventList
from ..core.logger import Logged, QueueLogger
from ..core.drawable import Drawable
from ..core.logger.traffic import TrafficLogger
from ..core.logger.queue import QueueLogger


class BaseQueue(EventSource, PacketSink, Drawable, ABC):
    """
    队列基类 - 对应 queue.h/cpp 中的 BaseQueue 类
    
    这是一个抽象基类，提供队列的通用功能但不实现具体的队列调度策略。
    子类必须实现不同的队列调度策略。
    """
    
    # 对应 C++ BaseQueue::_update_period = timeFromUs(0.1)
    _update_period = 100_000_000  # simtime_picosec _update_period (0.1微秒)
    
    def __init__(self, bitrate: int, eventlist, logger: Optional[QueueLogger] = None):
        """
        初始化基础队列 - 对应 C++ BaseQueue::BaseQueue(linkspeed_bps bitrate, EventList &eventlist, QueueLogger* logger)
        
        Args:
            bitrate: 链路速度（bps）- 对应 C++ 的 linkspeed_bps bitrate
            eventlist: 事件调度器 - 对应 C++ 的 EventList& eventlist
            logger: 队列日志记录器 - 对应 C++ 的 QueueLogger* logger
        """
        # 对应 C++ : EventSource(eventlist, "Queue"), _logger(logger), _bitrate(bitrate), _switch(NULL)
        EventSource.__init__(self, eventlist, "Queue")
        PacketSink.__init__(self)  # C++中PacketSink没有参数
        Drawable.__init__(self)
        
        # 对应 C++ BaseQueue 成员
        self._logger = logger           # QueueLogger* _logger
        self._bitrate = bitrate         # linkspeed_bps _bitrate
        self._switch = None             # Switch* _switch = NULL
        self._next_sink = None          # PacketSink* _next_sink
        
        # 计算服务时间（皮秒/字节）- 对应 C++ 的 _ps_per_byte = (simtime_picosec)((pow(10.0, 12.0) * 8) / _bitrate);
        self._ps_per_byte = int((10**12 * 8) / bitrate)
        
        # 对应 C++ BaseQueue 统计成员初始化
        self._window = 30_000_000            # simtime_picosec _window = timeFromUs(30.0) - 30微秒
        self._busy = 0                       # simtime_picosec _busy = 0
        self._idle = 0                       # simtime_picosec _idle
        
        # 对应 C++ BaseQueue 量化状态初始化
        self._last_update_qs = 0             # simtime_picosec _last_update_qs = 0
        self._last_update_utilization = 0    # simtime_picosec _last_update_utilization = 0
        self._last_qs = 0                    # uint8_t _last_qs = 0
        self._last_utilization = 0          # uint8_t _last_utilization = 0
        
        # 利用率统计 - 对应 C++ BaseQueue 成员
        self._busystart = CircularBuffer()   # CircularBuffer<simtime_picosec> _busystart
        self._busyend = CircularBuffer()     # CircularBuffer<simtime_picosec> _busyend
        
        # 节点名称（子类设置）
        self._nodename = ""
    
    # 配置方法 - 对应 C++ BaseQueue 虚函数接口
    
    def setLogger(self, logger: Optional[QueueLogger]) -> None:
        """设置队列日志记录器 - 对应 C++ BaseQueue::setLogger()"""
        self._logger = logger
    
    def setName(self, name: str) -> None:
        """设置队列名称 - 对应 C++ BaseQueue::setName()"""
        Logged.setName(self, name)
        self._nodename += name
    
    def forceName(self, name: str) -> None:
        """强制设置队列名称 - 对应 C++ BaseQueue::forceName()"""
        Logged.setName(self, name)
        self._nodename = name
    
    def setSwitch(self, switch) -> None:
        """设置关联的交换机 - 对应 C++ BaseQueue::setSwitch()"""
        assert self._switch is None
        self._switch = switch
    
    def getSwitch(self):
        """获取关联的交换机 - 对应 C++ BaseQueue::getSwitch()"""
        return self._switch
    
    def setNext(self, next_sink) -> None:
        """设置下一跳 - 对应 C++ BaseQueue::setNext()"""
        self._next_sink = next_sink
    
    def next(self):
        """获取下一跳 - 对应 C++ BaseQueue::next()"""
        return self._next_sink
    
    def nodename(self) -> str:
        """获取节点名称 - 对应 C++ BaseQueue::nodename()"""
        return self._nodename
    
    # 抽象方法 - 子类必须实现
    
    @abstractmethod
    def queuesize(self) -> int:
        """获取队列字节大小 - 对应 C++ BaseQueue::queuesize() const = 0"""
        pass
    
    @abstractmethod
    def maxsize(self) -> int:
        """获取队列最大字节容量 - 对应 C++ BaseQueue::maxsize() const = 0"""
        pass
    
    # 通用工具方法 - 对应 C++ BaseQueue 内联函数
    
    def drain_time(self, packet) -> int:
        """
        计算数据包传输时间 - 对应 C++ BaseQueue::drainTime()
        
        Args:
            packet: 数据包
            
        Returns:
            传输时间（皮秒）
        """
        return packet.size() * self._ps_per_byte
    
    def service_capacity(self, t: int) -> int:
        """
        计算在给定时间内能处理的字节数 - 对应 C++ BaseQueue::serviceCapacity()
        
        Args:
            t: 时间（皮秒）
            
        Returns:
            能处理的字节数
        """
        # 对应 C++: return (mem_b)(timeAsSec(t) * (double)_bitrate);
        time_in_seconds = t / 10**12
        return int(time_in_seconds * self._bitrate / 8)
    
    # 利用率统计方法 - 对应 C++ BaseQueue 虚函数
    
    def log_packet_send(self, duration: int) -> None:
        """
        记录数据包发送 - 对应 C++ BaseQueue::log_packet_send()
        
        Args:
            duration: 传输持续时间（皮秒）
        """
        # 对应 C++ 的实现：
        # simtime_picosec b = eventlist().now();
        # simtime_picosec a = b - duration;
        # _busystart.push(a);
        # _busyend.push(b);
        # _busy += duration;
        
        current_time = self._eventlist.now()
        start_time = current_time - duration
        
        self._busystart.push(start_time)
        self._busyend.push(current_time)
        self._busy += duration
        
        # 对应 C++ 的清理逻辑
        self._cleanup_old_busy_records(current_time)
    
    def _cleanup_old_busy_records(self, current_time: int) -> None:
        """清理超出测量窗口的忙碌记录"""
        if self._busyend.empty():
            return
            
        window_start = current_time - self._window
        y = self._busyend.back()
        
        while y < window_start:
            x = self._busystart.pop()
            self._busyend.pop()
            self._busy -= (y - x)
            
            if not self._busyend.empty():
                y = self._busyend.back()
            else:
                break
    
    def average_utilization(self) -> int:
        """
        计算平均利用率 - 对应 C++ BaseQueue::average_utilization()
        
        Returns:
            利用率百分比 (0-100)
        """
        if self._busystart.empty():
            return 0
        
        y = self._busyend.back()
        b = self._eventlist.now()
        
        while y < b - self._window:
            x = self._busystart.pop()
            self._busyend.pop()
            
            self._busy -= (y - x)
            assert self._busy >= 0
            
            if not self._busyend.empty():
                y = self._busyend.back()
            else:
                break
        
        # 对应 C++ 的 return (_busy*100/_window);
        return (self._busy * 100) // self._window
    
    def quantized_utilization(self) -> int:
        """
        量化利用率 - 对应 C++ BaseQueue::quantized_utilization()
        
        Returns:
            量化的利用率等级 (0-3)
        """
        current_time = self._eventlist.now()
        
        if current_time - self._last_update_utilization > BaseQueue._update_period:
            self._last_update_utilization = current_time
            
            avg = self.average_utilization()
            
            # 对应 C++ 的量化逻辑
            if avg == 0:
                self._last_utilization = 0
            elif avg < 15:
                self._last_utilization = 1
            elif avg < 50:
                self._last_utilization = 2
            else:
                self._last_utilization = 3
        
        return self._last_utilization
    
    def quantized_queuesize(self) -> int:
        """
        量化队列大小 - 对应 C++ BaseQueue::quantized_queuesize()
        
        Returns:
            量化的队列大小等级 (0-3)
        """
        current_time = self._eventlist.now()
        
        if current_time - self._last_update_qs > BaseQueue._update_period:
            self._last_update_qs = current_time
            
            qs = self.queuesize()
            max_size = self.maxsize()
            
            # 对应 C++ 的量化逻辑
            if qs < max_size * 0.05:
                self._last_qs = 0
            elif qs < max_size * 0.1:
                self._last_qs = 1
            elif qs < max_size * 0.2:
                self._last_qs = 2
            else:
                self._last_qs = 3
        
        return self._last_qs
    
    @property
    def bitrate(self) -> int:
        """获取链路速度"""
        return self._bitrate
    
    def __str__(self) -> str:
        """字符串表示"""
        return self._nodename
    
    def __repr__(self) -> str:
        """详细字符串表示"""
        return f"BaseQueue(nodename={self._nodename}, bitrate={self._bitrate})"


class Queue(BaseQueue):
    """
    标准FIFO队列 - 对应 queue.h/cpp 中的 Queue 类
    
    C++定义:
    class Queue : public BaseQueue {
    public:
        Queue(linkspeed_bps bitrate, mem_b maxsize, EventList &eventlist, 
              QueueLogger* logger);
        virtual void receivePacket(Packet& pkt);
        void do_next_event();
        mem_b _maxsize; 
        virtual mem_b queuesize() const;
        virtual mem_b maxsize() const {return _maxsize;}
    };
    """
    
    def __init__(self, bitrate: int, maxsize: int, eventlist: EventList, logger: Optional['QueueLogger'] = None):
        """
        对应 C++ 构造函数:
        Queue::Queue(linkspeed_bps bitrate, mem_b maxsize, EventList& eventlist, 
                     QueueLogger* logger)
            : BaseQueue(bitrate, eventlist, logger), 
              _maxsize(maxsize), _num_drops(0)
        {
            _queuesize = 0;
            stringstream ss;
            ss << "queue(" << bitrate/1000000 << "Mb/s," << maxsize << "bytes)";
            _nodename = ss.str();
        }
        """
        super().__init__(bitrate, eventlist, logger)
        
        # 对应 C++ 成员变量
        self._maxsize = maxsize     # mem_b _maxsize
        self._num_drops = 0         # int _num_drops  
        self._queuesize = 0         # mem_b _queuesize
        
        # 队列存储 - 对应 C++ CircularBuffer<Packet*> _enqueued
        self._enqueued = CircularBuffer()  # CircularBuffer<Packet*> _enqueued
        
        # 设置节点名称
        self._nodename = f"queue({bitrate//1000000}Mb/s,{maxsize}bytes)"
    
    def receivePacket(self, pkt: Packet) -> None:
        """
        对应 C++ Queue::receivePacket()
        接收数据包
        """
        # 如果当前队列大小 + 数据包大小 > 最大容量，丢弃数据包
        if self._queuesize + pkt.size() > self._maxsize:
            # 对应 C++ if (_logger) _logger->logQueue(*this, QueueLogger::PKT_DROP, pkt);
            if self._logger:
                self._logger.logQueue(self, QueueLogger.QueueEvent.PKT_DROP, pkt)
            
            # 对应 C++ pkt.flow().logTraffic(pkt,*this,TrafficLogger::PKT_DROP);
            if pkt.flow() and pkt.flow().log_me():
                pkt.flow().logTraffic(pkt, self, TrafficLogger.TrafficEvent.PKT_DROP)
            
            pkt.free()
            self._num_drops += 1
            return
        
        # 对应 C++ pkt.flow().logTraffic(pkt,*this,TrafficLogger::PKT_ARRIVE);
        # 只有在数据包不会被丢弃时才记录PKT_ARRIVE
        if pkt.flow() and pkt.flow().log_me():
            pkt.flow().logTraffic(pkt, self, TrafficLogger.TrafficEvent.PKT_ARRIVE)
        
        # 将数据包加入队列
        # 对应 C++ _enqueued.push(pkt_p);
        self._enqueued.push(pkt)
        self._queuesize += pkt.size()
        
        # 对应 C++ if (_logger) _logger->logQueue(*this, QueueLogger::PKT_ENQUEUE, pkt);
        if self._logger:
            self._logger.logQueue(self, QueueLogger.QueueEvent.PKT_ENQUEUE, pkt)
        
        # 如果队列之前是空的，开始服务
        if self._enqueued.size() == 1:
            # 对应 C++ beginService();
            self.beginService()
    
    def beginService(self) -> None:
        """
        对应 C++ Queue::beginService()
        开始服务下一个数据包
        """
        # 对应 C++ assert(!_enqueued.empty());
        assert not self._enqueued.empty()
        
        # 对应 C++ eventlist().sourceIsPendingRel(*this, drainTime(_enqueued.back()));
        # 注意：CircularBuffer的back()返回下一个要pop的元素（最老的）
        pkt = self._enqueued.back()
        self.eventlist().source_is_pending_rel(self, self.drain_time(pkt))
    
    def do_next_event(self) -> None:
        """
        对应 C++ Queue::doNextEvent()
        处理下一个事件（发送数据包）
        """
        self.completeService()
    
    def completeService(self) -> None:
        """
        对应 C++ Queue::completeService()
        完成服务
        """
        # 对应 C++ assert(!_enqueued.empty());
        assert not self._enqueued.empty()
        
        # 取出队首数据包
        # 对应 C++ Packet* pkt = _enqueued.pop();
        pkt = self._enqueued.pop()
        self._queuesize -= pkt.size()
        
        # 对应 C++ pkt->flow().logTraffic(*pkt, *this, TrafficLogger::PKT_DEPART);
        if pkt.flow() and pkt.flow().log_me():
            pkt.flow().logTraffic(pkt, self, TrafficLogger.TrafficEvent.PKT_DEPART)
        
        # 对应 C++ if (_logger) _logger->logQueue(*this, QueueLogger::PKT_SERVICE, *pkt);
        if self._logger:
            self._logger.logQueue(self, QueueLogger.QueueEvent.PKT_SERVICE, pkt)
        
        # 对应 C++ log_packet_send(drainTime(pkt));
        self.log_packet_send(self.drain_time(pkt))
        
        # 发送数据包
        # 对应 C++ pkt->sendOn();
        pkt.sendOn()
        
        # 如果队列还有数据包，继续服务
        if not self._enqueued.empty():
            self.beginService()
    
    def queuesize(self) -> int:
        """
        对应 C++ virtual mem_b queuesize() const
        返回当前队列大小
        """
        return self._queuesize
    
    def maxsize(self) -> int:
        """
        对应 C++ virtual mem_b maxsize() const {return _maxsize;}
        返回队列最大容量
        """
        return self._maxsize
    
    def serviceTime(self) -> int:
        """
        对应 C++ simtime_picosec Queue::serviceTime() {
            return _queuesize * _ps_per_byte;
        }
        """
        return self._queuesize * self._ps_per_byte
    
    def num_drops(self) -> int:
        """对应 C++ int num_drops() const {return _num_drops;}"""
        return self._num_drops
    
    def reset_drops(self) -> None:
        """对应 C++ void reset_drops() {_num_drops = 0;}"""
        self._num_drops = 0