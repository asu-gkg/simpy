# Layer计算模块 - 对应Layer.cc的计算和带宽计算方法
#
# 对应关系：
# - cal_ratio() -> Layer::cal_ratio()
# - _get_value() -> Layer::cal_ratio() 中的辅助逻辑
# - compute_time() -> Layer::compute_time()
# - _get_collective_type_string() -> Layer::compute_time() 中的辅助逻辑
# - _cal_busbw() -> Layer::compute_time() 中的辅助逻辑
# - compute_busbw() -> Layer::compute_busbw()

from system.common import ComType, Tick
from system.mock_nccl_group import GroupType
import math


# 精准复现C++版本的常量定义
CLOCK_PERIOD = 1
FREQ = 1000.0 / CLOCK_PERIOD
GBPS = 1.0 / (1024 * 1024 * 1024)  # 对应C++版本的GBps


class LayerComputation:
    """Layer计算类 - 包含带宽计算和通信时间计算逻辑"""
    
    def cal_ratio(self, data_size: int, nranks: int, tp_size: int,
                  gpus_per_server: int, group_type: GroupType, coll_type: str, is_nvlink: bool) -> float:
        """计算比率 - 精准复现C++版本的cal_ratio方法"""
        # 获取比率数据
        nic_ratio_data = self.generator.nic_ratio_data if hasattr(self.generator, 'nic_ratio_data') else []
        nvlink_ratio_data = self.generator.nvlink_ratio_data if hasattr(self.generator, 'nvlink_ratio_data') else []
        ata_ratio_data = self.generator.ata_ratio_data if hasattr(self.generator, 'ata_ratio_data') else []

        if (coll_type in ["allgather", "reducescatter"]) and group_type == GroupType.TP:
            data = nvlink_ratio_data if is_nvlink else nic_ratio_data
            temp_nnode = 1 if tp_size < gpus_per_server else tp_size // gpus_per_server
            return self._get_value(data_size, temp_nnode, data)

        elif coll_type == "alltoall" and group_type == GroupType.EP:
            data = ata_ratio_data
            if tp_size * nranks <= gpus_per_server:
                return self._get_value(data_size, 1, data)
            elif tp_size >= gpus_per_server:  # multi
                return self._get_value(data_size, 9, data)
            else:
                temp_nnode = (tp_size * nranks) // gpus_per_server
                return self._get_value(data_size, temp_nnode, data)

        elif coll_type == "alltoall" and group_type == GroupType.TP:
            data = ata_ratio_data
            if tp_size <= gpus_per_server:
                return self._get_value(data_size, 1, data)
            else:
                temp_nnode = tp_size // gpus_per_server
                return self._get_value(data_size, temp_nnode, data)

        elif group_type in [GroupType.DP, GroupType.DP_EP]:
            return 1.0
        else:
            return 1.0

    def _get_value(self, data_size: int, nnode: int, data: list) -> float:
        """从数据中获取值 - 精准复现C++版本的getValue方法"""
        if not data or len(data) == 0:
            return 1.0
            
        # 根据节点数量选择列索引，精准复现C++版本的逻辑
        col_index = 0
        if nnode == 1:
            col_index = 1
        elif nnode == 2:
            col_index = 2
        elif nnode == 4:
            col_index = 3
        elif nnode == 8:
            col_index = 4
        elif nnode == 16:
            col_index = 5
        elif nnode == 32:
            col_index = 6
        elif nnode == 64:
            col_index = 7
        elif nnode == 128:
            col_index = 8
        elif nnode == 9:
            col_index = 9
        else:
            col_index = 5  # 默认值
            
        if data_size == 0:
            return 1.0
            
        # 获取最小数据大小
        try:
            min_size = float(data[0][0])
        except (IndexError, ValueError):
            return 1.0
            
        # 如果数据大小小于最小值，返回第一个值除以最后一个值
        if data_size < min_size:
            try:
                first_value = float(data[0][col_index])
                last_value = float(data[-1][col_index])
                return first_value / last_value if last_value != 0 else 1.0
            except (IndexError, ValueError):
                return 1.0
                
        # 数据插值计算，精准复现C++版本的逻辑
        for i in range(len(data) - 1):
            try:
                size1 = float(data[i][0])
                size2 = float(data[i + 1][0])
                if data_size >= size1 and data_size <= size2:
                    value1 = float(data[i][col_index])
                    value2 = float(data[i + 1][col_index])
                    interpolated_value = self._interpolate(data_size, size1, size2, value1, value2)
                    # 除以最后一个值，精准复现C++版本的逻辑
                    last_value = float(data[-1][col_index])
                    return interpolated_value / last_value if last_value != 0 else 1.0
            except (IndexError, ValueError):
                continue
                
        # 如果数据大小超出范围，抛出异常（对应C++版本的runtime_error）
        raise RuntimeError("Data size out of range")

    def _interpolate(self, size: float, size1: float, size2: float, value1: float, value2: float) -> float:
        """插值计算 - 精准复现C++版本的interpolate函数"""
        if size2 == size1:
            return value1
        return value1 + (value2 - value1) * (size - size1) / (size2 - size1)

    def compute_time(self, comtype: ComType, tp_size: int, nranks: int, data_size: int,
                    group_type: GroupType, all_gpus: int, ep_size: int) -> Tick:
        """计算通信时间 - 精准复现C++版本的compute_time方法"""
        if comtype == ComType.None_:
            return 0

        # 精准复现C++版本的特殊处理逻辑
        if 1 < data_size < 1048576:
            if nranks == 2:
                return 10000
            elif nranks == 4:
                return 12000
            elif nranks == 8:
                return 15000
            elif nranks == 16:
                return 66000
            elif nranks == 32:
                return 135000
            elif nranks == 64:
                return 200000
            elif nranks == 128:
                return 320000

        # 获取参数配置（这些应该从系统参数中获取）
        gpus_per_server = getattr(self.generator, 'gpus_per_server', 8)
        nvlink_bw = getattr(self.generator, 'nvlink_bw', 300.0)  # GB/s
        bw_per_nic = getattr(self.generator, 'bw_per_nic', 100.0)  # GB/s
        nics_per_server = getattr(self.generator, 'nics_per_server', 8)
        gpu_type = getattr(self.generator, 'gpu_type', 'A100')
        nic_type = getattr(self.generator, 'nic_type', 'IB')

        # 确定通信类型字符串
        coll_type = self._get_collective_type_string(comtype)

        # 计算带宽结果
        result = self._cal_busbw(gpu_type, nvlink_bw, bw_per_nic, nics_per_server,
                                group_type.value, coll_type, tp_size, nranks, gpus_per_server,
                                ep_size, nic_type)

        # 计算带宽比率
        bw_ratio = self.cal_ratio(data_size, nranks, tp_size, gpus_per_server,
                                 group_type, coll_type, result.get('is_nvlink', False))

        # 输出调试信息，精准复现C++版本的输出格式
        if self.generator.id == 0:
            print(f"Communication Type: {coll_type}Communication Group: {group_type.value}Group Size: {nranks}Data Size: {data_size}Ratio: {bw_ratio}Bottleneck is nvlink: {result.get('is_nvlink', False)}")

        # 计算通信时间，精准复现C++版本的计算公式
        busbw = result.get('busbw', 100.0)  # GB/s

        if comtype == ComType.All_Reduce:
            comp_time = data_size * GBPS / (bw_ratio * busbw) * 1e9 * 2 * (nranks - 1) / (nranks / 1.0)
        else:
            comp_time = data_size * GBPS / (bw_ratio * busbw) * 1e9 * (nranks - 1) / (nranks / 1.0)

        return int(comp_time)

    def _get_collective_type_string(self, comtype: ComType) -> str:
        """获取通信类型字符串"""
        if comtype == ComType.All_Reduce:
            return "allreduce"
        elif comtype == ComType.All_Gather:
            return "allgather"
        elif comtype == ComType.Reduce_Scatter:
            return "reducescatter"
        elif comtype == ComType.All_to_All:
            return "alltoall"
        else:
            return "unknown"

    def _cal_busbw(self, gpu_type: str, nvlink_bw: float, bw_per_nic: float,
                nics_per_server: int, group_type: str, coll_type: str,
                tp_size: int, nranks: int, gpus_per_server: int,
                ep_size: int, nic_type: str) -> dict:
        """计算总线带宽 - 精准复现C++版本的逻辑"""
        result = {'busbw': 100.0, 'is_nvlink': False}

        if group_type == "TP":
            # TP 通信内部
            if tp_size <= gpus_per_server:
                result['busbw'] = nvlink_bw
                result['is_nvlink'] = True
            else:
                node_count = tp_size // gpus_per_server
                result['busbw'] = bw_per_nic * nics_per_server / node_count
                result['is_nvlink'] = False

        elif group_type == "EP" and nranks > 1:
            if tp_size * nranks <= gpus_per_server:
                temp_gpus_per_server = gpus_per_server // tp_size
                result['busbw'] = nvlink_bw
                result['is_nvlink'] = True
            else:
                node_count = (tp_size * nranks) // gpus_per_server
                temp_gpus_per_server = gpus_per_server // tp_size if gpus_per_server // tp_size > 1 else 1
                temp_nics_per_server = nics_per_server // gpus_per_server if tp_size > gpus_per_server else nics_per_server // tp_size
                result['busbw'] = bw_per_nic * temp_nics_per_server / node_count
                result['is_nvlink'] = False

        elif group_type == "DP" and nranks > 1:
            if tp_size <= gpus_per_server:
                temp_gpus_per_server = gpus_per_server // tp_size
                temp_nics_per_server = nics_per_server // tp_size
                result['busbw'] = bw_per_nic * temp_nics_per_server / nranks
            else:
                temp_nics_per_server = nics_per_server // gpus_per_server
                result['busbw'] = bw_per_nic * temp_nics_per_server / nranks
            result['is_nvlink'] = False

        elif group_type == "DP_EP" and nranks > 1:
            if tp_size * ep_size <= gpus_per_server:
                temp_nics_per_server = nics_per_server // (tp_size * ep_size)
                temp_gpus_per_server = gpus_per_server // (tp_size * ep_size)
                result['busbw'] = bw_per_nic * temp_nics_per_server / nranks
            else:
                temp_nics_per_server = nics_per_server // gpus_per_server
                result['busbw'] = bw_per_nic * temp_nics_per_server / nranks
            result['is_nvlink'] = False

        return result

    def compute_busbw(self, comtype: ComType, nranks: int, data_size: int, total_comm: Tick) -> tuple:
        """计算总线带宽 - 精准复现C++版本的compute_busbw方法"""
        # 精准复现C++版本的计算公式
        algbw = data_size / (total_comm / FREQ) * 1000000 * GBPS if total_comm > 0 else 0.0

        # 计算总线带宽，精准复现C++版本的逻辑
        if comtype == ComType.All_Reduce:
            busbw = algbw * 2 * (nranks - 1) / (nranks / 1.0) if nranks > 0 else 0.0
        elif comtype in [ComType.All_Gather, ComType.Reduce_Scatter, ComType.All_to_All]:
            busbw = algbw * (nranks - 1) / (nranks / 1.0) if nranks > 0 else 0.0
        else:
            busbw = 0.0

        return (algbw, busbw) 