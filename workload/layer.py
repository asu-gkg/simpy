# Layer class - corresponds to Layer.cc/Layer.hh in SimAI 

from typing import Dict, List, Any, Optional
from collections import defaultdict

from system.callable import Callable, CallData
from system.common import EventType, ComType, SchedulingPolicy, CollectiveBarrier, Tick
from system.dataset import DataSet
from system.int_data import IntData
from system.api import LayerData
from .parallelism_policy import ParallelismPolicy


class Layer(Callable):
    """层类 - 对应C++版本的Layer类"""
    
    def __init__(self, layer_id: str, layer_num: int, generator, workload,
                fwd_pass_compute_time: Tick, fwd_pass_comm_type: ComType,
                fwd_pass_group_type: str, fwd_pass_comm_size: int,
                fwd_pass_involved_dimensions: List[bool],
                ig_compute_time: Tick, ig_comm_type: ComType,
                ig_group_type: str, ig_comm_size: int,
                ig_involved_dimensions: List[bool],
                wg_compute_time: Tick, wg_comm_type: ComType,
                wg_group_type: str, wg_comm_size: int,
                wg_involved_dimensions: List[bool],
                wg_update_time: Tick, specific_policy: ParallelismPolicy = ParallelismPolicy.None_):
        """
        初始化层
        
        Args:
            layer_id: 层ID
            layer_num: 层编号
            generator: 系统生成器
            workload: 工作负载
            fwd_pass_compute_time: 前向传播计算时间
            fwd_pass_comm_type: 前向传播通信类型
            fwd_pass_group_type: 前向传播组类型
            fwd_pass_comm_size: 前向传播通信大小
            fwd_pass_involved_dimensions: 前向传播涉及维度
            ig_compute_time: 输入梯度计算时间
            ig_comm_type: 输入梯度通信类型
            ig_group_type: 输入梯度组类型
            ig_comm_size: 输入梯度通信大小
            ig_involved_dimensions: 输入梯度涉及维度
            wg_compute_time: 权重梯度计算时间
            wg_comm_type: 权重梯度通信类型
            wg_group_type: 权重梯度组类型
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
        self.fwd_update_time = wg_update_time
        self.input_grad_update_time = wg_update_time
        
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
        self.specific_parallelism = ParallelismPolicy.None_
        
        # 计数器
        self.collective_counter = 0
        self.lookup_table_size = 0
        
        assert generator is not None
    
    def call(self, event_type: EventType, data: CallData) -> None:
        """
        处理事件 - 实现Callable接口
        
        Args:
            event_type: 事件类型
            data: 事件数据
        """
        if event_type == EventType.Wight_Grad_Comm_Finished:
            self.last_wg_finished = self.generator.get_tick()
            self.generator.register_event(
                self, EventType.Wight_Grad_Comm_Finished_After_Delay, 
                data, self.weight_grad_update_time)
            return
        elif event_type == EventType.Input_Grad_Comm_Finished:
            self.last_ig_finished = self.generator.get_tick()
            self.generator.register_event(
                self, EventType.Input_Grad_Comm_Finished_After_Delay,
                data, self.input_grad_update_time)
            return
        elif event_type == EventType.Fwd_Comm_Finished:
            self.last_fwd_finished = self.generator.get_tick()
            self.generator.register_event(
                self, EventType.Fwd_Comm_Finished_After_Delay,
                data, self.fwd_update_time)
            return
        
        if data is None:
            return
            
        int_data = data  # 假设data是IntData类型
        data_id = int_data.data if hasattr(int_data, 'data') else 0
        
        if event_type == EventType.Wight_Grad_Comm_Finished_After_Delay:
            if self.generator.id == 0:
                print(f"***** info: weight gradient collective for layer: {self.id} is finished************")
            
            if data_id in self.weight_grad_datasets:
                dataset = self.weight_grad_datasets[data_id]
                dataset.finish_tick += self.weight_grad_update_time
                self.total_weight_grad_comm += dataset.finish_tick - dataset.creation_tick
                
                if (len(self.weight_grad_datasets) == 1 and 
                    self.wg_barrier == CollectiveBarrier.Blocking):
                    self.total_waiting_for_wg_comm += dataset.finish_tick - dataset.creation_tick
                    self.update_stream_stats(dataset)
                    dataset_streams = dataset.total_streams
                    del self.weight_grad_datasets[data_id]
                    self.workload.call(EventType.General, None)
                    self.generator.increase_finished_streams(dataset_streams)
                    return
                elif self.started_waiting_for_weight_grad:
                    self.total_waiting_for_wg_comm += dataset.finish_tick - self.started_waiting_for_weight_grad[0]
                    self.started_waiting_for_weight_grad.pop(0)
                    self.update_stream_stats(dataset)
                    dataset_streams = dataset.total_streams
                    del self.weight_grad_datasets[data_id]
                    self.workload.call(EventType.General, None)
                    self.generator.increase_finished_streams(dataset_streams)
                    return
                
                self.update_stream_stats(dataset)
                dataset_streams = dataset.total_streams
                del self.weight_grad_datasets[data_id]
                self.generator.increase_finished_streams(dataset_streams)
            return
            
        elif event_type == EventType.Input_Grad_Comm_Finished_After_Delay:
            if self.generator.id == 0:
                print(f"***** info: input gradient collective for layer: {self.id} is finished************")
            
            if data_id in self.input_grad_datasets:
                dataset = self.input_grad_datasets[data_id]
                dataset.finish_tick += self.input_grad_update_time
                self.total_input_grad_comm += dataset.finish_tick - dataset.creation_tick
                
                if (len(self.input_grad_datasets) == 1 and 
                    self.ig_barrier == CollectiveBarrier.Blocking):
                    self.total_waiting_for_ig_comm += dataset.finish_tick - dataset.creation_tick
                    self.update_stream_stats(dataset)
                    dataset_streams = dataset.total_streams
                    del self.input_grad_datasets[data_id]
                    self.workload.call(EventType.General, None)
                    self.generator.increase_finished_streams(dataset_streams)
                    return
                elif self.started_waiting_for_input_grad:
                    self.total_waiting_for_ig_comm += dataset.finish_tick - self.started_waiting_for_input_grad[0]
                    self.started_waiting_for_input_grad.pop(0)
                    self.update_stream_stats(dataset)
                    dataset_streams = dataset.total_streams
                    del self.input_grad_datasets[data_id]
                    self.workload.call(EventType.General, None)
                    self.generator.increase_finished_streams(dataset_streams)
                    return
                
                self.update_stream_stats(dataset)
                dataset_streams = dataset.total_streams
                del self.input_grad_datasets[data_id]
                self.generator.increase_finished_streams(dataset_streams)
            return
            
        elif event_type == EventType.Fwd_Comm_Finished_After_Delay:
            if self.generator.id == 0:
                print(f"***** info: forward pass collective for layer: {self.id} is finished************")
            
            if data_id in self.fwd_pass_datasets:
                dataset = self.fwd_pass_datasets[data_id]
                dataset.finish_tick += self.fwd_update_time
                self.total_fwd_comm += dataset.finish_tick - dataset.creation_tick
                
                if (len(self.fwd_pass_datasets) == 1 and 
                    self.fwd_barrier == CollectiveBarrier.Blocking):
                    self.total_waiting_for_fwd_comm += dataset.finish_tick - dataset.creation_tick
                    self.update_stream_stats(dataset)
                    dataset_streams = dataset.total_streams
                    del self.fwd_pass_datasets[data_id]
                    self.workload.call(EventType.General, None)
                    self.generator.increase_finished_streams(dataset_streams)
                    return
                elif self.started_waiting_for_fwd_pass:
                    self.total_waiting_for_fwd_comm += dataset.finish_tick - self.started_waiting_for_fwd_pass[0]
                    self.started_waiting_for_fwd_pass.pop(0)
                    self.update_stream_stats(dataset)
                    dataset_streams = dataset.total_streams
                    del self.fwd_pass_datasets[data_id]
                    self.workload.call(EventType.General, None)
                    self.generator.increase_finished_streams(dataset_streams)
                    return
                
                self.update_stream_stats(dataset)
                dataset_streams = dataset.total_streams
                del self.fwd_pass_datasets[data_id]
                self.generator.increase_finished_streams(dataset_streams)
            return
    
    def get_fwd_pass_compute(self) -> Tick:
        """获取前向传播计算时间"""
        return self.fwd_pass_compute_time
    
    def get_input_grad_compute(self) -> Tick:
        """获取输入梯度计算时间"""
        return self.input_grad_compute_time
    
    def get_weight_grad_compute(self) -> Tick:
        """获取权重梯度计算时间"""
        return self.weight_grad_compute_time
    
    def increment_waiting_for_wg(self):
        """增加等待权重梯度的计数"""
        self.started_waiting_for_weight_grad.append(self.generator.get_tick())
    
    def increment_waiting_for_ig(self):
        """增加等待输入梯度的计数"""
        self.started_waiting_for_input_grad.append(self.generator.get_tick())
    
    def increment_waiting_for_fwd(self):
        """增加等待前向传播的计数"""
        self.started_waiting_for_fwd_pass.append(self.generator.get_tick())
    
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
    
    def issue_forward_pass_comm(self, pref_scheduling: SchedulingPolicy, 
                               barrier: CollectiveBarrier):
        """发起前向传播通信"""
        self.fwd_barrier = barrier
        # 这里应该调用系统接口发起通信
        # 暂时使用简单的实现
        dataset = DataSet()
        dataset.creation_tick = self.generator.get_tick()
        dataset.total_streams = 1
        self.fwd_pass_datasets[self.collective_counter] = dataset
        self.collective_counter += 1
        
        # 模拟通信完成
        self.generator.register_event(
            self, EventType.Fwd_Comm_Finished, 
            IntData(self.collective_counter - 1), 100)  # 假设100个时钟周期
    
    def issue_input_grad_comm(self, pref_scheduling: SchedulingPolicy,
                             barrier: CollectiveBarrier):
        """发起输入梯度通信"""
        self.ig_barrier = barrier
        # 这里应该调用系统接口发起通信
        # 暂时使用简单的实现
        dataset = DataSet()
        dataset.creation_tick = self.generator.get_tick()
        dataset.total_streams = 1
        self.input_grad_datasets[self.collective_counter] = dataset
        self.collective_counter += 1
        
        # 模拟通信完成
        self.generator.register_event(
            self, EventType.Input_Grad_Comm_Finished,
            IntData(self.collective_counter - 1), 100)  # 假设100个时钟周期
    
    def issue_weight_grad_comm(self, pref_scheduling: SchedulingPolicy,
                              barrier: CollectiveBarrier):
        """发起权重梯度通信"""
        self.wg_barrier = barrier
        # 这里应该调用系统接口发起通信
        # 暂时使用简单的实现
        dataset = DataSet()
        dataset.creation_tick = self.generator.get_tick()
        dataset.total_streams = 1
        self.weight_grad_datasets[self.collective_counter] = dataset
        self.collective_counter += 1
        
        # 模拟通信完成
        self.generator.register_event(
            self, EventType.Wight_Grad_Comm_Finished,
            IntData(self.collective_counter - 1), 100)  # 假设100个时钟周期
    
    def update_stream_stats(self, dataset: DataSet):
        """更新流统计信息"""
        # 这里应该更新流统计信息
        pass
    
    def print_involved_dimensions(self, involved_dimensions: List[bool]):
        """打印涉及的维度"""
        print(f"Layer {self.id} involved dimensions: {involved_dimensions}")
    
    def report(self, run_name: str, layer_num: int, total_rows: int, stat_row: int,
               detailed, end_to_end, total_compute: float, total_exposed: float,
               separate_log: bool, total_fwd_time: List[float], total_wg_time: List[float],
               total_ig_time: List[float], pre_bubble_time: float, dp_comm: float,
               dp_ep_comm: float, expose_tp_comm: float, expose_ep_comm: float) -> LayerData:
        """
        生成层报告
        
        Args:
            run_name: 运行名称
            layer_num: 层编号
            total_rows: 总行数
            stat_row: 统计行数
            detailed: 详细CSV写入器
            end_to_end: 端到端CSV写入器
            total_compute: 总计算时间
            total_exposed: 总暴露时间
            separate_log: 是否分离日志
            
        Returns:
            LayerData对象
        """
        # 计算总时间（转换为秒）
        layer_fwd_time = self.total_forward_pass_compute / self.generator.freq
        layer_wg_time = self.total_weight_grad_compute / self.generator.freq
        layer_ig_time = self.total_input_grad_compute / self.generator.freq
        
        total_compute += layer_fwd_time + layer_wg_time + layer_ig_time
        total_exposed += (self.total_fwd_comm + self.total_weight_grad_comm + 
                         self.total_input_grad_comm) / self.generator.freq
        
        # 更新传入的列表
        total_fwd_time[0] += layer_fwd_time
        total_wg_time[0] += layer_wg_time
        total_ig_time[0] += layer_ig_time
        
        # 创建LayerData对象
        layer_data = LayerData()
        layer_data.layer_name = self.id
        layer_data.total_forward_pass_compute = layer_fwd_time
        layer_data.total_weight_grad_compute = layer_wg_time
        layer_data.total_input_grad_compute = layer_ig_time
        layer_data.total_waiting_for_fwd_comm = self.total_waiting_for_fwd_comm / self.generator.freq
        layer_data.total_waiting_for_wg_comm = self.total_waiting_for_wg_comm / self.generator.freq
        layer_data.total_waiting_for_ig_comm = self.total_waiting_for_ig_comm / self.generator.freq
        layer_data.total_fwd_comm = self.total_fwd_comm / self.generator.freq
        layer_data.total_weight_grad_comm = self.total_weight_grad_comm / self.generator.freq
        layer_data.total_input_grad_comm = self.total_input_grad_comm / self.generator.freq
        
        # 这里可以添加队列延迟和网络消息延迟的统计
        # 暂时使用空列表，后续可以根据需要实现
        layer_data.avg_queuing_delay = []
        layer_data.avg_network_message_delay = []
        
        return layer_data 