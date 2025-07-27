"""
Reorder Buffer Logger Classes - 重排序缓冲日志类

对应文件: loggers.h (ReorderBufferLoggerSampling)
功能: 专门用于记录重排序缓冲相关的统计信息

主要类:
- ReorderBufferLoggerSampling: 重排序缓冲采样日志记录器
"""

from typing import TYPE_CHECKING

from .protocols import ReorderBufferLogger

# 避免循环引用，使用TYPE_CHECKING
if TYPE_CHECKING:
    from ..eventlist import EventSource


class ReorderBufferLoggerSampling(ReorderBufferLogger):
    """
    重排序缓冲采样日志记录器 - 对应 loggers.h 中的 ReorderBufferLoggerSampling
    正确实现多重继承: ReorderBufferLogger + EventSource (与C++版本一致)
    """
    
    def __init__(self, period: int, eventlist):
        """对应 C++ 构造函数"""
        # 延迟导入避免循环引用
        from ..eventlist import EventSource
        
        # 运行时动态继承EventSource
        if not hasattr(self.__class__, '_eventsource_added'):
            self.__class__.__bases__ = self.__class__.__bases__ + (EventSource,)
            self.__class__._eventsource_added = True
        
        # 多重继承初始化 - 先初始化EventSource（因为它也调用了Logged.__init__）
        EventSource.__init__(self, eventlist, "ReorderBufferLoggerSampling")
        ReorderBufferLogger.__init__(self)  # ReorderBufferLogger继承自Logger
        
        self._period = period
        self._queue_len = 0
        self._min_queue = 0
        self._max_queue = 0
        
        # 设置定期事件
        if hasattr(eventlist, 'source_is_pending'):
            eventlist.source_is_pending(self, period)
    
    def logBuffer(self, ev: ReorderBufferLogger.BufferEvent) -> None:
        """对应 C++ 中的 logBuffer()"""
        if ev == ReorderBufferLogger.BufferEvent.BUF_ENQUEUE:
            self._queue_len += 1
            if self._queue_len > self._max_queue:
                self._max_queue = self._queue_len
        elif ev == ReorderBufferLogger.BufferEvent.BUF_DEQUEUE:
            self._queue_len -= 1
            if self._queue_len < self._min_queue:
                self._min_queue = self._queue_len
            assert self._queue_len >= 0
    
    def do_next_event(self) -> None:
        """
        对应 C++ 中的 ReorderBufferLoggerSampling::doNextEvent()
        实现 EventSource 的抽象方法
        """
        # 安排下一个事件 - 对应 C++ 中的 eventlist().sourceIsPending()
        if hasattr(self.eventlist(), 'source_is_pending'):
            current_time = self.eventlist().now() if hasattr(self.eventlist(), 'now') else 0
            start_time = self._logfile._starttime if self._logfile and hasattr(self._logfile, '_starttime') else 0
            next_time = max(current_time + self._period, start_time)
            self.eventlist().source_is_pending(self, next_time)
        
        # 记录重排序缓冲统计信息
        if self._logfile:
            self._logfile.writeRecord(ReorderBufferLogger.EventType.ENERGY, 0, 0,
                                    float(self._queue_len), float(self._min_queue), float(self._max_queue))
        
        # 重置统计
        self._min_queue = self._queue_len
        self._max_queue = self._queue_len
    
    @staticmethod
    def event_to_str(event) -> str:
        """对应 C++ 中的 static string event_to_str(RawLogEvent& event)"""
        return f"ReorderBufferLoggerSampling: {event}"