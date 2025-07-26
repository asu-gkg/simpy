# Base stream class - corresponds to BaseStream.hh/cc in SimAI

from typing import List, Optional, TYPE_CHECKING
from abc import ABC, abstractmethod
from .callable import Callable, CallData
from .stream_stat import StreamStat
from .common import EventType, Tick, SchedulingPolicy, ComType, StreamState

if TYPE_CHECKING:
    from .collective_phase import CollectivePhase
    from .dataset import DataSet
    from .sys import Sys


class RecvPacketEventHandlerData:
    """对应C++中的RecvPacketEventHandlerData类"""
    def __init__(self, owner: 'BaseStream', node_id: int, event: EventType, vnet: int, stream_num: int):
        self.owner = owner
        self.node_id = node_id
        self.event = event
        self.vnet = vnet
        self.stream_num = stream_num
        self.message_end = False
        self.ready_time: Tick = 0
        self.flow_id = 0
        self.channel_id = 0
        self.child_flow_id = 0


class SendPacketEventHandlerData:
    """对应C++中的SendPacketEventHandlerData类"""
    def __init__(self, owner: 'BaseStream', sender_node_id: int, receiver_node_id: int, tag: int, event: EventType):
        self.owner = owner
        self.sender_node_id = sender_node_id
        self.receiver_node_id = receiver_node_id
        self.tag = tag
        self.event = event
        self.child_flow_id = 0
        self.channel_id = 0


class BaseStream(Callable, StreamStat, ABC):
    """Base class for all streams in the simulation
    
    Corresponds to BaseStream.hh/cc in SimAI
    """
    
    def __init__(self, stream_num: int, owner: 'Sys', phases_to_go: List['CollectivePhase']):
        """Initialize base stream
        
        Args:
            stream_num: Stream number identifier
            owner: Reference to the system that owns this stream
            phases_to_go: List of collective phases to execute
        """
        # 调用父类构造函数
        super().__init__()
        
        # 基础属性 - 严格按照C++版本
        self.stream_num = stream_num
        self.owner = owner
        self.initialized = False
        self.phases_to_go = phases_to_go
        
        # 初始化phases中的algorithm
        for phase in self.phases_to_go:
            if hasattr(phase, 'algorithm') and phase.algorithm is not None:
                phase.init(self)
        
        # 状态和调度相关
        self.state = StreamState.Created
        self.preferred_scheduling = SchedulingPolicy.None_  # 对应C++中的None
        
        # 时间相关
        self.creation_time = self.owner.boosted_tick() if hasattr(self.owner, 'boosted_tick') else 0
        self.last_init: Tick = 0
        self.last_phase_change: Tick = 0
        
        # 计数器和标识符
        self.total_packets_sent = 0
        self.current_queue_id = -1  # C++版本初始化为-1
        self.priority = 0
        self.steps_finished = 0
        self.initial_data_size = 0
        
        # 当前状态
        self.my_current_phase: Optional['CollectivePhase'] = None
        self.current_com_type: ComType = ComType.None_
        self.dataset: Optional['DataSet'] = None
        
        # 测试和调试变量
        self.test = 0
        self.test2 = 0
        self.phase_latencies = [0] * 10  # uint64_t array[10]
    
    def change_state(self, state: StreamState) -> None:
        """Change the state of the stream
        
        Args:
            state: The new state to transition to
        """
        self.state = state
    
    @abstractmethod
    def consume(self, message: RecvPacketEventHandlerData) -> None:
        """Consume a received packet message
        
        Args:
            message: The received packet message to process
        """
        pass
    
    @abstractmethod
    def send_callback(self, messages: SendPacketEventHandlerData) -> None:
        """Callback for when a packet is sent
        
        Note: C++版本中方法名为sendcallback，这里使用更Pythonic的命名
        
        Args:
            messages: The sent packet message data
        """
        pass
    
    @abstractmethod
    def init(self) -> None:
        """Initialize the stream"""
        pass
    
    def call(self, event_type: EventType, data: CallData) -> None:
        """Handle events - implementation of Callable interface
        
        Args:
            event_type: Type of event to handle
            data: Event data
        """
        # 基类实现为空，子类可以重写
        pass 