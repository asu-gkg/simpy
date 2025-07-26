# MockNcclGroup.py - corresponds to MockNcclGroup.h in SimAI
# This file contains the GroupType enum and related classes

from enum import Enum
from typing import List, Dict, Any


class GroupType(Enum):
    """组类型枚举 - 对应C++版本的MockNccl::GroupType"""
    TP = "TP"      # Tensor Parallelism
    DP = "DP"      # Data Parallelism  
    PP = "PP"      # Pipeline Parallelism
    EP = "EP"      # Expert Parallelism
    DP_EP = "DP_EP"  # Data + Expert Parallelism
    NONE = "NONE"  # No parallelism


class GroupInfo:
    """组信息类 - 对应C++版本的GroupInfo结构"""
    def __init__(self, group_index: int, group_type: GroupType, 
                n_nodes: int, n_ranks: int, ranks: List[int], nv_switches: List[int]):
        self.group_index = group_index
        self.type = group_type
        self.n_nodes = n_nodes
        self.n_ranks = n_ranks
        self.ranks = ranks
        self.nv_switches = nv_switches


class MockNcclGroup:
    """MockNccl组类 - 对应C++版本的MockNcclGroup类"""
    def __init__(self):
        self.group_index: Dict[tuple, int] = {}
        self.all_groups: Dict[int, GroupInfo] = {}
        self.g_flow_id = 0
        
    def get_group_type_from_string(self, group_type_str: str) -> GroupType:
        """从字符串获取组类型"""
        try:
            return GroupType(group_type_str)
        except ValueError:
            return GroupType.NONE
    
    def get_group_type_string(self, group_type: GroupType) -> str:
        """从组类型获取字符串"""
        return group_type.value 