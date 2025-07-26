# IntData class - corresponds to IntData.hh in SimAI

from typing import List, Dict, Any, Optional
from .common import Tick, ComType, EventType
from .callable import Callable, CallData


class IntData(CallData):
    """整数数据类 - 对应C++版本的IntData.hh"""
    
    def __init__(self, data: int):
        """
        初始化整数数据
        
        Args:
            data: 整数值
        """
        super().__init__()
        self.data = data 