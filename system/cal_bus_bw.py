"""
Bus bandwidth calculation module - corresponds to calbusbw.cc/calbusbw.h in SimAI

This module provides bus bandwidth calculation functionality for analytical network simulation.
It includes hardware type detection, NIC bandwidth calculation, and complex bandwidth optimization logic.
"""

import csv
import os
from enum import Enum
from dataclasses import dataclass
from typing import List, Dict, Tuple, Optional, Union
import math

# Hardware bandwidth constants - corresponding to calbusbw.h defines
SM80_NVLINK_BW = 20.0
SM90_NVLINK_BW = 20.6
H100_NVLINKS = 18
H800_NVLINKS = 8
A100_NVLINKS = 12
A800_NVLINKS = 8

CX6_BW = 23.5  # 25
CX7_BW = 48.5  # 50
BF3_BW = 48.5  # 50

H100_NVLS_BW = 475.0
H800_NVLS_BW = 215.0

H800_PCIE_BW = 51.2  # 64*0.8
H100_PCIE_BW = 51.2  # 64*0.8
A100_PCIE_BW = 25.6  # 32*0.8
A800_PCIE_BW = 25.6  # 32*0.8

# Default ratio CSV paths
NIC_RATIO_PATH = "astra-sim-alibabacloud/inputs/ratio/nic_ratio.csv"
NVLINK_RATIO_PATH = "astra-sim-alibabacloud/inputs/ratio/nvlink_ratio.csv"
ATA_RATIO_PATH = "astra-sim-alibabacloud/inputs/ratio/ata_ratio.csv"

class GPUType(Enum):
    """GPU类型枚举"""
    H100 = "H100"
    H800 = "H800"
    H20 = "H20"
    A100 = "A100"
    A800 = "A800"

@dataclass
class CalculationParameters:
    """对应C++中的CalculationParameters结构体"""
    node_type: GPUType
    node_count: int
    nic_type: str
    coll_type: str
    cross_nic: int
    nccl_algo: str
    gpus_pernode: int
    nics_pernode: float
    bw_per_nic: float
    bw_intra: float
    group_split_mask: int
    real_nics_pernode: float
    is_nvlink: bool

@dataclass
class BusBwResult:
    """对应C++中的BusBwResult结构体"""
    busbw: float
    is_nvlink: bool

# Global variables for error handling
info = "Success!"
retcode = 0

def get_nvlink_bw(node_type: GPUType) -> float:
    """
    获取NVLink带宽 - 对应C++中的getNvlinkBw函数
    
    Args:
        node_type: GPU类型
        
    Returns:
        NVLink带宽值（GB/s）
    """
    global info, retcode
    
    if node_type in [GPUType.H100, GPUType.H20]:
        return SM90_NVLINK_BW * H100_NVLINKS
    elif node_type == GPUType.H800:
        return SM90_NVLINK_BW * H800_NVLINKS
    elif node_type == GPUType.A100:
        return SM80_NVLINK_BW * A100_NVLINKS
    elif node_type == GPUType.A800:
        return SM80_NVLINK_BW * A800_NVLINKS
    else:
        info = "Warning: unknown machine type. Please choose from H20, H100, H800, A100, A800."
        retcode = 1
        return -1

def get_nic_bw(nic_type: str) -> float:
    """
    获取网卡带宽 - 对应C++中的getNicBw函数
    
    Args:
        nic_type: 网卡类型字符串
        
    Returns:
        网卡带宽值（GB/s）
    """
    global info, retcode
    
    nic_type_lower = nic_type.lower()
    if nic_type_lower == "cx6":
        return CX6_BW
    elif nic_type_lower == "cx7":
        return CX7_BW
    elif nic_type_lower == "bf3":
        return BF3_BW
    else:
        info = "Warning: unknown NIC type. Please choose from CX6, CX7, BF3."
        retcode = 1
        return -1

