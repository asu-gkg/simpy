"""
Mock NCCL日志模块 - 对应C++版本的MockNcclLog.h和MockNcclLog.cc
提供单例模式的日志记录功能，支持详细的调试信息
"""

import os
import threading
import time
import inspect
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
    实现单例模式的日志记录功能，支持详细的调试信息
    """
    
    # 静态变量 - 对应C++版本的静态成员
    _instance: Optional['MockNcclLog'] = None
    _lock = threading.Lock()
    _log_level: NcclLogLevel = NcclLogLevel.INFO
    _log_name: str = ""
    _show_detailed_info: bool = True  # 新增：控制是否显示详细调试信息
    
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
        
        # 从环境变量控制是否显示详细信息
        MockNcclLog._show_detailed_info = os.getenv("AS_LOG_DETAILED", "1").lower() in ("1", "true", "yes")
        
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
    
    @classmethod
    def set_detailed_info(cls, enabled: bool) -> None:
        """
        设置是否显示详细调试信息
        """
        cls._show_detailed_info = enabled
    
    def _get_current_time(self) -> str:
        """
        获取当前时间字符串 - 对应C++版本的getCurrentTime()方法
        """
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]  # 包含毫秒
    
    def _get_caller_info(self) -> str:
        """
        获取调用者信息 - 包含文件名、行号、函数名
        """
        try:
            # 获取调用栈，跳过当前函数和writeLog函数
            frame = inspect.currentframe()
            caller_frame = frame.f_back.f_back  # 跳过两层：_get_caller_info -> writeLog -> 实际调用者
            
            if caller_frame:
                filename = os.path.basename(caller_frame.f_code.co_filename)
                line_number = caller_frame.f_lineno
                function_name = caller_frame.f_code.co_name
                
                # 获取类名（如果存在）
                class_name = ""
                if 'self' in caller_frame.f_locals:
                    class_name = f"{caller_frame.f_locals['self'].__class__.__name__}."
                elif 'cls' in caller_frame.f_locals:
                    class_name = f"{caller_frame.f_locals['cls'].__name__}."
                
                return f"{filename}:{line_number} {class_name}{function_name}()"
            else:
                return "unknown:0 unknown()"
        except Exception:
            return "error:0 error()"
        finally:
            del frame  # 避免循环引用
    
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
            
            # 获取调用者信息
            caller_info = ""
            if self._show_detailed_info:
                caller_info = f"[{self._get_caller_info()}] "
            
            # 写入日志
            with self._lock:
                log_entry = f"[{self._get_current_time()}][{level_str}][{thread_id:08x}] {caller_info}{message}\n"
                self.logfile.write(log_entry)
                self.logfile.flush()  # 确保立即写入
                print(f"📝 {log_entry.strip()}")
        # 修复：当日志级别不满足时，应该静默跳过，而不是退出程序
            
    def __del__(self):
        """析构函数 - 关闭日志文件"""
        if hasattr(self, 'logfile') and self.logfile:
            self.logfile.close() 