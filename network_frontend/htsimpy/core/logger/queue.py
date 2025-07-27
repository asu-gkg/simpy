"""
Queue Logger Classes - 队列日志类

对应文件: loggertypes.h (QueueLogger) 和 loggers.h (实现类)
功能: 专门用于记录队列相关的事件和统计信息

主要类:
- QueueLogger: 队列日志记录器基类
- QueueLoggerSimple: 简单队列日志记录器
- QueueLoggerEmpty: 空队列日志记录器（跟踪繁忙时间）
- QueueLoggerSampling: 采样队列日志记录器
- MultiQueueLoggerSampling: 多队列采样日志记录器
"""

from abc import ABC, abstractmethod
from enum import IntEnum
from typing import TYPE_CHECKING

from .base import Logger
from .core import Logged

# 避免循环引用，使用TYPE_CHECKING
if TYPE_CHECKING:
    from ..eventlist import EventSource


class QueueLogger(Logger, ABC):
    """队列日志记录器 - 对应 loggertypes.h 中的 QueueLogger"""
    
    class QueueEvent(IntEnum):
        """对应 QueueLogger::QueueEvent 枚举"""
        PKT_ENQUEUE = 0
        PKT_DROP = 1
        PKT_SERVICE = 2
        PKT_TRIM = 3
        PKT_BOUNCE = 4
        PKT_UNQUEUE = 5
        PKT_ARRIVE = 6
    
    class QueueRecord(IntEnum):
        """对应 QueueLogger::QueueRecord 枚举"""
        CUM_TRAFFIC = 0
    
    class QueueApprox(IntEnum):
        """对应 QueueLogger::QueueApprox 枚举"""
        QUEUE_RANGE = 0
        QUEUE_OVERFLOW = 1
    
    @abstractmethod
    def logQueue(self, queue, ev: 'QueueEvent', pkt) -> None:
        """对应 C++ 虚函数 logQueue()"""
        pass


# ========================= Implementations from loggers.h =========================

class QueueLoggerSimple(QueueLogger):
    """简单队列日志记录器 - 对应 loggers.h 中的 QueueLoggerSimple"""
    
    def logQueue(self, queue, ev: QueueLogger.QueueEvent, pkt) -> None:
        """对应 C++ 中的 QueueLoggerSimple::logQueue()"""
        if self._logfile:
            queue_size = queue.queuesize() if hasattr(queue, 'queuesize') else 0
            flow_id = pkt.flow().get_id() if hasattr(pkt, 'flow') and hasattr(pkt.flow(), 'get_id') else 0
            pkt_id = pkt.id() if hasattr(pkt, 'id') else 0
            self._logfile.writeRecord(Logger.EventType.QUEUE_EVENT,
                                    queue.get_id() if hasattr(queue, 'get_id') else 0,
                                    ev,
                                    float(queue_size),
                                    flow_id,
                                    pkt_id)
    
    @staticmethod
    def event_to_str(event) -> str:
        """对应 C++ 中的 static string event_to_str(RawLogEvent& event)"""
        return f"QueueEvent: {event}"


