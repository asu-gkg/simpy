# Layer通信模块 - 对应Layer.cc的通信发起方法
#
# 对应关系：
# - issue_forward_pass_comm() -> Layer::issue_forward_pass_comm()
# - issue_input_grad_comm() -> Layer::issue_input_grad_comm()
# - issue_weight_grad_comm() -> Layer::issue_weight_grad_comm()

from system.common import ComType, SchedulingPolicy, CollectiveBarrier, EventType
from system.mock_nccl_group import GroupType
from system.mock_nccl_log import MockNcclLog, NcclLogLevel


class LayerCommunication:
    """Layer通信类 - 包含通信发起逻辑"""
    
    def print_involved_dimensions(self, dimensions):
        """打印涉及的维度信息 - 对应C++版本的print_involved_dimensions函数"""
        if self.generator.id == 0:
            dim_str = ", ".join([f"dim{i}" for i, enabled in enumerate(dimensions) if enabled])
            print(f" involved dimensions: [{dim_str}]")
    
    def issue_forward_pass_comm(self, pref_scheduling: SchedulingPolicy,
                            barrier: CollectiveBarrier):
        """发起前向传播通信 - 精准复现C++版本逻辑"""
        # 添加 MockNcclLog 支持
        nccl_log = MockNcclLog.getInstance()

        # 分析模式处理 (对应 #ifdef ANALYTI)
        if hasattr(self.generator, 'analytical_mode') and self.generator.analytical_mode:
            self.fwd_barrier = barrier
            if self.generator.id == 0:
                nccl_log.writeLog(NcclLogLevel.DEBUG, 
                                  f"forward pass for layer {self.id} is analytical")
                nccl_log.writeLog(NcclLogLevel.DEBUG, 
                                  f"forward pass for layer-id {self.layer_num} is analytical")
            if barrier == CollectiveBarrier.Blocking:
                self.workload.call(EventType.General, None)
            return

        # 实际通信逻辑
        fp = None
        self.fwd_barrier = barrier
        self.collective_counter += 1

        if self.fwd_pass_comm_type == ComType.All_Reduce:
            # 检查是否启用PHY_MTP模式
            if hasattr(self.generator, 'phy_mtp_mode') and self.generator.phy_mtp_mode:
                fp = self.generator.generate_all_reduce(
                    self.fwd_pass_comm_size,
                    self.fwd_pass_comm_involved_dimensions,
                    pref_scheduling,
                    self.layer_num,
                    EventType.Fwd_Comm_Finished,
                    self)
            else:
                fp = self.generator.generate_all_reduce(
                    self.fwd_pass_comm_size,
                    self.fwd_pass_comm_involved_dimensions,
                    pref_scheduling,
                    self.layer_num)
        elif self.fwd_pass_comm_type == ComType.All_to_All:
            if hasattr(self.generator, 'phy_mtp_mode') and self.generator.phy_mtp_mode:
                fp = self.generator.generate_all_to_all(
                    self.fwd_pass_comm_size,
                    self.fwd_pass_comm_involved_dimensions,
                    pref_scheduling,
                    self.layer_num,
                    EventType.Fwd_Comm_Finished,
                    self)
            else:
                fp = self.generator.generate_all_to_all(
                    self.fwd_pass_comm_size,
                    self.fwd_pass_comm_involved_dimensions,
                    pref_scheduling,
                    self.layer_num)
        elif self.fwd_pass_comm_type == ComType.All_Gather:
            if hasattr(self.generator, 'phy_mtp_mode') and self.generator.phy_mtp_mode:
                fp = self.generator.generate_all_gather(
                    self.fwd_pass_comm_size,
                    self.fwd_pass_comm_involved_dimensions,
                    pref_scheduling,
                    self.layer_num,
                    EventType.Fwd_Comm_Finished,
                    self)
            else:
                fp = self.generator.generate_all_gather(
                    self.fwd_pass_comm_size,
                    self.fwd_pass_comm_involved_dimensions,
                    pref_scheduling,
                    self.layer_num)
        elif self.fwd_pass_comm_type == ComType.Reduce_Scatter:
            if hasattr(self.generator, 'phy_mtp_mode') and self.generator.phy_mtp_mode:
                fp = self.generator.generate_reduce_scatter(
                    self.fwd_pass_comm_size,
                    self.fwd_pass_comm_involved_dimensions,
                    pref_scheduling,
                    self.layer_num,
                    EventType.Fwd_Comm_Finished,
                    self)
            else:
                fp = self.generator.generate_reduce_scatter(
                    self.fwd_pass_comm_size,
                    self.fwd_pass_comm_involved_dimensions,
                    pref_scheduling,
                    self.layer_num)
        elif self.fwd_pass_comm_type == ComType.None_:
            self.collective_counter -= 1
            if self.generator.id == 0:
                print(f"info: no forward pass collective for layer: {self.id}")
            if barrier == CollectiveBarrier.Blocking:
                self.workload.call(EventType.General, None)
            return
        else:
            from ..system.sys import Sys
            Sys.sys_panic("no known collective operation!")

        # 检查数据集是否激活
        if fp and not fp.active:
            if self.generator.id == 0:
                print(f"info: all dims disabled, no forward pass collective for layer: {self.id}")
            self.collective_counter -= 1
            del fp
            if barrier == CollectiveBarrier.Blocking:
                self.workload.call(EventType.General, None)
            return

        # 添加详细的日志输出
        if fp and self.generator.id == 0:
            if self.fwd_pass_comm_type == ComType.All_Reduce:
                print(f"info: all-reduce forward pass collective issued for layer: {self.id},", end="")
            elif self.fwd_pass_comm_type == ComType.All_to_All:
                print(f"info: all-to-all forward pass collective issued for layer: {self.id},", end="")
            elif self.fwd_pass_comm_type == ComType.All_Gather:
                print(f"info: all-gather forward pass collective issued for layer: {self.id},", end="")
            elif self.fwd_pass_comm_type == ComType.Reduce_Scatter:
                print(f"info: reduce-scatter forward pass collective issued for layer: {self.id},", end="")
            self.print_involved_dimensions(self.fwd_pass_comm_involved_dimensions)

        # 存储数据集并设置通知器
        if fp:
            if not (hasattr(self.generator, 'phy_mtp_mode') and self.generator.phy_mtp_mode):
                self.fwd_pass_datasets[fp.my_id] = fp
                fp.set_notifier(self, EventType.Fwd_Comm_Finished)
        
        nccl_log.writeLog(NcclLogLevel.DEBUG, "Fwd_Comm_Finished set_notifier success")
    
    def issue_input_grad_comm(self, pref_scheduling: SchedulingPolicy,
                            barrier: CollectiveBarrier):
        """发起输入梯度通信 - 精准复现C++版本逻辑"""
        # 添加 MockNcclLog 支持
        nccl_log = MockNcclLog.getInstance()
        
        # 分析模式处理
        if hasattr(self.generator, 'analytical_mode') and self.generator.analytical_mode:
            self.ig_barrier = barrier
            if self.generator.id == 0:
                nccl_log.writeLog(NcclLogLevel.DEBUG, 
                                  f"input grad collective for layer {self.id} is analytical")
                nccl_log.writeLog(NcclLogLevel.DEBUG, 
                                  f"input grad collective for layer-id {self.layer_num} is analytical")
            if barrier == CollectiveBarrier.Blocking:
                self.workload.call(EventType.General, None)
            return

        # 实际通信逻辑
        ig = None
        self.ig_barrier = barrier
        self.collective_counter += 1

        if self.input_grad_comm_type == ComType.All_Reduce:
            if hasattr(self.generator, 'phy_mtp_mode') and self.generator.phy_mtp_mode:
                ig = self.generator.generate_all_reduce(
                    self.input_grad_comm_size,
                    self.input_grad_comm_involved_dimensions,
                    pref_scheduling,
                    self.layer_num,
                    EventType.Input_Grad_Comm_Finished,
                    self)
            else:
                ig = self.generator.generate_all_reduce(
                    self.input_grad_comm_size,
                    self.input_grad_comm_involved_dimensions,
                    pref_scheduling,
                    self.layer_num)
        elif self.input_grad_comm_type == ComType.All_to_All:
            if hasattr(self.generator, 'phy_mtp_mode') and self.generator.phy_mtp_mode:
                ig = self.generator.generate_all_to_all(
                    self.input_grad_comm_size,
                    self.input_grad_comm_involved_dimensions,
                    pref_scheduling,
                    self.layer_num,
                    EventType.Input_Grad_Comm_Finished,
                    self)
            else:
                ig = self.generator.generate_all_to_all(
                    self.input_grad_comm_size,
                    self.input_grad_comm_involved_dimensions,
                    pref_scheduling,
                    self.layer_num)
        elif self.input_grad_comm_type == ComType.All_Gather:
            if hasattr(self.generator, 'phy_mtp_mode') and self.generator.phy_mtp_mode:
                ig = self.generator.generate_all_gather(
                    self.input_grad_comm_size,
                    self.input_grad_comm_involved_dimensions,
                    pref_scheduling,
                    self.layer_num,
                    EventType.Input_Grad_Comm_Finished,
                    self)
            else:
                ig = self.generator.generate_all_gather(
                    self.input_grad_comm_size,
                    self.input_grad_comm_involved_dimensions,
                    pref_scheduling,
                    self.layer_num)
        elif self.input_grad_comm_type == ComType.Reduce_Scatter:
            if hasattr(self.generator, 'phy_mtp_mode') and self.generator.phy_mtp_mode:
                ig = self.generator.generate_reduce_scatter(
                    self.input_grad_comm_size,
                    self.input_grad_comm_involved_dimensions,
                    pref_scheduling,
                    self.layer_num,
                    EventType.Input_Grad_Comm_Finished,
                    self)
            else:
                ig = self.generator.generate_reduce_scatter(
                    self.input_grad_comm_size,
                    self.input_grad_comm_involved_dimensions,
                    pref_scheduling,
                    self.layer_num)
        elif self.input_grad_comm_type == ComType.None_:
            self.collective_counter -= 1
            if self.generator.id == 0:
                print(f"info: no input grad collective for layer: {self.id}")
            if barrier == CollectiveBarrier.Blocking:
                self.workload.call(EventType.General, None)
            return
        else:
            from ..system.sys import Sys
            Sys.sys_panic("no known collective operation!")

        # 检查数据集是否激活
        if ig and not ig.active:
            if self.generator.id == 0:
                print(f"info: all dims disabled, no input grad collective for layer: {self.id}")
            self.collective_counter -= 1
            del ig
            if barrier == CollectiveBarrier.Blocking:
                self.workload.call(EventType.General, None)
            return

        # 添加详细的日志输出
        if ig and self.generator.id == 0:
            if self.input_grad_comm_type == ComType.All_Reduce:
                print(f"info: all-reduce input grad collective issued for layer: {self.id},", end="")
            elif self.input_grad_comm_type == ComType.All_to_All:
                print(f"info: all-to-all input grad collective issued for layer: {self.id},", end="")
            elif self.input_grad_comm_type == ComType.All_Gather:
                print(f"info: all-gather input grad collective issued for layer: {self.id},", end="")
            elif self.input_grad_comm_type == ComType.Reduce_Scatter:
                print(f"info: reduce-scatter input grad collective issued for layer: {self.id},", end="")
            self.print_involved_dimensions(self.input_grad_comm_involved_dimensions)

        # 存储数据集并设置通知器
        if ig:
            if not (hasattr(self.generator, 'phy_mtp_mode') and self.generator.phy_mtp_mode):
                self.input_grad_datasets[ig.my_id] = ig
                ig.set_notifier(self, EventType.Input_Grad_Comm_Finished)
    
    def issue_weight_grad_comm(self, pref_scheduling: SchedulingPolicy,
                            barrier: CollectiveBarrier):
        """发起权重梯度通信 - 精准复现C++版本逻辑"""
        # 添加 MockNcclLog 支持
        nccl_log = MockNcclLog.getInstance()
        
        # 分析模式处理
        if hasattr(self.generator, 'analytical_mode') and self.generator.analytical_mode:
            self.wg_barrier = barrier
            if self.generator.id == 0:
                nccl_log.writeLog(NcclLogLevel.DEBUG, 
                                  f"weight grad collective for layer {self.id} is analytical")
                nccl_log.writeLog(NcclLogLevel.DEBUG, 
                                  f"weight grad collective for layer-id {self.layer_num} is analytical")
            if barrier == CollectiveBarrier.Blocking:
                self.workload.call(EventType.General, None)
            return

        # 实际通信逻辑
        wg = None
        self.wg_barrier = barrier
        self.collective_counter += 1

        if self.weight_grad_comm_type == ComType.All_Reduce:
            if hasattr(self.generator, 'phy_mtp_mode') and self.generator.phy_mtp_mode:
                wg = self.generator.generate_all_reduce(
                    self.weight_grad_comm_size,
                    self.weight_grad_comm_involved_dimensions,
                    pref_scheduling,
                    self.layer_num,
                    EventType.Wight_Grad_Comm_Finished,
                    self)
            else:
                wg = self.generator.generate_all_reduce(
                    self.weight_grad_comm_size,
                    self.weight_grad_comm_involved_dimensions,
                    pref_scheduling,
                    self.layer_num)
        elif self.weight_grad_comm_type == ComType.All_to_All:
            if hasattr(self.generator, 'phy_mtp_mode') and self.generator.phy_mtp_mode:
                wg = self.generator.generate_all_to_all(
                    self.weight_grad_comm_size,
                    self.weight_grad_comm_involved_dimensions,
                    pref_scheduling,
                    self.layer_num,
                    EventType.Wight_Grad_Comm_Finished,
                    self)
            else:
                wg = self.generator.generate_all_to_all(
                    self.weight_grad_comm_size,
                    self.weight_grad_comm_involved_dimensions,
                    pref_scheduling,
                    self.layer_num)
        elif self.weight_grad_comm_type == ComType.All_Gather:
            if self.generator.id == 0:
                print(f"Layer issue wg all gather at tick: {self.generator.get_tick()}")
            if hasattr(self.generator, 'phy_mtp_mode') and self.generator.phy_mtp_mode:
                wg = self.generator.generate_all_gather(
                    self.weight_grad_comm_size,
                    self.weight_grad_comm_involved_dimensions,
                    pref_scheduling,
                    self.layer_num,
                    EventType.Wight_Grad_Comm_Finished,
                    self)
            else:
                wg = self.generator.generate_all_gather(
                    self.weight_grad_comm_size,
                    self.weight_grad_comm_involved_dimensions,
                    pref_scheduling,
                    self.layer_num)
        elif self.weight_grad_comm_type == ComType.Reduce_Scatter:
            if hasattr(self.generator, 'phy_mtp_mode') and self.generator.phy_mtp_mode:
                wg = self.generator.generate_reduce_scatter(
                    self.weight_grad_comm_size,
                    self.weight_grad_comm_involved_dimensions,
                    pref_scheduling,
                    self.layer_num,
                    EventType.Wight_Grad_Comm_Finished,
                    self)
            else:
                wg = self.generator.generate_reduce_scatter(
                    self.weight_grad_comm_size,
                    self.weight_grad_comm_involved_dimensions,
                    pref_scheduling,
                    self.layer_num)
        elif self.weight_grad_comm_type == ComType.None_:
            self.collective_counter -= 1
            if self.generator.id == 0:
                print(f"info: no weight grad collective for layer: {self.id}")
            if barrier == CollectiveBarrier.Blocking:
                self.workload.call(EventType.General, None)
            return
        else:
            from ..system.sys import Sys
            Sys.sys_panic("no known collective operation!")

        # 检查数据集是否激活
        if wg and not wg.active:
            if self.generator.id == 0:
                print(f"info: all dims disabled, no weight grad collective for layer: {self.id}")
            self.collective_counter -= 1
            del wg
            if barrier == CollectiveBarrier.Blocking:
                self.workload.call(EventType.General, None)
            return

        # 添加详细的日志输出
        if wg and self.generator.id == 0:
            if self.weight_grad_comm_type == ComType.All_Reduce:
                print(f"info: all-reduce weight grad collective issued for layer: {self.id} with size: {self.weight_grad_comm_size},", end="")
            elif self.weight_grad_comm_type == ComType.All_to_All:
                print(f"info: all-to-all weight grad collective issued for layer: {self.id} with size: {self.weight_grad_comm_size},", end="")
            elif self.weight_grad_comm_type == ComType.All_Gather:
                print(f"info: all-gather weight grad collective issued for layer: {self.id},", end="")
            elif self.weight_grad_comm_type == ComType.Reduce_Scatter:
                print(f"info: reduce-scatter weight grad collective issued for layer: {self.id},", end="")
            self.print_involved_dimensions(self.weight_grad_comm_involved_dimensions)

        # 存储数据集并设置通知器
        if wg:
            if not (hasattr(self.generator, 'phy_mtp_mode') and self.generator.phy_mtp_mode):
                self.weight_grad_datasets[wg.my_id] = wg
                wg.set_notifier(self, EventType.Wight_Grad_Comm_Finished) 