def calc_tree_bus_bw(gpus_per_node: int, node_count: int, nvlink_bw: float, 
                     nic_bw: float, nics_per_node: float, all_gather_bus_bw: float) -> float:
    """
    计算树形算法总线带宽 - 对应C++中的calcTreeBusBw函数
    
    Args:
        gpus_per_node: 每节点GPU数量
        node_count: 节点数量
        nvlink_bw: NVLink带宽
        nic_bw: 网卡带宽
        nics_per_node: 每节点网卡数量
        all_gather_bus_bw: AllGather总线带宽
        
    Returns:
        树形算法总线带宽
    """
    nranks = gpus_per_node * node_count
    if nranks == 1:
        return 5000.0
        
    if node_count == 1:
        return all_gather_bus_bw * (gpus_per_node - 1) / gpus_per_node
    else:
        algbw_nic = nic_bw * nics_per_node
        if node_count == 2:
            algbw_nic *= 2
        elif node_count == 3:
            algbw_nic *= (4.0 / 3.0)
            
        if gpus_per_node == 1:
            return algbw_nic * (nranks - 1) / nranks
            
        algbw_nvlink = nvlink_bw * gpus_per_node / (gpus_per_node - 1)
        return (algbw_nic if algbw_nic < algbw_nvlink else algbw_nvlink) * (nranks - 1) / nranks

def calc_nvls_bus_bw(gpus_per_node: int, node_count: int, nvls_bw: float, 
                     nic_bw: float, nics_per_node: float) -> float:
    """
    计算NVLS算法总线带宽 - 对应C++中的calcNVLSBusBw函数
    
    Args:
        gpus_per_node: 每节点GPU数量
        node_count: 节点数量
        nvls_bw: NVLS带宽
        nic_bw: 网卡带宽
        nics_per_node: 每节点网卡数量
        
    Returns:
        NVLS算法总线带宽
    """
    nranks = gpus_per_node * node_count
    
    if gpus_per_node != 8:
        return -1.0
        
    algo_nvls_busbw = nvls_bw * gpus_per_node / (gpus_per_node - 1)
    
    if node_count == 1:
        return algo_nvls_busbw * (nranks - 1) / nranks
    else:
        algbw_nic = nic_bw * nics_per_node
        if node_count == 2:
            algbw_nic *= 2
        elif node_count == 3:
            algbw_nic *= (4.0 / 3.0)
            
        if gpus_per_node == 1:
            return algbw_nic * (nranks - 1) / nranks
            
        return (algbw_nic if algbw_nic < algo_nvls_busbw else algo_nvls_busbw) * (nranks - 1) / nranks

def lower_compare(coll_type: str, lower_str: str) -> int:
    """
    字符串小写比较 - 对应C++中的lower_compare函数
    
    Args:
        coll_type: 要比较的字符串
        lower_str: 小写字符串
        
    Returns:
        0表示相等，1表示不等
    """
    return 0 if coll_type.lower() == lower_str else 1

