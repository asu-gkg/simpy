# API definitions - corresponds to AstraComputeAPI.hh, AstraMemoryAPI.hh, AstraNetworkAPI.hh in SimAI 

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


class BackendType(Enum):
    """后端类型枚举，对应C++中的BackendType"""
    NOT_SPECIFIED = 0
    GARNET = 1
    NS3 = 2
    ANALYTICAL = 3


@dataclass
class TimeSpec:
    """时间规格结构体，对应C++中的timespec_t"""
    time_res: TimeType = TimeType.NS
    time_val: float = 0.0


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
    req_type: ReqType = ReqType.FP32
    req_count: int = 0
    vnet: int = 0
    layer_num: int = 0
    flow_tag: NcclFlowTag = None
    
    def __post_init__(self):
        if self.flow_tag is None:
            self.flow_tag = NcclFlowTag()


@dataclass
class SimComm:
    """模拟通信结构体，对应C++中的sim_comm"""
    comm_name: str = ""


class AstraMemoryAPI(ABC):
    """内存API抽象基类，对应C++中的AstraMemoryAPI"""
    
    @abstractmethod
    def mem_read(self, size: int) -> int:
        """内存读取"""
        pass
    
    @abstractmethod
    def mem_write(self, size: int) -> int:
        """内存写入"""
        pass
    
    @abstractmethod
    def npu_mem_read(self, size: int) -> int:
        """NPU内存读取"""
        pass
    
    @abstractmethod
    def npu_mem_write(self, size: int) -> int:
        """NPU内存写入"""
        pass
    
    @abstractmethod
    def nic_mem_read(self, size: int) -> int:
        """NIC内存读取"""
        pass
    
    @abstractmethod
    def nic_mem_write(self, size: int) -> int:
        """NIC内存写入"""
        pass


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
        """获取通信大小"""
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
        """完成模拟"""
        pass
    
    @abstractmethod
    def sim_time_resolution(self) -> float:
        """获取时间分辨率"""
        pass
    
    @abstractmethod
    def sim_init(self, mem: AstraMemoryAPI) -> int:
        """初始化模拟"""
        pass
    
    @abstractmethod
    def sim_get_time(self) -> TimeSpec:
        """获取当前时间"""
        pass
    
    @abstractmethod
    def sim_schedule(self, delta: TimeSpec, 
                    fun_ptr: Callable[[Any], None], 
                    fun_arg: Any) -> None:
        """调度任务"""
        pass
    
    @abstractmethod
    def sim_send(self, buffer: Any, count: int, type_: int, 
                dst: int, tag: int, request: SimRequest,
                msg_handler: Callable[[Any], None], 
                fun_arg: Any) -> int:
        """发送数据"""
        pass
    
    @abstractmethod
    def sim_recv(self, buffer: Any, count: int, type_: int,
                src: int, tag: int, request: SimRequest,
                msg_handler: Callable[[Any], None],
                fun_arg: Any) -> int:
        """接收数据"""
        pass
    
    def pass_front_end_report(self, astra_sim_data_api: Any) -> None:
        """传递前端报告"""
        pass
    
    def get_bw_at_dimension(self, dim: int) -> float:
        """获取指定维度的带宽"""
        return -1.0