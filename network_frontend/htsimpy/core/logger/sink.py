"""
Sink Logger Classes - Sink日志类

对应文件: loggers.h (SinkLoggerSampling 及其子类)
功能: 专门用于记录各种协议的Sink采样统计

主要类:
- SinkLoggerSampling: Sink采样日志记录器基类
- TcpSinkLoggerSampling: TCP Sink采样日志记录器
- SwiftSinkLoggerSampling: Swift Sink采样日志记录器
- STrackSinkLoggerSampling: STrack Sink采样日志记录器
- NdpSinkLoggerSampling: NDP Sink采样日志记录器
- RoceSinkLoggerSampling: RoCE Sink采样日志记录器
- HPCCSinkLoggerSampling: HPCC Sink采样日志记录器
"""

from typing import Dict, List, TYPE_CHECKING

from .base import Logger
from .tcp import TcpLogger
from .protocols import SwiftLogger, STrackLogger, NdpLogger, RoceLogger, HPCCLogger

# 避免循环引用，使用TYPE_CHECKING
if TYPE_CHECKING:
    from ..eventlist import EventSource


class SinkLoggerSampling(Logger):
    """
    Sink采样日志记录器基类 - 对应 loggers.h 中的 SinkLoggerSampling
    正确实现多重继承: Logger + EventSource (与C++版本一致)
    """
    
    def __init__(self, period: int, eventlist, sink_type, event_type: int):
        """对应 C++ 构造函数"""
        # 延迟导入避免循环引用
        from ..eventlist import EventSource
        
        # 运行时动态继承EventSource
        if not hasattr(self.__class__, '_eventsource_added'):
            self.__class__.__bases__ = self.__class__.__bases__ + (EventSource,)
            self.__class__._eventsource_added = True
        
        # 多重继承初始化 - 先初始化EventSource（因为它也调用了Logged.__init__）
        EventSource.__init__(self, eventlist, "SinkLoggerSampling")
        Logger.__init__(self)  # Logger的__init__比较简单
        
        self._period = period
        self._sink_type = sink_type
        self._event_type = event_type
        self._sinks = []
        self._multipath = []
        self._last_seq = []
        self._last_sndbuf = []
        self._last_rate = []
        self._last_time = 0
        self._multipath_src: Dict = {}
        self._multipath_seq: Dict = {}
        
        # 设置定期事件
        if hasattr(eventlist, 'source_is_pending'):
            eventlist.source_is_pending(self, period)
    
    def monitorSink(self, sink) -> None:
        """对应 C++ 中的 monitorSink()"""
        self._sinks.append(sink)
        self._last_seq.append(sink.cumulative_ack() if hasattr(sink, 'cumulative_ack') else 0)
        self._last_rate.append(0)
        self._multipath.append(0)
    
    def monitorMultipathSink(self, sink) -> None:
        """对应 C++ 中的 monitorMultipathSink()"""
        self._sinks.append(sink)
        self._last_seq.append(sink.cumulative_ack() if hasattr(sink, 'cumulative_ack') else 0)
        self._last_rate.append(0)
        self._multipath.append(1)
        
        # TCP特定逻辑
        if hasattr(sink, '_src'):
            src = sink._src
            if src and hasattr(src, '_mSrc') and src._mSrc:
                if src._mSrc not in self._multipath_src:
                    self._multipath_seq[src._mSrc] = 0
                    self._multipath_src[src._mSrc] = 0
    
    def do_next_event(self) -> None:
        """
        对应 C++ 中的 SinkLoggerSampling::doNextEvent()
        实现 EventSource 的抽象方法
        """
        # 安排下一个事件 - 对应 C++ 中的 eventlist().sourceIsPending()
        if hasattr(self.eventlist(), 'source_is_pending'):
            current_time = self.eventlist().now() if hasattr(self.eventlist(), 'now') else 0
            start_time = self._logfile._starttime if self._logfile and hasattr(self._logfile, '_starttime') else 0
            next_time = max(current_time + self._period, start_time)
            self.eventlist().source_is_pending(self, next_time)
        
        # 原有的doNextEvent逻辑...
        if not self._logfile:
            return
            
        current_time = self.eventlist().now() if hasattr(self.eventlist(), 'now') else 0
        dt = current_time - self._last_time
        
        for i, sink in enumerate(self._sinks):
            if i < len(self._last_seq):
                old_seq = self._last_seq[i]
                new_seq = sink.cumulative_ack() if hasattr(sink, 'cumulative_ack') else 0
                rate = (new_seq - old_seq) / dt if dt > 0 else 0
                self._last_seq[i] = new_seq
                
                if self._logfile:
                    self._logfile.writeRecord(self._sink_type, 
                                            sink.get_id() if hasattr(sink, 'get_id') else 0,
                                            self._event_type,
                                            float(rate), float(new_seq), 0.0)
        
        self._last_time = current_time
    
    @staticmethod
    def event_to_str(event) -> str:
        """对应 C++ 中的 static string event_to_str(RawLogEvent& event)"""
        return f"SinkLoggerSampling: {event}"