class QueueLoggerEmpty(QueueLogger):
    """
    空队列日志记录器 - 对应 loggers.h 中的 QueueLoggerEmpty
    
    仅跟踪队列忙碌时间的分数
    正确实现多重继承: QueueLogger + EventSource (与C++版本一致)
    """
    
    def __init__(self, period: int, eventlist):
        """对应 C++ 构造函数 QueueLoggerEmpty(simtime_picosec period, EventList& eventlist)"""
        # 延迟导入避免循环引用
        from ..eventlist import EventSource
        
        # 运行时动态继承EventSource
        if not hasattr(self.__class__, '_eventsource_added'):
            self.__class__.__bases__ = self.__class__.__bases__ + (EventSource,)
            self.__class__._eventsource_added = True
        
        # 多重继承初始化 - 先初始化EventSource（因为它也调用了Logged.__init__）
        EventSource.__init__(self, eventlist, "QueuelogEmpty")
        QueueLogger.__init__(self)  # QueueLogger继承自Logger
        
        self._period = period
        self._last_transition = 0
        self._total_busy = 0
        self._last_dump = 0
        self._busy = False
        self._queue = None
        self._pkt_arrivals = 0
        self._pkt_trims = 0
        
        # 设置定期事件 - 对应 C++ 中的 eventlist.sourceIsPending(*this,period)
        if hasattr(eventlist, 'source_is_pending'):
            eventlist.source_is_pending(self, period)
    
    def eventlist(self):
        """提供EventSource接口的eventlist()方法"""
        return self._eventlist
    
    def logQueue(self, queue, ev: QueueLogger.QueueEvent, pkt) -> None:
        """对应 C++ 中的 QueueLoggerEmpty::logQueue()"""
        if not self._queue:
            self._queue = queue
        
        current_time = self.eventlist().now() if hasattr(self.eventlist(), 'now') else 0
        
        if ev == QueueLogger.QueueEvent.PKT_ARRIVE:
            self._pkt_arrivals += 1
        elif ev == QueueLogger.QueueEvent.PKT_ENQUEUE:
            if not self._busy:
                self._last_transition = current_time
                self._busy = True
        elif ev == QueueLogger.QueueEvent.PKT_DROP:
            pass
        elif ev == QueueLogger.QueueEvent.PKT_TRIM:
            self._pkt_trims += 1
        elif ev == QueueLogger.QueueEvent.PKT_BOUNCE:
            pass
        elif ev in (QueueLogger.QueueEvent.PKT_UNQUEUE, QueueLogger.QueueEvent.PKT_SERVICE):
            if hasattr(self._queue, 'queuesize') and self._queue.queuesize() == 0:
                assert self._busy
                self._total_busy += current_time - self._last_transition
                self._busy = False
                self._last_transition = current_time
    
    def do_next_event(self) -> None:
        """对应 C++ 中的 QueueLoggerEmpty::doNextEvent()"""
        # 安排下一个事件 - 对应 C++ 中的 eventlist().sourceIsPending()
        if hasattr(self.eventlist(), 'source_is_pending'):
            current_time = self.eventlist().now() if hasattr(self.eventlist(), 'now') else 0
            start_time = self._logfile._starttime if self._logfile and hasattr(self._logfile, '_starttime') else 0
            next_time = max(current_time + self._period, start_time)
            self.eventlist().source_is_pending(self, next_time)
        
        current_time = self.eventlist().now() if hasattr(self.eventlist(), 'now') else 0
        
        if self._queue and self._logfile:
            # 如果队列繁忙，记录总繁忙时间
            if self._busy:
                self._total_busy += current_time - self._last_transition
            
            # 写入记录
            busy_fraction = self._total_busy / self._period if self._period > 0 else 0
            self._logfile.writeRecord(Logger.EventType.QUEUE_RECORD,
                                    self._queue.get_id() if hasattr(self._queue, 'get_id') else 0,
                                    QueueLogger.QueueRecord.CUM_TRAFFIC,
                                    busy_fraction, self._pkt_arrivals, self._pkt_trims)
        
        # 重置计数
        self.reset_count()
    
    def reset_count(self):
        """对应 C++ 中的 reset_count()"""
        current_time = self.eventlist().now() if hasattr(self.eventlist(), 'now') else 0
        self._last_transition = current_time
        self._total_busy = 0
        self._pkt_trims = 0
        self._pkt_arrivals = 0
        if self._queue and hasattr(self._queue, 'queuesize'):
            self._busy = self._queue.queuesize() > 0
        else:
            self._busy = False
    
    @staticmethod
    def event_to_str(event) -> str:
        """对应 C++ 中的 static string event_to_str(RawLogEvent& event)"""
        return "QueueLoggerEmpty::event_to_str TBD"


