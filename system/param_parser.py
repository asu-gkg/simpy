# Parameter parser - corresponds to AstraParamParse.cc/AstraParamParse.hh in SimAI 
from typing import List, Dict, Optional
from enum import Enum
import re
import threading
import os

# 对应C++中的GPUType枚举
class GPUType(Enum):
    A100 = 0
    A800 = 1
    H100 = 2
    H800 = 3
    NONE = 4
    H20 = 5

# 对应C++中的ModeType枚举
class ModeType(Enum):
    NONE = 0
    ASTRA_SIM = 1
    MOCKNCCL = 2
    ANALYTICAL = 3

class NetWorkParam:
    """网络参数结构体，对应C++中的NetWorkParam结构"""
    
    def __init__(self):
        self.node_num: int = 0
        self.switch_num: int = 0
        self.link_num: int = 0
        self.trace_num: int = 0
        self.nvswitch_num: int = 0
        self.gpus_per_server: int = 0
        self.nics_per_server: int = 0
        self.nvlink_bw: float = -1.0
        self.bw_per_nic: float = -1.0
        self.nic_type: str = "cx7"
        self.visual: bool = False
        self.dp_overlap_ratio: float = 0.0
        self.tp_overlap_ratio: float = 0.0
        self.ep_overlap_ratio: float = 0.0
        self.pp_overlap_ratio: float = 1.0
        self.gpu_type: GPUType = GPUType.NONE
        self.NVswitchs: List[int] = []
        self.all_gpus: List[List[int]] = []


