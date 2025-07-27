"""
Traffic Logger Classes - 流量日志类

对应文件: loggertypes.h (TrafficLogger, FlowEventLogger) 和 loggers.h (实现类)
功能: 专门用于记录网络流量相关的事件

主要类:
- TrafficLogger: 流量日志记录器基类
- FlowEventLogger: 流程事件日志记录器基类
- TrafficLoggerSimple: 简单流量日志记录器实现
- FlowEventLoggerSimple: 简单流程事件日志记录器实现
- 各种协议特定的流量日志记录器
"""

from abc import ABC, abstractmethod
from enum import IntEnum
from typing import TYPE_CHECKING

from .base import Logger
from .core import Logged
from .constants import (
    NDP_IS_ACK, NDP_IS_NACK, NDP_IS_PULL, 
    NDP_IS_HEADER, NDP_IS_LASTDATA,
    ROCE_IS_ACK, ROCE_IS_NACK, 
    ROCE_IS_HEADER, ROCE_IS_LASTDATA,
    HPCC_IS_ACK, HPCC_IS_NACK,
    HPCC_IS_HEADER, HPCC_IS_LASTDATA
)

if TYPE_CHECKING:
    pass


class TrafficLogger(Logger, ABC):
    """
    流量日志记录器 - 对应 loggertypes.h 中的 TrafficLogger 类
    
    专门用于记录网络流量相关的事件
    """
    
    class TrafficEvent(IntEnum):
        """对应 TrafficLogger::TrafficEvent 枚举 - 精准复现C++版本"""
        PKT_ARRIVE = 0
        PKT_DEPART = 1
        PKT_CREATESEND = 2
        PKT_DROP = 3
        PKT_RCVDESTROY = 4
        PKT_CREATE = 5
        PKT_SEND = 6
        PKT_TRIM = 7
        PKT_BOUNCE = 8
    
    @abstractmethod
    def logTraffic(self, pkt, location: Logged, ev: 'TrafficEvent') -> None:
        """对应 C++ 虚函数 logTraffic()"""
        pass


class FlowEventLogger(Logger, ABC):
    """流程事件日志记录器 - 对应 loggertypes.h 中的 FlowEventLogger"""
    
    class FlowEvent(IntEnum):
        """对应 FlowEventLogger::FlowEvent 枚举"""
        START = 0
        FINISH = 1
    
    @abstractmethod
    def logEvent(self, flow, location: Logged, ev: 'FlowEvent', bytes_val: int, pkts: int) -> None:
        """对应 C++ 虚函数 logEvent()"""
        pass


# ========================= Implementations from loggers.h =========================

class FlowEventLoggerSimple(FlowEventLogger):
    """简单流程事件日志记录器 - 对应 loggers.h 中的 FlowEventLoggerSimple"""
    
    def logEvent(self, flow, location: Logged, ev: FlowEventLogger.FlowEvent, bytes_val: int, pkts: int) -> None:
        """对应 C++ 中的 FlowEventLoggerSimple::logEvent()"""
        if self._logfile:
            self._logfile.writeRecord(Logger.EventType.FLOW_EVENT,
                                    location.get_id(),
                                    ev,
                                    flow.get_id() if hasattr(flow, 'get_id') else 0,
                                    bytes_val, pkts)
    
    @staticmethod
    def event_to_str(event) -> str:
        """对应 C++ 中的 static string event_to_str(RawLogEvent& event)"""
        return f"FlowEvent: {event}"


class TrafficLoggerSimple(TrafficLogger):
    """简单流量日志记录器 - 对应 loggers.h 中的 TrafficLoggerSimple"""
    
    def logTraffic(self, pkt, location: Logged, ev: TrafficLogger.TrafficEvent) -> None:
        """对应 C++ 中的 TrafficLoggerSimple::logTraffic()"""
        if self._logfile:
            flow_id = pkt.flow().get_id() if hasattr(pkt, 'flow') and hasattr(pkt.flow(), 'get_id') else 0
            pkt_id = pkt.id() if hasattr(pkt, 'id') else 0
            self._logfile.writeRecord(Logger.EventType.TRAFFIC_EVENT,
                                    location.get_id(),
                                    ev,
                                    flow_id,
                                    pkt_id,
                                    0)
    
    @staticmethod
    def event_to_str(event) -> str:
        """对应 C++ 中的 static string event_to_str(RawLogEvent& event)"""
        return f"TrafficEvent: {event}"