class QueueLoggerSampling(QueueLogger):
    """
    采样队列日志记录器 - 对应 loggers.h 中的 QueueLoggerSampling
    正确实现多重继承: QueueLogger + EventSource (与C++版本一致)
    """
    
    def __init__(self, period: int, eventlist):
        """对应 C++ 构造函数 QueueLoggerSampling(simtime_picosec period, EventList &eventlist)"""
        # 延迟导入避免循环引用
        from ..eventlist import EventSource
        
        # 运行时动态继承EventSource
        if not hasattr(self.__class__, '_eventsource_added'):
            self.__class__.__bases__ = self.__class__.__bases__ + (EventSource,)
            self.__class__._eventsource_added = True
        
        # 多重继承初始化 - 先初始化EventSource
        EventSource.__init__(self, eventlist, "QueuelogSampling") 
        QueueLogger.__init__(self)
        
        self._period = period
        self._queue = None
        self._lastlook = 0
        self._lastq = 0
        self._seenQueueInD = False
        self._minQueueInD = 0
        self._maxQueueInD = 0
        self._lastDroppedInD = 0
        self._lastIdledInD = 0
        self._numIdledInD = 0
        self._numDropsInD = 0
        self._cumidle = 0.0
        self._cumarr = 0.0
        self._cumdrop = 0.0
        
        # 设置定期事件
        if hasattr(eventlist, 'source_is_pending'):
            eventlist.source_is_pending(self, period)
    
    def logQueue(self, queue, ev: QueueLogger.QueueEvent, pkt) -> None:
        """对应 C++ 中的 QueueLoggerSampling::logQueue()"""
        if self._queue is None:
            self._queue = queue
        assert queue == self._queue
        
        queue_size = queue.queuesize() if hasattr(queue, 'queuesize') else 0
        self._lastq = queue_size
        
        current_time = self.eventlist().now() if hasattr(self.eventlist(), 'now') else 0
        
        if not self._seenQueueInD:
            self._seenQueueInD = True
            self._minQueueInD = queue_size
            self._maxQueueInD = self._minQueueInD
            self._lastDroppedInD = 0
            self._lastIdledInD = 0
            self._numIdledInD = 0
            self._numDropsInD = 0
        else:
            self._minQueueInD = min(self._minQueueInD, queue_size)
            self._maxQueueInD = max(self._maxQueueInD, queue_size)
        
        dt_ps = current_time - self._lastlook
        dt = dt_ps / 1000000000000.0  # 转换为秒
        self._lastlook = current_time
        
        if ev == QueueLogger.QueueEvent.PKT_SERVICE:
            pass
        elif ev == QueueLogger.QueueEvent.PKT_ENQUEUE:
            drain_time = queue.drainTime(pkt) if hasattr(queue, 'drainTime') else 0
            self._cumarr += drain_time / 1000000000000.0
            
            pkt_size = pkt.size() if hasattr(pkt, 'size') else 0
            if queue_size > pkt_size:
                pass  # 刚刚在工作
            else:  # 刚刚在空闲
                service_capacity = queue.serviceCapacity(dt_ps) if hasattr(queue, 'serviceCapacity') else 0
                self._cumidle += dt
                self._lastIdledInD = service_capacity
                self._numIdledInD += 1
        elif ev == QueueLogger.QueueEvent.PKT_DROP:
            pkt_size = pkt.size() if hasattr(pkt, 'size') else 0
            assert queue_size >= pkt_size
            
            drain_time = queue.drainTime(pkt) if hasattr(queue, 'drainTime') else 0
            localdroptime = drain_time / 1000000000000.0
            self._cumarr += localdroptime
            self._cumdrop += localdroptime
            self._lastDroppedInD = pkt_size
            self._numDropsInD += 1
    
    def do_next_event(self) -> None:
        """对应 C++ 中的 QueueLoggerSampling::doNextEvent()"""
        # 安排下一个事件 - 对应 C++ 中的 eventlist().sourceIsPending()
        if hasattr(self.eventlist(), 'source_is_pending'):
            current_time = self.eventlist().now() if hasattr(self.eventlist(), 'now') else 0
            start_time = self._logfile._starttime if self._logfile and hasattr(self._logfile, '_starttime') else 0
            next_time = max(current_time + self._period, start_time)
            self.eventlist().source_is_pending(self, next_time)
        
        if self._queue is None or not self._logfile:
            return
        
        current_time = self.eventlist().now() if hasattr(self.eventlist(), 'now') else 0
        queuebuff = self._queue.maxsize() if hasattr(self._queue, 'maxsize') else 0
        
        if not self._seenQueueInD:
            # 队列大小在过去D时间单位内没有变化
            self._logfile.writeRecord(Logger.EventType.QUEUE_APPROX, 
                                    self._queue.get_id() if hasattr(self._queue, 'get_id') else 0,
                                    QueueLogger.QueueApprox.QUEUE_RANGE,
                                    float(self._lastq), float(self._lastq), float(self._lastq))
            self._logfile.writeRecord(Logger.EventType.QUEUE_APPROX,
                                    self._queue.get_id() if hasattr(self._queue, 'get_id') else 0,
                                    QueueLogger.QueueApprox.QUEUE_OVERFLOW,
                                    0.0, 0.0, float(queuebuff))
        else:
            # 队列大小已经变化
            self._logfile.writeRecord(Logger.EventType.QUEUE_APPROX,
                                    self._queue.get_id() if hasattr(self._queue, 'get_id') else 0,
                                    QueueLogger.QueueApprox.QUEUE_RANGE,
                                    float(self._lastq), float(self._minQueueInD), float(self._maxQueueInD))
            self._logfile.writeRecord(Logger.EventType.QUEUE_APPROX,
                                    self._queue.get_id() if hasattr(self._queue, 'get_id') else 0,
                                    QueueLogger.QueueApprox.QUEUE_OVERFLOW,
                                    -float(self._lastIdledInD), float(self._lastDroppedInD), float(queuebuff))
        
        self._seenQueueInD = False
        dt_ps = current_time - self._lastlook
        self._lastlook = current_time
        
        # 如果队列为空，我们一直在空闲
        if hasattr(self._queue, 'queuesize') and self._queue.queuesize() == 0:
            dt_sec = dt_ps / 1000000000000.0  # 转换为秒
            self._cumidle += dt_sec
        
        self._logfile.writeRecord(Logger.EventType.QUEUE_RECORD,
                                self._queue.get_id() if hasattr(self._queue, 'get_id') else 0,
                                QueueLogger.QueueRecord.CUM_TRAFFIC,
                                self._cumarr, self._cumidle, self._cumdrop)
    
    @staticmethod
    def event_to_str(event) -> str:
        """对应 C++ 中的 static string event_to_str(RawLogEvent& event)"""
        return f"QueueLoggerSampling: {event}"


