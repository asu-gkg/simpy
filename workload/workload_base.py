# Workload基础类 - 对应Workload.cc/Workload.hh中的基础部分
# 对应C++函数签名：
# - Workload::Workload(std::string run_name, Sys* generator, std::string name, int TOTAL_PASS, int total_rows, int stat_row, std::string path, bool seprate_log)
# - Workload::~Workload()
# - void Workload::call(EventType event, CallData* data)
# - void Workload::fire()
# - void Workload::check_for_sim_end()

from typing import List, Dict, Any, Optional, Tuple
import os
import sys

from system.callable import Callable, CallData
from system.common import EventType, ComType, SchedulingPolicy, CollectiveBarrier, Tick
from system.api import AstraSimDataAPI
from .parallelism_policy import ParallelismPolicy, LoopState
from .layer import Layer
from .csv_writer import CSVWriter
from .workload_parser import WorkloadParser
from .workload_iterators import WorkloadIterators
from .workload_reporting import WorkloadReporting


class Workload(Callable):
    """工作负载类 - 对应C++版本的Workload类"""
    
    def __init__(self, run_name: str, generator, name: str, total_pass: int, 
                total_rows: int, stat_row: int, path: str, separate_log: bool):
        """
        初始化工作负载 - 对应C++构造函数
        Workload::Workload(std::string run_name, Sys* generator, std::string name, int TOTAL_PASS, int total_rows, int stat_row, std::string path, bool seprate_log)
        
        Args:
            run_name: 运行名称
            generator: 系统生成器
            name: 工作负载文件名
            total_pass: 总轮次
            total_rows: 总行数
            stat_row: 统计行数
            path: 输出路径
            separate_log: 是否分离日志
        """
        super().__init__()
        
        # 基本属性
        self.initialized = False
        self.layers = []
        self.size = 0
        self.counter = 0
        self.delay_loaded = False
        self.checkpoint_initiated = False
        self.collective_issued = False
        self.current_state = LoopState.Forward_Pass
        self.generator = generator
        self.total_pass = total_pass
        self.pass_counter = 0
        self.index = 0
        self.waiting_for_comm = 0
        
        # DLRM特定参数
        self.dlrm_last_bottom_layer = 0
        
        # Transformer特定参数
        self.model_parallel_npu_group = 0  # TP Size
        self.expert_parallel_npu_group = 0  # Ep Size
        self.pipeline_model_parallelism = 0  # PP Size
        self.ga = 0  # Ga_Size
        self.all_gpus = 0
        self.vpp = 0
        self.pp_commsize = 0
        
        # 检查点机制
        self.checkpoints = {}
        self.need_checkpoint_initiation = {}
        
        # 运行类型
        self.run_type = ""
        
        # 待处理的集体通信数量
        self.pending_collectives = 0
        
        # CSV写入器
        self.detailed = None
        self.end_to_end = None
        self.dimension_utilization = None
        
        # 路径和日志设置
        self.path = path
        self.stat_row = stat_row
        self.separate_log = separate_log
        
        # 初始化工作负载
        parser = WorkloadParser()
        self.initialized = parser.initialize_workload(self, name)
        if not self.initialized:
            return
            
        self.total_rows = total_rows
        self.run_name = run_name
        self.registered_for_finished_streams = False
        
        # 初始化统计文件
        if generator.id == 0 and separate_log:
            print(f"stat path: {path}, total rows: {total_rows}, stat row: {stat_row}")
            self.detailed = CSVWriter(path, f"detailed_{generator.total_nodes}.csv")
            self.end_to_end = CSVWriter(path, "EndToEnd.csv")
            self.dimension_utilization = CSVWriter(
                path, f"{run_name}_dimension_utilization_{generator.npu_offset}.csv")
            if stat_row == 0:
                self.initialize_stat_files()
        
        # 初始化迭代器和报告器
        self.iterators = WorkloadIterators(self)
        self.reporting = WorkloadReporting(self)
    
    def __del__(self):
        """
        析构函数 - 对应C++析构函数
        Workload::~Workload()
        """
        if self.end_to_end:
            del self.end_to_end
        if self.detailed:
            del self.detailed
        if self.dimension_utilization:
            del self.dimension_utilization
        for layer in self.layers:
            del layer
    
    def initialize_stat_files(self):
        """
        初始化统计文件 - 对应C++函数
        void Workload::initialize_stat_files()
        """
        self.detailed.initialize_csv(self.size * self.total_rows + 20, 50)
        self.end_to_end.initialize_csv(self.size * self.total_rows + 20, 50)
    
    def call(self, event_type: EventType, data: CallData) -> None:
        """
        处理事件 - 实现Callable接口 - 对应C++函数
        void Workload::call(EventType event, CallData* data)
        
        Args:
            event_type: 事件类型
            data: 事件数据
        """
        if self.counter > 0:
            if self.generator.id == 0:
                print("counter > 0")
            self.generator.try_register_event(
                self, EventType.Workload_Wait, None, self.counter)
            return
        
        # 根据并行策略选择迭代方法
        if self.parallelism_policy == ParallelismPolicy.Data:
            self.iterators.iterate_data_parallel()
        elif self.parallelism_policy == ParallelismPolicy.Transformer:
            self.iterators.iterate_hybrid_parallel_transformer()
        elif (self.parallelism_policy == ParallelismPolicy.DLRM or 
            self.parallelism_policy == ParallelismPolicy.DLRMEnhanced):
            self.iterators.iterate_hybrid_parallel_dlrm()
        elif self.parallelism_policy == ParallelismPolicy.MicroBenchmark:
            self.iterators.iterate_micro_benchmark()
        elif self.parallelism_policy == ParallelismPolicy.Model:
            self.iterators.iterate_model_parallel()
        elif self.parallelism_policy == ParallelismPolicy.HybridDataModel:
            self.iterators.iterate_hybrid_parallel_data_model()
        elif self.parallelism_policy == ParallelismPolicy.HybridModelData:
            self.iterators.iterate_hybrid_parallel_model_data()
        elif self.parallelism_policy == ParallelismPolicy.DistributedInference:
            self.iterators.iterate_distributed_inference()
        elif self.parallelism_policy == ParallelismPolicy.TransformerFwdInBckwd:
            self.iterators.iterate_hybrid_parallel_transformer_fwd_in_bckwd()
        elif self.parallelism_policy == ParallelismPolicy.HybridCustomized:
            self.iterators.iterate_hybrid_parallel_customized()
        else:
            raise RuntimeError("No known parallelism!")
    
    def check_for_sim_end(self):
        """
        检查仿真是否结束 - 对应C++函数
        void Workload::check_for_sim_end()
        """
        if self.pass_counter == self.total_pass:
            self.current_state = LoopState.Wait_For_Sim_Finish
            if (self.generator.streams_finished != self.generator.streams_injected and
                not self.registered_for_finished_streams):
                self.generator.register_for_finished_stream(self)
                self.registered_for_finished_streams = True
                self.layers[0].is_weight_grad_comm_finished_blocking()
                return
            
            if self.generator.streams_finished == self.generator.streams_injected:
                if self.generator.id == 0:
                    self.reporting.report()
                self.generator.workload_finished()
                return
    
    def fire(self):
        """
        触发工作负载执行 - 对应C++函数
        void Workload::fire()
        """
        self.call(EventType.General, None)
    
    @staticmethod
    def get_layer_numbers(workload_input: str) -> int:
        """
        获取层数 - 对应C++静态函数
        static int Workload::get_layer_numbers(std::string workload_input)
        
        Args:
            workload_input: 工作负载输入文件名
            
        Returns:
            层数
        """
        try:
            with open(f"workload_inputs/{workload_input}", 'r') as in_file:
                # 跳过第一行
                in_file.readline()
                # 读取层数
                lines = int(in_file.readline().strip())
                return lines
        except FileNotFoundError:
            print(f"无法打开文件: {workload_input}")
            sys.exit(1)
        except Exception as e:
            print(f"读取层数时出错: {e}")
            sys.exit(1) 