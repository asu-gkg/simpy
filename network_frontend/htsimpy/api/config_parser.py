"""
HTSimPyConfig - Configuration Parser

对应文件: 无直接对应，这是配置接口
功能: 解析和管理HTSimPy的配置参数

主要类:
- HTSimPyConfig: 配置解析器类

配置对应关系:
- 协议选择 -> protocol
- 拓扑类型 -> topology
- 链路速度 -> link_speed
- 队列大小 -> queue_size
"""

from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from enum import Enum


class ProtocolType(Enum):
    """协议类型枚举"""
    TCP = "tcp"
    NDP = "ndp"
    SWIFT = "swift"
    ROCE = "roce"
    HPCC = "hpcc"
    STRACK = "strack"


class TopologyType(Enum):
    """拓扑类型枚举"""
    FAT_TREE = "fat_tree"
    LEAF_SPINE = "leaf_spine"
    MESH = "mesh"
    DUMBBELL = "dumbbell"


class LinkSpeed(Enum):
    """链路速度枚举"""
    SPEED_1G = "1Gb/s"
    SPEED_10G = "10Gb/s"
    SPEED_25G = "25Gb/s"
    SPEED_40G = "40Gb/s"
    SPEED_100G = "100Gb/s"
    SPEED_400G = "400Gb/s"


@dataclass
class HTSimPyConfig:
    """
    HTSimPy配置解析器
    
    对应配置接口中定义的所有参数
    """
    
    # 协议配置
    protocol: ProtocolType = ProtocolType.NDP
    
    # 拓扑配置
    topology: TopologyType = TopologyType.FAT_TREE
    
    # 链路配置
    link_speed: LinkSpeed = LinkSpeed.SPEED_100G
    link_delay: int = 100  # 纳秒
    
    # 队列配置
    queue_size: int = 64
    buffer_size: int = 1024
    
    # 数据包配置
    packet_size: int = 1500
    mtu: int = 1500
    
    # 协议特定配置
    tcp_window_size: int = 65536
    tcp_mss: int = 1460
    ndp_window_size: int = 65536
    swift_window_size: int = 65536
    
    # 拓扑特定配置
    fat_tree_k: int = 4
    leaf_spine_leaves: int = 8
    leaf_spine_spines: int = 4
    
    # 仿真配置
    simulation_time: int = 100_000_000_000_000  # 100秒（皮秒）
    warmup_time: int = 10_000_000_000_000  # 10秒（皮秒）
    cooldown_time: int = 10_000_000_000_000  # 10秒（皮秒）
    
    # 统计配置
    stats_interval: int = 100_000_000_000  # 100ms（皮秒）
    flow_stats_interval: int = 1_000_000_000_000  # 1s（皮秒）
    
    # 日志配置
    log_level: str = "INFO"
    log_file: str = "htsimpy.log"
    
    # 流量配置
    flow_count: int = 100
    flow_size: int = 1_000_000  # 1MB
    flow_duration: int = 10_000_000_000_000  # 10秒（皮秒）
    
    # 高级配置
    enable_ecn: bool = False
    enable_pfc: bool = False
    enable_qcn: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """
        将配置转换为字典
        
        Returns:
            配置字典
        """
        return {
            'protocol': self.protocol.value,
            'topology': self.topology.value,
            'link_speed': self.link_speed.value,
            'link_delay': self.link_delay,
            'queue_size': self.queue_size,
            'buffer_size': self.buffer_size,
            'packet_size': self.packet_size,
            'mtu': self.mtu,
            'tcp_window_size': self.tcp_window_size,
            'tcp_mss': self.tcp_mss,
            'ndp_window_size': self.ndp_window_size,
            'swift_window_size': self.swift_window_size,
            'fat_tree_k': self.fat_tree_k,
            'leaf_spine_leaves': self.leaf_spine_leaves,
            'leaf_spine_spines': self.leaf_spine_spines,
            'simulation_time': self.simulation_time,
            'warmup_time': self.warmup_time,
            'cooldown_time': self.cooldown_time,
            'stats_interval': self.stats_interval,
            'flow_stats_interval': self.flow_stats_interval,
            'log_level': self.log_level,
            'log_file': self.log_file,
            'flow_count': self.flow_count,
            'flow_size': self.flow_size,
            'flow_duration': self.flow_duration,
            'enable_ecn': self.enable_ecn,
            'enable_pfc': self.enable_pfc,
            'enable_qcn': self.enable_qcn,
        }
    
    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> 'HTSimPyConfig':
        """
        从字典创建配置
        
        Args:
            config_dict: 配置字典
            
        Returns:
            HTSimPyConfig实例
        """
        # 处理枚举类型
        if 'protocol' in config_dict:
            config_dict['protocol'] = ProtocolType(config_dict['protocol'])
        if 'topology' in config_dict:
            config_dict['topology'] = TopologyType(config_dict['topology'])
        if 'link_speed' in config_dict:
            config_dict['link_speed'] = LinkSpeed(config_dict['link_speed'])
        
        return cls(**config_dict)
    
    def validate(self) -> bool:
        """
        验证配置参数的有效性
        
        Returns:
            如果配置有效返回True，否则返回False
        """
        # 基本参数验证
        if self.queue_size <= 0:
            return False
        if self.buffer_size <= 0:
            return False
        if self.packet_size <= 0:
            return False
        if self.mtu <= 0:
            return False
        
        # 协议特定验证
        if self.tcp_window_size <= 0:
            return False
        if self.tcp_mss <= 0:
            return False
        if self.ndp_window_size <= 0:
            return False
        if self.swift_window_size <= 0:
            return False
        
        # 拓扑特定验证
        if self.fat_tree_k <= 0:
            return False
        if self.leaf_spine_leaves <= 0:
            return False
        if self.leaf_spine_spines <= 0:
            return False
        
        # 时间验证
        if self.simulation_time <= 0:
            return False
        if self.warmup_time < 0:
            return False
        if self.cooldown_time < 0:
            return False
        
        return True
    
    def get_link_speed_bps(self) -> int:
        """
        获取链路速度（比特每秒）
        
        Returns:
            链路速度（bps）
        """
        speed_map = {
            LinkSpeed.SPEED_1G: 1_000_000_000,
            LinkSpeed.SPEED_10G: 10_000_000_000,
            LinkSpeed.SPEED_25G: 25_000_000_000,
            LinkSpeed.SPEED_40G: 40_000_000_000,
            LinkSpeed.SPEED_100G: 100_000_000_000,
            LinkSpeed.SPEED_400G: 400_000_000_000,
        }
        return speed_map.get(self.link_speed, 100_000_000_000)
    
    def __str__(self) -> str:
        """字符串表示"""
        return (f"HTSimPyConfig(protocol={self.protocol.value}, "
                f"topology={self.topology.value}, "
                f"link_speed={self.link_speed.value})")
    
    def __repr__(self) -> str:
        """详细字符串表示"""
        return (f"HTSimPyConfig(protocol={self.protocol.value}, "
                f"topology={self.topology.value}, "
                f"link_speed={self.link_speed.value}, "
                f"queue_size={self.queue_size}, "
                f"packet_size={self.packet_size})")