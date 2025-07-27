"""
Aggregate Logger Classes - 聚合日志类

对应文件: loggers.h (AggregateTcpLogger)
功能: 专门用于记录聚合统计信息

主要类:
- AggregateTcpLogger: 聚合TCP日志记录器
"""

from typing import List, TYPE_CHECKING

from .base import Logger
from .tcp import TcpLogger

# 避免循环引用，使用TYPE_CHECKING
if TYPE_CHECKING:
    from ..eventlist import EventSource


class AggregateTcpLogger(Logger):
    """
    聚合TCP日志记录器 - 对应 loggers.h 中的 AggregateTcpLogger
    
    功能: 定期收集和记录多个TCP流的聚合统计信息
    正确实现多重继承: Logger + EventSource (与C++版本一致)
    """
    
    def __init__(self, period: int, eventlist):
        """对应 C++ 构造函数 AggregateTcpLogger(simtime_picosec period, EventList& eventlist)"""
        # 延迟导入避免循环引用
        from ..eventlist import EventSource
        
        # 运行时动态继承EventSource
        if not hasattr(self.__class__, '_eventsource_added'):
            self.__class__.__bases__ = self.__class__.__bases__ + (EventSource,)
            self.__class__._eventsource_added = True
        
        # 多重继承初始化 - 先初始化EventSource（因为它也调用了Logged.__init__）
        EventSource.__init__(self, eventlist, "bunchofflows")
        Logger.__init__(self)  # Logger的__init__比较简单
        
        self._period = period
        self._monitored_tcps: List = []  # 对应 C++ 中的 tcplist_t _monitoredTcps
        
        # 设置定期事件 - 对应 C++ 中的 eventlist.sourceIsPending(*this,period)
        if hasattr(eventlist, 'source_is_pending'):
            eventlist.source_is_pending(self, period)
    
    def monitorTcp(self, tcp) -> None:
        """
        对应 C++ 中的 AggregateTcpLogger::monitorTcp(TcpSrc& tcp)
        添加TCP源到监控列表
        """
        self._monitored_tcps.append(tcp)
    
    def do_next_event(self) -> None:
        """
        对应 C++ 中的 AggregateTcpLogger::doNextEvent()
        实现 EventSource 的抽象方法
        
        核心功能：
        1. 收集所有监控TCP流的统计信息
        2. 计算聚合值（平均cwnd、unacked、effcwnd）
        3. 写入日志记录
        4. 安排下一个事件
        """
        # 安排下一个事件 - 对应 C++ 中的 eventlist().sourceIsPending()
        if hasattr(self.eventlist(), 'source_is_pending'):
            current_time = self.eventlist().now() if hasattr(self.eventlist(), 'now') else 0
            start_time = self._logfile._starttime if self._logfile and hasattr(self._logfile, '_starttime') else 0
            next_time = max(current_time + self._period, start_time)
            self.eventlist().source_is_pending(self, next_time)
        
        # 聚合统计计算 - 对应 C++ 实现
        tot_unacked = 0.0
        tot_effcwnd = 0.0  
        tot_cwnd = 0.0
        num_flows = 0
        
        for tcp in self._monitored_tcps:
            # 假设TCP对象有这些属性（对应 C++ TcpSrc 成员）
            if hasattr(tcp, '_cwnd') and hasattr(tcp, '_unacked') and hasattr(tcp, '_effcwnd'):
                cwnd = tcp._cwnd
                unacked = tcp._unacked
                effcwnd = tcp._effcwnd
                
                tot_cwnd += cwnd
                tot_effcwnd += effcwnd
                tot_unacked += unacked
                num_flows += 1
        
        # 写入聚合记录 - 对应 C++ 中的 _logfile->writeRecord()
        if num_flows > 0 and self._logfile:
            avg_cwnd = tot_cwnd / num_flows
            avg_unacked = tot_unacked / num_flows  
            avg_effcwnd = tot_effcwnd / num_flows
            
            self._logfile.writeRecord(
                Logger.EventType.TCP_RECORD,  # 对应 Logger::TCP_RECORD
                self.get_id() if hasattr(self, 'get_id') else 0,
                TcpLogger.TcpRecord.AVE_CWND,  # 对应 TcpLogger::AVE_CWND
                avg_cwnd,
                avg_unacked,
                avg_effcwnd
            )
    
    @staticmethod
    def event_to_str(event) -> str:
        """
        对应 C++ 中的 static string AggregateTcpLogger::event_to_str(RawLogEvent& event)
        格式化聚合TCP事件为字符串
        """
        import time
        
        # 对应 C++ 的格式化逻辑
        time_str = f"{event._time:.9f}" if hasattr(event, '_time') else "0.000000000"
        
        result = f"{time_str} Type=TCP_RECORD ID={event._id if hasattr(event, '_id') else 0}"
        result += f" Ev AVE_CWND Cwnd {event._val1:.2f}" if hasattr(event, '_val1') else " Ev AVE_CWND Cwnd 0.00"
        result += f" Unacked {event._val2:.2f}" if hasattr(event, '_val2') else " Unacked 0.00"
        result += f" EffCwnd {event._val3:.2f}" if hasattr(event, '_val3') else " EffCwnd 0.00"
        
        return result