class TcpTrafficLogger(TrafficLogger):
    """TCP流量日志记录器 - 对应 loggers.h 中的 TcpTrafficLogger"""
    
    def logTraffic(self, pkt, location: Logged, ev: TrafficLogger.TrafficEvent) -> None:
        """对应 C++ 中的 TcpTrafficLogger::logTraffic()"""
        if self._logfile:
            flow_id = pkt.flow().get_id() if hasattr(pkt, 'flow') and hasattr(pkt.flow(), 'get_id') else 0
            pkt_id = pkt.id() if hasattr(pkt, 'id') else 0
            self._logfile.writeRecord(Logger.EventType.TCP_TRAFFIC,
                                    location.get_id(),
                                    ev,
                                    flow_id,
                                    pkt_id,
                                    0)
    
    @staticmethod
    def event_to_str(event) -> str:
        """对应 C++ 中的 static string event_to_str(RawLogEvent& event)"""
        return f"TcpTrafficEvent: {event}"


class SwiftTrafficLogger(TrafficLogger):
    """Swift流量日志记录器 - 对应 loggers.h 中的 SwiftTrafficLogger"""
    
    def logTraffic(self, pkt, location: Logged, ev: TrafficLogger.TrafficEvent) -> None:
        """对应 C++ 中的 SwiftTrafficLogger::logTraffic()"""
        if self._logfile:
            flow_id = pkt.flow().get_id() if hasattr(pkt, 'flow') and hasattr(pkt.flow(), 'get_id') else 0
            pkt_id = pkt.id() if hasattr(pkt, 'id') else 0
            self._logfile.writeRecord(Logger.EventType.SWIFT_TRAFFIC,
                                    location.get_id(),
                                    ev,
                                    flow_id,
                                    pkt_id,
                                    0)
    
    @staticmethod
    def event_to_str(event) -> str:
        """对应 C++ 中的 static string event_to_str(RawLogEvent& event)"""
        return f"SwiftTrafficEvent: {event}"


class STrackTrafficLogger(TrafficLogger):
    """STrack流量日志记录器 - 对应 loggers.h 中的 STrackTrafficLogger"""
    
    def logTraffic(self, pkt, location: Logged, ev: TrafficLogger.TrafficEvent) -> None:
        """对应 C++ 中的 STrackTrafficLogger::logTraffic()"""
        if self._logfile:
            flow_id = pkt.flow().get_id() if hasattr(pkt, 'flow') and hasattr(pkt.flow(), 'get_id') else 0
            pkt_id = pkt.id() if hasattr(pkt, 'id') else 0
            self._logfile.writeRecord(Logger.EventType.STRACK_TRAFFIC,
                                    location.get_id(),
                                    ev,
                                    flow_id,
                                    pkt_id,
                                    0)
    
    @staticmethod
    def event_to_str(event) -> str:
        """对应 C++ 中的 static string event_to_str(RawLogEvent& event)"""
        return f"STrackTrafficEvent: {event}"


