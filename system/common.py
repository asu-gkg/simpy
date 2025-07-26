# Common definitions and utilities - corresponds to Common.hh in SimAI 

class ModeType:
    """模式类型枚举"""
    ANALYTICAL = "ANALYTICAL"
    
# Common definitions - corresponds to Common.hh in SimAI

from enum import Enum
from typing import List, Dict, Any

# Constants
CLOCK_PERIOD = 1
FREQ = 1000.0 / CLOCK_PERIOD
GBps = 1.0 / (1024 * 1024 * 1024)

# Type alias
Tick = int

class GPUType(Enum):
    A100 = "A100"
    A800 = "A800"
    H100 = "H100"
    H800 = "H800"
    NONE = "NONE"
    H20 = "H20"

class ComType(Enum):
    None_ = "None"
    Reduce_Scatter = "Reduce_Scatter"
    All_Gather = "All_Gather"
    All_Reduce = "All_Reduce"
    All_to_All = "All_to_All"
    All_Reduce_All_to_All = "All_Reduce_All_to_All"
    All_Reduce_NVLS = "All_Reduce_NVLS"

class MockNcclGroupType(Enum):
    """MockNccl::GroupType枚举 - 对应C++版本的MockNccl::GroupType"""
    TP = "TP"
    DP = "DP"
    EP = "EP"
    DP_EP = "DP_EP"

class CollectiveOptimization(Enum):
    Baseline = "Baseline"
    LocalBWAware = "LocalBWAware"

class CollectiveImplementationType(Enum):
    Ring = "Ring"
    OneRing = "OneRing"
    Direct = "Direct"
    OneDirect = "OneDirect"
    AllToAll = "AllToAll"
    DoubleBinaryTreeLocalAllToAll = "DoubleBinaryTreeLocalAllToAll"
    LocalRingNodeA2AGlobalDBT = "LocalRingNodeA2AGlobalDBT"
    HierarchicalRing = "HierarchicalRing"
    DoubleBinaryTree = "DoubleBinaryTree"
    HalvingDoubling = "HalvingDoubling"
    OneHalvingDoubling = "OneHalvingDoubling"
    NcclFlowModel = "NcclFlowModel"
    NcclTreeFlowModel = "NcclTreeFlowModel"

class CollectiveBarrier(Enum):
    Blocking = "Blocking"
    Non_Blocking = "Non_Blocking"

class SchedulingPolicy(Enum):
    LIFO = "LIFO"
    FIFO = "FIFO"
    HIGHEST = "HIGHEST"
    None_ = "None"

class IntraDimensionScheduling(Enum):
    FIFO = "FIFO"
    RG = "RG"
    SmallestFirst = "SmallestFirst"
    LessRemainingPhaseFirst = "LessRemainingPhaseFirst"

class InterDimensionScheduling(Enum):
    Ascending = "Ascending"
    OnlineGreedy = "OnlineGreedy"
    RoundRobin = "RoundRobin"
    OfflineGreedy = "OfflineGreedy"
    OfflineGreedyFlex = "OfflineGreedyFlex"

class InjectionPolicy(Enum):
    Infinite = "Infinite"
    Aggressive = "Aggressive"
    SemiAggressive = "SemiAggressive"
    ExtraAggressive = "ExtraAggressive"
    Normal = "Normal"

class PacketRouting(Enum):
    Hardware = "Hardware"
    Software = "Software"

class BusType(Enum):
    Both = "Both"
    Shared = "Shared"
    Mem = "Mem"

class StreamState(Enum):
    Created = "Created"
    Transferring = "Transferring"
    Ready = "Ready"
    Executing = "Executing"
    Zombie = "Zombie"
    Dead = "Dead"

