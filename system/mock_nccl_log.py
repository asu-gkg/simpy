"""
Mock NCCL日志模块 - 对应C++版本的MockNcclLog.h和MockNcclLog.cc
提供单例模式的日志记录功能
"""

import os
import threading
import time
from datetime import datetime
from enum import Enum
from typing import Optional


class NcclLogLevel(Enum):
    """NCCL日志级别 - 对应C++版本的NcclLogLevel枚举"""
    DEBUG = 0
    INFO = 1
    WARNING = 2
    ERROR = 3


class MockNcclLog:
    """
    Mock NCCL日志类 - 对应C++版本的MockNcclLog类
    实现单例模式的日志记录功能
    """
    
    # 静态变量 - 对应C++版本的静态成员
    _instance: Optional['MockNcclLog'] = None
    _lock = threading.Lock()
    _log_level: NcclLogLevel = NcclLogLevel.INFO
    _log_name: str = ""
    
    LOG_PATH = "./logs/"  # 使用当前目录下的logs文件夹
    
    def __init__(self):
        """私有构造函数 - 实现单例模式"""
        # 从环境变量获取日志级别
        log_level_env = os.getenv("AS_LOG_LEVEL")
        if log_level_env:
            try:
                MockNcclLog._log_level = NcclLogLevel(int(log_level_env))
            except ValueError:
                MockNcclLog._log_level = NcclLogLevel.INFO
        else:
            MockNcclLog._log_level = NcclLogLevel.INFO
        
        # 打开日志文件
        if MockNcclLog._log_name:
            log_file_path = os.path.join(MockNcclLog.LOG_PATH, MockNcclLog._log_name)
            # 确保目录存在
            os.makedirs(os.path.dirname(log_file_path), exist_ok=True)
            self.logfile = open(log_file_path, 'a', encoding='utf-8')
            print(f"📝 日志文件已打开: {log_file_path}")
        else:
            self.logfile = None
            print("⚠️ 未设置日志文件名，日志将不会写入文件")
    
    @classmethod
    def getInstance(cls) -> 'MockNcclLog':
        """
        获取单例实例 - 对应C++版本的getInstance()方法
        """
        with cls._lock:
            if cls._instance is None:
                cls._instance = MockNcclLog()
            return cls._instance
    
    @classmethod
    def set_log_name(cls, log_name: str) -> None:
        """
        设置日志文件名 - 对应C++版本的set_log_name()方法
        """
        cls._log_name = log_name
    
    def _get_current_time(self) -> str:
        """
        获取当前时间字符串 - 对应C++版本的getCurrentTime()方法
        """
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    def writeLog(self, level: NcclLogLevel, format_str: str, *args) -> None:
        """
        写入日志 - 对应C++版本的writeLog()方法
        
        Args:
            level: 日志级别
            format_str: 格式字符串
            *args: 格式化参数
        """
        if level.value >= self._log_level.value and self.logfile:
            # 获取日志级别字符串
            level_str = level.name
            
            # 格式化消息
            try:
                message = format_str % args if args else format_str
            except (TypeError, ValueError):
                message = format_str
            
            # 获取线程ID
            thread_id = threading.get_ident()
            
            # 写入日志
            with self._lock:
                log_entry = f"[{self._get_current_time()}][{level_str}] [{thread_id:016x}]{message}\n"
                self.logfile.write(log_entry)
                self.logfile.flush()  # 确保立即写入
                print(f"📝 写入日志: {log_entry.strip()}")
        else:
            print(f"⚠️ 日志未写入: level={level.value}, log_level={self._log_level.value}, has_file={self.logfile is not None}")
            exit(1)
            
    def __del__(self):
        """析构函数 - 关闭日志文件"""
        if hasattr(self, 'logfile') and self.logfile:
            self.logfile.close() 