def calculate_bus_bw(params: CalculationParameters) -> float:
    """
    计算总线带宽 - 对应C++中的calculateBusBw函数
    
    Args:
        params: 计算参数结构体
        
    Returns:
        计算得到的总线带宽
    """
    global info, retcode
    
    # 获取NVLink带宽
    if params.bw_intra > 0.0:
        nvlink_bw = params.bw_intra
    else:
        nvlink_bw = get_nvlink_bw(params.node_type)
    
    # 获取网卡带宽
    if params.bw_per_nic > 0.0:
        nic_bw = params.bw_per_nic
    else:
        nic_bw = get_nic_bw(params.nic_type)
    
    all_gather_bus_bw = 0.0
    gpus_per_node = params.gpus_pernode
    nics_per_node = params.nics_pernode
    real_nics_per_node = params.real_nics_pernode
    node_count = params.node_count
    nranks = node_count * gpus_per_node
    params.is_nvlink = False
    
    # 参数检验
    if nvlink_bw <= 0 or nic_bw <= 0 or gpus_per_node < 1 or nics_per_node < 1 or node_count < 1:
        return -1
    
    # cross_nic参数自动调整
    if real_nics_per_node * nic_bw > nvlink_bw:
        if params.cross_nic == 2:
            params.cross_nic = 1
    else:
        if params.cross_nic == 2:
            params.cross_nic = 0
    
    # 计算all_gather_bus_bw
    if node_count == 1:
        all_gather_bus_bw = nvlink_bw
    else:
        if gpus_per_node == 1:
            all_gather_bus_bw = nic_bw * real_nics_per_node
        else:
            if nvlink_bw < nic_bw * real_nics_per_node:
                params.is_nvlink = True
                all_gather_bus_bw = nvlink_bw
            else:
                all_gather_bus_bw = nic_bw * real_nics_per_node
                
            if params.cross_nic == 1:
                params.is_nvlink = False
                nvlink_adjusted = nvlink_bw * gpus_per_node / (gpus_per_node - 1)
                if nvlink_adjusted < nic_bw * real_nics_per_node:
                    params.is_nvlink = True
                    all_gather_bus_bw = nvlink_adjusted
                else:
                    all_gather_bus_bw = nic_bw * real_nics_per_node
    
    # 计算tree和nvls带宽
    tree_bus_bw = calc_tree_bus_bw(gpus_per_node, node_count, nvlink_bw, nic_bw, real_nics_per_node, all_gather_bus_bw)
    
    nvls_bus_bw = 0.0
    if params.node_type in [GPUType.H100, GPUType.H20]:
        nvls_bus_bw = calc_nvls_bus_bw(gpus_per_node, node_count, H100_NVLS_BW, nic_bw, real_nics_per_node)
    elif params.node_type == GPUType.H800:
        nvls_bus_bw = calc_nvls_bus_bw(gpus_per_node, node_count, H800_NVLS_BW, nic_bw, real_nics_per_node)
    
    # 根据通信类型选择算法和带宽
    if lower_compare(params.coll_type, "allreduce") == 0:
        if lower_compare(params.nccl_algo, "ring") == 0:
            return all_gather_bus_bw
        elif lower_compare(params.nccl_algo, "tree") == 0:
            return tree_bus_bw
        elif lower_compare(params.nccl_algo, "nvls") == 0 or lower_compare(params.nccl_algo, "nvlstree") == 0:
            if lower_compare(params.nccl_algo, "nvls") == 0 and node_count > 1:
                params.nccl_algo = "nvlstree"
            if lower_compare(params.nccl_algo, "nvlstree") == 0 and node_count == 1:
                params.nccl_algo = "nvls"
                
            if gpus_per_node == 8:
                if params.node_type in [GPUType.H100, GPUType.H800, GPUType.H20]:
                    return nvls_bus_bw
                else:
                    info = "Warning: unsupported machine type for NVLS algorithm. Please choose from H20,H100,H800."
                    retcode = 1
                    return -1
            else:
                info = "Warning: unsupported GPU count for NVLS algorithm. Please use 8 GPUs per node."
                retcode = 1
                return -1
        else:
            # 自动选择最优算法
            if nvls_bus_bw > tree_bus_bw:
                if all_gather_bus_bw > nvls_bus_bw:
                    params.nccl_algo = "Ring"
                    return all_gather_bus_bw
                else:
                    params.nccl_algo = "NVLSTree" if node_count > 1 else "NVLS"
                    return nvls_bus_bw
            else:
                if all_gather_bus_bw > tree_bus_bw:
                    params.nccl_algo = "Ring"
                    return all_gather_bus_bw
                else:
                    params.nccl_algo = "Tree"
                    return tree_bus_bw
                    
    elif lower_compare(params.coll_type, "allgather") == 0:
        params.nccl_algo = "Ring"
        return all_gather_bus_bw
        
    elif lower_compare(params.coll_type, "alltoall") == 0:
        params.nccl_algo = "none"
        if node_count == 1:
            params.is_nvlink = True
            return nvlink_bw
        return nic_bw * real_nics_per_node / gpus_per_node * (nranks - 1) / ((node_count - 1) * gpus_per_node)
        
    elif lower_compare(params.coll_type, "broadcast") == 0:
        params.nccl_algo = "Ring"
        return all_gather_bus_bw
        
    elif lower_compare(params.coll_type, "reducescatter") == 0:
        params.nccl_algo = "Ring"
        return all_gather_bus_bw
        
    elif lower_compare(params.coll_type, "reduce") == 0:
        params.nccl_algo = "Ring"
        return all_gather_bus_bw
        
    else:
        info = "Warning: unknown collective type. Please choose from allreduce, allgather, alltoall, broadcast, reducescatter, reduce, multiallreduce."
        retcode = 1
        return -1
        
    return -1

