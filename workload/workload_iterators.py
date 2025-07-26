# Workload迭代器 - 对应Workload.cc中的各种迭代方法
# 对应C++函数签名：
# - void Workload::iterate_micro_benchmark()
# - void Workload::iterate_data_parallel()
# - void Workload::iterate_hybrid_parallel_Transformer()
# - void Workload::iterate_hybrid_parallel_Transformer_fwd_in_bckwd()
# - void Workload::iterate_hybrid_parallel_DLRM()
# - void Workload::iterate_model_parallel()
# - void Workload::iterate_hybrid_parallel_data_model()
# - void Workload::iterate_hybrid_parallel_model_data()
# - void Workload::iterate_distributed_inference()
# - void Workload::iterate_hybrid_parallel_customized()

from typing import List, Dict, Any, Optional
from system.common import EventType, ComType, SchedulingPolicy, CollectiveBarrier
from .parallelism_policy import LoopState
import rich

class WorkloadIterators:
    """工作负载迭代器 - 负责各种并行策略的迭代逻辑"""
    
    def __init__(self, workload):
        """
        初始化迭代器
        
        Args:
            workload: 工作负载对象
        """
        self.workload = workload
    
    def iterate_micro_benchmark(self):
        """
        微基准测试迭代 - 对应C++函数
        void Workload::iterate_micro_benchmark()
        """
        assert 0 <= self.workload.index < self.workload.size
        if self.workload.current_state != LoopState.Wait_For_Sim_Finish:
            for pass_counter in range(self.workload.total_pass):
                self.workload.layers[self.workload.index].issue_weight_grad_comm(
                    SchedulingPolicy.None_, CollectiveBarrier.Non_Blocking)
            # 更新成员变量以反映所有 pass 都已完成
            self.workload.pass_counter = self.workload.total_pass
        self.workload.check_for_sim_end()
    def iterate_data_parallel(self):
        """
        数据并行迭代 - 对应C++函数
        void Workload::iterate_data_parallel()
        """
        assert 0 <= self.workload.index < self.workload.size
        self.workload.check_for_sim_end()
        
        if self.workload.current_state == LoopState.Forward_Pass:
            if not self.workload.layers[self.workload.index].is_weight_grad_comm_finished_blocking():
                return
            
            if not self.workload.delay_loaded:
                self.workload.counter = self.workload.layers[self.workload.index].get_fwd_pass_compute()
                self.workload.delay_loaded = True
            
            if self.workload.counter > 0:
                self.workload.generator.try_register_event(
                    self.workload, EventType.Workload_Wait, None, self.workload.counter)
                return
            
            self.workload.index += 1
            self.workload.delay_loaded = False
            if self.workload.index >= self.workload.size:
                self.workload.current_state = LoopState.Weight_Gradient
                self.workload.index -= 1
            
            self.workload.generator.register_event(self.workload, EventType.General, None, 1)
            return
            
        elif self.workload.current_state == LoopState.Weight_Gradient:
            if not self.workload.delay_loaded:
                self.workload.counter = self.workload.layers[self.workload.index].get_weight_grad_compute()
                self.workload.delay_loaded = True
            
            if self.workload.counter > 0:
                self.workload.generator.try_register_event(
                    self.workload, EventType.Workload_Wait, None, self.workload.counter)
                return
            
            self.workload.delay_loaded = False
            self.workload.layers[self.workload.index].issue_weight_grad_comm(
                SchedulingPolicy.None_, CollectiveBarrier.Non_Blocking)
            
            if self.workload.index == 0:
                if self.workload.generator.id == 0:
                    print(f"pass: {self.workload.pass_counter} finished at time: {self.workload.generator.get_tick()}")
                self.workload.pass_counter += 1
                self.workload.current_state = LoopState.Forward_Pass
            else:
                self.workload.current_state = LoopState.Input_Gradient
            
            self.workload.generator.register_event(self.workload, EventType.General, None, 1)
            return
            
        elif self.workload.current_state == LoopState.Input_Gradient:
            if not self.workload.delay_loaded:
                self.workload.counter = self.workload.layers[self.workload.index].get_input_grad_compute()
                self.workload.delay_loaded = True
            
            if self.workload.counter > 0:
                self.workload.generator.try_register_event(
                    self.workload, EventType.Workload_Wait, None, self.workload.counter)
                return
            
            self.workload.delay_loaded = False
            self.workload.index -= 1
            self.workload.current_state = LoopState.Weight_Gradient
            self.workload.generator.register_event(self.workload, EventType.General, None, 1)
            return
    
    def iterate_hybrid_parallel_transformer(self):
        """
        Transformer混合并行迭代 - 对应C++函数
        void Workload::iterate_hybrid_parallel_Transformer()
        """
        assert 0 <= self.workload.index < self.workload.size
        self.workload.check_for_sim_end()
        
        if self.workload.current_state == LoopState.Forward_Pass:
            if not self.workload.layers[self.workload.index].is_weight_grad_comm_finished_blocking():
                return
            
            if not self.workload.delay_loaded:
                self.workload.counter = self.workload.layers[self.workload.index].get_fwd_pass_compute()
                self.workload.delay_loaded = True
            
            if self.workload.counter > 0:
                self.workload.generator.try_register_event(
                    self.workload, EventType.Workload_Wait, None, self.workload.counter)
                return
            
            if not self.workload.collective_issued:
                self.workload.collective_issued = True
                self.workload.layers[self.workload.index].issue_forward_pass_comm(
                    SchedulingPolicy.None_, CollectiveBarrier.Blocking)
                return
            
            self.workload.index += 1
            self.workload.delay_loaded = False
            self.workload.collective_issued = False
            if self.workload.index >= self.workload.size:
                self.workload.current_state = LoopState.Input_Gradient
                self.workload.index -= 1
            
            self.workload.generator.register_event(self.workload, EventType.General, None, 1)
            return
            
        elif self.workload.current_state == LoopState.Weight_Gradient:
            if not self.workload.delay_loaded:
                self.workload.counter = self.workload.layers[self.workload.index].get_weight_grad_compute()
                self.workload.delay_loaded = True
            
            if self.workload.counter > 0:
                self.workload.generator.try_register_event(
                    self.workload, EventType.Workload_Wait, None, self.workload.counter)
                return
            
            if not self.workload.collective_issued:
                self.workload.collective_issued = True
                self.workload.layers[self.workload.index].issue_weight_grad_comm(
                    SchedulingPolicy.FIFO, CollectiveBarrier.Non_Blocking)
            
            if not self.workload.layers[self.workload.index].is_input_grad_comm_finished_blocking():
                return
            
            self.workload.collective_issued = False
            self.workload.delay_loaded = False
            if self.workload.index >= 0:
                self.workload.index -= 1
            if self.workload.index == -1:
                self.workload.index = 0
                if self.workload.generator.id == 0:
                    print(f"pass: {self.workload.pass_counter} finished at time: {self.workload.generator.get_tick()}")
                self.workload.pass_counter += 1
                self.workload.current_state = LoopState.Forward_Pass
            else:
                self.workload.current_state = LoopState.Input_Gradient
            
            self.workload.generator.register_event(self.workload, EventType.General, None, 1)
            return
            
        elif self.workload.current_state == LoopState.Input_Gradient:
            if not self.workload.delay_loaded:
                self.workload.counter = self.workload.layers[self.workload.index].get_input_grad_compute()
                self.workload.delay_loaded = True
            
            if self.workload.counter > 0:
                self.workload.generator.try_register_event(
                    self.workload, EventType.Workload_Wait, None, self.workload.counter)
                return
            
            if not self.workload.collective_issued:
                self.workload.collective_issued = True
                self.workload.layers[self.workload.index].issue_input_grad_comm(
                    SchedulingPolicy.LIFO, CollectiveBarrier.Blocking)
                return
            
            self.workload.collective_issued = False
            self.workload.delay_loaded = False
            self.workload.current_state = LoopState.Weight_Gradient
            self.workload.generator.register_event(self.workload, EventType.General, None, 1)
            return
    
    def iterate_hybrid_parallel_dlrm(self):
        """
        DLRM混合并行迭代 - 对应C++函数
        void Workload::iterate_hybrid_parallel_DLRM()
        """
        assert 0 <= self.workload.index < self.workload.size
        self.workload.check_for_sim_end()
        
        if self.workload.current_state == LoopState.Forward_Pass:
            if not self.workload.layers[self.workload.index].is_weight_grad_comm_finished_blocking():
                return
            
            if not self.workload.delay_loaded:
                self.workload.counter = self.workload.layers[self.workload.index].get_fwd_pass_compute()
                self.workload.delay_loaded = True
            
            if self.workload.counter > 0:
                self.workload.generator.try_register_event(
                    self.workload, EventType.Workload_Wait, None, self.workload.counter)
                return
            
            if not self.workload.collective_issued and self.workload.layers[self.workload.index].fwd_pass_comm_type == ComType.All_to_All:
                self.workload.collective_issued = True
                self.workload.layers[self.workload.index].issue_forward_pass_comm(
                    SchedulingPolicy.HIGHEST, CollectiveBarrier.Non_Blocking)
            elif self.workload.index == self.workload.dlrm_last_bottom_layer:
                if not self.workload.layers[0].is_fwd_pass_comm_finished_blocking():
                    return
            
            self.workload.index += 1
            self.workload.delay_loaded = False
            self.workload.collective_issued = False
            if self.workload.index >= self.workload.size:
                self.workload.current_state = LoopState.Weight_Gradient
                self.workload.index -= 1
            
            if self.workload.generator.id == 0:
                print(f"layer changed to: {self.workload.index}")
            
            self.workload.generator.register_event(self.workload, EventType.General, None, 1)
            return
            
        elif self.workload.current_state == LoopState.Weight_Gradient:
            if not self.workload.delay_loaded:
                self.workload.counter = self.workload.layers[self.workload.index].get_weight_grad_compute()
                self.workload.delay_loaded = True
            
            if self.workload.counter > 0:
                self.workload.generator.try_register_event(
                    self.workload, EventType.Workload_Wait, None, self.workload.counter)
                return
            
            if not self.workload.collective_issued:
                self.workload.collective_issued = True
                self.workload.layers[self.workload.index].issue_weight_grad_comm(
                    SchedulingPolicy.None_, CollectiveBarrier.Non_Blocking)
            
            if (self.workload.parallelism_policy == ParallelismPolicy.DLRM and
                not self.workload.layers[self.workload.index].is_input_grad_comm_finished_blocking()):
                return
            
            if self.workload.index == 0:
                if self.workload.generator.id == 0:
                    print(f"pass: {self.workload.pass_counter} finished at time: {self.workload.generator.get_tick()}")
                self.workload.pass_counter += 1
                self.workload.current_state = LoopState.Forward_Pass
            else:
                self.workload.current_state = LoopState.Input_Gradient
            
            self.workload.delay_loaded = False
            self.workload.collective_issued = False
            self.workload.generator.register_event(self.workload, EventType.General, None, 1)
            
        elif self.workload.current_state == LoopState.Input_Gradient:
            if not self.workload.delay_loaded:
                self.workload.counter = self.workload.layers[self.workload.index].get_input_grad_compute()
                self.workload.delay_loaded = True
            
            if self.workload.counter > 0:
                self.workload.generator.try_register_event(
                    self.workload, EventType.Workload_Wait, None, self.workload.counter)
                return
            
            if self.workload.index == self.workload.dlrm_last_bottom_layer + 1:
                self.workload.layers[0].issue_input_grad_comm(
                    SchedulingPolicy.HIGHEST, CollectiveBarrier.Non_Blocking)
            
            self.workload.index -= 1
            if self.workload.generator.id == 0:
                print(f"layer changed to: {self.workload.index} in ig")
            
            self.workload.current_state = LoopState.Weight_Gradient
            self.workload.collective_issued = False
            self.workload.delay_loaded = False
            self.workload.generator.register_event(self.workload, EventType.General, None, 1)
    
    def iterate_model_parallel(self):
        """
        模型并行迭代 - 对应C++函数
        void Workload::iterate_model_parallel()
        """
        assert 0 <= self.workload.index < self.workload.size
        self.workload.check_for_sim_end()
        
        if self.workload.current_state == LoopState.Forward_Pass:
            if not self.workload.layers[self.workload.index].is_weight_grad_comm_finished_blocking():
                return
            
            if not self.workload.delay_loaded:
                self.workload.counter = self.workload.layers[self.workload.index].get_fwd_pass_compute()
                self.workload.delay_loaded = True
            
            if self.workload.counter > 0:
                self.workload.generator.try_register_event(
                    self.workload, EventType.Workload_Wait, None, self.workload.counter)
                return
            
            if not self.workload.collective_issued:
                self.workload.collective_issued = True
                involved_dimensions = [True, True, True]
                self.workload.layers[self.workload.index].issue_forward_pass_comm(
                    SchedulingPolicy.None_, CollectiveBarrier.Blocking)
                return
            
            self.workload.index += 1
            self.workload.delay_loaded = False
            self.workload.collective_issued = False
            if self.workload.index >= self.workload.size:
                self.workload.current_state = LoopState.Input_Gradient
                self.workload.index -= 1
            
            self.workload.generator.register_event(self.workload, EventType.General, None, 1)
            return
            
        elif self.workload.current_state == LoopState.Weight_Gradient:
            if not self.workload.delay_loaded:
                self.workload.counter = self.workload.layers[self.workload.index].get_weight_grad_compute()
                self.workload.delay_loaded = True
            
            if self.workload.counter > 0:
                self.workload.generator.try_register_event(
                    self.workload, EventType.Workload_Wait, None, self.workload.counter)
                return
            
            if not self.workload.layers[self.workload.index].is_input_grad_comm_finished_blocking():
                return
            
            self.workload.collective_issued = False
            self.workload.delay_loaded = False
            if self.workload.index >= 0:
                self.workload.index -= 1
            if self.workload.index == -1:
                self.workload.index = 0
                if self.workload.generator.id == 0:
                    print(f"pass: {self.workload.pass_counter} finished at time: {self.workload.generator.get_tick()}")
                self.workload.pass_counter += 1
                self.workload.current_state = LoopState.Forward_Pass
            else:
                self.workload.current_state = LoopState.Input_Gradient
            
            self.workload.generator.register_event(self.workload, EventType.General, None, 1)
            return
            
        elif self.workload.current_state == LoopState.Input_Gradient:
            if not self.workload.delay_loaded:
                self.workload.counter = self.workload.layers[self.workload.index].get_input_grad_compute()
                self.workload.delay_loaded = True
            
            if self.workload.counter > 0:
                self.workload.generator.try_register_event(
                    self.workload, EventType.Workload_Wait, None, self.workload.counter)
                return
            
            if not self.workload.collective_issued and self.workload.index > 0:
                self.workload.collective_issued = True
                involved_dimensions = [True, True, True]
                self.workload.layers[self.workload.index].issue_input_grad_comm(
                    SchedulingPolicy.LIFO, CollectiveBarrier.Non_Blocking)
            
            self.workload.collective_issued = False
            self.workload.delay_loaded = False
            self.workload.current_state = LoopState.Weight_Gradient
            self.workload.generator.register_event(self.workload, EventType.General, None, 1)
            return
    
    def iterate_hybrid_parallel_data_model(self):
        """
        数据模型混合并行迭代 - 对应C++函数
        void Workload::iterate_hybrid_parallel_data_model()
        """
        assert 0 <= self.workload.index < self.workload.size
        self.workload.check_for_sim_end()
        
        if self.workload.current_state == LoopState.Forward_Pass:
            if not self.workload.layers[self.workload.index].is_weight_grad_comm_finished_blocking():
                return
            
            if not self.workload.delay_loaded:
                self.workload.counter = self.workload.layers[self.workload.index].get_fwd_pass_compute()
                self.workload.delay_loaded = True
            
            if self.workload.counter > 0:
                self.workload.generator.try_register_event(
                    self.workload, EventType.Workload_Wait, None, self.workload.counter)
                return
            
            if not self.workload.collective_issued:
                self.workload.collective_issued = True
                self.workload.layers[self.workload.index].issue_forward_pass_comm(
                    SchedulingPolicy.None_, CollectiveBarrier.Blocking)
                return
            
            self.workload.index += 1
            self.workload.delay_loaded = False
            self.workload.collective_issued = False
            if self.workload.index >= self.workload.size:
                self.workload.current_state = LoopState.Input_Gradient
                self.workload.index -= 1
            
            self.workload.generator.register_event(self.workload, EventType.General, None, 1)
            return
            
        elif self.workload.current_state == LoopState.Weight_Gradient:
            if not self.workload.delay_loaded:
                self.workload.counter = self.workload.layers[self.workload.index].get_weight_grad_compute()
                self.workload.delay_loaded = True
            
            if self.workload.counter > 0:
                self.workload.generator.try_register_event(
                    self.workload, EventType.Workload_Wait, None, self.workload.counter)
                return
            
            if not self.workload.collective_issued:
                self.workload.collective_issued = True
                self.workload.layers[self.workload.index].issue_weight_grad_comm(
                    SchedulingPolicy.FIFO, CollectiveBarrier.Non_Blocking)
            
            if not self.workload.layers[self.workload.index].is_input_grad_comm_finished_blocking():
                return
            
            self.workload.collective_issued = False
            self.workload.delay_loaded = False
            if self.workload.index >= 0:
                self.workload.index -= 1
            if self.workload.index == -1:
                self.workload.index = 0
                if self.workload.generator.id == 0:
                    print(f"pass: {self.workload.pass_counter} finished at time: {self.workload.generator.get_tick()}")
                self.workload.pass_counter += 1
                self.workload.current_state = LoopState.Forward_Pass
            else:
                self.workload.current_state = LoopState.Input_Gradient
            
            self.workload.generator.register_event(self.workload, EventType.General, None, 1)
            return
            
        elif self.workload.current_state == LoopState.Input_Gradient:
            if not self.workload.delay_loaded:
                self.workload.counter = self.workload.layers[self.workload.index].get_input_grad_compute()
                self.workload.delay_loaded = True
            
            if self.workload.counter > 0:
                self.workload.generator.try_register_event(
                    self.workload, EventType.Workload_Wait, None, self.workload.counter)
                return
            
            if not self.workload.collective_issued and self.workload.index > 0:
                self.workload.collective_issued = True
                self.workload.layers[self.workload.index].issue_input_grad_comm(
                    SchedulingPolicy.LIFO, CollectiveBarrier.Non_Blocking)
            
            self.workload.collective_issued = False
            self.workload.delay_loaded = False
            self.workload.current_state = LoopState.Weight_Gradient
            self.workload.generator.register_event(self.workload, EventType.General, None, 1)
            return
    
    def iterate_hybrid_parallel_model_data(self):
        """
        模型数据混合并行迭代 - 对应C++函数
        void Workload::iterate_hybrid_parallel_model_data()
        """
        assert 0 <= self.workload.index < self.workload.size
        self.workload.check_for_sim_end()
        
        if self.workload.current_state == LoopState.Forward_Pass:
            if not self.workload.layers[self.workload.index].is_weight_grad_comm_finished_blocking():
                return
            
            if not self.workload.delay_loaded:
                self.workload.counter = self.workload.layers[self.workload.index].get_fwd_pass_compute()
                self.workload.delay_loaded = True
            
            if self.workload.counter > 0:
                self.workload.generator.try_register_event(
                    self.workload, EventType.Workload_Wait, None, self.workload.counter)
                return
            
            if not self.workload.collective_issued:
                self.workload.collective_issued = True
                self.workload.layers[self.workload.index].issue_forward_pass_comm(
                    SchedulingPolicy.None_, CollectiveBarrier.Blocking)
                return
            
            self.workload.index += 1
            self.workload.delay_loaded = False
            self.workload.collective_issued = False
            if self.workload.index >= self.workload.size:
                self.workload.current_state = LoopState.Input_Gradient
                self.workload.index -= 1
            
            self.workload.generator.register_event(self.workload, EventType.General, None, 1)
            return
            
        elif self.workload.current_state == LoopState.Weight_Gradient:
            if not self.workload.delay_loaded:
                self.workload.counter = self.workload.layers[self.workload.index].get_weight_grad_compute()
                self.workload.delay_loaded = True
            
            if self.workload.counter > 0:
                self.workload.generator.try_register_event(
                    self.workload, EventType.Workload_Wait, None, self.workload.counter)
                return
            
            if not self.workload.collective_issued:
                self.workload.collective_issued = True
                self.workload.layers[self.workload.index].issue_weight_grad_comm(
                    SchedulingPolicy.FIFO, CollectiveBarrier.Non_Blocking)
            
            if not self.workload.layers[self.workload.index].is_input_grad_comm_finished_blocking():
                return
            
            self.workload.collective_issued = False
            self.workload.delay_loaded = False
            if self.workload.index >= 0:
                self.workload.index -= 1
            if self.workload.index == -1:
                self.workload.index = 0
                if self.workload.generator.id == 0:
                    print(f"pass: {self.workload.pass_counter} finished at time: {self.workload.generator.get_tick()}")
                self.workload.pass_counter += 1
                self.workload.current_state = LoopState.Forward_Pass
            else:
                self.workload.current_state = LoopState.Input_Gradient
            
            self.workload.generator.register_event(self.workload, EventType.General, None, 1)
            return
            
        elif self.workload.current_state == LoopState.Input_Gradient:
            if not self.workload.delay_loaded:
                self.workload.counter = self.workload.layers[self.workload.index].get_input_grad_compute()
                self.workload.delay_loaded = True
            
            if self.workload.counter > 0:
                self.workload.generator.try_register_event(
                    self.workload, EventType.Workload_Wait, None, self.workload.counter)
                return
            
            if not self.workload.collective_issued and self.workload.index > 0:
                self.workload.collective_issued = True
                self.workload.layers[self.workload.index].issue_input_grad_comm(
                    SchedulingPolicy.LIFO, CollectiveBarrier.Non_Blocking)
            
            self.workload.collective_issued = False
            self.workload.delay_loaded = False
            self.workload.current_state = LoopState.Weight_Gradient
            self.workload.generator.register_event(self.workload, EventType.General, None, 1)
            return
    
    def iterate_distributed_inference(self):
        """
        分布式推理迭代 - 对应C++函数
        void Workload::iterate_distributed_inference()
        """
        assert 0 <= self.workload.index < self.workload.size
        self.workload.check_for_sim_end()
        
        if self.workload.current_state == LoopState.Forward_Pass:
            if not self.workload.layers[self.workload.index].is_weight_grad_comm_finished_blocking():
                return
            
            if not self.workload.delay_loaded:
                self.workload.counter = self.workload.layers[self.workload.index].get_fwd_pass_compute()
                self.workload.delay_loaded = True
            
            if self.workload.counter > 0:
                self.workload.generator.try_register_event(
                    self.workload, EventType.Workload_Wait, None, self.workload.counter)
                return
            
            if not self.workload.collective_issued:
                self.workload.collective_issued = True
                self.workload.layers[self.workload.index].issue_forward_pass_comm(
                    SchedulingPolicy.None_, CollectiveBarrier.Blocking)
                return
            
            self.workload.index += 1
            self.workload.delay_loaded = False
            self.workload.collective_issued = False
            if self.workload.index >= self.workload.size:
                self.workload.index = 0
                self.workload.pass_counter += 1
            
            self.workload.generator.register_event(self.workload, EventType.General, None, 1)
            return
    
    def iterate_hybrid_parallel_transformer_fwd_in_bckwd(self):
        """
        Transformer前向反向混合并行迭代 - 对应C++函数
        void Workload::iterate_hybrid_parallel_Transformer_fwd_in_bckwd()
        """
        # 获取MockNcclLog实例 - 对应C++版本
        from system.mock_nccl_log import MockNcclLog, NcclLogLevel
        NcclLog = MockNcclLog.getInstance()
        
        # 添加边界检查，对应C++版本的断言
        assert 0 <= self.workload.index < self.workload.size
        self.workload.check_for_sim_end()
        NcclLog.writeLog(NcclLogLevel.INFO, f'Transformer前向反向混合并行迭代')
        NcclLog.writeLog(NcclLogLevel.INFO, f"进入WorkloadIterators迭代器 - 当前状态: {self.workload.current_state}, 层索引: {self.workload.index}, 总层数: {self.workload.size}")
        
        if self.workload.current_state == LoopState.Forward_Pass:
            NcclLog.writeLog(NcclLogLevel.INFO, f"处理前向传播阶段 - 层 {self.workload.index}")
            
            if not self.workload.layers[self.workload.index].is_weight_grad_comm_finished_blocking():
                NcclLog.writeLog(NcclLogLevel.INFO, f"等待层 {self.workload.index} 的权重梯度通信完成")
                return
            
            if not self.workload.delay_loaded:
                self.workload.counter = self.workload.layers[self.workload.index].get_fwd_pass_compute()
                self.workload.delay_loaded = True
                NcclLog.writeLog(NcclLogLevel.INFO, f"设置层 {self.workload.index} 前向计算时间: {self.workload.counter}")
            
            if self.workload.counter > 0:
                NcclLog.writeLog(NcclLogLevel.INFO, f"注册层 {self.workload.index} 前向计算等待事件，等待时间: {self.workload.counter}")
                self.workload.generator.try_register_event(
                    self.workload, EventType.Workload_Wait, None, self.workload.counter)
                return
            
            if not self.workload.collective_issued:
                self.workload.collective_issued = True
                # 调整通信大小（如果小于4096且大于0）
                if (self.workload.layers[self.workload.index].fwd_pass_comm_size < 4096 and 
                    self.workload.layers[self.workload.index].fwd_pass_comm_size > 0):
                    old_size = self.workload.layers[self.workload.index].fwd_pass_comm_size
                    self.workload.layers[self.workload.index].fwd_pass_comm_size = 4096
                    NcclLog.writeLog(NcclLogLevel.INFO, f"调整层 {self.workload.index} 前向通信大小: {old_size} -> 4096")
                
                NcclLog.writeLog(NcclLogLevel.INFO, f"发起层 {self.workload.index} 前向传播通信，大小: {self.workload.layers[self.workload.index].fwd_pass_comm_size}")
                self.workload.layers[self.workload.index].issue_forward_pass_comm(
                    SchedulingPolicy.None_, CollectiveBarrier.Blocking)
                return
            
            self.workload.index += 1
            self.workload.delay_loaded = False
            self.workload.collective_issued = False
            if self.workload.index >= self.workload.size:
                NcclLog.writeLog(NcclLogLevel.INFO, "前向传播阶段完成，切换到输入梯度阶段")
                self.workload.current_state = LoopState.Input_Gradient
                self.workload.index -= 1
            else:
                NcclLog.writeLog(NcclLogLevel.INFO, f"前向传播继续，移动到下一层: {self.workload.index}")
            
            # 添加日志记录 - 对应C++版本
            NcclLog.writeLog(NcclLogLevel.DEBUG, "workload::call fwd_pass register_event EventType::General ")
            
            self.workload.generator.register_event(self.workload, EventType.General, None, 1)
            return
            
        elif self.workload.current_state == LoopState.Weight_Gradient:
            NcclLog.writeLog(NcclLogLevel.INFO, f"处理权重梯度阶段 - 层 {self.workload.index}")
            
            if not self.workload.delay_loaded:
                self.workload.counter = self.workload.layers[self.workload.index].get_weight_grad_compute()
                self.workload.delay_loaded = True
                NcclLog.writeLog(NcclLogLevel.INFO, f"设置层 {self.workload.index} 权重梯度计算时间: {self.workload.counter}")
            
            if self.workload.counter > 0:
                NcclLog.writeLog(NcclLogLevel.INFO, f"注册层 {self.workload.index} 权重梯度计算等待事件，等待时间: {self.workload.counter}")
                self.workload.generator.try_register_event(
                    self.workload, EventType.Workload_Wait, None, self.workload.counter)
                return
            
            if not self.workload.collective_issued:
                self.workload.collective_issued = True
                NcclLog.writeLog(NcclLogLevel.INFO, f"发起层 {self.workload.index} 权重梯度通信")
                self.workload.layers[self.workload.index].issue_weight_grad_comm(
                    SchedulingPolicy.FIFO, CollectiveBarrier.Non_Blocking)
            
            if not self.workload.layers[self.workload.index].is_input_grad_comm_finished_blocking():
                NcclLog.writeLog(NcclLogLevel.INFO, f"等待层 {self.workload.index} 的输入梯度通信完成")
                return
            
            self.workload.collective_issued = False
            self.workload.delay_loaded = False
            if self.workload.index >= 0:
                self.workload.index -= 1
            if self.workload.index == -1:
                self.workload.index = 0
                if self.workload.generator.id == 0:
                    print(f"pass: {self.workload.pass_counter} finished at time: {self.workload.generator.get_tick()}")
                self.workload.pass_counter += 1
                self.workload.current_state = LoopState.Forward_Pass
                NcclLog.writeLog(NcclLogLevel.INFO, f"完成第 {self.workload.pass_counter-1} 轮训练，重置为前向传播阶段")
            else:
                self.workload.current_state = LoopState.Input_Gradient
                NcclLog.writeLog(NcclLogLevel.INFO, f"权重梯度完成，切换到输入梯度阶段，层: {self.workload.index}")
            
            self.workload.generator.register_event(self.workload, EventType.General, None, 1)
            return
            
        elif self.workload.current_state == LoopState.Input_Gradient:
            NcclLog.writeLog(NcclLogLevel.INFO, f"处理输入梯度阶段 - 层 {self.workload.index}")
            
            # 检查是否需要前向反向初始化
            if (self.workload.layers[self.workload.index].needs_fwd_in_bckwd_initiation and 
                not self.workload.checkpoint_initiated):
                tmp = self.workload.index
                while not self.workload.layers[self.workload.index].is_checkpoint:
                    self.workload.index -= 1
                self.workload.index += 1
                self.workload.current_state = LoopState.Forward_In_BackPass
                self.workload.checkpoint_initiated = True
                NcclLog.writeLog(NcclLogLevel.INFO, f"启动前向反向检查点机制，从层 {self.workload.index} 到层 {tmp}")
                self.workload.generator.register_event(self.workload, EventType.General, None, 1)
                if self.workload.generator.id == 0:
                    print(f"***** info, initiating fwd_in_bkwd starting from layer: "
                        f"{self.workload.index} to layer: {tmp}, at time: {self.workload.generator.get_tick()}")
                return
            
            if not self.workload.delay_loaded:
                self.workload.counter = self.workload.layers[self.workload.index].get_input_grad_compute()
                self.workload.delay_loaded = True
                NcclLog.writeLog(NcclLogLevel.INFO, f"设置层 {self.workload.index} 输入梯度计算时间: {self.workload.counter}")
            
            if self.workload.counter > 0:
                NcclLog.writeLog(NcclLogLevel.INFO, f"注册层 {self.workload.index} 输入梯度计算等待事件，等待时间: {self.workload.counter}")
                self.workload.generator.try_register_event(
                    self.workload, EventType.Workload_Wait, None, self.workload.counter)
                return
            
            if not self.workload.collective_issued:
                self.workload.collective_issued = True
                NcclLog.writeLog(NcclLogLevel.INFO, f"发起层 {self.workload.index} 输入梯度通信")
                self.workload.layers[self.workload.index].issue_input_grad_comm(
                    SchedulingPolicy.LIFO, CollectiveBarrier.Blocking)
                return
            
            self.workload.checkpoint_initiated = False
            self.workload.collective_issued = False
            self.workload.delay_loaded = False
            self.workload.current_state = LoopState.Weight_Gradient
            NcclLog.writeLog(NcclLogLevel.INFO, f"输入梯度完成，切换到权重梯度阶段，层: {self.workload.index}")
            self.workload.generator.register_event(self.workload, EventType.General, None, 1)
            return
            
        elif self.workload.current_state == LoopState.Forward_In_BackPass:
            NcclLog.writeLog(NcclLogLevel.INFO, f"处理反向传播中的前向阶段 - 层 {self.workload.index}")
            
            if not self.workload.layers[self.workload.index].is_weight_grad_comm_finished_blocking():
                NcclLog.writeLog(NcclLogLevel.INFO, f"等待层 {self.workload.index} 的权重梯度通信完成（反向前向阶段）")
                return
            
            if not self.workload.delay_loaded:
                self.workload.counter = self.workload.layers[self.workload.index].get_fwd_pass_compute()
                self.workload.delay_loaded = True
                NcclLog.writeLog(NcclLogLevel.INFO, f"设置层 {self.workload.index} 反向前向计算时间: {self.workload.counter}")
            
            if self.workload.counter > 0:
                NcclLog.writeLog(NcclLogLevel.INFO, f"注册层 {self.workload.index} 反向前向计算等待事件，等待时间: {self.workload.counter}")
                self.workload.generator.try_register_event(
                    self.workload, EventType.Workload_Wait, None, self.workload.counter)
                return
            
            if not self.workload.collective_issued:
                self.workload.collective_issued = True
                NcclLog.writeLog(NcclLogLevel.INFO, f"发起层 {self.workload.index} 反向前向通信")
                self.workload.layers[self.workload.index].issue_forward_pass_comm(
                    SchedulingPolicy.None_, CollectiveBarrier.Blocking)
                return
            
            self.workload.index += 1
            self.workload.delay_loaded = False
            self.workload.collective_issued = False
            # 添加边界检查 - 这是关键修复
            if self.workload.index < self.workload.size and self.workload.layers[self.workload.index].needs_fwd_in_bckwd_initiation:
                self.workload.current_state = LoopState.Input_Gradient
                NcclLog.writeLog(NcclLogLevel.INFO, f"反向前向阶段完成，返回输入梯度阶段，层: {self.workload.index}")
            else:
                NcclLog.writeLog(NcclLogLevel.INFO, f"反向前向阶段继续，移动到下一层: {self.workload.index}")
            
            self.workload.generator.register_event(self.workload, EventType.General, None, 1)
            return
    
    def iterate_hybrid_parallel_customized(self):
        """
        自定义混合并行迭代 - 对应C++函数
        void Workload::iterate_hybrid_parallel_customized()
        """
        assert 0 <= self.workload.index < self.workload.size
        self.workload.check_for_sim_end()
        
        if self.workload.current_state == LoopState.Forward_Pass:
            if not self.workload.layers[self.workload.index].is_weight_grad_comm_finished_blocking():
                return
            
            if not self.workload.delay_loaded:
                self.workload.counter = self.workload.layers[self.workload.index].get_fwd_pass_compute()
                self.workload.delay_loaded = True
            
            if self.workload.counter > 0:
                self.workload.generator.try_register_event(
                    self.workload, EventType.Workload_Wait, None, self.workload.counter)
                return
            
            if not self.workload.collective_issued:
                self.workload.collective_issued = True
                self.workload.layers[self.workload.index].issue_forward_pass_comm(
                    SchedulingPolicy.None_, CollectiveBarrier.Blocking)
                return
            
            self.workload.index += 1
            self.workload.delay_loaded = False
            self.workload.collective_issued = False
            if self.workload.index >= self.workload.size:
                self.workload.current_state = LoopState.Input_Gradient
                self.workload.index -= 1
            
            self.workload.generator.register_event(self.workload, EventType.General, None, 1)
            return
            
        elif self.workload.current_state == LoopState.Weight_Gradient:
            if not self.workload.delay_loaded:
                self.workload.counter = self.workload.layers[self.workload.index].get_weight_grad_compute()
                self.workload.delay_loaded = True
            
            if self.workload.counter > 0:
                self.workload.generator.try_register_event(
                    self.workload, EventType.Workload_Wait, None, self.workload.counter)
                return
            
            if not self.workload.collective_issued:
                self.workload.collective_issued = True
                self.workload.layers[self.workload.index].issue_weight_grad_comm(
                    SchedulingPolicy.FIFO, CollectiveBarrier.Non_Blocking)
            
            if not self.workload.layers[self.workload.index].is_input_grad_comm_finished_blocking():
                return
            
            self.workload.collective_issued = False
            self.workload.delay_loaded = False
            if self.workload.index >= 0:
                self.workload.index -= 1
            if self.workload.index == -1:
                self.workload.index = 0
                if self.workload.generator.id == 0:
                    print(f"pass: {self.workload.pass_counter} finished at time: {self.workload.generator.get_tick()}")
                self.workload.pass_counter += 1
                self.workload.current_state = LoopState.Forward_Pass
            else:
                self.workload.current_state = LoopState.Input_Gradient
            
            self.workload.generator.register_event(self.workload, EventType.General, None, 1)
            return
            
        elif self.workload.current_state == LoopState.Input_Gradient:
            if not self.workload.delay_loaded:
                self.workload.counter = self.workload.layers[self.workload.index].get_input_grad_compute()
                self.workload.delay_loaded = True
            
            if self.workload.counter > 0:
                self.workload.generator.try_register_event(
                    self.workload, EventType.Workload_Wait, None, self.workload.counter)
                return
            
            if not self.workload.collective_issued and self.workload.index > 0:
                self.workload.collective_issued = True
                self.workload.layers[self.workload.index].issue_input_grad_comm(
                    SchedulingPolicy.LIFO, CollectiveBarrier.Non_Blocking)
            
            self.workload.collective_issued = False
            self.workload.delay_loaded = False
            self.workload.current_state = LoopState.Weight_Gradient
            self.workload.generator.register_event(self.workload, EventType.General, None, 1)
            return 