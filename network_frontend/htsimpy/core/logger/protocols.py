"""
Protocol Logger Classes - 协议日志类

对应文件: loggertypes.h (各种协议Logger) 和 loggers.h (实现类)
功能: 专门用于记录各种网络协议相关的事件和状态

主要类:
- SwiftLogger: Swift协议日志记录器
- STrackLogger: STrack协议日志记录器  
- NdpLogger: NDP协议日志记录器
- RoceLogger: RoCE协议日志记录器
- HPCCLogger: HPCC协议日志记录器
- QcnLogger: QCN协议日志记录器
- EnergyLogger: 能耗日志记录器
- ReorderBufferLogger: 重排序缓冲日志记录器
"""

from abc import ABC, abstractmethod
from enum import IntEnum
from typing import TYPE_CHECKING

from .base import Logger
from .traffic import TrafficLogger

if TYPE_CHECKING:
    pass


# ========================= Swift Logger =========================

class SwiftLogger(Logger, ABC):
    """Swift日志记录器 - 对应 loggertypes.h 中的 SwiftLogger"""
    
    class SwiftEvent(IntEnum):
        """对应 SwiftLogger::SwiftEvent 枚举"""
        SWIFT_RCV = 0
        SWIFT_RCV_FR_END = 1
        SWIFT_RCV_FR = 2
        SWIFT_RCV_DUP_FR = 3
        SWIFT_RCV_DUP = 4
        SWIFT_RCV_3DUPNOFR = 5
        SWIFT_RCV_DUP_FASTXMIT = 6
        SWIFT_TIMEOUT = 7
    
    class SwiftState(IntEnum):
        """对应 SwiftLogger::SwiftState 枚举"""
        SWIFTSTATE_CNTRL = 0
        SWIFTSTATE_SEQ = 1
    
    class SwiftRecord(IntEnum):
        """对应 SwiftLogger::SwiftRecord 枚举"""
        AVE_CWND = 0
    
    class SwiftSinkRecord(IntEnum):
        """对应 SwiftLogger::SwiftSinkRecord 枚举"""
        RATE = 0
    
    class SwiftMemoryRecord(IntEnum):
        """对应 SwiftLogger::SwiftMemoryRecord 枚举"""
        MEMORY = 0
    
    @abstractmethod
    def logSwift(self, src, ev: 'SwiftEvent') -> None:
        """对应 C++ 虚函数 logSwift()"""
        pass


# ========================= STrack Logger =========================

class STrackLogger(Logger, ABC):
    """STrack日志记录器 - 对应 loggertypes.h 中的 STrackLogger"""
    
    class STrackEvent(IntEnum):
        """对应 STrackLogger::STrackEvent 枚举"""
        STRACK_RCV = 0
        STRACK_RCV_FR_END = 1
        STRACK_RCV_FR = 2
        STRACK_RCV_DUP_FR = 3
        STRACK_RCV_DUP = 4
        STRACK_RCV_3DUPNOFR = 5
        STRACK_RCV_DUP_FASTXMIT = 6
        STRACK_TIMEOUT = 7
    
    class STrackState(IntEnum):
        """对应 STrackLogger::STrackState 枚举"""
        STRACKSTATE_CNTRL = 0
        STRACKSTATE_SEQ = 1
    
    class STrackRecord(IntEnum):
        """对应 STrackLogger::STrackRecord 枚举"""
        AVE_CWND = 0
    
    class STrackSinkRecord(IntEnum):
        """对应 STrackLogger::STrackSinkRecord 枚举"""
        RATE = 0
    
    class STrackMemoryRecord(IntEnum):
        """对应 STrackLogger::STrackMemoryRecord 枚举"""
        MEMORY = 0
    
    @abstractmethod
    def logSTrack(self, src, ev: 'STrackEvent') -> None:
        """对应 C++ 虚函数 logSTrack()"""
        pass


# ========================= NDP Logger =========================

