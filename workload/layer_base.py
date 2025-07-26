# Layer基础模块 - 对应Layer.cc的构造函数和基本属性
# 
# 对应关系：
# - __init__() -> Layer::Layer() 构造函数
# - get_fwd_pass_compute() -> Layer::get_fwd_pass_compute()
# - get_input_grad_compute() -> Layer::get_input_grad_compute() 
# - get_weight_grad_compute() -> Layer::get_weight_grad_compute()
# - increment_waiting_for_wg() -> Layer::increment_waiting_for_wg()
# - increment_waiting_for_ig() -> Layer::increment_waiting_for_ig()
# - increment_waiting_for_fwd() -> Layer::increment_waiting_for_fwd()
# - is_fwd_pass_comm_finished() -> Layer::is_fwd_pass_comm_finished()
# - is_input_grad_comm_finished() -> Layer::is_input_grad_comm_finished()
# - is_weight_grad_comm_finished() -> Layer::is_weight_grad_comm_finished()
# - is_fwd_pass_comm_finished_blocking() -> Layer::is_fwd_pass_comm_finished_blocking()
# - is_input_grad_comm_finished_blocking() -> Layer::is_input_grad_comm_finished_blocking()
# - is_weight_grad_comm_finished_blocking() -> Layer::is_weight_grad_comm_finished_blocking()
# - print_involved_dimensions() -> Layer::print_involved_dimensions()

from typing import Dict, List
from system.callable import Callable, CallData
from system.common import EventType, ComType, SchedulingPolicy, CollectiveBarrier, Tick
from system.dataset import DataSet
from system.stream_stat import StreamStat
from system.mock_nccl_group import GroupType
from .parallelism_policy import ParallelismPolicy


