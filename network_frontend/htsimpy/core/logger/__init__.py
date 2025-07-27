"""
Logger Package - 日志系统

对应文件: loggers.h/cpp, loggertypes.h
功能: 提供完整的日志记录和统计系统

主要模块:
- core: 核心类（LoggedManager, Logged）
- base: 基础Logger类和事件类型
- traffic: 流量相关日志记录器
- tcp: TCP相关日志记录器  
- queue: 队列相关日志记录器
- protocols: 其他协议日志记录器
- constants: 协议常量定义
"""

# 核心类
from .core import LoggedManager, Logged

# 基础类
from .base import Logger

# 流量相关
from .traffic import (
    TrafficLogger, FlowEventLogger,
    TrafficLoggerSimple, FlowEventLoggerSimple,
    TcpTrafficLogger, SwiftTrafficLogger, 
    STrackTrafficLogger, NdpTrafficLogger,
    RoceTrafficLogger, HPCCTrafficLogger
)

# TCP相关
from .tcp import (
    TcpLogger, TcpLoggerSimple,
    MultipathTcpLogger, MultipathTcpLoggerSimple
)

# 队列相关
from .queue import (
    QueueLogger, QueueLoggerSimple, 
    QueueLoggerEmpty, QueueLoggerSampling,
    MultiQueueLoggerSampling, QueueLoggerFactory
)

# 协议相关
from .protocols import (
    SwiftLogger, STrackLogger, NdpLogger, 
    RoceLogger, HPCCLogger, QcnLogger,
    EnergyLogger, ReorderBufferLogger,
    SwiftLoggerSimple, STrackLoggerSimple, QcnLoggerSimple
)

# Sink相关
from .sink import (
    SinkLoggerSampling, TcpSinkLoggerSampling,
    SwiftSinkLoggerSampling, STrackSinkLoggerSampling,
    NdpSinkLoggerSampling, RoceSinkLoggerSampling,
    HPCCSinkLoggerSampling
)

# 内存相关
from .memory import MemoryLoggerSampling

# 聚合相关
from .aggregate import AggregateTcpLogger

# 重排序相关
from .reorder import ReorderBufferLoggerSampling

# 常量
from .constants import (
    NDP_IS_ACK, NDP_IS_NACK, NDP_IS_PULL, 
    NDP_IS_HEADER, NDP_IS_LASTDATA,
    ROCE_IS_ACK, ROCE_IS_NACK,
    ROCE_IS_HEADER, ROCE_IS_LASTDATA,
    HPCC_IS_ACK, HPCC_IS_NACK,
    HPCC_IS_HEADER, HPCC_IS_LASTDATA
)

# 向后兼容接口
from .compat import (
    LogLevel, ModernLogged, SimpleLogger,
    get_global_logger, set_global_logger
)

# 导出的主要类和接口
__all__ = [
    # 核心类
    'LoggedManager', 'Logged', 'Logger',
    
    # 流量相关
    'TrafficLogger', 'FlowEventLogger',
    'TrafficLoggerSimple', 'FlowEventLoggerSimple', 
    'TcpTrafficLogger', 'SwiftTrafficLogger',
    'STrackTrafficLogger', 'NdpTrafficLogger',
    'RoceTrafficLogger', 'HPCCTrafficLogger',
    
    # TCP相关
    'TcpLogger', 'TcpLoggerSimple',
    'MultipathTcpLogger', 'MultipathTcpLoggerSimple',
    
    # 队列相关
    'QueueLogger', 'QueueLoggerSimple',
    'QueueLoggerEmpty', 'QueueLoggerSampling',
    'MultiQueueLoggerSampling', 'QueueLoggerFactory',
    
    # 协议相关
    'SwiftLogger', 'STrackLogger', 'NdpLogger',
    'RoceLogger', 'HPCCLogger', 'QcnLogger',
    'EnergyLogger', 'ReorderBufferLogger',
    'SwiftLoggerSimple', 'STrackLoggerSimple', 'QcnLoggerSimple',
    
    # Sink相关
    'SinkLoggerSampling', 'TcpSinkLoggerSampling',
    'SwiftSinkLoggerSampling', 'STrackSinkLoggerSampling',
    'NdpSinkLoggerSampling', 'RoceSinkLoggerSampling',
    'HPCCSinkLoggerSampling',
    
    # 其他高级Logger
    'MemoryLoggerSampling', 'AggregateTcpLogger', 'ReorderBufferLoggerSampling',
    
    # 常量
    'NDP_IS_ACK', 'NDP_IS_NACK', 'NDP_IS_PULL',
    'NDP_IS_HEADER', 'NDP_IS_LASTDATA',
    'ROCE_IS_ACK', 'ROCE_IS_NACK', 
    'ROCE_IS_HEADER', 'ROCE_IS_LASTDATA',
    'HPCC_IS_ACK', 'HPCC_IS_NACK',
    'HPCC_IS_HEADER', 'HPCC_IS_LASTDATA',
    
    # 向后兼容接口
    'LogLevel', 'ModernLogged', 'SimpleLogger',
    'get_global_logger', 'set_global_logger'
]