def read_csv(file_path: str) -> List[List[str]]:
    """
    读取CSV文件 - 对应C++中的readCSV函数
    
    Args:
        file_path: CSV文件路径
        
    Returns:
        CSV数据的二维列表
    """
    if not os.path.exists(file_path):
        raise RuntimeError(f"Failed to open file: {file_path}")
    
    data = []
    with open(file_path, 'r') as file:
        reader = csv.reader(file)
        is_first_line = True
        
        for row in reader:
            if is_first_line:
                is_first_line = False
                continue
                
            # 清理每个单元格的数据
            cleaned_row = []
            for cell in row:
                cell = cell.strip()
                if not cell:
                    cell = "1"
                cleaned_row.append(cell)
                
            if cleaned_row:
                data.append(cleaned_row)
    
    return data

def interpolate(size: float, size1: float, size2: float, value1: float, value2: float) -> float:
    """线性插值函数"""
    return value1 + (value2 - value1) * (size - size1) / (size2 - size1)

def get_value(datasize: float, temp_nnode: int, data: List[List[str]]) -> float:
    """
    从CSV数据中获取插值结果 - 对应C++中的getValue函数
    
    Args:
        datasize: 数据大小
        temp_nnode: 节点数量
        data: CSV数据
        
    Returns:
        插值后的比例值
    """
    # 确定列索引
    col_index_map = {1: 1, 2: 2, 4: 3, 8: 4, 16: 5, 32: 6, 64: 7, 128: 8, 9: 9}
    col_index = col_index_map.get(temp_nnode, 5)
    
    if datasize == 0:
        return 1.0
        
    min_size = float(data[0][0])
    if datasize < min_size:
        return float(data[0][col_index]) / float(data[-1][col_index])
    
    # 查找插值区间
    for i in range(len(data) - 1):
        size1 = float(data[i][0])
        size2 = float(data[i + 1][0])
        if size1 <= datasize <= size2:
            value1 = float(data[i][col_index])
            value2 = float(data[i + 1][col_index])
            return interpolate(datasize, size1, size2, value1, value2) / float(data[-1][col_index])
    
    raise RuntimeError("Data size out of range")