class NdpLogger(Logger, ABC):
    """NDP日志记录器 - 对应 loggertypes.h 中的 NdpLogger"""
    
    class NdpEvent(IntEnum):
        """对应 NdpLogger::NdpEvent 枚举"""
        NDP_RCV = 0
        NDP_RCV_FR_END = 1
        NDP_RCV_FR = 2
        NDP_RCV_DUP_FR = 3
        NDP_RCV_DUP = 4
        NDP_RCV_3DUPNOFR = 5
        NDP_RCV_DUP_FASTXMIT = 6
        NDP_TIMEOUT = 7
    
    class NdpState(IntEnum):
        """对应 NdpLogger::NdpState 枚举"""
        NDPSTATE_CNTRL = 0
        NDPSTATE_SEQ = 1
    
    class NdpRecord(IntEnum):
        """对应 NdpLogger::NdpRecord 枚举"""
        AVE_CWND = 0
    
    class NdpSinkRecord(IntEnum):
        """对应 NdpLogger::NdpSinkRecord 枚举"""
        RATE = 0
    
    class NdpMemoryRecord(IntEnum):
        """对应 NdpLogger::NdpMemoryRecord 枚举"""
        MEMORY = 0
    
    @abstractmethod
    def logNdp(self, src, ev: 'NdpEvent') -> None:
        """对应 C++ 虚函数 logNdp()"""
        pass


# ========================= RoCE Logger =========================

class RoceLogger(Logger, ABC):
    """RoCE日志记录器 - 对应 loggertypes.h 中的 RoceLogger"""
    
    class RoceEvent(IntEnum):
        """对应 RoceLogger::RoceEvent 枚举"""
        ROCE_RCV = 0
        ROCE_TIMEOUT = 1
    
    class RoceState(IntEnum):
        """对应 RoceLogger::RoceState 枚举"""
        ROCESTATE_ON = 0
        ROCESTATE_OFF = 0  # 注意C++中两个值都是0
    
    class RoceRecord(IntEnum):
        """对应 RoceLogger::RoceRecord 枚举"""
        AVE_RATE = 0
    
    class RoceSinkRecord(IntEnum):
        """对应 RoceLogger::RoceSinkRecord 枚举"""
        RATE = 0
    
    class RoceMemoryRecord(IntEnum):
        """对应 RoceLogger::RoceMemoryRecord 枚举"""
        MEMORY = 0
    
    @abstractmethod
    def logRoce(self, src, ev: 'RoceEvent') -> None:
        """对应 C++ 虚函数 logRoce()"""
        pass


# ========================= HPCC Logger =========================

class HPCCLogger(Logger, ABC):
    """HPCC日志记录器 - 对应 loggertypes.h 中的 HPCCLogger"""
    
    class HPCCEvent(IntEnum):
        """对应 HPCCLogger::HPCCEvent 枚举"""
        HPCC_RCV = 0
        HPCC_TIMEOUT = 1
    
    class HPCCState(IntEnum):
        """对应 HPCCLogger::HPCCState 枚举"""
        HPCCSTATE_ON = 1
        HPCCSTATE_OFF = 0
    
    class HPCCRecord(IntEnum):
        """对应 HPCCLogger::HPCCRecord 枚举"""
        AVE_RATE = 0
    
    class HPCCSinkRecord(IntEnum):
        """对应 HPCCLogger::HPCCSinkRecord 枚举"""
        RATE = 0
    
    class HPCCMemoryRecord(IntEnum):
        """对应 HPCCLogger::HPCCMemoryRecord 枚举"""
        MEMORY = 0
    
    @abstractmethod
    def logHPCC(self, src, ev: 'HPCCEvent') -> None:
        """对应 C++ 虚函数 logHPCC()"""
        pass


# ========================= QCN Logger =========================

class QcnLogger(Logger, ABC):
    """QCN日志记录器 - 对应 loggertypes.h 中的 QcnLogger"""
    
    class QcnEvent(IntEnum):
        """对应 QcnLogger::QcnEvent 枚举"""
        QCN_SEND = 0
        QCN_INC = 1
        QCN_DEC = 2
        QCN_INCD = 3
        QCN_DECD = 4
    
    class QcnQueueEvent(IntEnum):
        """对应 QcnLogger::QcnQueueEvent 枚举"""
        QCN_FB = 0
        QCN_NOFB = 1
    
    @abstractmethod
    def logQcn(self, src, ev: 'QcnEvent', var3: float) -> None:
        """对应 C++ 虚函数 logQcn()"""
        pass
    
    @abstractmethod
    def logQcnQueue(self, src, ev: 'QcnQueueEvent', var1: float, var2: float, var3: float) -> None:
        """对应 C++ 虚函数 logQcnQueue()"""
        pass


# ========================= Energy Logger =========================

class EnergyLogger(Logger, ABC):
    """能耗日志记录器 - 对应 loggertypes.h 中的 EnergyLogger"""
    
    class EnergyEvent(IntEnum):
        """对应 EnergyLogger::EnergyEvent 枚举"""
        DRAW = 0


