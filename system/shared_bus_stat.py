# SharedBusStat class - corresponds to SharedBusStat.hh in SimAI

from .common import BusType
from .callable import CallData


class SharedBusStat(CallData):
    """共享总线统计类 - 对应C++版本的SharedBusStat类"""
    
    def __init__(self, bus_type: BusType, total_bus_transfer_queue_delay: float = 0.0,
                    total_bus_transfer_delay: float = 0.0, total_bus_processing_queue_delay: float = 0.0,
                    total_bus_processing_delay: float = 0.0):
        """
        初始化共享总线统计
        
        Args:
            bus_type: 总线类型
            total_bus_transfer_queue_delay: 总总线传输队列延迟
            total_bus_transfer_delay: 总总线传输延迟
            total_bus_processing_queue_delay: 总总线处理队列延迟
            total_bus_processing_delay: 总总线处理延迟
        """
        super().__init__()
        
        # 共享总线统计
        self.total_shared_bus_transfer_queue_delay = 0.0
        self.total_shared_bus_transfer_delay = 0.0
        self.total_shared_bus_processing_queue_delay = 0.0
        self.total_shared_bus_processing_delay = 0.0
        
        # 内存总线统计
        self.total_mem_bus_transfer_queue_delay = 0.0
        self.total_mem_bus_transfer_delay = 0.0
        self.total_mem_bus_processing_queue_delay = 0.0
        self.total_mem_bus_processing_delay = 0.0
        
        # 计数器
        self.mem_request_counter = 0
        self.shared_request_counter = 0
        
        # 根据总线类型初始化
        if bus_type == BusType.Shared:
            self.total_shared_bus_transfer_queue_delay = total_bus_transfer_queue_delay
            self.total_shared_bus_transfer_delay = total_bus_transfer_delay
            self.total_shared_bus_processing_queue_delay = total_bus_processing_queue_delay
            self.total_shared_bus_processing_delay = total_bus_processing_delay
        elif bus_type == BusType.Mem:
            self.total_mem_bus_transfer_queue_delay = total_bus_transfer_queue_delay
            self.total_mem_bus_transfer_delay = total_bus_transfer_delay
            self.total_mem_bus_processing_queue_delay = total_bus_processing_queue_delay
            self.total_mem_bus_processing_delay = total_bus_processing_delay
    
    def update_bus_stats(self, bus_type: BusType, other: 'SharedBusStat'):
        """
        更新总线统计
        
        Args:
            bus_type: 总线类型
            other: 要合并的总线统计
        """
        if bus_type == BusType.Shared:
            self.total_shared_bus_transfer_queue_delay += other.total_shared_bus_transfer_queue_delay
            self.total_shared_bus_transfer_delay += other.total_shared_bus_transfer_delay
            self.total_shared_bus_processing_queue_delay += other.total_shared_bus_processing_queue_delay
            self.total_shared_bus_processing_delay += other.total_shared_bus_processing_delay
            self.shared_request_counter += 1
        elif bus_type == BusType.Mem:
            self.total_mem_bus_transfer_queue_delay += other.total_mem_bus_transfer_queue_delay
            self.total_mem_bus_transfer_delay += other.total_mem_bus_transfer_delay
            self.total_mem_bus_processing_queue_delay += other.total_mem_bus_processing_queue_delay
            self.total_mem_bus_processing_delay += other.total_mem_bus_processing_delay
            self.mem_request_counter += 1
        else:  # BusType.Both
            self.total_shared_bus_transfer_queue_delay += other.total_shared_bus_transfer_queue_delay
            self.total_shared_bus_transfer_delay += other.total_shared_bus_transfer_delay
            self.total_shared_bus_processing_queue_delay += other.total_shared_bus_processing_queue_delay
            self.total_shared_bus_processing_delay += other.total_shared_bus_processing_delay
            self.total_mem_bus_transfer_queue_delay += other.total_mem_bus_transfer_queue_delay
            self.total_mem_bus_transfer_delay += other.total_mem_bus_transfer_delay
            self.total_mem_bus_processing_queue_delay += other.total_mem_bus_processing_queue_delay
            self.total_mem_bus_processing_delay += other.total_mem_bus_processing_delay
            self.shared_request_counter += 1
            self.mem_request_counter += 1
    
    def take_bus_stats_average(self):
        """计算总线统计平均值"""
        if self.shared_request_counter > 0:
            self.total_shared_bus_transfer_queue_delay /= self.shared_request_counter
            self.total_shared_bus_transfer_delay /= self.shared_request_counter
            self.total_shared_bus_processing_queue_delay /= self.shared_request_counter
            self.total_shared_bus_processing_delay /= self.shared_request_counter
        
        if self.mem_request_counter > 0:
            self.total_mem_bus_transfer_queue_delay /= self.mem_request_counter
            self.total_mem_bus_transfer_delay /= self.mem_request_counter
            self.total_mem_bus_processing_queue_delay /= self.mem_request_counter
            self.total_mem_bus_processing_delay /= self.mem_request_counter 