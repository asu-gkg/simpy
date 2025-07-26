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
    flow_size: int = -1
    p_qps: Optional[Any] = None
    tag_id: int = -1
    tree_flow_list: List[int] = None
    nvls_on: bool = False
    
    def __post_init__(self):
        if self.tree_flow_list is None:
            self.tree_flow_list = []


@dataclass
class SimRequest:
    """模拟请求结构体，对应C++中的sim_request"""
    src_rank: int = 0
    dst_rank: int = 0
    tag: int = 0
    req_type: ReqType = ReqType.UINT8
    req_count: int = 0
    vnet: int = 0
    layer_num: int = 0
    flow_tag: NcclFlowTag = None
    
    def __post_init__(self):
        if self.flow_tag is None:
            self.flow_tag = NcclFlowTag()


@dataclass
class MetaData:
    """元数据结构体，对应C++中的MetaData"""
    timestamp: TimeSpec = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = TimeSpec()


class BackendType(Enum):
    """后端类型枚举，对应C++中的BackendType"""
    NOT_SPECIFIED = 0
    GARNET = 1
    NS3 = 2
    ANALYTICAL = 3


class AstraNetworkAPI(ABC):
    """网络API抽象基类，对应C++中的AstraNetworkAPI"""
    
    def __init__(self, rank: int):
        self.rank = rank
        self.enabled = True
    
    def get_backend_type(self) -> BackendType:
        """获取后端类型"""
        return BackendType.NOT_SPECIFIED
    
    @abstractmethod
    def sim_comm_size(self, comm: SimComm, size: List[int]) -> int:
        """
        获取通信大小
        
        Args:
            comm: 通信对象
            size: 输出参数，存储通信大小
            
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
            时间分辨率值
        """
        pass
    
    @abstractmethod
    def sim_init(self, mem: Any) -> int:
        """
        初始化模拟
        
        Args:
            mem: 内存API对象
            
        Returns:
            0表示成功
        """
        pass
    
    @abstractmethod
    def sim_get_time(self) -> TimeSpec:
        """
        获取当前模拟时间
        
        Returns:
            当前时间规格对象
        """
        pass
    
    @abstractmethod
    def sim_schedule(self, delta: TimeSpec, 
                    fun_ptr: Callable[[Any], None], 
                    fun_arg: Any) -> None:
        """
        调度任务
        
        Args:
            delta: 延迟时间
            fun_ptr: 要执行的函数指针
            fun_arg: 函数参数
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
            buffer: 发送缓冲区
            count: 数据数量
            type_: 数据类型
            dst: 目标rank
            tag: 消息标签
            request: 请求对象
            msg_handler: 消息处理函数
            fun_arg: 函数参数
            
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
            buffer: 接收缓冲区
            count: 数据数量
            type_: 数据类型
            src: 源rank
            tag: 消息标签
            request: 请求对象
            msg_handler: 消息处理函数
            fun_arg: 函数参数
            
        Returns:
            0表示成功
        """
        pass
    
    def pass_front_end_report(self, astra_sim_data_api: Any) -> None:
        """
        传递前端报告
        
        Args:
            astra_sim_data_api: 前端数据API对象
        """
        return
    
    def get_bw_at_dimension(self, dim: int) -> float:
        """
        获取指定维度的带宽
        
        Args:
            dim: 维度索引
            
        Returns:
            带宽值，-1.0表示无效
        """
        return -1.0