class EventType(Enum):
    NONE = "NONE"
    RendezvousSend = "RendezvousSend"
    RendezvousRecv = "RendezvousRecv"
    CallEvents = "CallEvents"
    PacketReceived = "PacketReceived"
    PacketSent = "PacketSent"
    PacketSentFinshed = "PacketSentFinshed"
    WaitForVnetTurn = "WaitForVnetTurn"
    NCCL_General = "NCCL_General"
    General = "General"
    TX_DMA = "TX_DMA"
    RX_DMA = "RX_DMA"
    Wight_Grad_Comm_Finished = "Wight_Grad_Comm_Finished"
    Input_Grad_Comm_Finished = "Input_Grad_Comm_Finished"
    Fwd_Comm_Finished = "Fwd_Comm_Finished"
    Wight_Grad_Comm_Finished_After_Delay = "Wight_Grad_Comm_Finished_After_Delay"
    Input_Grad_Comm_Finished_After_Delay = "Input_Grad_Comm_Finished_After_Delay"
    Fwd_Comm_Finished_After_Delay = "Fwd_Comm_Finished_After_Delay"
    Workload_Wait = "Workload_Wait"
    Reduction_Ready = "Reduction_Ready"
    Rec_Finished = "Rec_Finished"
    Send_Finished = "Send_Finished"
    Processing_Finished = "Processing_Finished"
    Delivered = "Delivered"
    NPU_to_MA = "NPU_to_MA"
    MA_to_NPU = "MA_to_NPU"
    Read_Port_Free = "Read_Port_Free"
    Write_Port_Free = "Write_Port_Free"
    Apply_Boost = "Apply_Boost"
    Stream_Transfer_Started = "Stream_Transfer_Started"
    Stream_Ready = "Stream_Ready"
    Consider_Process = "Consider_Process"
    Consider_Retire = "Consider_Retire"
    Consider_Send_Back = "Consider_Send_Back"
    StreamInit = "StreamInit"
    StreamsFinishedIncrease = "StreamsFinishedIncrease"
    CommProcessingFinished = "CommProcessingFinished"
    NotInitialized = "NotInitialized"

class ParallelStrategy(Enum):
    TP = "TP"
    DP = "DP"
    PP = "PP"
    EP = "EP"
    DP_EP = "DP_EP"
    NONE = "NONE"

# Simulation request types - corresponds to AstraNetworkAPI.hh
class ReqType(Enum):
    """Request type enumeration - corresponds to req_type_e in C++"""
    UINT8 = "UINT8"
    BFLOAT16 = "BFLOAT16"
    FP32 = "FP32"

class NcclFlowTag:
    """NCCL flow tag - corresponds to ncclFlowTag struct in C++"""
    
    def __init__(self, channel_id: int = -1, chunk_id: int = -1, 
                 current_flow_id: int = -1, child_flow_id: int = -1,
                 sender_node: int = -1, receiver_node: int = -1,
                 flow_size: int = -1, pQps: Any = None, 
                 tag_id: int = -1, nvls_on: bool = False):
        self.channel_id = channel_id
        self.chunk_id = chunk_id
        self.current_flow_id = current_flow_id
        self.child_flow_id = child_flow_id
        self.sender_node = sender_node
        self.receiver_node = receiver_node
        self.flow_size = flow_size
        self.pQps = pQps
        self.tag_id = tag_id
        self.tree_flow_list: List[int] = []
        self.nvls_on = nvls_on

class SimRequest:
    """Simulation request - corresponds to sim_request struct in C++"""
    
    def __init__(self, src_rank: int = 0, dst_rank: int = 0, tag: int = 0,
                 req_type: ReqType = ReqType.FP32, req_count: int = 0,
                 vnet: int = 0, layer_num: int = 0, 
                 flow_tag: NcclFlowTag = None):
        self.srcRank = src_rank
        self.dstRank = dst_rank
        self.tag = tag
        self.reqType = req_type
        self.reqCount = req_count
        self.vnet = vnet
        self.layerNum = layer_num
        self.flowTag = flow_tag if flow_tag is not None else NcclFlowTag()

# 辅助函数
def comtype_to_coll(comtype: ComType) -> str:
    """将ComType转换为字符串表示"""
    if comtype == ComType.All_Reduce:
        return "allreduce"
    elif comtype == ComType.All_Gather:
        return "allgather"
    elif comtype == ComType.Reduce_Scatter:
        return "reducescatter"
    elif comtype == ComType.All_to_All:
        return "alltoall"
    else:
        return "unknown"