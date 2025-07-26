# AstraComputeAPI.py - corresponds to AstraComputeAPI.hh in SimAI

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Callable, Any


@dataclass
class ComputeMetaData:
    """计算元数据，对应C++中的ComputeMetaData"""
    compute_delay: int = 0


class ComputeAPI(ABC):
    """计算API抽象基类，对应C++中的ComputeAPI"""
    
    @abstractmethod
    def compute(self, M: int, K: int, N: int, 
                msg_handler: Callable[[Any], None], 
                fun_arg: ComputeMetaData) -> None:
        """
        执行计算操作
        
        Args:
            M: 矩阵维度M
            K: 矩阵维度K  
            N: 矩阵维度N
            msg_handler: 消息处理函数
            fun_arg: 函数参数（ComputeMetaData类型）
        """
        pass
    
    def __del__(self):
        """析构函数"""
        pass