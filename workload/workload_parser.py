# Workload解析器 - 对应Workload.cc中的解析和初始化功能
# 对应C++函数签名：
# - bool Workload::initialize_workload(std::string name)
# - ParallelismPolicy Workload::decode_parallelsim(std::string parallelism)
# - std::map<std::string, std::vector<bool>> Workload::decode_involved_dimensions(ParallelismPolicy policy, int model_parallel_npu_group)

from typing import List, Dict, Any, Optional, Tuple
import os
import sys

from system.common import ComType
from .parallelism_policy import ParallelismPolicy
from .layer import Layer


class WorkloadParser:
    """工作负载解析器 - 负责解析工作负载文件和初始化层"""
    
    def __init__(self):
        """初始化解析器"""
        pass
    
    def initialize_workload(self, workload, name: str) -> bool:
        """
        初始化工作负载 - 对应C++函数
        bool Workload::initialize_workload(std::string name)
        
        Args:
            workload: 工作负载对象
            name: 工作负载文件名
            
        Returns:
            是否初始化成功
        """
        with open(name, 'r') as in_file:
            # 读取第一行获取并行策略
            first_line = in_file.readline().strip()
            tokens = first_line.split()
            
            if not tokens:
                return False
            
            workload.parallelism_policy = self.decode_parallelism(tokens[0])
            workload.run_type = tokens[0]
            
            # 解析Transformer相关参数
            if (workload.parallelism_policy == ParallelismPolicy.TransformerFwdInBckwd or
                workload.parallelism_policy == ParallelismPolicy.Transformer):
                
                # 解析基本参数
                for i in range(1, len(tokens), 2):
                    if i + 1 >= len(tokens):
                        break
                    if tokens[i] == "model_parallel_NPU_group:":
                        workload.model_parallel_npu_group = int(tokens[i + 1])
                    elif tokens[i] == "ep:":
                        workload.expert_parallel_npu_group = int(tokens[i + 1])
                    elif tokens[i] == "pp:":
                        workload.pipeline_model_parallelism = int(tokens[i + 1])
                    elif tokens[i] == "vpp:":
                        workload.vpp = int(tokens[i + 1])
                    elif tokens[i] == "ga:":
                        workload.ga = int(tokens[i + 1])
                    elif tokens[i] == "all_gpus:":
                        workload.all_gpus = int(tokens[i + 1])
                    elif tokens[i] == "pp_comm" or tokens[i] == "pp_comm:":
                        workload.pp_commsize = int(tokens[i + 1])
                
                # 解析检查点信息（仅对TransformerFwdInBckwd）
                if workload.parallelism_policy == ParallelismPolicy.TransformerFwdInBckwd:
                    if workload.generator.id == 0:
                        print("checkpoints layers are: ", end="")
                    
                    for i in range(1, len(tokens), 2):
                        if i + 1 >= len(tokens):
                            break
                        if tokens[i] == "checkpoints:":
                            account = int(tokens[i + 1])
                            j = 2
                            while account > 0:
                                if i + j < len(tokens):
                                    layer = int(tokens[i + j])
                                    workload.checkpoints[layer] = True
                                    if workload.generator.id == 0:
                                        print(f"{layer}, ", end="")
                                j += 1
                                account -= 1
                        elif tokens[i] == "checkpoint_initiates:":
                            if workload.generator.id == 0:
                                print("\nlayers initiating fwd_in_bckwd are: ", end="")
                            account = int(tokens[i + 1])
                            j = 2
                            while account > 0:
                                if i + j < len(tokens):
                                    layer = int(tokens[i + j])
                                    workload.need_checkpoint_initiation[layer] = True
                                    if workload.generator.id == 0:
                                        print(f"{layer}, ", end="")
                                j += 1
                                account -= 1
                            if workload.generator.id == 0:
                                print()
            
            # 解析DLRM相关参数
            elif (workload.parallelism_policy == ParallelismPolicy.DLRM or
                workload.parallelism_policy == ParallelismPolicy.DLRMEnhanced):
                for i in range(1, len(tokens), 2):
                    if i + 1 >= len(tokens):
                        break
                    if tokens[i] == "DLRM_LAST_BOTTOM_LAYER:":
                        workload.dlrm_last_bottom_layer = int(tokens[i + 1])
                
                if workload.generator.id == 0:
                    print(f"****************** info: DLRM workload last bottom layer is: {workload.dlrm_last_bottom_layer}")
            
            elif workload.parallelism_policy == ParallelismPolicy.None_:
                print("无法解码工作负载并行化策略")
                return False
            
            # 解析pp_comm参数
            for i in range(1, len(tokens), 2):
                if i + 1 >= len(tokens):
                    break
                if tokens[i] == "pp_comm" or tokens[i] == "pp_comm:":
                    workload.pp_commsize = int(tokens[i + 1])
            
            if workload.generator.id == 0:
                print(f"pp_commize: {workload.pp_commsize}")
            
            # 验证参数
            if workload.generator.id == 0:
                if (workload.model_parallel_npu_group == 0 or workload.expert_parallel_npu_group == 0 or 
                    workload.pipeline_model_parallelism == 0 or workload.vpp == 0 or workload.ga == 0 or 
                    workload.all_gpus == 0 or 
                    (workload.pipeline_model_parallelism != 1 and workload.pp_commsize == 0) or
                    (workload.pipeline_model_parallelism == 1 and workload.pp_commsize != 0)):
                    print("*****Warning: Input workload format mismatch. It may cause simulation error. Please use the latest AICB to generate.*****")
            
            # 读取层数
            second_line = in_file.readline().strip()
            lines = int(second_line)
            workload.size = lines
            
            # 获取涉及维度
            general_involved_dimensions = self.decode_involved_dimensions(
                workload.parallelism_policy, workload.model_parallel_npu_group, workload.generator)
            
            # 创建层
            for i in range(lines):
                # 读取层信息
                layer_data = in_file.readline().strip().split()
                if len(layer_data) < 12:  # 修复：实际只需要12个字段
                    print(f"this layer data is not valid: {layer_data}")
                    sys.exit(1)
                
                layer_id = layer_data[0]
                depen = int(layer_data[1])
                fp_compute_time = int(layer_data[2])
                fp_comm_type_s = layer_data[3]
                fp_comm_size = int(layer_data[4])
                ig_compute_time = int(layer_data[5])
                ig_comm_type_s = layer_data[6]
                ig_comm_size = int(layer_data[7])
                wg_compute_time = int(layer_data[8])
                wg_comm_type_s = layer_data[9]
                wg_comm_size = int(layer_data[10])
                wg_update_time = int(layer_data[11])
                
                # 解析通信类型
                fp_comm_type, fp_group_type = self._parse_comm_type(fp_comm_type_s)
                ig_comm_type, ig_group_type = self._parse_comm_type(ig_comm_type_s)
                wg_comm_type, wg_group_type = self._parse_comm_type(wg_comm_type_s)
                
                # 确定特定并行策略
                specific_policy = ParallelismPolicy.None_
                selected_involved_dimensions = general_involved_dimensions
                
                # 处理自定义混合并行
                if workload.parallelism_policy == ParallelismPolicy.HybridCustomized:
                    if len(layer_data) > 12:
                        specific_parallelism = layer_data[12]
                        specific_policy = self.decode_parallelism(specific_parallelism)
                
                # 处理DLRM特殊情况
                if ((workload.parallelism_policy == ParallelismPolicy.DLRM or
                    workload.parallelism_policy == ParallelismPolicy.DLRMEnhanced) and i == 0):
                    specific_policy = ParallelismPolicy.All
                
                if specific_policy != ParallelismPolicy.None_:
                    selected_involved_dimensions = self.decode_involved_dimensions(
                        specific_policy, workload.model_parallel_npu_group, workload.generator)
                
                # 创建层对象
                layer = Layer(
                    layer_id, i, workload.generator, workload,
                    fp_compute_time * workload.generator.compute_scale,
                    fp_comm_type, fp_group_type,
                    fp_comm_size * workload.generator.comm_scale,
                    selected_involved_dimensions["fwd"],
                    ig_compute_time * workload.generator.compute_scale,
                    ig_comm_type, ig_group_type,
                    ig_comm_size * workload.generator.comm_scale,
                    selected_involved_dimensions["ig"],
                    wg_compute_time * workload.generator.compute_scale,
                    wg_comm_type, wg_group_type,
                    wg_comm_size * workload.generator.comm_scale,
                    selected_involved_dimensions["wg"],
                    wg_update_time,  # 对应C++版本的weight_grad_update_time
                    specific_policy
                )
                
                # 设置检查点属性
                if i in workload.checkpoints:
                    layer.is_checkpoint = True
                if i in workload.need_checkpoint_initiation:
                    layer.needs_fwd_in_bckwd_initiation = True
                
                workload.layers.append(layer)
                
                if workload.generator.id == 0:
                    print(f"id: {layer_id}, depen: {depen}, wg_comp_time: {wg_compute_time}")
            
            if workload.generator.id == 0:
                print(f"type: {workload.run_type}, num passes: {workload.total_pass}, "
                        f"lines: {lines}, compute scale: {workload.generator.compute_scale}, "
                        f"comm scale: {workload.generator.comm_scale}")
            
            return True
                

    def decode_parallelism(self, parallelism: str) -> ParallelismPolicy:
        """
        解码并行策略字符串 - 对应C++函数
        ParallelismPolicy Workload::decode_parallelsim(std::string parallelism)
        
        Args:
            parallelism: 并行策略字符串
            
        Returns:
            对应的并行策略枚举
        """
        parallelism_map = {
            "DATA": ParallelismPolicy.Data,
            "HYBRID_TRANSFORMER": ParallelismPolicy.Transformer,
            "HYBRID_TRANSFORMER_FWD_IN_BCKWD": ParallelismPolicy.TransformerFwdInBckwd,
            "HYBRID_DLRM": ParallelismPolicy.DLRM,
            "HYBRID_DLRM_ENHANCED": ParallelismPolicy.DLRMEnhanced,
            "MODEL": ParallelismPolicy.Model,
            "HYBRID_DATA_MODEL": ParallelismPolicy.HybridDataModel,
            "HYBRID_MODEL_DATA": ParallelismPolicy.HybridModelData,
            "HYBRID_CUSTOMIZED": ParallelismPolicy.HybridCustomized,
            "MICRO": ParallelismPolicy.MicroBenchmark,
            "DISTRIBUTED_INFERENCE": ParallelismPolicy.DistributedInference
        }
        return parallelism_map.get(parallelism, ParallelismPolicy.None_)
    
    def decode_involved_dimensions(self, policy: ParallelismPolicy, 
                                model_parallel_npu_group: int, generator=None) -> Dict[str, List[bool]]:
        """
        解码涉及的维度 - 对应C++函数
        std::map<std::string, std::vector<bool>> Workload::decode_involved_dimensions(ParallelismPolicy policy, int model_parallel_npu_group)
        
        Args:
            policy: 并行策略
            model_parallel_npu_group: 模型并行NPU组大小
            generator: 生成器对象（可选）
            
        Returns:
            涉及维度的映射
        """
        result = {}
        none_dims = [False] * 10
        all_dims = [True] * 10
        
        if policy == ParallelismPolicy.All:
            result["fwd"] = all_dims
            result["ig"] = all_dims
            result["wg"] = all_dims
        elif (policy == ParallelismPolicy.Data or 
                policy == ParallelismPolicy.DLRM or
                policy == ParallelismPolicy.DLRMEnhanced or
                policy == ParallelismPolicy.MicroBenchmark):
            result["fwd"] = none_dims
            result["ig"] = none_dims
            result["wg"] = all_dims
        elif (policy == ParallelismPolicy.Model or
            policy == ParallelismPolicy.DistributedInference):
            result["fwd"] = all_dims
            result["ig"] = all_dims
            result["wg"] = none_dims
        elif policy == ParallelismPolicy.HybridModelData:
            data_dims = [True] + [False] * 9
            model_dims = [False] + [True] * 9
            result["fwd"] = model_dims
            result["ig"] = model_dims
            result["wg"] = data_dims
        elif policy == ParallelismPolicy.HybridDataModel:
            model_dims = [True] + [False] * 9
            data_dims = [False] + [True] * 9
            result["fwd"] = model_dims
            result["ig"] = model_dims
            result["wg"] = data_dims
        elif (policy == ParallelismPolicy.TransformerFwdInBckwd or
            policy == ParallelismPolicy.Transformer):
            if generator:
                model_parallel_boundary = generator.break_dimension(model_parallel_npu_group)
            else:
                model_parallel_boundary = 0  # 默认值
            model_dims = [True] * (model_parallel_boundary + 1) + [False] * (10 - model_parallel_boundary - 1)
            data_dims = [False] * (model_parallel_boundary + 1) + [True] * (10 - model_parallel_boundary - 1)
            result["fwd"] = model_dims
            result["ig"] = model_dims
            result["wg"] = data_dims
        
        return result
    
    def _parse_comm_type(self, comm_type_str: str) -> Tuple[ComType, str]:
        """
        解析通信类型字符串，返回通信类型和组类型
        
        Args:
            comm_type_str: 通信类型字符串
            
        Returns:
            (通信类型, 组类型)
        """
        # 通信类型映射
        comm_type_map = {
            "ALLREDUCE": ComType.All_Reduce,
            "ALLTOALL": ComType.All_to_All,
            "ALLREDUCEALLTOALL": ComType.All_Reduce_All_to_All,
            "ALLGATHER": ComType.All_Gather,
            "REDUCESCATTER": ComType.Reduce_Scatter,
            "None": ComType.None_
        }
        
        # 组类型映射
        group_type_map = {
            "ALLREDUCE": "DP",
            "ALLREDUCE_EP": "EP", 
            "ALLREDUCE_DP_EP": "DP_EP",
            "ALLTOALL": "DP",
            "ALLTOALL_EP": "EP",
            "ALLTOALL_DP_EP": "DP_EP",
            "ALLREDUCEALLTOALL": "DP",
            "ALLREDUCEALLTOALL_EP": "EP",
            "ALLREDUCEALLTOALL_DP_EP": "DP_EP",
            "ALLGATHER": "DP",
            "ALLGATHER_EP": "EP",
            "ALLGATHER_DP_EP": "DP_EP",
            "REDUCESCATTER": "DP",
            "REDUCESCATTER_EP": "EP",
            "REDUCESCATTER_DP_EP": "DP_EP"
        }
        
        # 对于前向传播和输入梯度，使用TP组类型
        if comm_type_str.startswith(("ALLREDUCE", "ALLTOALL", "ALLREDUCEALLTOALL", "ALLGATHER", "REDUCESCATTER")):
            if comm_type_str in group_type_map:
                group_type = group_type_map[comm_type_str]
                # 对于前向传播和输入梯度，将DP改为TP
                if group_type == "DP":
                    group_type = "TP"
            else:
                group_type = "NONE"
        else:
            group_type = "NONE"
        
        comm_type = comm_type_map.get(comm_type_str, ComType.None_)
        return comm_type, group_type 