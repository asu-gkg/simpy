"""
TCP Logger Classes - TCP日志类

对应文件: loggertypes.h (TcpLogger) 和 loggers.h (实现类)
功能: 专门用于记录TCP协议相关的事件和状态

主要类:
- TcpLogger: TCP日志记录器基类
- TcpLoggerSimple: 简单TCP日志记录器实现
- MultipathTcpLogger: 多路径TCP日志记录器
- MultipathTcpLoggerSimple: 简单多路径TCP日志记录器实现
"""

from abc import ABC, abstractmethod
from enum import IntEnum
from typing import TYPE_CHECKING

from .base import Logger

if TYPE_CHECKING:
    pass


class TcpLogger(Logger, ABC):
    """TCP日志记录器 - 对应 loggertypes.h 中的 TcpLogger"""
    
    class TcpEvent(IntEnum):
        """对应 TcpLogger::TcpEvent 枚举"""
        TCP_RCV = 0
        TCP_RCV_FR_END = 1
        TCP_RCV_FR = 2
        TCP_RCV_DUP_FR = 3
        TCP_RCV_DUP = 4
        TCP_RCV_3DUPNOFR = 5
        TCP_RCV_DUP_FASTXMIT = 6
        TCP_TIMEOUT = 7
    
    class TcpState(IntEnum):
        """对应 TcpLogger::TcpState 枚举"""
        TCPSTATE_CNTRL = 0
        TCPSTATE_SEQ = 1
    
    class TcpRecord(IntEnum):
        """对应 TcpLogger::TcpRecord 枚举"""
        AVE_CWND = 0
    
    class TcpSinkRecord(IntEnum):
        """对应 TcpLogger::TcpSinkRecord 枚举"""
        RATE = 0
    
    class TcpMemoryRecord(IntEnum):
        """对应 TcpLogger::TcpMemoryRecord 枚举"""
        MEMORY = 0
    
    @abstractmethod
    def logTcp(self, src, ev: 'TcpEvent') -> None:
        """对应 C++ 虚函数 logTcp()"""
        pass


class MultipathTcpLogger(Logger, ABC):
    """多路径TCP日志记录器 - 对应 loggertypes.h 中的 MultipathTcpLogger"""
    
    class MultipathTcpEvent(IntEnum):
        """对应 MultipathTcpLogger::MultipathTcpEvent 枚举"""
        CHANGE_A = 0
        RTT_UPDATE = 1
        WINDOW_UPDATE = 2
        RATE = 3
        MEMORY = 4
    
    @abstractmethod
    def logMultipathTcp(self, src, ev: 'MultipathTcpEvent') -> None:
        """对应 C++ 虚函数 logMultipathTcp()"""
        pass


# ========================= Implementations from loggers.h =========================

class TcpLoggerSimple(TcpLogger):
    """简单TCP日志记录器 - 对应 loggers.h 中的 TcpLoggerSimple"""
    
    def logTcp(self, tcp, ev: TcpLogger.TcpEvent) -> None:
        """对应 C++ 中的 TcpLoggerSimple::logTcp()"""
        if self._logfile:
            # 对应C++实现中的三个writeRecord调用
            cwnd = getattr(tcp, '_cwnd', 0)
            unacked = getattr(tcp, '_unacked', 0)
            ssthresh = getattr(tcp, '_ssthresh', 0)
            in_fast_recovery = getattr(tcp, '_in_fast_recovery', False)
            
            # TCP_EVENT record
            self._logfile.writeRecord(Logger.EventType.TCP_EVENT, tcp.get_id(),
                                    ev, cwnd, unacked,
                                    ssthresh if in_fast_recovery else cwnd)
            
            # TCP_STATE TCPSTATE_CNTRL record
            recoverq = getattr(tcp, '_recoverq', 0)
            self._logfile.writeRecord(Logger.EventType.TCP_STATE, tcp.get_id(),
                                    TcpLogger.TcpState.TCPSTATE_CNTRL,
                                    cwnd, ssthresh, recoverq)
            
            # TCP_STATE TCPSTATE_SEQ record
            last_acked = getattr(tcp, '_last_acked', 0)
            highest_sent = getattr(tcp, '_highest_sent', 0)
            rto_timeout = getattr(tcp, '_RFC2988_RTO_timeout', 0)
            self._logfile.writeRecord(Logger.EventType.TCP_STATE, tcp.get_id(),
                                    TcpLogger.TcpState.TCPSTATE_SEQ,
                                    last_acked, highest_sent, rto_timeout)
    
    @staticmethod
    def event_to_str(event) -> str:
        """对应 C++ 中的 static string event_to_str(RawLogEvent& event)"""
        return f"TcpEvent: {event}"


class MultipathTcpLoggerSimple(MultipathTcpLogger):
    """简单多路径TCP日志记录器 - 对应 loggers.h 中的 MultipathTcpLoggerSimple"""
    
    def logMultipathTcp(self, mtcp, ev: MultipathTcpLogger.MultipathTcpEvent) -> None:
        """对应 C++ 中的 MultipathTcpLoggerSimple::logMultipathTcp()"""
        if self._logfile:
            if ev == MultipathTcpLogger.MultipathTcpEvent.CHANGE_A:
                a = getattr(mtcp, 'a', 0)
                alfa = getattr(mtcp, '_alfa', 0)
                self._logfile.writeRecord(Logger.EventType.MTCP, mtcp.get_id(),
                                        ev, a, alfa, 0)
            elif ev == MultipathTcpLogger.MultipathTcpEvent.RTT_UPDATE:
                subflows = getattr(mtcp, '_subflows', [])
                if len(subflows) >= 2:
                    rtt1 = getattr(subflows[0], '_rtt', 0) / 1000000000
                    rtt2 = getattr(subflows[-1], '_rtt', 0) / 1000000000
                    mdev = getattr(subflows[0], '_mdev', 0) / 1000000000
                    self._logfile.writeRecord(Logger.EventType.MTCP, mtcp.get_id(),
                                            ev, rtt1, rtt2, mdev)
            elif ev == MultipathTcpLogger.MultipathTcpEvent.WINDOW_UPDATE:
                subflows = getattr(mtcp, '_subflows', [])
                if len(subflows) >= 2:
                    win1 = subflows[0].effective_window() if hasattr(subflows[0], 'effective_window') else 0
                    win2 = subflows[-1].effective_window() if hasattr(subflows[-1], 'effective_window') else 0
                    self._logfile.writeRecord(Logger.EventType.MTCP, mtcp.get_id(),
                                            ev, win1, win2, 0)
    
    @staticmethod
    def event_to_str(event) -> str:
        """对应 C++ 中的 static string event_to_str(RawLogEvent& event)"""
        return f"MultipathTcpEvent: {event}"