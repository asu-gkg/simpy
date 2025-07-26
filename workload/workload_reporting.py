# WorkloadReporting.py - corresponds to Workload::report() and related functions in SimAI 

from typing import List
from system.AstraSimDataAPI import AstraSimDataAPI, LayerData
from system.common import FREQ


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
        from system.mock_nccl_log import MockNcclLog, NcclLogLevel
        log = MockNcclLog.getInstance()
        
        log.writeLog(NcclLogLevel.INFO, f"📊 开始生成工作负载报告")
        
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
        
        log.writeLog(NcclLogLevel.INFO, f"📊 创建AstraSimDataAPI对象")
        
        # 创建AstraSimDataAPI对象
        astra_sim_data_api = AstraSimDataAPI()
        log.writeLog(NcclLogLevel.INFO, f"📊 AstraSimDataAPI对象创建成功")
        
        astra_sim_data_api.run_name = self.workload.run_name
        log.writeLog(NcclLogLevel.INFO, f"📊 设置run_name: {self.workload.run_name}")
        
        try:
            current_tick = self.workload.generator.get_tick()
            log.writeLog(NcclLogLevel.INFO, f"📊 获取当前tick: {current_tick}")
            
            log.writeLog(NcclLogLevel.INFO, f"📊 使用FREQ常量: {FREQ}")
            
            astra_sim_data_api.workload_finished_time = current_tick / FREQ
            log.writeLog(NcclLogLevel.INFO, f"📊 计算完成时间: {astra_sim_data_api.workload_finished_time}")
        except Exception as e:
            log.writeLog(NcclLogLevel.INFO, f"❌ 设置workload_finished_time失败: {e}")
            # 使用默认值
            astra_sim_data_api.workload_finished_time = 0.0
        
        print(f"workload stats for the job scheduled at NPU offset: {self.workload.generator.npu_offset}")
        
        log.writeLog(NcclLogLevel.INFO, f"📊 开始收集 {self.workload.size} 层的统计信息")
        
        # 收集每层的统计信息
        for i in range(self.workload.size):
            log.writeLog(NcclLogLevel.INFO, f"📊 处理第 {i} 层报告")
            try:
                layer_stats = self.workload.layers[i].report(
                    self.workload.run_name, i, self.workload.total_rows, self.workload.stat_row,
                    self.workload.detailed, self.workload.end_to_end, total_compute, total_exposed,
                    self.workload.separate_log, total_fwd_time, total_wg_time, total_ig_time,
                    pre_bubble_time, dp_comm, dp_ep_comm, expose_tp_comm, expose_ep_comm
                )
                astra_sim_data_api.layers_stats.append(layer_stats)
                
                # 手动累加计算时间（修复Python按值传递问题）
                layer = self.workload.layers[i]
                layer_fwd_time = layer.total_forward_pass_compute / FREQ
                layer_wg_time = layer.total_weight_grad_compute / FREQ  
                layer_ig_time = layer.total_input_grad_compute / FREQ
                total_compute += layer_fwd_time + layer_wg_time + layer_ig_time
                
                log.writeLog(NcclLogLevel.INFO, f"✅ 第 {i} 层报告完成，累计时间: {total_compute}")
            except Exception as e:
                log.writeLog(NcclLogLevel.INFO, f"❌ 第 {i} 层报告失败: {e}")
                raise
        
        log.writeLog(NcclLogLevel.INFO, f"📊 设置总统计信息")
        
        # 设置总统计信息
        astra_sim_data_api.total_compute = total_compute
        astra_sim_data_api.total_exposed_comm = total_exposed
        
        log.writeLog(NcclLogLevel.INFO, f"📊 获取平均延迟信息")
        
        # 获取平均延迟信息
        astra_sim_data_api.avg_chunk_latency_per_logical_dimension = (
            self.workload.generator.scheduler_unit.get_average_latency_per_dimension()
        )
        
        # 转换延迟单位为秒
        for i, latency in enumerate(astra_sim_data_api.avg_chunk_latency_per_logical_dimension):
            astra_sim_data_api.avg_chunk_latency_per_logical_dimension[i] = latency / FREQ
        
        print("*************************")
        print(f"all passes finished at time: {self.workload.generator.get_tick()}, "
            f"id of first layer: {self.workload.layers[0].id}")
        
        log.writeLog(NcclLogLevel.INFO, f"📊 调用网络接口报告")
        
        # 调用网络接口的报告方法
        self.workload.generator.NI.pass_front_end_report(astra_sim_data_api)
        
        log.writeLog(NcclLogLevel.INFO, f"📊 处理维度利用率报告, separate_log={self.workload.separate_log}")
        
        # 处理维度利用率报告
        if self.workload.separate_log:
            try:
                dims = []
                usage_count = len(self.workload.generator.scheduler_unit.usage)
                log.writeLog(NcclLogLevel.INFO, f"📊 有 {usage_count} 个使用维度")
                
                for i in range(usage_count):
                    percentage_data = self.workload.generator.scheduler_unit.usage[i].report_percentage(10000)
                    log.writeLog(NcclLogLevel.INFO, f"📊 维度 {i} 报告数据长度: {len(percentage_data)}")
                    dims.append(percentage_data)
                
                log.writeLog(NcclLogLevel.INFO, f"📊 开始写入dimension_utilization CSV")
                self.workload.dimension_utilization.finalize_csv(dims)
                log.writeLog(NcclLogLevel.INFO, f"✅ dimension_utilization CSV写入完成")
            except Exception as e:
                log.writeLog(NcclLogLevel.INFO, f"❌ 维度利用率报告失败: {e}")
                raise
        
        log.writeLog(NcclLogLevel.INFO, f"🎊 工作负载报告生成完成！")