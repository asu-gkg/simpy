"""
Logger Compatibility Interface - 日志兼容性接口

功能: 提供向后兼容的接口，保持与旧代码的兼容性

主要类:
- LogLevel: 日志级别枚举
- ModernLogged: 现代化日志接口
- SimpleLogger: 简单日志记录器
- 全局logger实例管理
"""

from abc import ABC
from enum import Enum
from typing import Optional
import time


class LogLevel(Enum):
    """日志级别 - 保留用于向后兼容"""
    DEBUG = 0
    INFO = 1
    WARNING = 2
    ERROR = 3
    CRITICAL = 4


class ModernLogged(ABC):
    """
    现代化日志接口 - 保留用于向后兼容
    """
    
    def __init__(self, name: str):
        self._name = name
        self._logger = None
    
    @property
    def name(self) -> str:
        """获取组件名称"""
        return self._name
    
    def set_logger(self, logger) -> None:
        """设置日志记录器"""
        self._logger = logger
    
    def log(self, level: LogLevel, message: str, **kwargs) -> None:
        """记录日志"""
        if self._logger:
            self._logger.log(level, self._name, message, **kwargs)


class SimpleLogger:
    """
    简单日志记录器 - 提供基本的日志记录功能
    """
    
    def __init__(self, level: LogLevel = LogLevel.INFO, output_file: Optional[str] = None):
        self._level = level
        self._output_file = output_file
    
    def log(self, level: LogLevel, component: str, message: str, **kwargs) -> None:
        """记录日志"""
        if level.value < self._level.value:
            return
        
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        level_str = level.name
        log_entry = f"[{timestamp}] {level_str} [{component}] {message}"
        
        if kwargs:
            log_entry += f" {kwargs}"
        
        print(log_entry)
        
        if self._output_file:
            with open(self._output_file, 'a') as f:
                f.write(log_entry + '\n')


# ========================= Global Logger Instance =========================

# 全局日志记录器实例 - 保留用于向后兼容
_global_logger: Optional[SimpleLogger] = None


def get_global_logger() -> SimpleLogger:
    """获取全局日志记录器"""
    global _global_logger
    if _global_logger is None:
        _global_logger = SimpleLogger()
    return _global_logger


def set_global_logger(logger: SimpleLogger) -> None:
    """设置全局日志记录器"""
    global _global_logger
    _global_logger = logger