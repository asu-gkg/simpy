# Layer主文件 - 整合所有Layer模块，对外暴露Layer类
# 
# 本文件通过多重继承整合了以下模块，完整对应C++版本的Layer类：
# 
# 继承关系：
# Layer(LayerBase, LayerEvents, LayerCommunication, LayerComputation, LayerReporting)
# 
# 对应 layer.cc/layer.hh 的完整功能：
# - LayerBase: 构造函数、基本属性、计算时间获取、状态检查等
# - LayerEvents: call() 事件处理方法及各种事件处理逻辑
# - LayerCommunication: 三种通信发起方法 (issue_*_comm)
# - LayerComputation: 带宽计算、通信时间计算等
# - LayerReporting: 两个report重载方法、统计平均等
# 
# 所有方法都通过多重继承获得，保持与C++版本完全一致的接口

from typing import List

from system.common import ComType, Tick
from system.mock_nccl_group import GroupType
from .parallelism_policy import ParallelismPolicy

# 导入各个模块
from .layer_base import LayerBase
from .layer_events import LayerEvents
from .layer_communication import LayerCommunication
from .layer_computation import LayerComputation
from .layer_reporting import LayerReporting


class Layer(LayerBase, LayerEvents, LayerCommunication, LayerComputation, LayerReporting):
    """
    Layer类 - 整合所有Layer功能模块
    
    这个类通过多重继承整合了以下功能模块：
    - LayerBase: 基础属性和初始化
    - LayerEvents: 事件处理
    - LayerCommunication: 通信发起
    - LayerComputation: 计算和带宽计算
    - LayerReporting: 报告和统计
    
    对外暴露完整的Layer接口，对应C++版本的Layer类
    """
    
    def __init__(self, layer_id: str, layer_num: int, generator, workload,
                fwd_pass_compute_time: Tick, fwd_pass_comm_type: ComType,
                fwd_pass_group_type: GroupType, fwd_pass_comm_size: int,
                fwd_pass_involved_dimensions: List[bool],
                ig_compute_time: Tick, ig_comm_type: ComType,
                ig_group_type: GroupType, ig_comm_size: int,
                ig_involved_dimensions: List[bool],
                wg_compute_time: Tick, wg_comm_type: ComType,
                wg_group_type: GroupType, wg_comm_size: int,
                wg_involved_dimensions: List[bool],
                wg_update_time: Tick, fwd_update_time: Tick,
                ig_update_time: Tick, specific_policy: ParallelismPolicy = ParallelismPolicy.None_):
        """
        初始化Layer对象
        
        调用父类LayerBase的初始化方法
        """
        super().__init__(layer_id, layer_num, generator, workload,
                        fwd_pass_compute_time, fwd_pass_comm_type,
                        fwd_pass_group_type, fwd_pass_comm_size,
                        fwd_pass_involved_dimensions,
                        ig_compute_time, ig_comm_type,
                        ig_group_type, ig_comm_size,
                        ig_involved_dimensions,
                        wg_compute_time, wg_comm_type,
                        wg_group_type, wg_comm_size,
                        wg_involved_dimensions,
                        wg_update_time, fwd_update_time,
                        ig_update_time, specific_policy)
    
    # 所有方法都通过多重继承从各个模块获得
    # 这里不需要重新定义任何方法，因为它们都从父类继承
    
    def __str__(self) -> str:
        """字符串表示"""
        return f"Layer(id={self.id}, layer_num={self.layer_num})"
    
    def __repr__(self) -> str:
        """详细字符串表示"""
        return (f"Layer(id='{self.id}', layer_num={self.layer_num}, "
                f"fwd_pass_compute_time={self.fwd_pass_compute_time}, "
                f"weight_grad_compute_time={self.weight_grad_compute_time}, "
                f"input_grad_compute_time={self.input_grad_compute_time})")


# 为了向后兼容，确保导入时能正确获取Layer类
__all__ = ['Layer']