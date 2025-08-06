"""
Switch Logger Classes - 交换机日志类

功能: 记录交换机相关的事件和统计信息
"""

from abc import ABC, abstractmethod
from enum import IntEnum
from typing import TYPE_CHECKING, Optional, Dict, List

from .base import Logger
from .core import Logged

# 避免循环引用
if TYPE_CHECKING:
    from ..eventlist import EventSource
    from ..switch import Switch
    from ..packet import Packet


class SwitchLogger(Logger, ABC):
    """交换机日志记录器基类"""
    
    class SwitchEvent(IntEnum):
        """交换机事件类型"""
        PKT_ARRIVE = 0      # 数据包到达
        PKT_FORWARD = 1     # 数据包转发
        PKT_DROP = 2        # 数据包丢弃
        ROUTE_LOOKUP = 3    # 路由查找
        QUEUE_SELECT = 4    # 队列选择
        
    class SwitchRecord(IntEnum):
        """交换机记录类型"""
        PKT_COUNT = 0       # 数据包计数
        BYTE_COUNT = 1      # 字节计数
        DROP_COUNT = 2      # 丢弃计数
        UTILIZATION = 3     # 利用率
        
    @abstractmethod
    def log_switch(self, switch: 'Switch', ev: 'SwitchEvent', pkt: Optional['Packet'] = None) -> None:
        """记录交换机事件"""
        pass
        
    def event_to_str(self, event: IntEnum) -> str:
        """将事件转换为字符串"""
        if event == self.SwitchEvent.PKT_ARRIVE:
            return "PKT_ARRIVE"
        elif event == self.SwitchEvent.PKT_FORWARD:
            return "PKT_FORWARD"
        elif event == self.SwitchEvent.PKT_DROP:
            return "PKT_DROP"
        elif event == self.SwitchEvent.ROUTE_LOOKUP:
            return "ROUTE_LOOKUP"
        elif event == self.SwitchEvent.QUEUE_SELECT:
            return "QUEUE_SELECT"
        else:
            return "UNKNOWN"


class SwitchLoggerSimple(SwitchLogger):
    """简单交换机日志记录器"""
    
    def log_switch(self, switch: 'Switch', ev: SwitchLogger.SwitchEvent, pkt: Optional['Packet'] = None) -> None:
        """记录交换机事件"""
        if self._logfile:
            switch_id = switch.get_id() if hasattr(switch, 'get_id') else 0
            flow_id = pkt.flow().get_id() if pkt and hasattr(pkt, 'flow') else 0
            pkt_id = pkt.id() if pkt and hasattr(pkt, 'id') else 0
            pkt_size = pkt.size() if pkt and hasattr(pkt, 'size') else 0
            
            self._logfile.writeRecord(
                Logger.EventType.FLOW_EVENT,  # 使用FLOW_EVENT类型
                switch_id,
                ev,
                float(pkt_size),
                flow_id,
                pkt_id
            )