class LayerBase(Callable, StreamStat):
    """Layer基础类 - 包含基本属性和初始化逻辑"""
    
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
        初始化层
        
        Args:
            layer_id: 层ID
            layer_num: 层编号
            generator: 系统生成器
            workload: 工作负载
            fwd_pass_compute_time: 前向传播计算时间
            fwd_pass_comm_type: 前向传播通信类型
            fwd_pass_group_type: 前向传播组类型 (GroupType枚举)
            fwd_pass_comm_size: 前向传播通信大小
            fwd_pass_involved_dimensions: 前向传播涉及维度
            ig_compute_time: 输入梯度计算时间
            ig_comm_type: 输入梯度通信类型
            ig_group_type: 输入梯度组类型 (GroupType枚举)
            ig_comm_size: 输入梯度通信大小
            ig_involved_dimensions: 输入梯度涉及维度
            wg_compute_time: 权重梯度计算时间
            wg_comm_type: 权重梯度通信类型
            wg_group_type: 权重梯度组类型 (GroupType枚举)
            wg_comm_size: 权重梯度通信大小
            wg_involved_dimensions: 权重梯度涉及维度
            wg_update_time: 权重梯度更新时间
            specific_policy: 特定并行策略
        """
        super().__init__()
        
        # 基本属性
        self.id = layer_id
        self.layer_num = layer_num
        self.generator = generator
        self.workload = workload
        
        # 前向传播相关
        self.fwd_pass_compute_time = fwd_pass_compute_time
        self.fwd_pass_comm_type = fwd_pass_comm_type
        self.fwd_pass_group_type = fwd_pass_group_type
        self.fwd_pass_comm_size = fwd_pass_comm_size
        self.fwd_pass_comm_involved_dimensions = fwd_pass_involved_dimensions
        
        # 输入梯度相关
        self.input_grad_compute_time = ig_compute_time
        self.input_grad_comm_type = ig_comm_type
        self.input_grad_group_type = ig_group_type
        self.input_grad_comm_size = ig_comm_size
        self.input_grad_comm_involved_dimensions = ig_involved_dimensions
        
        # 权重梯度相关
        self.weight_grad_compute_time = wg_compute_time
        self.weight_grad_comm_type = wg_comm_type
        self.weight_grad_group_type = wg_group_type
        self.weight_grad_comm_size = wg_comm_size
        self.weight_grad_comm_involved_dimensions = wg_involved_dimensions
        
        # 特定并行策略
        self.specific_policy = specific_policy
        
        # 检查点相关
        self.is_checkpoint = False
        self.needs_fwd_in_bckwd_initiation = False
        
        # 更新时间
        self.weight_grad_update_time = wg_update_time
        self.fwd_update_time = fwd_update_time
        self.input_grad_update_time = ig_update_time
        
        # 统计信息
        self.total_forward_pass_compute = 0
        self.total_input_grad_compute = 0
        self.total_weight_grad_compute = 0
        self.total_weight_grad_comm = 0
        self.total_input_grad_comm = 0
        self.total_fwd_comm = 0
        
        self.last_fwd_finished = 0
        self.last_wg_finished = 0
        self.last_ig_finished = 0
        
        self.total_waiting_for_wg_comm = 0
        self.total_waiting_for_ig_comm = 0
        self.total_waiting_for_fwd_comm = 0
        
        # 数据集和等待队列
        self.fwd_pass_datasets: Dict[int, DataSet] = {}
        self.started_waiting_for_fwd_pass = []
        self.input_grad_datasets: Dict[int, DataSet] = {}
        self.started_waiting_for_input_grad = []
        self.weight_grad_datasets: Dict[int, DataSet] = {}
        self.started_waiting_for_weight_grad = []
        
        # 屏障设置
        self.fwd_barrier = CollectiveBarrier.Blocking
        self.wg_barrier = CollectiveBarrier.Non_Blocking
        self.ig_barrier = CollectiveBarrier.Non_Blocking
        
        # 特殊标志
        self.needs_fwd_in_bckwd_initiation = False
        self.is_checkpoint = False
        self.specific_parallelism = specific_policy
        
        # 计数器
        self.collective_counter = 0
        self.lookup_table_size = 0
        
        assert generator is not None
    
    def get_fwd_pass_compute(self) -> Tick:
        """获取前向传播计算时间 - 对应C++版本的累加逻辑"""
        self.total_forward_pass_compute += self.fwd_pass_compute_time
        return self.fwd_pass_compute_time

    def get_input_grad_compute(self) -> Tick:
        """获取输入梯度计算时间 - 对应C++版本的累加逻辑"""
        self.total_input_grad_compute += self.input_grad_compute_time
        return self.input_grad_compute_time

    def get_weight_grad_compute(self) -> Tick:
        """获取权重梯度计算时间 - 对应C++版本的累加逻辑"""
        self.total_weight_grad_compute += self.weight_grad_compute_time
        return self.weight_grad_compute_time
    
    def increment_waiting_for_wg(self):
        """增加等待权重梯度的计数 - 对应C++版本的简单计数器递增"""
        self.total_waiting_for_wg_comm += 1

    def increment_waiting_for_ig(self):
        """增加等待输入梯度的计数 - 对应C++版本的简单计数器递增"""
        self.total_waiting_for_ig_comm += 1

    def increment_waiting_for_fwd(self):
        """增加等待前向传播的计数 - 对应C++版本的简单计数器递增"""
        self.total_waiting_for_fwd_comm += 1
    
    def is_fwd_pass_comm_finished(self) -> bool:
        """检查前向传播通信是否完成"""
        return len(self.fwd_pass_datasets) == 0
    
    def is_input_grad_comm_finished(self) -> bool:
        """检查输入梯度通信是否完成"""
        return len(self.input_grad_datasets) == 0
    
    def is_weight_grad_comm_finished(self) -> bool:
        """检查权重梯度通信是否完成"""
        return len(self.weight_grad_datasets) == 0
    
    def is_fwd_pass_comm_finished_blocking(self) -> bool:
        """阻塞检查前向传播通信是否完成"""
        return self.is_fwd_pass_comm_finished()
    
    def is_input_grad_comm_finished_blocking(self) -> bool:
        """阻塞检查输入梯度通信是否完成"""
        return self.is_input_grad_comm_finished()
    
    def is_weight_grad_comm_finished_blocking(self) -> bool:
        """阻塞检查权重梯度通信是否完成"""
        return self.is_weight_grad_comm_finished()
    
    def print_involved_dimensions(self, involved_dimensions: List[bool]):
        """打印涉及的维度 - 对应C++版本的格式化输出"""
        print(" involved dimensions: ", end="")
        for i, involved in enumerate(involved_dimensions):
            if involved:
                print(" 1,", end="")
            else:
                print(" 0,", end="")
        print()  # 换行 