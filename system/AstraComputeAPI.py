 # AstraComputeAPI.py - corresponds to AstraComputeAPI.hh in SimAI 

from abc import ABC, abstractmethod
from enum import Enum
from typing import Optional, Callable, Any, List
from dataclasses import dataclass


class ReqType(Enum):
    """请求类型枚举，对应C++中的req_type_e"""
    UINT8 = 0
    BFLOAT16 = 1
    FP32 = 2


@dataclass
class SimRequest:
    """模拟请求结构体，对应C++中的sim_request"""
    src_rank: int = 0
    dst_rank: int = 0
    tag: int = 0
    req_type: ReqType = ReqType.FP32
    req_count: int = 0
    vnet: int = 0
    layer_num: int = 0
    flow_tag: Any = None  # 这里引用NcclFlowTag，但避免循环导入
    
    def __post_init__(self):
        if self.flow_tag is None:
            # 延迟导入避免循环依赖
            from .AstraNetworkAPI import NcclFlowTag
            self.flow_tag = NcclFlowTag()


class AstraComputeAPI(ABC):
    """计算API抽象基类，对应C++中的AstraComputeAPI"""
    
    @abstractmethod
    def compute(self, operation: str, size: int, data_type: ReqType) -> int:
        """
        执行计算操作
        
        Args:
            operation: 计算操作类型（如 "add", "multiply", "reduce" 等）
            size: 数据大小
            data_type: 数据类型
            
        Returns:
            计算延迟时间
        """
        pass
    
    @abstractmethod
    def get_compute_capability(self) -> dict:
        """
        获取计算能力信息
        
        Returns:
            包含计算能力信息的字典
        """
        pass
    
    @abstractmethod
    def set_compute_capability(self, capability: dict) -> None:
        """
        设置计算能力
        
        Args:
            capability: 计算能力配置字典
        """
        pass
    
    @abstractmethod
    def get_utilization(self) -> float:
        """
        获取当前计算利用率
        
        Returns:
            利用率百分比 (0.0 - 1.0)
        """
        pass
    
    @abstractmethod
    def schedule_compute(self, operation: str, size: int, 
                        data_type: ReqType, callback: Callable[[Any], None], 
                        callback_arg: Any) -> None:
        """
        调度计算任务
        
        Args:
            operation: 计算操作类型
            size: 数据大小
            data_type: 数据类型
            callback: 完成后的回调函数
            callback_arg: 回调函数参数
        """
        pass