class MultiQueueLoggerSampling(QueueLogger):
    """
    多队列采样日志记录器 - 对应 loggers.h 中的 MultiQueueLoggerSampling
    正确实现多重继承: QueueLogger + EventSource (与C++版本一致)
    """
    
    def __init__(self, id_val: int, period: int, eventlist):
        """对应 C++ 构造函数"""
        # 延迟导入避免循环引用
        from ..eventlist import EventSource
        
        # 运行时动态继承EventSource
        if not hasattr(self.__class__, '_eventsource_added'):
            self.__class__.__bases__ = self.__class__.__bases__ + (EventSource,)
            self.__class__._eventsource_added = True
        
        # 多重继承初始化
        EventSource.__init__(self, eventlist, f"MultiQueueLoggerSampling_{id_val}")
        QueueLogger.__init__(self)
        
        self._id = id_val
        self._period = period
        self._seenQueueInD = False
        self._minQueueInD = 0
        self._maxQueueInD = 0
        self._currentQueueSizeBytes = 0
        self._currentQueueSizePkts = 0
        
        # 设置定期事件
        if hasattr(eventlist, 'source_is_pending'):
            eventlist.source_is_pending(self, period)
    
    def logQueue(self, queue, ev: QueueLogger.QueueEvent, pkt) -> None:
        """对应 C++ 中的 MultiQueueLoggerSampling::logQueue()"""
        pkt_size = pkt.size() if hasattr(pkt, 'size') else 0
        
        if ev == QueueLogger.QueueEvent.PKT_ENQUEUE:
            self._currentQueueSizeBytes += pkt_size
            self._currentQueueSizePkts += 1
            queue_size = queue.queuesize() if hasattr(queue, 'queuesize') else 0
            assert queue_size <= self._currentQueueSizeBytes
        elif ev == QueueLogger.QueueEvent.PKT_TRIM:
            pass
        elif ev == QueueLogger.QueueEvent.PKT_SERVICE:
            self._currentQueueSizeBytes -= pkt_size
            self._currentQueueSizePkts -= 1
        elif ev == QueueLogger.QueueEvent.PKT_UNQUEUE:
            self._currentQueueSizeBytes -= pkt_size
            self._currentQueueSizePkts -= 1
        elif ev in (QueueLogger.QueueEvent.PKT_DROP, 
                   QueueLogger.QueueEvent.PKT_BOUNCE, 
                   QueueLogger.QueueEvent.PKT_ARRIVE):
            pass  # 不改变队列大小
        
        if not self._seenQueueInD:
            self._seenQueueInD = True
            self._minQueueInD = self._currentQueueSizeBytes
            self._maxQueueInD = self._minQueueInD
        else:
            self._minQueueInD = min(self._minQueueInD, self._currentQueueSizeBytes)
            self._maxQueueInD = max(self._maxQueueInD, self._currentQueueSizeBytes)
        
        assert self._currentQueueSizePkts >= 0
        assert self._currentQueueSizeBytes >= 0
    
    def do_next_event(self) -> None:
        """对应 C++ 中的 MultiQueueLoggerSampling::doNextEvent()"""
        # 安排下一个事件
        if hasattr(self.eventlist(), 'source_is_pending'):
            current_time = self.eventlist().now() if hasattr(self.eventlist(), 'now') else 0
            start_time = self._logfile._starttime if self._logfile and hasattr(self._logfile, '_starttime') else 0
            next_time = max(current_time + self._period, start_time)
            self.eventlist().source_is_pending(self, next_time)
        
        if self._logfile:
            # 记录队列统计信息
            self._logfile.writeRecord(Logger.EventType.QUEUE_RECORD,
                                    self._id,
                                    QueueLogger.QueueRecord.CUM_TRAFFIC,
                                    float(self._currentQueueSizeBytes),
                                    float(self._currentQueueSizePkts),
                                    0.0)
        
        # 重置统计
        self._seenQueueInD = False
        self._minQueueInD = self._currentQueueSizeBytes
        self._maxQueueInD = self._currentQueueSizeBytes
    
    @staticmethod
    def event_to_str(event) -> str:
        """对应 C++ 中的 static string event_to_str(RawLogEvent& event)"""
        return f"MultiQueueLoggerSampling: {event}"


