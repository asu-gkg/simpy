# Workload报告器 - 对应Workload.cc中的报告功能
# 对应C++函数签名：
# - void Workload::report()

from typing import List, Dict, Any, Optional
from system.api import AstraSimDataAPI


class WorkloadReporting:
    """工作负载报告器 - 负责生成报告和统计信息"""
    
    def __init__(self, workload):
        """
        初始化报告器
        
        Args:
            workload: 工作负载对象
        """
        self.workload = workload
    
    def report(self):
        """
        生成报告 - 对应C++函数
        void Workload::report()
        """
        total_compute = 0.0
        total_exposed = 0.0
        
        # 分析相关变量
        pre_bubble_time = 0.0
        dp_comm = 0.0
        dp_ep_comm = 0.0
        expose_tp_comm = 0.0
        expose_ep_comm = 0.0
        
        # 时间统计向量
        total_fwd_time = [0.0, 0.0, 0.0]
        total_wg_time = [0.0, 0.0, 0.0]
        total_ig_time = [0.0, 0.0, 0.0]
        
        # 创建AstraSimDataAPI对象
        astra_sim_data_api = AstraSimDataAPI()
        astra_sim_data_api.run_name = self.workload.run_name
        astra_sim_data_api.workload_finished_time = self.workload.generator.get_tick() / self.workload.generator.freq
        
        print(f"workload stats for the job scheduled at NPU offset: {self.workload.generator.npu_offset}")
        
        # 收集每层的统计信息
        for i in range(self.workload.size):
            layer_stats = self.workload.layers[i].report(
                self.workload.run_name, i, self.workload.total_rows, self.workload.stat_row,
                self.workload.detailed, self.workload.end_to_end, total_compute, total_exposed,
                self.workload.separate_log, total_fwd_time, total_wg_time, total_ig_time,
                pre_bubble_time, dp_comm, dp_ep_comm, expose_tp_comm, expose_ep_comm
            )
            astra_sim_data_api.layers_stats.append(layer_stats)
        
        # 设置总统计信息
        astra_sim_data_api.total_compute = total_compute
        astra_sim_data_api.total_exposed_comm = total_exposed
        
        # 获取平均延迟信息
        astra_sim_data_api.avg_chunk_latency_per_logical_dimension = (
            self.workload.generator.scheduler_unit.get_average_latency_per_dimension()
        )
        
        # 转换延迟单位为秒
        for latency in astra_sim_data_api.avg_chunk_latency_per_logical_dimension:
            latency /= self.workload.generator.freq
        
        print("*************************")
        print(f"all passes finished at time: {self.workload.generator.get_tick()}, "
            f"id of first layer: {self.workload.layers[0].id}")
        
        # 调用网络接口的报告方法
        self.workload.generator.NI.pass_front_end_report(astra_sim_data_api)
        
        # 处理维度利用率报告
        if self.workload.separate_log:
            dims = []
            for i in range(len(self.workload.generator.scheduler_unit.usage)):
                dims.append(
                    self.workload.generator.scheduler_unit.usage[i].report_percentage(10000)
                )
            self.workload.dimension_utilization.finalize_csv(dims)