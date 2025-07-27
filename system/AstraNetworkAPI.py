# AstraNetworkAPI.py - corresponds to AstraNetworkAPI.hh in SimAI 

from abc import ABC, abstractmethod
from enum import Enum
from typing import Optional, Callable, Any, List
from dataclasses import dataclass


class TimeType(Enum):
    """时间类型枚举，对应C++中的time_type_e"""
    SE = 0  # 秒
    MS = 1  # 毫秒
    US = 2  # 微秒
    NS = 3  # 纳秒
    FS = 4  # 飞秒


class ReqType(Enum):
    """请求类型枚举，对应C++中的req_type_e"""
    UINT8 = 0
    BFLOAT16 = 1
    FP32 = 2


@dataclass
class TimeSpec:
    """时间规格结构体，对应C++中的timespec_t"""
    time_res: TimeType = TimeType.NS
    time_val: float = 0.0


@dataclass
class SimComm:
    """模拟通信结构体，对应C++中的sim_comm"""
    comm_name: str = ""


@dataclass
class NcclFlowTag:
    """NCCL流标签结构体，对应C++中的ncclFlowTag"""
    channel_id: int = -1
    chunk_id: int = -1
    current_flow_id: int = -1
    child_flow_id: int = -1
    sender_node: int = -1
    receiver_node: int = -1
    flow_size: int = -1  # uint64_t in C++
    pQps: Optional[Any] = None  # void* in C++
    tag_id: int = -1
    tree_flow_list: List[int] = None
    nvls_on: bool = False
    
    def __post_init__(self):
        if self.tree_flow_list is None:
            self.tree_flow_list = []


@dataclass
class SimRequest:
    """模拟请求结构体，对应C++中的sim_request"""
    srcRank: int = 0  # uint32_t in C++
    dstRank: int = 0  # uint32_t in C++
    tag: int = 0      # uint32_t in C++
    reqType: ReqType = ReqType.UINT8
    reqCount: int = 0  # uint64_t in C++
    vnet: int = 0      # uint32_t in C++
    layerNum: int = 0  # uint32_t in C++
    flowTag: NcclFlowTag = None
    
    def __post_init__(self):
        if self.flowTag is None:
            self.flowTag = NcclFlowTag()


@dataclass
class MetaData:
    """元数据结构体，对应C++中的MetaData"""
    timestamp: TimeSpec = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = TimeSpec()


class BackendType(Enum):
    """后端类型枚举，对应C++中的BackendType"""
    NotSpecified = 0
    Garnet = 1
    NS3 = 2
    Analytical = 3
    HTSimPy = 4


class AstraNetworkAPI(ABC):
    """网络API抽象基类，对应C++中的AstraNetworkAPI"""
    
    def __init__(self, rank: int):
        self.rank = rank
        self.enabled = True
    
    def get_backend_type(self) -> BackendType:
        """获取后端类型"""
        return BackendType.NotSpecified
    
    @abstractmethod
    def sim_comm_size(self, comm: SimComm, size: List[int]) -> int:
        """
        获取通信大小
        
        Args:
            comm: 通信对象
            size: 输出参数，存储通信大小 (对应C++中的int* size)
            
        Returns:
            0表示成功
        """
        pass
    
    def sim_comm_get_rank(self) -> int:
        """获取当前rank"""
        return self.rank
    
    def sim_comm_set_rank(self, rank: int) -> int:
        """设置rank"""
        self.rank = rank
        return self.rank
    
    @abstractmethod
    def sim_finish(self) -> int:
        """
        完成模拟
        
        Returns:
            0表示成功
        """
        pass
    
    @abstractmethod
    def sim_time_resolution(self) -> float:
        """
        获取时间分辨率
        
        Returns:
            时间分辨率值 (对应C++中的double)
        """
        pass
    
    @abstractmethod
    def sim_init(self, MEM: Any) -> int:
        """
        初始化模拟
        
        Args:
            MEM: 内存API对象 (对应C++中的AstraMemoryAPI*)
            
        Returns:
            0表示成功
        """
        pass
    
    @abstractmethod
    def sim_get_time(self) -> TimeSpec:
        """
        获取当前模拟时间
        
        Returns:
            当前时间规格对象 (对应C++中的timespec_t)
        """
        pass
    
    @abstractmethod
    def sim_schedule(self, delta: TimeSpec, 
                    fun_ptr: Callable[[Any], None], 
                    fun_arg: Any) -> None:
        """
        调度任务
        
        Args:
            delta: 延迟时间 (对应C++中的timespec_t)
            fun_ptr: 要执行的函数指针 (对应C++中的void (*fun_ptr)(void* fun_arg))
            fun_arg: 函数参数 (对应C++中的void*)
        """
        pass
    
    @abstractmethod
    def sim_send(self, buffer: Any, count: int, type_: int, 
                dst: int, tag: int, request: SimRequest,
                msg_handler: Callable[[Any], None], 
                fun_arg: Any) -> int:
        """
        发送数据
        
        Args:
            buffer: 发送缓冲区 (对应C++中的void*)
            count: 数据数量 (对应C++中的uint64_t)
            type_: 数据类型 (对应C++中的int)
            dst: 目标rank (对应C++中的int)
            tag: 消息标签 (对应C++中的int)
            request: 请求对象 (对应C++中的sim_request*)
            msg_handler: 消息处理函数 (对应C++中的void (*msg_handler)(void* fun_arg))
            fun_arg: 函数参数 (对应C++中的void*)
            
        Returns:
            0表示成功
        """
        pass
    
    @abstractmethod
    def sim_recv(self, buffer: Any, count: int, type_: int,
                src: int, tag: int, request: SimRequest,
                msg_handler: Callable[[Any], None],
                fun_arg: Any) -> int:
        """
        接收数据
        
        Args:
            buffer: 接收缓冲区 (对应C++中的void*)
            count: 数据数量 (对应C++中的uint64_t)
            type_: 数据类型 (对应C++中的int)
            src: 源rank (对应C++中的int)
            tag: 消息标签 (对应C++中的int)
            request: 请求对象 (对应C++中的sim_request*)
            msg_handler: 消息处理函数 (对应C++中的void (*msg_handler)(void* fun_arg))
            fun_arg: 函数参数 (对应C++中的void*)
            
        Returns:
            0表示成功
        """
        pass
    
    def pass_front_end_report(self, astraSimDataAPI: Any) -> None:
        """
        传递前端报告
        
        Args:
            astraSimDataAPI: 前端数据API对象 (对应C++中的AstraSimDataAPI)
        """
        return
    
    def get_BW_at_dimension(self, dim: int) -> float:
        """
        获取指定维度的带宽
        
        Args:
            dim: 维度索引 (对应C++中的int)
            
        Returns:
            带宽值，-1.0表示无效 (对应C++中的double)
        """
        return -1.0