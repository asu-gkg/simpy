"""
Config - Configuration Definitions

对应文件: config.h
功能: 定义仿真配置参数和常量

主要内容:
- 仿真时间类型定义
- 配置常量
- 默认参数值

C++对应关系:
- simtime_picosec -> SimTime
- 各种配置常量 -> Python常量
"""

from typing import TypeAlias
from dataclasses import dataclass

# 对应 C++ 中的 simtime_picosec 类型
SimTime: TypeAlias = int  # 皮秒级时间戳

# 时间单位常量
PICOSECONDS_PER_SECOND = 1_000_000_000_000
NANOSECONDS_PER_SECOND = 1_000_000_000
MICROSECONDS_PER_SECOND = 1_000_000
MILLISECONDS_PER_SECOND = 1_000

# 时间转换函数
def seconds_to_picoseconds(seconds: float) -> SimTime:
    """将秒转换为皮秒"""
    return int(seconds * PICOSECONDS_PER_SECOND)

def picoseconds_to_seconds(picoseconds: SimTime) -> float:
    """将皮秒转换为秒"""
    return picoseconds / PICOSECONDS_PER_SECOND

def milliseconds_to_picoseconds(milliseconds: float) -> SimTime:
    """将毫秒转换为皮秒"""
    return int(milliseconds * 1_000_000_000)

def microseconds_to_picoseconds(microseconds: float) -> SimTime:
    """将微秒转换为皮秒"""
    return int(microseconds * 1_000_000)

def nanoseconds_to_picoseconds(nanoseconds: float) -> SimTime:
    """将纳秒转换为皮秒"""
    return int(nanoseconds * 1_000)

# 网络配置常量
DEFAULT_PACKET_SIZE = 9000  # 字节 - 对应main_roce.cpp: int packet_size = 9000
DEFAULT_MTU = 9000  # 最大传输单元
DEFAULT_BUFFER_SIZE = 100  # 默认缓冲区大小
DEFAULT_QUEUE_SIZE = 15  # 默认队列大小(数据包数) - 对应main_roce.cpp: DEFAULT_QUEUE_SIZE 15

# 链路速度常量 (Gbps)
LINK_SPEED_1G = 1_000_000_000
LINK_SPEED_10G = 10_000_000_000
LINK_SPEED_25G = 25_000_000_000
LINK_SPEED_40G = 40_000_000_000
LINK_SPEED_100G = 100_000_000_000
LINK_SPEED_400G = 400_000_000_000

# 协议配置
DEFAULT_TCP_WINDOW_SIZE = 65536
DEFAULT_TCP_MSS = 1460
DEFAULT_NDP_WINDOW_SIZE = 65536
DEFAULT_SWIFT_WINDOW_SIZE = 65536

# 仿真配置
DEFAULT_SIMULATION_TIME = seconds_to_picoseconds(100)  # 100秒
DEFAULT_WARMUP_TIME = seconds_to_picoseconds(10)  # 10秒预热
DEFAULT_COOLDOWN_TIME = seconds_to_picoseconds(10)  # 10秒冷却

# 日志配置
DEFAULT_LOG_LEVEL = "INFO"
DEFAULT_LOG_FILE = "htsimpy.log"

# 拓扑配置
DEFAULT_FAT_TREE_K = 4
DEFAULT_LEAF_SPINE_LEAVES = 8
DEFAULT_LEAF_SPINE_SPINES = 4

# 队列配置
DEFAULT_FIFO_QUEUE_SIZE = 15  # 数据包数
DEFAULT_PRIORITY_QUEUE_SIZE = 15  # 数据包数
DEFAULT_RANDOM_QUEUE_SIZE = 15  # 数据包数
DEFAULT_LOSSLESS_QUEUE_SIZE = 15  # 数据包数

# 统计配置
DEFAULT_STATS_INTERVAL = milliseconds_to_picoseconds(100)  # 100ms
DEFAULT_FLOW_STATS_INTERVAL = milliseconds_to_picoseconds(1000)  # 1s


@dataclass
class SimulationConfig:
    """
    仿真配置类
    
    包含仿真运行所需的所有配置参数
    """
    
    # 时间配置
    simulation_time: SimTime = DEFAULT_SIMULATION_TIME
    warmup_time: SimTime = DEFAULT_WARMUP_TIME
    cooldown_time: SimTime = DEFAULT_COOLDOWN_TIME
    
    # 网络配置
    packet_size: int = DEFAULT_PACKET_SIZE
    mtu: int = DEFAULT_MTU
    buffer_size: int = DEFAULT_BUFFER_SIZE
    queue_size: int = DEFAULT_QUEUE_SIZE
    
    # 链路配置
    link_speed: int = LINK_SPEED_100G
    link_delay: SimTime = nanoseconds_to_picoseconds(100)  # 100ns
    
    # 协议配置
    tcp_window_size: int = DEFAULT_TCP_WINDOW_SIZE
    tcp_mss: int = DEFAULT_TCP_MSS
    ndp_window_size: int = DEFAULT_NDP_WINDOW_SIZE
    swift_window_size: int = DEFAULT_SWIFT_WINDOW_SIZE
    
    # 拓扑配置
    fat_tree_k: int = DEFAULT_FAT_TREE_K
    leaf_spine_leaves: int = DEFAULT_LEAF_SPINE_LEAVES
    leaf_spine_spines: int = DEFAULT_LEAF_SPINE_SPINES
    
    # 队列配置
    fifo_queue_size: int = DEFAULT_FIFO_QUEUE_SIZE
    priority_queue_size: int = DEFAULT_PRIORITY_QUEUE_SIZE
    random_queue_size: int = DEFAULT_RANDOM_QUEUE_SIZE
    lossless_queue_size: int = DEFAULT_LOSSLESS_QUEUE_SIZE
    
    # 统计配置
    stats_interval: SimTime = DEFAULT_STATS_INTERVAL
    flow_stats_interval: SimTime = DEFAULT_FLOW_STATS_INTERVAL
    
    # 日志配置
    log_level: str = DEFAULT_LOG_LEVEL
    log_file: str = DEFAULT_LOG_FILE
    
    def validate(self) -> bool:
        """
        验证配置参数的有效性
        
        Returns:
            如果配置有效返回True，否则返回False
        """
        # TODO: 实现配置验证逻辑
        return True
    
    def to_dict(self) -> dict:
        """
        将配置转换为字典
        
        Returns:
            配置字典
        """
        return {
            'simulation_time': self.simulation_time,
            'warmup_time': self.warmup_time,
            'cooldown_time': self.cooldown_time,
            'packet_size': self.packet_size,
            'mtu': self.mtu,
            'buffer_size': self.buffer_size,
            'queue_size': self.queue_size,
            'link_speed': self.link_speed,
            'link_delay': self.link_delay,
            'tcp_window_size': self.tcp_window_size,
            'tcp_mss': self.tcp_mss,
            'ndp_window_size': self.ndp_window_size,
            'swift_window_size': self.swift_window_size,
            'fat_tree_k': self.fat_tree_k,
            'leaf_spine_leaves': self.leaf_spine_leaves,
            'leaf_spine_spines': self.leaf_spine_spines,
            'fifo_queue_size': self.fifo_queue_size,
            'priority_queue_size': self.priority_queue_size,
            'random_queue_size': self.random_queue_size,
            'lossless_queue_size': self.lossless_queue_size,
            'stats_interval': self.stats_interval,
            'flow_stats_interval': self.flow_stats_interval,
            'log_level': self.log_level,
            'log_file': self.log_file,
        }