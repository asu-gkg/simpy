"""
Memory Logger Classes - 内存日志类

对应文件: loggers.h (MemoryLoggerSampling)
功能: 专门用于记录内存使用相关的统计信息

主要类:
- MemoryLoggerSampling: 内存采样日志记录器
"""

from typing import List, TYPE_CHECKING

from .base import Logger

# 避免循环引用，使用TYPE_CHECKING
if TYPE_CHECKING:
    from ..eventlist import EventSource


class MemoryLoggerSampling(Logger):
    """
    内存采样日志记录器 - 对应 loggers.h 中的 MemoryLoggerSampling
    正确实现多重继承: Logger + EventSource (与C++版本一致)
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
        EventSource.__init__(self, eventlist, "MemoryLoggerSampling")
        Logger.__init__(self)  # Logger的__init__比较简单
        
        self._period = period
        self._tcp_sinks: List = []
        self._mtcp_sinks: List = []
        self._tcp_sources: List = []
        self._mtcp_sources: List = []
        
        # 设置定期事件
        if hasattr(eventlist, 'source_is_pending'):
            eventlist.source_is_pending(self, period)
    
    def monitorTcpSink(self, sink) -> None:
        """对应 C++ 中的 monitorTcpSink()"""
        self._tcp_sinks.append(sink)
    
    def monitorTcpSource(self, source) -> None:
        """对应 C++ 中的 monitorTcpSource()"""
        self._tcp_sources.append(source)
    
    def monitorMultipathTcpSink(self, sink) -> None:
        """对应 C++ 中的 monitorMultipathTcpSink()"""
        self._mtcp_sinks.append(sink)
    
    def monitorMultipathTcpSource(self, source) -> None:
        """对应 C++ 中的 monitorMultipathTcpSource()"""
        self._mtcp_sources.append(source)
    
    def do_next_event(self) -> None:
        """
        对应 C++ 中的 MemoryLoggerSampling::doNextEvent()
        实现 EventSource 的抽象方法
        """
        # 安排下一个事件 - 对应 C++ 中的 eventlist().sourceIsPending()
        if hasattr(self.eventlist(), 'source_is_pending'):
            current_time = self.eventlist().now() if hasattr(self.eventlist(), 'now') else 0
            start_time = self._logfile._starttime if self._logfile and hasattr(self._logfile, '_starttime') else 0
            next_time = max(current_time + self._period, start_time)
            self.eventlist().source_is_pending(self, next_time)
        
        # 收集内存统计信息
        if not self._logfile:
            return
            
        total_tcp_memory = 0
        total_mtcp_memory = 0
        
        # 统计TCP sink内存
        for sink in self._tcp_sinks:
            if hasattr(sink, 'get_memory_usage'):
                total_tcp_memory += sink.get_memory_usage()
        
        # 统计TCP source内存
        for source in self._tcp_sources:
            if hasattr(source, 'get_memory_usage'):
                total_tcp_memory += source.get_memory_usage()
        
        # 统计MTCP sink内存
        for sink in self._mtcp_sinks:
            if hasattr(sink, 'get_memory_usage'):
                total_mtcp_memory += sink.get_memory_usage()
        
        # 统计MTCP source内存
        for source in self._mtcp_sources:
            if hasattr(source, 'get_memory_usage'):
                total_mtcp_memory += source.get_memory_usage()
        
        # 记录内存统计
        if self._logfile:
            self._logfile.writeRecord(Logger.EventType.TCP_MEMORY, 0, 0,
                                    float(total_tcp_memory), float(total_mtcp_memory), 0.0)
    
    @staticmethod
    def event_to_str(event) -> str:
        """对应 C++ 中的 static string event_to_str(RawLogEvent& event)"""
        return f"MemoryLoggerSampling: {event}"