# ========================= Reorder Buffer Logger =========================

class ReorderBufferLogger(Logger, ABC):
    """重排序缓冲日志记录器 - 对应 loggertypes.h 中的 ReorderBufferLogger"""
    
    class BufferEvent(IntEnum):
        """对应 ReorderBufferLogger::BufferEvent 枚举"""
        BUF_ENQUEUE = 0
        BUF_DEQUEUE = 1
    
    @abstractmethod
    def logBuffer(self, ev: 'BufferEvent') -> None:
        """对应 C++ 虚函数 logBuffer()"""
        pass


# ========================= NDP Tunnel and Lite Loggers =========================

class NdpTunnelLogger(Logger, ABC):
    """NDP隧道日志记录器 - 对应 loggertypes.h 中的 NdpTunnelLogger"""
    
    class NdpEvent(IntEnum):
        """对应 NdpTunnelLogger::NdpEvent 枚举"""
        NDP_RCV = 0
        NDP_RCV_FR_END = 1
        NDP_RCV_FR = 2
        NDP_RCV_DUP_FR = 3
        NDP_RCV_DUP = 4
        NDP_RCV_3DUPNOFR = 5
        NDP_RCV_DUP_FASTXMIT = 6
        NDP_TIMEOUT = 7
    
    class NdpState(IntEnum):
        """对应 NdpTunnelLogger::NdpState 枚举"""
        NDPSTATE_CNTRL = 0
        NDPSTATE_SEQ = 1
    
    class NdpRecord(IntEnum):
        """对应 NdpTunnelLogger::NdpRecord 枚举"""
        AVE_CWND = 0
    
    class NdpSinkRecord(IntEnum):
        """对应 NdpTunnelLogger::NdpSinkRecord 枚举"""
        RATE = 0
    
    class NdpMemoryRecord(IntEnum):
        """对应 NdpTunnelLogger::NdpMemoryRecord 枚举"""
        MEMORY = 0
    
    @abstractmethod
    def logNdp(self, src, ev: 'NdpEvent') -> None:
        """对应 C++ 虚函数 logNdp()"""
        pass


class NdpLiteLogger(Logger, ABC):
    """NDP Lite日志记录器 - 对应 loggertypes.h 中的 NdpLiteLogger"""
    
    class NdpLiteEvent(IntEnum):
        """对应 NdpLiteLogger::NdpLiteEvent 枚举"""
        NDP_RCV = 0
        NDP_RCV_FR_END = 1
        NDP_RCV_FR = 2
        NDP_RCV_DUP_FR = 3
        NDP_RCV_DUP = 4
        NDP_RCV_3DUPNOFR = 5
        NDP_RCV_DUP_FASTXMIT = 6
        NDP_TIMEOUT = 7
    
    class NdpLiteState(IntEnum):
        """对应 NdpLiteLogger::NdpLiteState 枚举"""
        NDPSTATE_CNTRL = 0
        NDPSTATE_SEQ = 1
    
    class NdpLiteRecord(IntEnum):
        """对应 NdpLiteLogger::NdpLiteRecord 枚举"""
        AVE_CWND = 0
    
    class NdpLiteSinkRecord(IntEnum):
        """对应 NdpLiteLogger::NdpLiteSinkRecord 枚举"""
        RATE = 0
    
    class NdpLiteMemoryRecord(IntEnum):
        """对应 NdpLiteLogger::NdpLiteMemoryRecord 枚举"""
        MEMORY = 0
    
    @abstractmethod
    def logNdpLite(self, src, ev: 'NdpLiteEvent') -> None:
        """对应 C++ 虚函数 logNdpLite()"""
        pass


# ========================= Protocol-specific Traffic Loggers =========================

class SwiftTrafficLogger(TrafficLogger):
    """Swift流量日志记录器 - 对应 loggers.h 中的 SwiftTrafficLogger"""
    
    def logTraffic(self, pkt, location, ev: TrafficLogger.TrafficEvent) -> None:
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
    
    def logTraffic(self, pkt, location, ev: TrafficLogger.TrafficEvent) -> None:
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


# ========================= Simple Logger Implementations =========================

