import os
import sys
import string
import io
from typing import Dict, List, Tuple, Optional

# 导入系统模块
from system.sys import Sys
from system.param_parser import UserParam, UserParamManager
from system.common import ModeType
import rich
# 导入网络模块
from .analytical_network import AnalyticalNetwork
from .ana_sim import AnaSim

# 常量定义
RESULT_PATH = "./results/"
WORKLOAD_PATH = ""

# 全局变量声明（对应extern变量）
receiver_pending_queue: Dict[Tuple[Tuple[int, int], int], 'AstraSim.ncclFlowTag'] = {}
node_num: int = 0
switch_num: int = 0
link_num: int = 0
trace_num: int = 0
nvswitch_num: int = 0
gpus_per_server: int = 0
gpu_type: str = ""
NVswitchs: List[int] = []
all_gpus: List[List[int]] = []
ngpus_per_node: int = 0
expeRecvHash: Dict[Tuple[int, Tuple[int, int]], 'task1'] = {}
recvHash: Dict[Tuple[int, Tuple[int, int]], int] = {}
sentHash: Dict[Tuple[int, Tuple[int, int]], 'task1'] = {}
nodeHash: Dict[Tuple[int, int], int] = {}
local_rank: int = 0

# 全局变量
workloads: List[str] = []
physical_dims: List[List[int]] = []

def main(args) -> int:
    """主函数，使用 argparse 解析的参数对象"""
    
    # 获取参数实例
    param = UserParam.getInstance()
    
    # 将 args 转换为命令行参数列表，只包含 UserParam.parse 能识别的参数
    # 注意：UserParam.parse 期望从索引 1 开始解析（跳过程序名），所以需要添加一个程序名
    argv = ["program_name"]  # 添加程序名作为第一个参数
    if args.workload:
        argv.extend(["-w", args.workload])
    if args.gpus:
        argv.extend(["-g", str(args.gpus)])
    if args.result:
        argv.extend(["-r", args.result])
    if args.gpus_per_server:
        argv.extend(["-g_p_s", str(args.gpus_per_server)])
    if args.gpu_type:
        argv.extend(["-g_type", args.gpu_type])
    # 注意：comm_scale 参数在 C++ 版本的 UserParam.parse 中没有处理
    # 所以不传递给 UserParam.parse，而是直接设置
    # 注意：gid_index, network_topo, network_conf 不是 UserParam.parse 支持的参数
    # 所以不传递给 UserParam.parse
    
    if param.parse(len(argv), argv):
        print("-h,     --help              Help message", file=sys.stderr)
        return -1
    
    # 直接设置 comm_scale 参数（因为 C++ 版本的 UserParam.parse 不处理 -s 参数）
    param.comm_scale = args.comm_scale if args.comm_scale else 1
    
    # 设置模式
    param.mode = ModeType.ANALYTICAL
    physical_dims = [param.gpus]
    
    # 计算使用的GPU数量
    print(f'param.gpus: {param.gpus}')
    rich.inspect(param)
    rich.inspect(param.net_work_param)
    all_gpu_num = param.gpus[0]
    using_num_gpus = all_gpu_num
    
    # 创建节点到NVSwitch的映射
    node2nvswitch = {}
    for i in range(all_gpu_num):
        node2nvswitch[i] = all_gpu_num + i // param.net_work_param.gpus_per_server
    
    for i in range(all_gpu_num, all_gpu_num + param.net_work_param.nvswitch_num):
        node2nvswitch[i] = i
        param.net_work_param.NVswitchs.append(i)
    
    # 更新物理维度
    physical_dims[0][0] += param.net_work_param.nvswitch_num
    using_num_gpus += param.net_work_param.nvswitch_num
    
    # 计算队列维度
    queues_per_dim = [1] * len(physical_dims[0])
    
    # 创建分析网络
    analytical_network = AnalyticalNetwork(0)
    
    # 创建系统实例
    systems = Sys(
        analytical_network,
        None,  # nullptr
        0,     # 各种参数
        0,
        1,
        physical_dims[0],
        queues_per_dim,
        "",
        WORKLOAD_PATH + param.workload,
        param.comm_scale,
        1,
        1,
        1,
        0,
        RESULT_PATH + param.res,
        "Analytical_test",
        True,
        False,
        param.net_work_param.gpu_type,
        param.gpus,
        param.net_work_param.NVswitchs,
        param.net_work_param.gpus_per_server
    )
    
    # 设置系统属性
    systems.nvswitch_id = node2nvswitch[0]
    systems.num_gpus = using_num_gpus - param.net_work_param.nvswitch_num
    
    # 启动工作负载
    systems.workload.fire()
    print("SimAI begin run Analytical")
    
    # 运行分析模拟
    AnaSim.Run()
    AnaSim.Stop()
    AnaSim.Destroy()
    
    print("SimAI-Analytical finished.")
    return 0