class TcpSinkLoggerSampling(SinkLoggerSampling):
    """TCP Sink采样日志记录器 - 对应 loggers.h 中的 TcpSinkLoggerSampling"""
    
    def __init__(self, period: int, eventlist):
        """对应 C++ 构造函数"""
        super().__init__(period, eventlist, Logger.EventType.TCP_SINK, TcpLogger.TcpSinkRecord.RATE)
    
    @staticmethod
    def event_to_str(event) -> str:
        """对应 C++ 中的 static string event_to_str(RawLogEvent& event)"""
        return f"TcpSinkLoggerSampling: {event}"


class SwiftSinkLoggerSampling(SinkLoggerSampling):
    """Swift Sink采样日志记录器 - 对应 loggers.h 中的 SwiftSinkLoggerSampling"""
    
    def __init__(self, period: int, eventlist):
        """对应 C++ 构造函数"""
        super().__init__(period, eventlist, Logger.EventType.SWIFT_SINK, SwiftLogger.SwiftSinkRecord.RATE)
        self._last_sub_seq: List = []
    
    @staticmethod
    def event_to_str(event) -> str:
        """对应 C++ 中的 static string event_to_str(RawLogEvent& event)"""
        return f"SwiftSinkLoggerSampling: {event}"


class STrackSinkLoggerSampling(SinkLoggerSampling):
    """STrack Sink采样日志记录器 - 对应 loggers.h 中的 STrackSinkLoggerSampling"""
    
    def __init__(self, period: int, eventlist):
        """对应 C++ 构造函数"""
        super().__init__(period, eventlist, Logger.EventType.STRACK_SINK, STrackLogger.STrackSinkRecord.RATE)
        self._last_sub_seq: List = []
    
    @staticmethod
    def event_to_str(event) -> str:
        """对应 C++ 中的 static string event_to_str(RawLogEvent& event)"""
        return f"STrackSinkLoggerSampling: {event}"


class NdpSinkLoggerSampling(SinkLoggerSampling):
    """NDP Sink采样日志记录器 - 对应 loggers.h 中的 NdpSinkLoggerSampling"""
    
    def __init__(self, period: int, eventlist):
        """对应 C++ 构造函数"""
        super().__init__(period, eventlist, Logger.EventType.NDP_SINK, NdpLogger.NdpSinkRecord.RATE)
    
    @staticmethod
    def event_to_str(event) -> str:
        """对应 C++ 中的 static string event_to_str(RawLogEvent& event)"""
        return f"NdpSinkLoggerSampling: {event}"


class RoceSinkLoggerSampling(SinkLoggerSampling):
    """RoCE Sink采样日志记录器 - 对应 loggers.h 中的 RoceSinkLoggerSampling"""
    
    def __init__(self, period: int, eventlist):
        """对应 C++ 构造函数"""
        super().__init__(period, eventlist, Logger.EventType.ROCE_SINK, RoceLogger.RoceSinkRecord.RATE)
    
    @staticmethod
    def event_to_str(event) -> str:
        """对应 C++ 中的 static string event_to_str(RawLogEvent& event)"""
        return f"RoceSinkLoggerSampling: {event}"


class HPCCSinkLoggerSampling(SinkLoggerSampling):
    """HPCC Sink采样日志记录器 - 对应 loggers.h 中的 HPCCSinkLoggerSampling"""
    
    def __init__(self, period: int, eventlist):
        """对应 C++ 构造函数"""
        super().__init__(period, eventlist, Logger.EventType.HPCC_SINK, HPCCLogger.HPCCSinkRecord.RATE)
    
    @staticmethod
    def event_to_str(event) -> str:
        """对应 C++ 中的 static string event_to_str(RawLogEvent& event)"""
        return f"HPCCSinkLoggerSampling: {event}"