class SwiftLoggerSimple(SwiftLogger):
    """简单Swift日志记录器 - 对应 loggers.h 中的 SwiftLoggerSimple"""
    
    def logSwift(self, swift, ev: SwiftLogger.SwiftEvent) -> None:
        """对应 C++ 中的 SwiftLoggerSimple::logSwift()"""
        if self._logfile:
            # 对应C++实现中的三个writeRecord调用
            swift_cwnd = getattr(swift, '_swift_cwnd', 0)
            inflate = getattr(swift, '_inflate', 0)
            
            # SWIFT_EVENT record
            self._logfile.writeRecord(Logger.EventType.SWIFT_EVENT, swift.get_id(),
                                    ev, swift_cwnd, inflate, 0)
            
            # SWIFT_STATE SWIFTSTATE_CNTRL record
            recoverq = getattr(swift, '_recoverq', 0)
            self._logfile.writeRecord(Logger.EventType.SWIFT_STATE, swift.get_id(),
                                    SwiftLogger.SwiftState.SWIFTSTATE_CNTRL,
                                    swift_cwnd, 0, recoverq)
            
            # SWIFT_STATE SWIFTSTATE_SEQ record
            last_acked = getattr(swift, '_last_acked', 0)
            highest_sent = getattr(swift, '_highest_sent', 0)
            rto_timeout = getattr(swift, '_RFC2988_RTO_timeout', 0)
            self._logfile.writeRecord(Logger.EventType.SWIFT_STATE, swift.get_id(),
                                    SwiftLogger.SwiftState.SWIFTSTATE_SEQ,
                                    last_acked, highest_sent, rto_timeout)
    
    @staticmethod
    def event_to_str(event) -> str:
        """对应 C++ 中的 static string event_to_str(RawLogEvent& event)"""
        return f"SwiftEvent: {event}"


class STrackLoggerSimple(STrackLogger):
    """简单STrack日志记录器 - 对应 loggers.h 中的 STrackLoggerSimple"""
    
    def logSTrack(self, strack, ev: STrackLogger.STrackEvent) -> None:
        """对应 C++ 中的 STrackLoggerSimple::logSTrack()"""
        if self._logfile:
            # 对应C++实现中的三个writeRecord调用
            strack_cwnd = getattr(strack, '_strack_cwnd', 0)
            inflate = getattr(strack, '_inflate', 0)
            
            # STRACK_EVENT record
            self._logfile.writeRecord(Logger.EventType.STRACK_EVENT, strack.get_id(),
                                    ev, strack_cwnd, inflate, 0)
            
            # STRACK_STATE STRACKSTATE_CNTRL record
            recoverq = getattr(strack, '_recoverq', 0)
            self._logfile.writeRecord(Logger.EventType.STRACK_STATE, strack.get_id(),
                                    STrackLogger.STrackState.STRACKSTATE_CNTRL,
                                    strack_cwnd, 0, recoverq)
            
            # STRACK_STATE STRACKSTATE_SEQ record
            last_acked = getattr(strack, '_last_acked', 0)
            highest_sent = getattr(strack, '_highest_sent', 0)
            rto_timeout = getattr(strack, '_RFC2988_RTO_timeout', 0)
            self._logfile.writeRecord(Logger.EventType.STRACK_STATE, strack.get_id(),
                                    STrackLogger.STrackState.STRACKSTATE_SEQ,
                                    last_acked, highest_sent, rto_timeout)
    
    @staticmethod
    def event_to_str(event) -> str:
        """对应 C++ 中的 static string event_to_str(RawLogEvent& event)"""
        return f"STrackEvent: {event}"


class QcnLoggerSimple(QcnLogger):
    """简单QCN日志记录器 - 对应 loggers.h 中的 QcnLoggerSimple"""
    
    def logQcn(self, src, ev: QcnLogger.QcnEvent, var3: float) -> None:
        """对应 C++ 中的 QcnLoggerSimple::logQcn()"""
        if self._logfile and ev != QcnLogger.QcnEvent.QCN_SEND:
            current_rate = getattr(src, '_currentRate', 0)
            packet_cycles = getattr(src, '_packetCycles', 0)
            self._logfile.writeRecord(Logger.EventType.QCN_EVENT, src.get_id(),
                                    ev, current_rate, packet_cycles, var3)
    
    def logQcnQueue(self, src, ev: QcnLogger.QcnQueueEvent, var1: float, var2: float, var3: float) -> None:
        """对应 C++ 中的 QcnLoggerSimple::logQcnQueue()"""
        if self._logfile:
            self._logfile.writeRecord(Logger.EventType.QCNQUEUE_EVENT, src.get_id(),
                                    ev, var1, var2, var3)
    
    @staticmethod
    def event_to_str(event) -> str:
        """对应 C++ 中的 static string event_to_str(RawLogEvent& event)"""
        return f"QcnEvent: {event}"