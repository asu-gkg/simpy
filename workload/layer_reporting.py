# Layer报告模块 - 对应Layer.cc的报告和统计方法
#
# 对应关系：
# - report() -> Layer::report() (第一个重载版本，16个参数)
# - report_simple() -> Layer::report() (第二个重载版本，9个参数)
# - take_stream_stats_average() -> Layer::take_stream_stats_average()
# - _calculate_group_size() -> 辅助方法，用于计算组大小

from typing import List
from system.api import LayerData
from system.mock_nccl_group import GroupType
from system.common import ComType
from system.param_parser import UserParam, ModeType
from system.common import GBps as GBPS
from system.common import FREQ


class LayerReporting:
    """Layer报告类 - 包含报告生成和统计逻辑"""
    
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
        # 计算组大小
        tp_size = self.workload.model_parallel_npu_group
        pp_size = self.workload.pipeline_model_parallelism
        dp_size = self.workload.all_gpus // (tp_size * pp_size)
        ep_size = self.workload.expert_parallel_npu_group
        
        # 计算组大小
        fwd_pass_group_size = self._calculate_group_size(self.fwd_pass_group_type, tp_size, dp_size, ep_size)
        weight_grad_group_size = self._calculate_group_size(self.weight_grad_group_type, tp_size, dp_size, ep_size)
        input_grad_group_size = self._calculate_group_size(self.input_grad_group_type, tp_size, dp_size, ep_size)
        
        # 获取用户参数实例
        param = UserParam.getInstance()
        
        # 气泡时间计算（对应C++版本的embedding_layer检查）
        if self.id != "embedding_layer":
            pre_bubble_time += ((self.total_waiting_for_fwd_comm + self.total_forward_pass_compute + 
                                self.total_weight_grad_compute + self.total_input_grad_compute + 
                                self.total_waiting_for_ig_comm) / FREQ)
        
        # DP通信时间计算（精准复现C++版本的重叠比率处理）
        if self.weight_grad_group_type == GroupType.DP_EP:
            self.total_waiting_for_wg_comm *= (1 - param.net_work_param.dp_overlap_ratio)
            dp_ep_comm += (self.total_waiting_for_wg_comm / FREQ)
        else:
            self.total_waiting_for_wg_comm *= (1 - param.net_work_param.dp_overlap_ratio)
            dp_comm += (self.total_waiting_for_wg_comm / FREQ)
        
        # TP/EP通信时间计算（精准复现C++版本的重叠比率处理）
        if self.fwd_pass_group_type == GroupType.EP:
            self.total_waiting_for_fwd_comm *= (1 - param.net_work_param.ep_overlap_ratio)
            self.total_waiting_for_ig_comm *= (1 - param.net_work_param.ep_overlap_ratio)
            expose_ep_comm += ((self.total_waiting_for_fwd_comm + self.total_waiting_for_ig_comm) / FREQ)
        else:
            self.total_waiting_for_fwd_comm *= (1 - param.net_work_param.tp_overlap_ratio)
            self.total_waiting_for_ig_comm *= (1 - param.net_work_param.tp_overlap_ratio)
            expose_tp_comm += ((self.total_waiting_for_fwd_comm + self.total_waiting_for_ig_comm) / FREQ)
        
        # 计算总时间（转换为秒）
        layer_fwd_time = self.total_forward_pass_compute / FREQ
        layer_wg_time = self.total_weight_grad_compute / FREQ
        layer_ig_time = self.total_input_grad_compute / FREQ
        
        # 注意：total_compute现在在workload_reporting中累加，避免Python按值传递问题
        # total_exposed应该累加等待时间，而不是实际通信时间（与C++版本保持一致）
        total_exposed += (self.total_waiting_for_fwd_comm + self.total_waiting_for_wg_comm + 
                        self.total_waiting_for_ig_comm) / FREQ
        
        # 更新传入的列表（对应C++版本的数组更新）
        total_fwd_time[0] += layer_fwd_time
        total_fwd_time[1] += self.total_waiting_for_fwd_comm / FREQ
        total_fwd_time[2] += self.total_fwd_comm / FREQ
        total_wg_time[0] += layer_wg_time
        total_wg_time[1] += self.total_waiting_for_wg_comm / FREQ
        total_wg_time[2] += self.total_weight_grad_comm / FREQ
        total_ig_time[0] += layer_ig_time
        total_ig_time[1] += self.total_waiting_for_ig_comm / FREQ
        total_ig_time[2] += self.total_input_grad_comm / FREQ
        
        # 创建LayerData对象
        layer_data = LayerData()
        layer_data.layer_name = self.id
        layer_data.total_forward_pass_compute = layer_fwd_time
        layer_data.total_weight_grad_compute = layer_wg_time
        layer_data.total_input_grad_compute = layer_ig_time
        layer_data.total_waiting_for_fwd_comm = self.total_waiting_for_fwd_comm / FREQ
        layer_data.total_waiting_for_wg_comm = self.total_waiting_for_wg_comm / FREQ
        layer_data.total_waiting_for_ig_comm = self.total_waiting_for_ig_comm / FREQ
        layer_data.total_fwd_comm = self.total_fwd_comm / FREQ
        layer_data.total_weight_grad_comm = self.total_weight_grad_comm / FREQ
        layer_data.total_input_grad_comm = self.total_input_grad_comm / FREQ
        
        # 填充队列延迟和网络消息延迟的统计
        layer_data.avg_queuing_delay = []
        for i, delay in enumerate(self.queuing_delay):
            layer_data.avg_queuing_delay.append((i, delay / FREQ))
        
        layer_data.avg_network_message_delay = []
        for i, delay in enumerate(self.net_message_latency):
            layer_data.avg_network_message_delay.append((i + 1, delay / FREQ))
        
        # 分离日志输出 - 精准复现C++版本
        if separate_log:
            print("*******************")
            print(f"Layer id: {self.id}")
            print(f"Total collectives issued for this layer: {self.collective_counter}")
            print(f"************************* Workload stats ************************* {self.id}")
            
            # CSV 头部 - 精准复现C++版本格式
            if stat_row == 0 and layer_num == 0:
                header = f"layer_name,{run_name},fwd compute,wg compute,ig compute,fwd exposed comm,wg exposed comm,ig exposed comm,fwd total comm,algbw,busbw,wg total comm,algbw,busbw,ig total comm,algbw,busbw,workload finished at"
                end_to_end.write_line(header)
            
            # 数据行
            data = ""
            if stat_row == 0:
                data += self.id
            
            data += f",{run_name}"
            
            print(f"id: {self.id} ,Total cycles spent on fwd pass compute: {self.total_forward_pass_compute}")
            data += f",{layer_fwd_time:.6f}"
            
            print(f"id: {self.id} ,Total cycles spent on weight grad compute: {self.total_weight_grad_compute}")
            data += f",{layer_wg_time:.6f}"
            
            print(f"id: {self.id} ,Total cycles spent on input grad compute: {self.total_input_grad_compute}")
            data += f",{layer_ig_time:.6f}"
            
            print(f"id: {self.id} ,Total cycles spent idle waiting for fwd finish: {self.total_waiting_for_fwd_comm}")
            data += f",{self.total_waiting_for_fwd_comm / FREQ:.6f}"
            
            print(f"id: {self.id} ,Total cycles spent idle waiting for weight grad finish: {self.total_waiting_for_wg_comm}")
            data += f",{self.total_waiting_for_wg_comm / FREQ:.6f}"
            
            print(f"id: {self.id} ,Total cycles spent idle waiting for input grad finish: {self.total_waiting_for_ig_comm}")
            data += f",{self.total_waiting_for_ig_comm / FREQ:.6f}"
            
            print(f"id: {self.id} ,Total cycles spent on fwd pass comm: {self.total_fwd_comm}")
            
            # 计算带宽
            fwd_bw = self.compute_busbw(self.fwd_pass_comm_type, fwd_pass_group_size,
                                       self.fwd_pass_comm_size, self.total_fwd_comm)
            data += f",{self.total_fwd_comm / FREQ:.6f},{fwd_bw[0]:.2f},{fwd_bw[1]:.2f}"
            
            print(f"id: {self.id} ,Total cycles spent on weight grad comm: {self.total_weight_grad_comm}")
            wg_bw = self.compute_busbw(self.weight_grad_comm_type, weight_grad_group_size,
                                      self.weight_grad_comm_size, self.total_weight_grad_comm)
            data += f",{self.total_weight_grad_comm / FREQ:.6f},{wg_bw[0]:.2f},{wg_bw[1]:.2f}"
            
            print(f"id: {self.id} ,Total cycles spent on input grad comm: {self.total_input_grad_comm}")
            ig_bw = self.compute_busbw(self.input_grad_comm_type, input_grad_group_size,
                                      self.input_grad_comm_size, self.total_input_grad_comm)
            data += f",{self.total_input_grad_comm / FREQ:.6f},{ig_bw[0]:.2f},{ig_bw[1]:.2f}"
            
            # 添加workload finished at时间
            data += f",{self.generator.get_tick() / FREQ:.6f}"
            
            end_to_end.write_line(data)
            
            # 最后一层的总结
            if layer_num == self.workload.size - 1:
                # 使用正确的total_exposed计算方法：累加等待时间，而不是用总时间减法
                # total_exposed应该等于所有层的等待通信时间总和
                actual_total_exposed = total_fwd_time[1] + total_wg_time[1] + total_ig_time[1]
                
                # 写入SUM行
                sum_data = f"SUM,{run_name},{total_fwd_time[0]:.6f},{total_wg_time[0]:.6f},{total_ig_time[0]:.6f},{total_fwd_time[1]:.6f},{total_wg_time[1]:.6f},{total_ig_time[1]:.6f},{total_fwd_time[2]:.6f},NONE,NONE,{total_wg_time[2]:.6f},NONE,NONE,{total_ig_time[2]:.6f},NONE,NONE"
                end_to_end.write_line(sum_data)
                
                # 计算正确的总计算时间（使用累加的数组值）
                actual_total_compute = total_fwd_time[0] + total_wg_time[0] + total_ig_time[0]
                total_time = actual_total_compute + actual_total_exposed
                summary_data = f"total exposed comm,{actual_total_exposed:.6f},total comp,{actual_total_compute:.6f},total time,{total_time:.6f}"
                end_to_end.write_line(summary_data)
        
        return layer_data

    def report_simple(self, run_name: str, layer_num: int, total_rows: int, stat_row: int,
                     detailed, end_to_end, total_compute: float, total_exposed: float,
                     pre_bubble_time: float, dp_comm: float, dp_ep_comm: float,
                     expose_tp_comm: float, expose_ep_comm: float, separate_log: bool) -> LayerData:
        """
        生成层报告 - 第二个重载版本（9个参数版本）
        对应C++版本的第二个report重载
        """
        layer_data = LayerData()
        self.take_stream_stats_average()

        # 获取并行配置
        tp_size = self.workload.model_parallel_npu_group
        pp_size = self.workload.pipeline_model_parallelism
        vpp = self.workload.vpp
        pp_commsize = self.workload.pp_commsize
        dp_size = self.generator.all_gpus[0] // (tp_size * pp_size)
        ga = self.workload.GA
        ep_size = self.workload.expert_parallel_npu_group

        # 计算组大小
        fwd_pass_group_size = self._calculate_group_size(self.fwd_pass_group_type, tp_size, dp_size, ep_size)
        weight_grad_group_size = self._calculate_group_size(self.weight_grad_group_type, tp_size, dp_size, ep_size)
        input_grad_group_size = self._calculate_group_size(self.input_grad_group_type, tp_size, dp_size, ep_size)

        # 获取用户参数实例
        param = UserParam.getInstance()

        # Analytical Mode处理 - 精准复现C++版本
        if param.mode == ModeType.ANALYTICAL:
            self.total_fwd_comm = self.compute_time(self.fwd_pass_comm_type, tp_size, fwd_pass_group_size,
                                                   self.fwd_pass_comm_size, self.fwd_pass_group_type,
                                                   self.generator.all_gpus[0], ep_size)
            self.total_weight_grad_comm = self.compute_time(self.weight_grad_comm_type, tp_size, weight_grad_group_size,
                                                           self.weight_grad_comm_size, self.weight_grad_group_type,
                                                           self.generator.all_gpus[0], ep_size)
            self.total_input_grad_comm = self.compute_time(self.input_grad_comm_type, tp_size, input_grad_group_size,
                                                          self.input_grad_comm_size, self.input_grad_group_type,
                                                          self.generator.all_gpus[0], ep_size)
            self.total_waiting_for_fwd_comm = self.total_fwd_comm  # tp forward
            self.total_waiting_for_ig_comm = self.total_input_grad_comm  # tp backward
            self.total_waiting_for_wg_comm = self.total_weight_grad_comm

        # 气泡时间计算（对应C++版本的embedding_layer检查）
        if self.id != "embedding_layer":
            pre_bubble_time += ((self.total_waiting_for_fwd_comm + self.total_forward_pass_compute + 
                                self.total_weight_grad_compute + self.total_input_grad_compute + 
                                self.total_waiting_for_ig_comm) / FREQ)
        
        # DP通信时间计算（精准复现C++版本的重叠比率处理）
        if self.weight_grad_group_type == GroupType.DP_EP:
            self.total_waiting_for_wg_comm *= (1 - param.net_work_param.dp_overlap_ratio)
            dp_ep_comm += (self.total_waiting_for_wg_comm / FREQ)
        else:
            self.total_waiting_for_wg_comm *= (1 - param.net_work_param.dp_overlap_ratio)
            dp_comm += (self.total_waiting_for_wg_comm / FREQ)
        
        # TP/EP通信时间计算（精准复现C++版本的重叠比率处理）
        if self.fwd_pass_group_type == GroupType.EP:
            self.total_waiting_for_fwd_comm *= (1 - param.net_work_param.ep_overlap_ratio)
            self.total_waiting_for_ig_comm *= (1 - param.net_work_param.ep_overlap_ratio)
            expose_ep_comm += ((self.total_waiting_for_fwd_comm + self.total_waiting_for_ig_comm) / FREQ)
        else:
            self.total_waiting_for_fwd_comm *= (1 - param.net_work_param.tp_overlap_ratio)
            self.total_waiting_for_ig_comm *= (1 - param.net_work_param.tp_overlap_ratio)
            expose_tp_comm += ((self.total_waiting_for_fwd_comm + self.total_waiting_for_ig_comm) / FREQ)
        
        # 计算时间（转换为秒）
        layer_fwd_time = self.total_forward_pass_compute / FREQ
        layer_wg_time = self.total_weight_grad_compute / FREQ
        layer_ig_time = self.total_input_grad_compute / FREQ

        # 注意：total_compute现在在workload_reporting中累加，避免Python按值传递问题

        # 计算通信时间
        layer_fwd_comm = self.total_fwd_comm / FREQ
        layer_wg_comm = self.total_weight_grad_comm / FREQ
        layer_ig_comm = self.total_input_grad_comm / FREQ

        # 计算等待时间
        layer_fwd_wait = self.total_waiting_for_fwd_comm / FREQ
        layer_wg_wait = self.total_waiting_for_wg_comm / FREQ
        layer_ig_wait = self.total_waiting_for_ig_comm / FREQ

        # 分离日志输出
        if separate_log:
            print("*******************")
            print(f"Layer id: {self.id}")
            print(f"Total collectives issued for this layer: {self.collective_counter}")
            print(f"************************* Workload stats ************************* {self.id}")

            # CSV 头部 - 精准复现C++版本格式
            if stat_row == 0 and layer_num == 0:
                header = f"layer_name,{run_name},fwd compute,wg compute,ig compute,fwd exposed comm,wg exposed comm,ig exposed comm,fwd total comm,algbw,busbw,wg total comm,algbw,busbw,ig total comm,algbw,busbw"
                end_to_end.write_line(header)

            # 数据行
            data = ""
            if stat_row == 0:
                data += self.id

            data += f",{run_name},{layer_fwd_time:.6f},{layer_wg_time:.6f},{layer_ig_time:.6f}"
            data += f",{layer_fwd_wait:.6f},{layer_wg_wait:.6f},{layer_ig_wait:.6f}"

            # 计算带宽
            fwd_bw = self.compute_busbw(self.fwd_pass_comm_type, fwd_pass_group_size,
                                       self.fwd_pass_comm_size, self.total_fwd_comm)
            wg_bw = self.compute_busbw(self.weight_grad_comm_type, weight_grad_group_size,
                                      self.weight_grad_comm_size, self.total_weight_grad_comm)
            ig_bw = self.compute_busbw(self.input_grad_comm_type, input_grad_group_size,
                                      self.input_grad_comm_size, self.total_input_grad_comm)

            data += f",{layer_fwd_comm:.6f},{fwd_bw[0]:.2f},{fwd_bw[1]:.2f}"
            data += f",{layer_wg_comm:.6f},{wg_bw[0]:.2f},{wg_bw[1]:.2f}"
            data += f",{layer_ig_comm:.6f},{ig_bw[0]:.2f},{ig_bw[1]:.2f}"

            end_to_end.write_line(data)

            # 最后一层的总结
            if layer_num == self.workload.size - 1:
                # 精准复现C++版本的analytical mode检查
                if param.mode != ModeType.ANALYTICAL:
                    total_exposed = (self.generator.get_tick() / FREQ) - total_compute

                # PP 通信时间 - 精准复现C++版本的计算公式
                expose_pp_time = (2 * vpp * ga * (pp_commsize * GBPS / (param.net_work_param.pp_overlap_ratio) * 1e9) / FREQ)
                expose_pp_time *= (1 - param.net_work_param.pp_overlap_ratio)

                # PP 气泡时间
                pre_bubble_time *= (pp_size - 1) / (ga * vpp)

                # 总时间
                total_time = total_compute + total_exposed + pre_bubble_time + expose_pp_time

                def format_percentage(value):
                    percentage = (value / total_time) * 100 if total_time > 0 else 0
                    return f"{percentage:.2f}%"

                def format_value(value):
                    return f"{value:.6f}" if abs(value) < float('inf') else "NaN or Inf"

                # 文件路径处理 - 精准复现C++版本
                file_name = param.res
                last_slash_pos = param.res.rfind('/')
                if last_slash_pos != -1:
                    file_name = param.res[last_slash_pos + 1:]

                # 输出最终统计
                keys = "File name, Expose DP comm, Expose DP_EP comm, Expose TP comm, Expose_EP_comm, Expose_PP_comm, bubble time, total comp, total exposed comm, Total time"
                values = f"{file_name}, {format_value(dp_comm)} ({format_percentage(dp_comm)}), "
                values += f"{format_value(dp_ep_comm)} ({format_percentage(dp_ep_comm)}), "
                values += f"{format_value(expose_tp_comm)} ({format_percentage(expose_tp_comm)}), "
                values += f"{format_value(expose_ep_comm)} ({format_percentage(expose_ep_comm)}), "
                values += f"{format_value(expose_pp_time)} ({format_percentage(expose_pp_time)}), "
                values += f"{format_value(pre_bubble_time)} ({format_percentage(pre_bubble_time)}), "
                values += f"{format_value(total_compute)} ({format_percentage(total_compute)}), "
                values += f"{format_value(total_exposed)} ({format_percentage(total_exposed)}), "
                values += f"{format_value(total_time)} (100.00%)"

                result_data = keys + "\n" + values
                end_to_end.write_res(result_data)

        # 填充 LayerData
        layer_data.layer_name = self.id
        layer_data.total_forward_pass_compute = layer_fwd_time
        layer_data.total_weight_grad_compute = layer_wg_time
        layer_data.total_input_grad_compute = layer_ig_time
        layer_data.total_waiting_for_fwd_comm = layer_fwd_wait
        layer_data.total_waiting_for_wg_comm = layer_wg_wait
        layer_data.total_waiting_for_ig_comm = layer_ig_wait
        layer_data.total_fwd_comm = layer_fwd_comm
        layer_data.total_weight_grad_comm = layer_wg_comm
        layer_data.total_input_grad_comm = layer_ig_comm

        # 填充队列延迟和网络消息延迟的统计
        layer_data.avg_queuing_delay = []
        for i, delay in enumerate(self.queuing_delay):
            layer_data.avg_queuing_delay.append((i, delay / FREQ))
        
        layer_data.avg_network_message_delay = []
        for i, delay in enumerate(self.net_message_latency):
            layer_data.avg_network_message_delay.append((i + 1, delay / FREQ))

        return layer_data

    def take_stream_stats_average(self):
        """计算流统计平均值 - 对应C++版本的take_stream_stats_average"""
        # 计算队列延迟的平均值
        if self.stream_stat_counter > 0:
            for i in range(len(self.queuing_delay)):
                self.queuing_delay[i] /= self.stream_stat_counter
        
        # 计算网络消息延迟的平均值
        if hasattr(self, 'net_message_latency') and self.stream_stat_counter > 0:
            for i in range(len(self.net_message_latency)):
                self.net_message_latency[i] /= self.stream_stat_counter

    def _calculate_group_size(self, group_type: GroupType, tp_size: int, dp_size: int, ep_size: int) -> int:
        """计算组大小 - 辅助方法"""
        if group_type == GroupType.TP:
            return tp_size
        elif group_type == GroupType.DP:
            return dp_size
        elif group_type == GroupType.EP:
            return ep_size
        elif group_type == GroupType.DP_EP:
            return dp_size * ep_size
        else:
            return 1 