class UserParam:
    """用户参数结构体，对应C++中的UserParam类"""
    
    _instance = None
    _lock = threading.Lock()
    
    def __init__(self):
        self.thread: int = 1
        self.gpus: List[int] = []
        self.workload: str = ""
        self.res: str = "None"
        self.res_folder: str = "None"
        self.comm_scale: int = 1
        self.mode: ModeType = ModeType.MOCKNCCL
        self.net_work_param: NetWorkParam = NetWorkParam()
    
    @classmethod
    def getInstance(cls):
        """单例模式获取实例，对应C++中的getInstance()方法"""
        with cls._lock:
            if cls._instance is None:
                cls._instance = UserParam()
            return cls._instance
    
    def parse(self, argc: int, argv: List[str]) -> int:
        """解析命令行参数，对应C++中的parse方法"""
        i = 1  # 跳过程序名
        while i < argc:
            arg = argv[i]
            
            if arg == "-h" or arg == "--help":
                print("-w,     --workload          Workloads, default none")
                print("-g,     --gpus              Number of GPUs, default 1")
                print("-g_p_s, --gpus-per-server   GPUs per server")
                print("-r,     --result            Output results path")
                print("-nv, --nvlink     Nvlink")
                print("-nic, --nic_busbw     NIC busbw")
                print("-n_p_s, --bus-bandwidth     Bus bandwidth file")
                print("-nic_t, --nic_type     NIC type(cx7,bf3),choose when disable nic ")
                print("-g_type, --gpu_type     GPU type(A100,H100),choose when disable nvlink ")
                print("-v, --visual    Enable visual output")
                print("-dp_o, --dp_overlap    dp overlap ratio(Default 0)")
                print("-ep_o, --ep_overlap    ep overlap ratio(Default 0)")
                print("-tp_o, --tp_overlap    tp overlap ratio(Default 0)")
                print("-pp_o, --pp_overlap    pp overlap ratio(Default 1)")
                return 1
                
            elif arg == "-w" or arg == "--workload":
                if i + 1 < argc:
                    i += 1
                    self.workload = argv[i]
                    
            elif arg == "-g" or arg == "--gpus":
                if i + 1 < argc:
                    i += 1
                    self.gpus.append(int(argv[i]))
                    
            elif arg == "-r" or arg == "--result":
                if i + 1 < argc:
                    i += 1
                    self.res = argv[i]
                    
            elif arg == "-r_f" or arg == "--result_folder":
                if i + 1 < argc:
                    i += 1
                    self.res_folder = argv[i]
                    
            elif arg == "-g_p_s" or arg == "--gpus-per-server":
                if i + 1 < argc:
                    i += 1
                    self.net_work_param.gpus_per_server = int(argv[i])
                    
            elif arg == "-nv" or arg == "--nvlink":
                if i + 1 < argc:
                    i += 1
                    self.net_work_param.nvlink_bw = float(argv[i])
                    
            elif arg == "-nic" or arg == "--nic_busbw":
                if i + 1 < argc:
                    i += 1
                    self.net_work_param.bw_per_nic = float(argv[i])
                    
            elif arg == "-n_p_s" or arg == "--nic_per_server":
                if i + 1 < argc:
                    i += 1
                    self.net_work_param.nics_per_server = int(argv[i])
                    
            elif arg == "-nic_t" or arg == "--nic_type":
                if i + 1 < argc:
                    i += 1
                    self.net_work_param.nic_type = argv[i]
                    
            elif arg == "-g_type" or arg == "--gpu_type":
                if i + 1 < argc:
                    i += 1
                    gpu_type = argv[i]
                    if gpu_type.lower() == "a100":
                        self.net_work_param.gpu_type = GPUType.A100
                    elif gpu_type.lower() == "a800":
                        self.net_work_param.gpu_type = GPUType.A800
                    elif gpu_type.lower() == "h100":
                        self.net_work_param.gpu_type = GPUType.H100
                    elif gpu_type.lower() == "h800":
                        self.net_work_param.gpu_type = GPUType.H800
                    elif gpu_type.lower() == "h20":
                        self.net_work_param.gpu_type = GPUType.H20
                    else:
                        self.net_work_param.gpu_type = GPUType.NONE
                        
            elif arg == "-v" or arg == "--visual":
                if i + 1 < argc:
                    i += 1
                    self.net_work_param.visual = bool(int(argv[i]))
                    
            elif arg == "--dp_overlap" or arg == "-dp_o":
                if i + 1 < argc:
                    i += 1
                    self.net_work_param.dp_overlap_ratio = float(argv[i])
                    
            elif arg == "--tp_overlap" or arg == "-tp_o":
                if i + 1 < argc:
                    i += 1
                    self.net_work_param.tp_overlap_ratio = float(argv[i])
                    
            elif arg == "--ep_overlap" or arg == "-ep_o":
                if i + 1 < argc:
                    i += 1
                    self.net_work_param.ep_overlap_ratio = float(argv[i])
                    
            elif arg == "--pp_overlap" or arg == "-pp_o":
                if i + 1 < argc:
                    i += 1
                    self.net_work_param.pp_overlap_ratio = float(argv[i])
                    
            else:
                return 1
                
            i += 1
        
        # 计算网络参数
        if self.gpus:
            self.net_work_param.nvswitch_num = self.gpus[0] // self.net_work_param.gpus_per_server
            self.net_work_param.switch_num = 120 + self.net_work_param.gpus_per_server
            self.net_work_param.node_num = (self.net_work_param.nvswitch_num + 
                                        self.net_work_param.switch_num + self.gpus[0])
        
        # 生成结果文件名
        if self.res == "None":
            full_path = self.workload
            model_info = full_path
            last_slash_pos = full_path.rfind('/')
            if last_slash_pos != -1:
                model_info = full_path[last_slash_pos + 1:]
            
            model_name = ""
            world_size = 0
            tp = 0
            pp = 0
            ep = 0
            gbs = 0
            mbs = 0
            seq = 0
            
            # 提取模型名称
            world_size_pos = model_info.find("world_size")
            if world_size_pos != -1:
                model_name = model_info[:world_size_pos - 1]
            
            # 使用正则表达式提取参数
            param_regex = r'(world_size|tp|pp|ep|gbs|mbs|seq)(\d+)'
            matches = re.findall(param_regex, model_info)
            
            for param_name, param_value in matches:
                value = int(param_value)
                if param_name == "world_size":
                    world_size = value
                elif param_name == "tp":
                    tp = value
                elif param_name == "pp":
                    pp = value
                elif param_name == "ep":
                    ep = value
                elif param_name == "gbs":
                    gbs = value
                elif param_name == "mbs":
                    mbs = value
                elif param_name == "seq":
                    seq = value
            
            # 计算dp和ga
            dp = world_size // (tp * pp) if tp * pp > 0 else 0
            ga = gbs / (dp * mbs) if dp * mbs > 0 else 0
            
            # 构建结果字符串
            result_parts = [
                model_name,
                f'tp{tp}',
                f'pp{pp}',
                f'dp{dp}',
                f'ga{int(ga)}',
                f'ep{ep}',
                f'NVL{self.net_work_param.gpus_per_server}',
                f'{self.net_work_param.bw_per_nic * 8:.1f}G',
                f'DP{self.net_work_param.dp_overlap_ratio}'
            ]
            
            self.res = '-'.join(result_parts)
        
        # 处理结果文件夹
        if self.res_folder != "None":
            if not self.res_folder.endswith('/'):
                self.res = self.res_folder + '/' + self.res
            else:
                self.res = self.res_folder + self.res
        
        return 0
    
    def __del__(self):
        pass


class UserParamManager:
    """UserParam单例管理器，对应C++中的UserParam::getInstance()"""
    
    @classmethod
    def getInstance(cls):
        return UserParam.getInstance()


class ParamParser:
    """参数解析器类，提供便捷的解析接口"""
    
    def __init__(self):
        pass

    def parse(self, argc: int, argv: List[str]) -> int:
        """解析命令行参数"""
        user_param = UserParam.getInstance()
        return user_param.parse(argc, argv)