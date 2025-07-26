# Layer事件处理模块 - 对应Layer.cc的call方法
#
# 对应关系：
# - call() -> Layer::call() 事件处理方法
# - _handle_weight_grad_comm_finished() -> Layer::call() 中处理 Wight_Grad_Comm_Finished_After_Delay 事件的部分
# - _handle_input_grad_comm_finished() -> Layer::call() 中处理 Input_Grad_Comm_Finished_After_Delay 事件的部分  
# - _handle_fwd_comm_finished() -> Layer::call() 中处理 Fwd_Comm_Finished_After_Delay 事件的部分
# - update_stream_stats() -> Layer::update_stream_stats()

from system.callable import CallData
from system.common import EventType, CollectiveBarrier
from system.dataset import DataSet


class LayerEvents:
    """Layer事件处理类 - 包含事件处理逻辑"""
    
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
            self._handle_weight_grad_comm_finished(data_id)
        elif event_type == EventType.Input_Grad_Comm_Finished_After_Delay:
            self._handle_input_grad_comm_finished(data_id)
        elif event_type == EventType.Fwd_Comm_Finished_After_Delay:
            self._handle_fwd_comm_finished(data_id)
    
    def _handle_weight_grad_comm_finished(self, data_id: int):
        """处理权重梯度通信完成事件"""
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
    
    def _handle_input_grad_comm_finished(self, data_id: int):
        """处理输入梯度通信完成事件"""
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
    
    def _handle_fwd_comm_finished(self, data_id: int):
        """处理前向传播通信完成事件"""
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
    
    def update_stream_stats(self, dataset: DataSet):
        """更新流统计信息 - 对应C++版本的update_stream_stats"""
        # 调用父类的update_stream_stats方法
        if hasattr(dataset, 'queuing_delay'):
            # 扩展queuing_delay列表以匹配dataset的大小
            while len(self.queuing_delay) < len(dataset.queuing_delay):
                self.queuing_delay.append(0)
            
            # 累加延迟数据
            for i, delay in enumerate(dataset.queuing_delay):
                if i < len(self.queuing_delay):
                    self.queuing_delay[i] += delay
            
            self.stream_stat_counter += 1 