def cal_busbw(node_type: GPUType, bw_intra: float, bw_per_nic: float, 
              nics_pernode: float, node_count: int, coll_type: str, 
              gpus_pernode: int, nic_type: str) -> BusBwResult:
    """
    计算总线带宽的主函数 - 对应C++中的cal_busbw函数
    
    Args:
        node_type: GPU类型
        bw_intra: NVLink带宽
        bw_per_nic: 每网卡带宽
        nics_pernode: 每节点网卡数量
        node_count: 节点数量
        coll_type: 通信类型
        gpus_pernode: 每节点GPU数量
        nic_type: 网卡类型
        
    Returns:
        BusBwResult对象，包含带宽和是否使用NVLink
    """
    global info, retcode
    
    result = BusBwResult(busbw=0.0, is_nvlink=False)
    params = CalculationParameters(
        node_type=node_type,
        node_count=node_count,
        nic_type=nic_type,
        coll_type=coll_type,
        cross_nic=2,
        nccl_algo="ring",
        gpus_pernode=gpus_pernode,
        nics_pernode=nics_pernode,
        bw_per_nic=bw_per_nic,
        bw_intra=bw_intra,
        group_split_mask=0,
        real_nics_pernode=float(nics_pernode),
        is_nvlink=False
    )
    
    retcode = 0
    info = "Success!"
    
    # 参数验证
    if params.node_count < 1:
        info = "Error: The number of nodes must be greater than 0."
        retcode = 1
    
    # 处理multi类型通信
    if params.coll_type.lower().startswith("multi"):
        params.nccl_algo = "Ring"
        params.cross_nic = 2
        if params.gpus_pernode == 8:
            params.group_split_mask = 7
        else:
            params.real_nics_pernode = float(params.nics_pernode) / params.gpus_pernode
            params.gpus_pernode = 1
        params.coll_type = params.coll_type[5:]  # 移除"multi"前缀
    
    # 处理group_split_mask
    if params.group_split_mask == 7:
        params.gpus_pernode = 1
        params.real_nics_pernode = float(params.nics_pernode) / 8.0
    elif params.group_split_mask == 3:
        params.gpus_pernode = 2
        params.real_nics_pernode = float(params.nics_pernode) / 4.0
    elif params.group_split_mask == 1:
        params.gpus_pernode = 4
        params.real_nics_pernode = float(params.nics_pernode) / 2.0
    
    if params.gpus_pernode * params.node_count == 1:
        info = "Warning: collective communication requires the participation of at least two gpus."
        retcode = 1
    
    bus_bw = 0.0
    if retcode == 0:
        bus_bw = calculate_bus_bw(params)
    
    if params.node_count == 1:
        params.cross_nic = 0
    
    result.busbw = bus_bw
    result.is_nvlink = params.is_nvlink
    return result

def cal_ratio(nic_ratio_data: List[List[str]], nvlink_ratio_data: List[List[str]], 
              ata_ratio_data: List[List[str]], data_size: int, nranks: int, 
              tp_size: int, gpus_per_server: int, group_type: str, 
              coll_type: str, is_nvlink: bool) -> float:
    """
    计算通信比例 - 对应C++中的cal_ratio函数
    
    Args:
        nic_ratio_data: NIC比例数据
        nvlink_ratio_data: NVLink比例数据
        ata_ratio_data: AllToAll比例数据
        data_size: 数据大小
        nranks: rank数量
        tp_size: TP大小
        gpus_per_server: 每服务器GPU数量
        group_type: 组类型
        coll_type: 通信类型
        is_nvlink: 是否使用NVLink
        
    Returns:
        计算得到的比例值
    """
    if coll_type.lower() in ["allgather", "reducescatter"] and group_type.lower() == "tp":
        data = nvlink_ratio_data if is_nvlink else nic_ratio_data
        temp_nnode = 1 if tp_size < gpus_per_server else tp_size // gpus_per_server
        return get_value(data_size, temp_nnode, data)
        
    elif coll_type.lower() == "alltoall" and group_type.lower() == "ep":
        data = ata_ratio_data
        if tp_size * nranks <= gpus_per_server:
            return get_value(data_size, 1, data)
        elif tp_size >= gpus_per_server:
            return get_value(data_size, 9, data)
        else:
            temp_nnode = (tp_size * nranks) // gpus_per_server
            return get_value(data_size, temp_nnode, data)
            
    elif coll_type.lower() == "alltoall" and group_type.lower() == "tp":
        data = ata_ratio_data
        if tp_size <= gpus_per_server:
            return get_value(data_size, 1, data)
        else:
            temp_nnode = tp_size // gpus_per_server
            return get_value(data_size, temp_nnode, data)
            
    elif group_type.lower() in ["dp", "dp_ep"]:
        return 1.0
    else:
        return 1.0