class SwitchLoggerSampling(SwitchLogger):
    """采样交换机日志记录器"""
    
    def __init__(self, period: int, eventlist, switch: Optional['Switch'] = None):
        """初始化采样交换机日志记录器"""
        # 延迟导入避免循环引用
        from ..eventlist import EventSource
        
        # 运行时动态继承EventSource
        if not hasattr(self.__class__, '_eventsource_added'):
            self.__class__.__bases__ = self.__class__.__bases__ + (EventSource,)
            self.__class__._eventsource_added = True
            
        # 多重继承初始化
        EventSource.__init__(self, eventlist, "SwitchLoggerSampling")
        SwitchLogger.__init__(self)
        
        self._period = period
        self._switch = switch
        self._pkt_count = 0
        self._byte_count = 0
        self._drop_count = 0
        self._forward_count = 0
        self._last_sample_time = 0
        
        # Per-port statistics
        self._port_stats: Dict[int, Dict[str, int]] = {}
        
        # 设置定期事件
        if hasattr(eventlist, 'source_is_pending'):
            eventlist.source_is_pending(self, period)
            
    def log_switch(self, switch: 'Switch', ev: SwitchLogger.SwitchEvent, pkt: Optional['Packet'] = None) -> None:
        """记录交换机事件"""
        if self._switch is None:
            self._switch = switch
            
        pkt_size = pkt.size() if pkt and hasattr(pkt, 'size') else 0
        
        if ev == SwitchLogger.SwitchEvent.PKT_ARRIVE:
            self._pkt_count += 1
            self._byte_count += pkt_size
        elif ev == SwitchLogger.SwitchEvent.PKT_FORWARD:
            self._forward_count += 1
        elif ev == SwitchLogger.SwitchEvent.PKT_DROP:
            self._drop_count += 1
            
        # Track per-port statistics if available
        if pkt and hasattr(pkt, 'ingress_port'):
            port_id = pkt.ingress_port
            if port_id not in self._port_stats:
                self._port_stats[port_id] = {
                    'pkt_count': 0,
                    'byte_count': 0,
                    'drop_count': 0
                }
            self._port_stats[port_id]['pkt_count'] += 1
            self._port_stats[port_id]['byte_count'] += pkt_size
            if ev == SwitchLogger.SwitchEvent.PKT_DROP:
                self._port_stats[port_id]['drop_count'] += 1
                
    def do_next_event(self) -> None:
        """处理下一个采样事件"""
        # 安排下一个事件
        if hasattr(self.eventlist(), 'source_is_pending'):
            current_time = self.eventlist().now() if hasattr(self.eventlist(), 'now') else 0
            self.eventlist().source_is_pending(self, current_time + self._period)
            
        if self._switch and self._logfile:
            current_time = self.eventlist().now() if hasattr(self.eventlist(), 'now') else 0
            interval = current_time - self._last_sample_time if self._last_sample_time > 0 else self._period
            
            # Calculate utilization
            utilization = self._byte_count * 8.0 / interval if interval > 0 else 0.0
            
            # Write aggregate statistics
            self._logfile.writeRecord(
                Logger.EventType.FLOW_EVENT,
                self._switch.get_id() if hasattr(self._switch, 'get_id') else 0,
                SwitchLogger.SwitchRecord.PKT_COUNT,
                float(self._pkt_count),
                float(self._forward_count),
                float(self._drop_count)
            )
            
            self._logfile.writeRecord(
                Logger.EventType.FLOW_EVENT,
                self._switch.get_id() if hasattr(self._switch, 'get_id') else 0,
                SwitchLogger.SwitchRecord.BYTE_COUNT,
                float(self._byte_count),
                utilization,
                0.0
            )
            
            # Reset counters
            self._pkt_count = 0
            self._byte_count = 0
            self._drop_count = 0
            self._forward_count = 0
            self._last_sample_time = current_time
            
    @staticmethod
    def event_to_str(event) -> str:
        """将事件转换为字符串"""
        return f"SwitchLoggerSampling: {event}"


class SwitchLoggerFactory:
    """交换机日志记录器工厂"""
    
    class SwitchLoggerType(IntEnum):
        """交换机日志记录器类型"""
        LOGGER_SIMPLE = 0
        LOGGER_SAMPLING = 1
        
    def __init__(self, logfile, logtype: 'SwitchLoggerType', eventlist):
        """初始化工厂"""
        self._logfile = logfile
        self._logger_type = logtype
        self._eventlist = eventlist
        self._sample_period = 1000000000  # 默认1ms
        self._loggers: List[SwitchLogger] = []
        
    def set_sample_period(self, sample_period: int) -> None:
        """设置采样周期"""
        self._sample_period = sample_period
        
    def create_switch_logger(self, switch: Optional['Switch'] = None) -> SwitchLogger:
        """创建交换机日志记录器"""
        logger = None
        
        if self._logger_type == self.SwitchLoggerType.LOGGER_SIMPLE:
            logger = SwitchLoggerSimple()
            if self._logfile:
                self._logfile.addLogger(logger)
        elif self._logger_type == self.SwitchLoggerType.LOGGER_SAMPLING:
            logger = SwitchLoggerSampling(self._sample_period, self._eventlist, switch)
            if self._logfile:
                self._logfile.addLogger(logger)
                
        if logger:
            self._loggers.append(logger)
            
        return logger