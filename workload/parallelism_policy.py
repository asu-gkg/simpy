# ParallelismPolicy enum - corresponds to ParallelismPolicy in SimAI

from enum import Enum


class ParallelismPolicy(Enum):
    """并行策略枚举 - 对应C++版本的ParallelismPolicy"""
    MicroBenchmark = "MicroBenchmark"
    Data = "Data"
    Transformer = "Transformer"
    TransformerFwdInBckwd = "TransformerFwdInBckwd"
    DLRM = "DLRM"
    DLRMEnhanced = "DLRMEnhanced"
    Model = "Model"
    HybridDataModel = "HybridDataModel"
    HybridModelData = "HybridModelData"
    HybridCustomized = "HybridCustomized"
    DistributedInference = "DistributedInference"
    All = "All"
    None_ = "None"


class LoopState(Enum):
    """循环状态枚举 - 对应C++版本的LoopState"""
    Forward_Pass = "Forward_Pass"
    Weight_Gradient = "Weight_Gradient"
    Input_Gradient = "Input_Gradient"
    Wait_For_Sim_Finish = "Wait_For_Sim_Finish"
    Forward_In_BackPass = "Forward_In_BackPass" 