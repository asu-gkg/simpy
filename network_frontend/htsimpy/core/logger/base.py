"""
Base Logger Class - 基础日志类

对应文件: loggertypes.h (Logger基类和事件类型)
功能: 定义所有日志事件类型，提供统一的日志记录接口

主要类:
- Logger: 日志记录器基类
- Logger.EventType: 日志事件类型枚举
"""

from abc import ABC, abstractmethod
from enum import IntEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


class Logger:
    """
    日志记录器基类 - 对应 loggertypes.h 中的 Logger 类
    
    定义了所有日志事件类型，提供统一的日志记录接口
    """
    
    class EventType(IntEnum):
        """对应 Logger::EventType 枚举 - 精准复现C++版本"""
        QUEUE_EVENT = 0
        TCP_EVENT = 1
        TCP_STATE = 2
        TRAFFIC_EVENT = 3
        QUEUE_RECORD = 4
        QUEUE_APPROX = 5
        TCP_RECORD = 6
        QCN_EVENT = 7
        QCNQUEUE_EVENT = 8
        TCP_TRAFFIC = 9
        NDP_TRAFFIC = 10
        TCP_SINK = 11
        MTCP = 12
        ENERGY = 13
        TCP_MEMORY = 14
        NDP_EVENT = 15
        NDP_STATE = 16
        NDP_RECORD = 17
        NDP_SINK = 18
        NDP_MEMORY = 19
        SWIFT_EVENT = 20
        SWIFT_STATE = 21
        SWIFT_TRAFFIC = 22
        SWIFT_SINK = 23
        SWIFT_MEMORY = 24
        ROCE_TRAFFIC = 25
        ROCE_SINK = 26
        HPCC_TRAFFIC = 27
        HPCC_SINK = 28
        STRACK_EVENT = 29
        STRACK_STATE = 30
        STRACK_TRAFFIC = 31
        STRACK_SINK = 32
        STRACK_MEMORY = 33
        EQDS_EVENT = 38
        EQDS_STATE = 39
        EQDS_RECORD = 40
        EQDS_SINK = 41
        EQDS_MEMORY = 42
        EQDS_TRAFFIC = 43
        FLOW_EVENT = 44
    
    def __init__(self):
        """对应 C++ 构造函数 Logger()"""
        self._logfile = None
    
    def __del__(self):
        """对应 C++ 虚析构函数"""
        pass
    
    def setLogfile(self, logfile) -> None:
        """对应 C++ 中的 setLogfile() - friend class Logfile访问"""
        self._logfile = logfile
    
    @staticmethod
    def event_to_str(event) -> str:
        """对应 C++ 中的 static string event_to_str(RawLogEvent& event)"""
        return event.str()