# Memory bus class - corresponds to MemBus.hh/cc in SimAI

from enum import Enum
from typing import Optional, TYPE_CHECKING
from .common import Tick, EventType, BusType
from .callable import Callable, CallData
from .shared_bus_stat import SharedBusStat

if TYPE_CHECKING:
    from .sys import Sys


class Transmition(Enum):
    """传输类型枚举 - 对应C++版本的MemBus::Transmition"""
    Fast = "Fast"
    Usual = "Usual"


class LogGP(Callable):
    """LogGP类 - 对应C++版本的LogGP.hh/LogGP.cc
    
    这是一个简化的LogGP实现，主要用于MemBus
    """
    
    def __init__(self, name: str, generator: 'Sys', L: Tick, o: Tick, g: Tick, 
                 G: float, trigger_event: EventType):
        """
        初始化LogGP
        
        Args:
            name: LogGP名称
            generator: 系统生成器
            L: 延迟参数
            o: 开销参数  
            g: 间隔参数
            G: 带宽参数
            trigger_event: 触发事件类型
        """
        super().__init__()
        self.name = name
        self.generator = generator
        self.L = L
        self.o = o
        self.g = g
        self.G = G
        self.trigger_event = trigger_event
        self.partner: Optional['LogGP'] = None
    
    def call(self, event_type: EventType, data: CallData) -> None:
        """处理事件调用"""
        pass
    
    def request_read(self, bytes_count: int, processed: bool, send_back: bool, 
                    callable_obj: Callable) -> None:
        """请求读取操作"""
        # 简化实现，直接回调
        if callable_obj:
            callable_obj.call(self.trigger_event, None)
    
    def attach_mem_bus(self, generator: 'Sys', L: Tick, o: Tick, g: Tick, 
                      G: float, model_shared_bus: bool, communication_delay: int) -> None:
        """附加内存总线"""
        pass


class MemBus:
    """内存总线类 - 对应C++版本的MemBus.hh/MemBus.cc
    
    管理NPU和MA之间的内存传输
    """
    
    def __init__(self, side1: str, side2: str, generator: 'Sys', L: Tick, o: Tick, 
                 g: Tick, G: float, model_shared_bus: bool, communication_delay: int, 
                 attach: bool = True):
        """
        初始化内存总线
        
        Args:
            side1: 第一端名称（NPU端）
            side2: 第二端名称（MA端）
            generator: 系统生成器
            L: 延迟参数
            o: 开销参数
            g: 间隔参数
            G: 带宽参数
            model_shared_bus: 是否建模共享总线
            communication_delay: 通信延迟
            attach: 是否附加到内存总线
        """
        # 创建NPU端和MA端LogGP
        self.NPU_side = LogGP(side1, generator, L, o, g, G, EventType.MA_to_NPU)
        self.MA_side = LogGP(side2, generator, L, o, g, G, EventType.NPU_to_MA)
        
        # 设置伙伴关系
        self.NPU_side.partner = self.MA_side
        self.MA_side.partner = self.NPU_side
        
        self.generator = generator
        self.model_shared_bus = model_shared_bus
        self.communication_delay = communication_delay
        
        # 如果需要，附加内存总线
        if attach:
            self.NPU_side.attach_mem_bus(
                generator, L, o, g, 0.0038, model_shared_bus, communication_delay
            )
    
    def __del__(self):
        """析构函数 - 对应C++版本的析构函数"""
        # Python的垃圾回收会自动处理，但这里保持与C++版本的一致性
        pass
    
    def send_from_NPU_to_MA(self, transmition: Transmition, bytes_count: int, 
                           processed: bool, send_back: bool, callable_obj: Callable) -> None:
        """
        从NPU发送到MA
        
        Args:
            transmition: 传输类型
            bytes_count: 字节数
            processed: 是否已处理
            send_back: 是否发送回
            callable_obj: 可调用对象
        """
        if self.model_shared_bus and transmition == Transmition.Usual:
            self.NPU_side.request_read(bytes_count, processed, send_back, callable_obj)
        else:
            if transmition == Transmition.Fast:
                # 快速传输，延迟为10
                stat = SharedBusStat(BusType.Shared, 0, 10, 0, 0)
                self.generator.register_event(
                    callable_obj, 
                    EventType.NPU_to_MA, 
                    stat, 
                    10
                )
            else:
                # 普通传输，使用communication_delay
                stat = SharedBusStat(BusType.Shared, 0, self.communication_delay, 0, 0)
                self.generator.register_event(
                    callable_obj,
                    EventType.NPU_to_MA,
                    stat,
                    self.communication_delay
                )
    
    def send_from_MA_to_NPU(self, transmition: Transmition, bytes_count: int,
                           processed: bool, send_back: bool, callable_obj: Callable) -> None:
        """
        从MA发送到NPU
        
        Args:
            transmition: 传输类型
            bytes_count: 字节数
            processed: 是否已处理
            send_back: 是否发送回
            callable_obj: 可调用对象
        """
        if self.model_shared_bus and transmition == Transmition.Usual:
            self.MA_side.request_read(bytes_count, processed, send_back, callable_obj)
        else:
            if transmition == Transmition.Fast:
                # 快速传输，延迟为10
                stat = SharedBusStat(BusType.Shared, 0, 10, 0, 0)
                self.generator.register_event(
                    callable_obj,
                    EventType.MA_to_NPU,
                    stat,
                    10
                )
            else:
                # 普通传输，使用communication_delay
                stat = SharedBusStat(BusType.Shared, 0, self.communication_delay, 0, 0)
                self.generator.register_event(
                    callable_obj,
                    EventType.MA_to_NPU,
                    stat,
                    self.communication_delay
                ) 