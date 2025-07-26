# Stream baseline implementation - corresponds to StreamBaseline.hh/cc in SimAI

from typing import List, TYPE_CHECKING, Optional
from .base_stream import BaseStream, RecvPacketEventHandlerData
from .send_packet_event_handler_data import SendPacketEventHandlerData
from .common import EventType, BusType
from .callable import CallData
from .mock_nccl_log import MockNcclLog, NcclLogLevel
from .basic_event_handler_data import BasicEventHandlerData
from .shared_bus_stat import SharedBusStat

if TYPE_CHECKING:
    from .sys import Sys
    from .dataset import DataSet
    from .collective_phase import CollectivePhase


class StreamBaseline(BaseStream):
    """Baseline implementation of stream processing
    
    Corresponds to StreamBaseline.hh/cc in SimAI
    """
    
    def __init__(self, owner: 'Sys', dataset: 'DataSet', stream_num: int, 
                 phases_to_go: List['CollectivePhase'], priority: int):
        """Initialize stream baseline
        
        Args:
            owner: System that owns this stream
            dataset: Dataset associated with this stream
            stream_num: Stream number identifier
            phases_to_go: List of collective phases to execute
            priority: Priority of this stream
        """
        # 调用基类构造函数 - 对应C++版本的BaseStream构造
        super().__init__(stream_num, owner, phases_to_go)
        
        # 设置成员变量 - 严格按照C++版本
        self.owner = owner
        self.stream_num = stream_num
        self.phases_to_go = phases_to_go
        self.dataset = dataset
        self.priority = priority
        
        # 初始化C++版本中的额外成员变量
        self.steps_finished = 0
        if self.phases_to_go:
            self.initial_data_size = self.phases_to_go[0].initial_data_size
        else:
            self.initial_data_size = 0
    
    def init(self) -> None:
        """Initialize the stream baseline - 对应C++版本的init()方法"""
        # 设置初始化标志
        self.initialized = True
        
        # 记录last_init时间 - 对应C++版本的Sys::boostedTick()
        if hasattr(self.owner, 'boosted_tick'):
            self.last_init = self.owner.boosted_tick()
        else:
            self.last_init = 0
        
        # 检查当前阶段是否启用 - 对应C++版本的enabled检查
        if not self.my_current_phase or not self.my_current_phase.enabled:
            return
        
        # 运行算法的StreamInit事件 - 对应C++版本的algorithm->run
        if self.my_current_phase.algorithm is not None:
            self.my_current_phase.algorithm.run(EventType.StreamInit, None)
        
        # 记录日志 - 对应C++版本的MockNcclLog
        nccl_log = MockNcclLog.getInstance()
        nccl_log.writeLog(NcclLogLevel.DEBUG, "StreamBaseline::algorithm->run finished")
        
        # 处理queuing_delay统计 - 对应C++版本的queuing_delay逻辑
        if self.steps_finished == 1:
            delay = self.last_phase_change - self.creation_time
            if hasattr(self, 'queuing_delay'):
                self.queuing_delay.append(delay)
            else:
                self.queuing_delay = [delay]
        
        # 添加当前阶段的延迟
        current_tick = self.owner.boosted_tick() if hasattr(self.owner, 'boosted_tick') else 0
        delay = current_tick - self.last_phase_change
        if hasattr(self, 'queuing_delay'):
            self.queuing_delay.append(delay)
        else:
            self.queuing_delay = [delay]
        
        # 设置total_packets_sent - 对应C++版本
        self.total_packets_sent = 1
    
    def call(self, event_type: EventType, data: Optional[CallData]) -> None:
        """Handle events for stream baseline - 对应C++版本的call()方法
        
        Args:
            event_type: Type of event to handle
            data: Event data
        """
        # 处理WaitForVnetTurn事件 - 对应C++版本
        if event_type == EventType.WaitForVnetTurn:
            if hasattr(self.owner, 'proceed_to_next_vnet_baseline'):
                self.owner.proceed_to_next_vnet_baseline(self)
            return
        
        # 处理NCCL_General事件 - 对应C++版本
        elif event_type == EventType.NCCL_General:
            if isinstance(data, BasicEventHandlerData):
                behd = data
                channel_id = behd.channel_id
                # 运行算法的General事件
                if (self.my_current_phase and 
                    self.my_current_phase.algorithm is not None):
                    self.my_current_phase.algorithm.run(EventType.General, data)
        
        # 处理其他事件 - 对应C++版本的else分支
        else:
            if isinstance(data, SharedBusStat):
                # 更新总线统计 - 对应C++版本的update_bus_stats
                self.update_bus_stats(BusType.Both, data)
                
                # 运行算法的General事件
                if (self.my_current_phase and 
                    self.my_current_phase.algorithm is not None):
                    self.my_current_phase.algorithm.run(EventType.General, data)
                
                # 删除SharedBusStat对象 - 对应C++版本的delete
                # Python中由垃圾回收器处理，但我们可以显式清理
                del data
    
    def consume(self, message: RecvPacketEventHandlerData) -> None:
        """Consume a received packet message - 对应C++版本的consume()方法
        
        Args:
            message: The received packet message to process
        """
        # 更新网络消息延迟统计 - 对应C++版本
        current_tick = self.owner.boosted_tick() if hasattr(self.owner, 'boosted_tick') else 0
        latency = current_tick - message.ready_time
        
        # 确保net_message_latency列表存在
        if not hasattr(self, 'net_message_latency'):
            self.net_message_latency = []
        
        if self.net_message_latency:
            self.net_message_latency[-1] += latency
        else:
            self.net_message_latency.append(latency)
        
        # 增加网络消息计数器 - 对应C++版本
        if not hasattr(self, 'net_message_counter'):
            self.net_message_counter = 0
        self.net_message_counter += 1
        
        # 运行算法的PacketReceived事件 - 对应C++版本
        if (self.my_current_phase and 
            self.my_current_phase.algorithm is not None):
            self.my_current_phase.algorithm.run(EventType.PacketReceived, message)
    
    def send_callback(self, messages: SendPacketEventHandlerData) -> None:
        """Callback for when a packet is sent - 对应C++版本的sendcallback()方法
        
        Args:
            messages: The sent packet message data
        """
        # 检查算法是否存在并运行PacketSentFinshed事件 - 对应C++版本
        if (self.my_current_phase and 
            self.my_current_phase.algorithm is not None):
            self.my_current_phase.algorithm.run(EventType.PacketSentFinshed, messages) 