# ========================= Queue Logger Factory =========================

class QueueLoggerFactory:
    """
    队列日志记录器工厂 - 对应 loggers.h 中的 QueueLoggerFactory
    """
    
    class QueueLoggerType(IntEnum):
        """对应 QueueLoggerFactory::QueueLoggerType 枚举"""
        LOGGER_SIMPLE = 0
        LOGGER_SAMPLING = 1
        MULTIQUEUE_SAMPLING = 2
        LOGGER_EMPTY = 3
    
    def __init__(self, logfile, logtype: 'QueueLoggerType', eventlist):
        """对应 C++ 构造函数"""
        self._logfile = logfile
        self._logger_type = logtype
        self._eventlist = eventlist
        self._sample_period = 0
        self._loggers = []
    
    def set_sample_period(self, sample_period: int) -> None:
        """对应 C++ 中的 set_sample_period()"""
        self._sample_period = sample_period
    
    def createQueueLogger(self) -> QueueLogger:
        """对应 C++ 中的 createQueueLogger()"""
        queue_logger = None
        
        if self._logger_type == self.QueueLoggerType.LOGGER_SIMPLE:
            queue_logger = QueueLoggerSimple()
            if self._logfile:
                self._logfile.addLogger(queue_logger)
        elif self._logger_type == self.QueueLoggerType.LOGGER_SAMPLING:
            queue_logger = QueueLoggerSampling(self._sample_period, self._eventlist)
            if self._logfile:
                self._logfile.addLogger(queue_logger)
        elif self._logger_type == self.QueueLoggerType.MULTIQUEUE_SAMPLING:
            # 注意：这里需要ID，但我们无法从函数参数中获得，所以设为0
            queue_logger = MultiQueueLoggerSampling(0, self._sample_period, self._eventlist)
            if self._logfile:
                self._logfile.addLogger(queue_logger)
        elif self._logger_type == self.QueueLoggerType.LOGGER_EMPTY:
            queue_logger = QueueLoggerEmpty(self._sample_period, self._eventlist)
            if self._logfile:
                self._logfile.addLogger(queue_logger)
        
        if queue_logger:
            self._loggers.append(queue_logger)
        
        return queue_logger