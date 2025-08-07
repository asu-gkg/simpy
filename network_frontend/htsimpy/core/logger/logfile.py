"""
Logfile - 日志文件管理器

对应文件: logfile.h/cpp
功能: 管理仿真的日志输出

主要类:
- Logfile: 日志文件管理器
"""

from typing import List, Optional, TextIO
from .base import Logger
from .core import Logged
from ..eventlist import EventList, SimTime
import os


class Logfile:
    """
    日志文件管理器 - 对应 logfile.h/cpp 中的 Logfile 类
    
    管理所有日志器的输出
    """
    
    def __init__(self, filename: str, eventlist: EventList):
        """
        对应 C++ 构造函数:
        Logfile(string filename, simtime_picosec starttime, EventList& eventlist)
        """
        self._filename = filename
        self._eventlist = eventlist
        self._starttime: SimTime = 0
        self._loggers: List[Logger] = []
        self._file: Optional[TextIO] = None
        
        # 确保目录存在
        dirname = os.path.dirname(filename)
        if dirname and not os.path.exists(dirname):
            os.makedirs(dirname, exist_ok=True)
        
        # 打开文件
        try:
            self._file = open(filename, 'w')
        except IOError as e:
            print(f"Warning: Cannot open logfile {filename}: {e}")
    
    def __del__(self):
        """析构函数 - 关闭文件"""
        if self._file:
            self._file.close()
    
    def setStartTime(self, starttime: SimTime) -> None:
        """
        对应 C++ 的 setStartTime()
        设置开始记录日志的时间
        """
        self._starttime = starttime
    
    def addLogger(self, logger: Logger) -> None:
        """
        对应 C++ 的 addLogger()
        添加一个日志器
        """
        self._loggers.append(logger)
        # 设置日志器的logfile引用
        if hasattr(logger, 'setLogfile'):
            logger.setLogfile(self)
    
    def write(self, msg: str) -> None:
        """
        对应 C++ 的 write()
        写入日志消息
        """
        if self._file:
            self._file.write(msg + '\n')
            self._file.flush()
    
    def writeName(self, item: Logged) -> None:
        """
        对应 C++ 的 writeName()
        写入对象的名称
        """
        if hasattr(item, 'str'):
            self.write(item.str())
        elif hasattr(item, 'nodename'):
            self.write(f"# {item.nodename()}")
        else:
            self.write(f"# {item._name if hasattr(item, '_name') else str(item)}")
    
    def writeRecord(self, type_val: int, id_val: int, ev: int, 
                    val1: float, val2: float, val3: float) -> None:
        """
        对应 C++ 的 writeRecord()
        写入日志记录，自动添加时间戳
        """
        
        if self._file and self._eventlist:
            # 获取当前时间
            current_time = self._eventlist.now() if hasattr(self._eventlist, 'now') else 0
            # 写入记录：时间 类型 ID 事件 值1 值2 值3
            self._file.write(f"{current_time} {type_val} {id_val} {ev} {val1} {val2} {val3}\n")
            self._file.flush()
    
    def getEventList(self) -> EventList:
        """获取事件列表"""
        return self._eventlist
    
    def close(self) -> None:
        """关闭日志文件"""
        if self._file:
            self._file.close()
            self._file = None