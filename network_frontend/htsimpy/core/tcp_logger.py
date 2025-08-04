"""
TCP Logger - TCP日志记录器

对应文件: tcplogger.h/cpp
功能: TCP连接的日志记录功能

主要类:
- TcpLogger: TCP日志记录基类
- TcpSinkLoggerSampling: TCP接收端采样日志记录器
"""

from typing import List, Optional
from .eventlist import EventList, EventSource


class TcpLogger:
    """TCP日志记录基类 - 对应 C++ TcpLogger"""
    
    def __init__(self):
        self._sinks = []  # 监控的TCP sink列表
    
    def monitor_sink(self, sink):
        """添加要监控的TCP sink"""
        self._sinks.append(sink)


class TcpSinkLoggerSampling(TcpLogger, EventSource):
    """TCP接收端采样日志记录器 - 对应 C++ TcpSinkLoggerSampling"""
    
    def __init__(self, period: int, eventlist: EventList):
        """
        初始化采样日志记录器
        
        Args:
            period: 采样周期（皮秒）
            eventlist: 事件列表
        """
        TcpLogger.__init__(self)
        EventSource.__init__(self, eventlist, "TcpSinkLoggerSampling")
        self._period = period
        
        # 注册第一个采样事件
        self._eventlist.addEvent(self._period, self)
    
    def doNextEvent(self):
        """处理采样事件"""
        # 记录所有被监控sink的状态
        for sink in self._sinks:
            # 这里可以添加实际的日志记录逻辑
            pass
        
        # 注册下一个采样事件
        self._eventlist.addEvent(self._eventlist.now + self._period, self)
    
    def print_stats(self):
        """打印统计信息"""
        pass