class NdpTrafficLogger(TrafficLogger):
    """NDP流量日志记录器 - 对应 loggers.h 中的 NdpTrafficLogger"""
    
    def logTraffic(self, pkt, location: Logged, ev: TrafficLogger.TrafficEvent) -> None:
        """对应 C++ 中的 NdpTrafficLogger::logTraffic()"""
        if self._logfile:
            flow_id = pkt.flow().get_id() if hasattr(pkt, 'flow') and hasattr(pkt.flow(), 'get_id') else 0
            pkt_id = pkt.id() if hasattr(pkt, 'id') else 0
            
            # 对应C++中的特殊处理逻辑
            val3 = 0
            if hasattr(pkt, 'type'):
                if pkt.type() == 'NDPACK':
                    val3 |= NDP_IS_ACK
                elif pkt.type() == 'NDPNACK':
                    val3 |= NDP_IS_NACK
                elif pkt.type() == 'NDPPULL':
                    val3 |= NDP_IS_PULL
                elif pkt.type() == 'NDP':
                    if hasattr(pkt, 'last_packet') and pkt.last_packet():
                        val3 |= NDP_IS_LASTDATA
                    if hasattr(pkt, 'header_only') and pkt.header_only():
                        val3 |= NDP_IS_HEADER
            
            self._logfile.writeRecord(Logger.EventType.NDP_TRAFFIC,
                                    location.get_id(),
                                    ev,
                                    flow_id,
                                    pkt_id,
                                    val3)
    
    @staticmethod
    def event_to_str(event) -> str:
        """对应 C++ 中的 static string event_to_str(RawLogEvent& event)"""
        return f"NdpTrafficEvent: {event}"


class RoceTrafficLogger(TrafficLogger):
    """RoCE流量日志记录器 - 对应 loggers.h 中的 RoceTrafficLogger"""
    
    def logTraffic(self, pkt, location: Logged, ev: TrafficLogger.TrafficEvent) -> None:
        """对应 C++ 中的 RoceTrafficLogger::logTraffic()"""
        if self._logfile:
            flow_id = pkt.flow().get_id() if hasattr(pkt, 'flow') and hasattr(pkt.flow(), 'get_id') else 0
            pkt_id = pkt.id() if hasattr(pkt, 'id') else 0
            
            # 对应C++中的特殊处理逻辑
            val3 = 0
            if hasattr(pkt, 'type'):
                if pkt.type() == 'ROCEACK':
                    val3 |= ROCE_IS_ACK
                elif pkt.type() == 'ROCENACK':
                    val3 |= ROCE_IS_NACK
                elif pkt.type() == 'ROCE' and hasattr(pkt, 'last_packet') and pkt.last_packet():
                    val3 |= ROCE_IS_LASTDATA
                
                if hasattr(pkt, 'header_only') and pkt.header_only():
                    val3 |= ROCE_IS_HEADER
            
            self._logfile.writeRecord(Logger.EventType.ROCE_TRAFFIC,
                                    location.get_id(),
                                    ev,
                                    flow_id,
                                    pkt_id,
                                    val3)
    
    @staticmethod
    def event_to_str(event) -> str:
        """对应 C++ 中的 static string event_to_str(RawLogEvent& event)"""
        return f"RoceTrafficEvent: {event}"


class HPCCTrafficLogger(TrafficLogger):
    """HPCC流量日志记录器 - 对应 loggers.h 中的 HPCCTrafficLogger"""
    
    def logTraffic(self, pkt, location: Logged, ev: TrafficLogger.TrafficEvent) -> None:
        """对应 C++ 中的 HPCCTrafficLogger::logTraffic()"""
        if self._logfile:
            flow_id = pkt.flow().get_id() if hasattr(pkt, 'flow') and hasattr(pkt.flow(), 'get_id') else 0
            pkt_id = pkt.id() if hasattr(pkt, 'id') else 0
            
            # 对应C++中的特殊处理逻辑
            val3 = 0
            if hasattr(pkt, 'type'):
                if pkt.type() == 'HPCCACK':
                    val3 |= HPCC_IS_ACK
                elif pkt.type() == 'HPCCNACK':
                    val3 |= HPCC_IS_NACK
                elif pkt.type() == 'HPCC' and hasattr(pkt, 'last_packet') and pkt.last_packet():
                    val3 |= HPCC_IS_LASTDATA
                
                if hasattr(pkt, 'header_only') and pkt.header_only():
                    val3 |= HPCC_IS_HEADER
            
            self._logfile.writeRecord(Logger.EventType.HPCC_TRAFFIC,
                                    location.get_id(),
                                    ev,
                                    flow_id,
                                    pkt_id,
                                    val3)
    
    @staticmethod
    def event_to_str(event) -> str:
        """对应 C++ 中的 static string event_to_str(RawLogEvent& event)"""
        return f"HPCCTrafficEvent: {event}"