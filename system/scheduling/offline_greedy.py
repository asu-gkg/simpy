# Offline greedy scheduler - corresponds to scheduling/OfflineGreedy.hh/cc in SimAI

from typing import List, Dict, Optional, Any
import math
from ..common import Tick, ComType, InterDimensionScheduling


class DimElapsedTime:
    """维度耗时信息类 - 对应C++中的DimElapsedTime"""
    
    def __init__(self, dim_num: int):
        """初始化维度耗时信息
        
        Args:
            dim_num: 维度编号
        """
        self.dim_num = dim_num
        self.elapsed_time = 0.0
    
    def __lt__(self, other: 'DimElapsedTime') -> bool:
        """比较操作符，用于排序
        
        Args:
            other: 另一个DimElapsedTime对象
            
        Returns:
            如果当前耗时小于other的耗时返回True
        """
        return self.elapsed_time < other.elapsed_time


class OfflineGreedy:
    """离线贪心调度器 - 对应C++中的OfflineGreedy类
    
    用于多维度网络通信的离线贪心调度算法
    """
    
    # 静态类变量，对应C++中的静态成员
    chunk_schedule: Dict[int, List[int]] = {}
    schedule_consumer: Dict[int, int] = {}
    global_chunk_size: Dict[int, int] = {}
    
    def __init__(self, sys):
        """初始化离线贪心调度器
        
        Args:
            sys: 系统对象，对应C++中的Sys*
        """
        self.sys = sys
        self.dim_elapsed_time: List[DimElapsedTime] = []
        
        # 初始化维度信息
        if sys.dim_to_break == -1:
            self.dim_size = sys.physical_dims[:]  # 复制列表
            self.dim_BW = [0.0] * len(self.dim_size)
            
            for i in range(len(self.dim_size)):
                self.dim_BW[i] = sys.NI.get_BW_at_dimension(i)
                self.dim_elapsed_time.append(DimElapsedTime(i))
        else:
            self.dim_size = sys.logical_broken_dims[:]  # 复制列表
            self.dim_BW = [0.0] * len(self.dim_size)
            
            for i in range(len(self.dim_size)):
                if i > sys.dim_to_break:
                    self.dim_BW[i] = sys.NI.get_BW_at_dimension(i - 1)
                else:
                    self.dim_BW[i] = sys.NI.get_BW_at_dimension(i)
                self.dim_elapsed_time.append(DimElapsedTime(i))
        
        # 打印配置信息（仅在节点0上）
        if sys.id == 0:
            print("Themis is configured with the following parameters:")
            print("Dim size:", ", ".join(map(str, self.dim_size)))
            print("BW per dim:", ", ".join(map(str, self.dim_BW)))
            print()
    
    def reset_loads(self) -> None:
        """重置负载信息"""
        for i, dim in enumerate(self.dim_elapsed_time):
            dim.elapsed_time = 0.0
            dim.dim_num = i
    
    def get_chunk_size_from_elapsed_time(
        self,
        elapsed_time: float,
        dim: DimElapsedTime,
        comm_type: ComType
    ) -> int:
        """根据耗时计算chunk大小
        
        Args:
            elapsed_time: 耗时
            dim: 维度信息
            comm_type: 通信类型
            
        Returns:
            计算得到的chunk大小
        """
        if comm_type == ComType.Reduce_Scatter:
            result = (
                (elapsed_time * (self.dim_BW[dim.dim_num] / self.dim_BW[0])) /
                (((self.dim_size[dim.dim_num] - 1.0) / self.dim_size[dim.dim_num]))
            ) * 1048576
        else:  # All_Gather
            result = (
                (elapsed_time * (self.dim_BW[dim.dim_num] / self.dim_BW[0])) /
                (((self.dim_size[dim.dim_num] - 1.0) / 1.0))
            ) * 1048576
        
        return int(result)
    
    def get_chunk_scheduling(
        self,
        chunk_id: int,
        remaining_data_size_ref: List[int],  # 使用列表来模拟引用传递
        recommended_chunk_size: int,
        dimensions_involved: List[bool],
        inter_dim_scheduling: InterDimensionScheduling,
        comm_type: ComType
    ) -> List[int]:
        """获取chunk调度顺序 - 主要的调度算法
        
        Args:
            chunk_id: chunk标识符
            remaining_data_size_ref: 剩余数据大小（引用）
            recommended_chunk_size: 推荐的chunk大小
            dimensions_involved: 涉及的维度标志
            inter_dim_scheduling: 维度间调度策略
            comm_type: 通信类型
            
        Returns:
            调度顺序列表
        """
        remaining_data_size = remaining_data_size_ref[0]
        
        # 检查是否已经调度过
        if chunk_id in self.chunk_schedule:
            self.schedule_consumer[chunk_id] += 1
            
            if self.schedule_consumer[chunk_id] == len(self.sys.all_generators):
                # 所有生成器都消费了，清理缓存
                result = self.chunk_schedule[chunk_id][:]
                remaining_data_size -= self.global_chunk_size[chunk_id]
                del self.chunk_schedule[chunk_id]
                del self.schedule_consumer[chunk_id]
                del self.global_chunk_size[chunk_id]
                remaining_data_size_ref[0] = remaining_data_size
                return result
            
            remaining_data_size -= self.global_chunk_size[chunk_id]
            remaining_data_size_ref[0] = remaining_data_size
            return self.chunk_schedule[chunk_id][:]
        
        # 如果不是节点0，转发给节点0处理
        if self.sys.id != 0:
            return self.sys.all_generators[0].offline_greedy.get_chunk_scheduling(
                chunk_id,
                remaining_data_size_ref,
                recommended_chunk_size,
                dimensions_involved,
                inter_dim_scheduling,
                comm_type
            )
        
        # 节点0执行调度逻辑
        # All_Reduce转换为Reduce_Scatter
        if comm_type == ComType.All_Reduce:
            comm_type = ComType.Reduce_Scatter
        
        # 排序维度耗时
        self.dim_elapsed_time.sort()
        
        # All_Gather需要反向排序
        if comm_type == ComType.All_Gather:
            self.dim_elapsed_time.reverse()
        
        result = []
        chunk_size = recommended_chunk_size
        chunk_size_calculated = False
        
        if inter_dim_scheduling == InterDimensionScheduling.OfflineGreedy:
            self.global_chunk_size[chunk_id] = min(remaining_data_size, chunk_size)
            remaining_data_size -= min(remaining_data_size, chunk_size)
        
        dim_elapsed_time_pointer = -1
        
        for dim in self.dim_elapsed_time:
            dim_elapsed_time_pointer += 1
            
            if not dimensions_involved[dim.dim_num] or self.dim_size[dim.dim_num] == 1:
                result.append(dim.dim_num)
                continue
            
            # OfflineGreedyFlex逻辑
            elif (inter_dim_scheduling == InterDimensionScheduling.OfflineGreedyFlex and
                  not chunk_size_calculated):
                chunk_size_calculated = True
                
                if comm_type == ComType.Reduce_Scatter:
                    load_difference = abs(self.dim_elapsed_time[-1].elapsed_time - dim.elapsed_time)
                    chunk_size = self.get_chunk_size_from_elapsed_time(
                        load_difference, dim, ComType.Reduce_Scatter
                    )
                else:
                    # 找到最后一个有效维度
                    last_index = len(self.dim_elapsed_time) - 1
                    while (not dimensions_involved[self.dim_elapsed_time[last_index].dim_num] or
                           self.dim_size[self.dim_elapsed_time[last_index].dim_num] == 1):
                        last_index -= 1
                    
                    load_difference = abs(
                        self.dim_elapsed_time[last_index].elapsed_time - dim.elapsed_time
                    )
                    chunk_size = self.get_chunk_size_from_elapsed_time(
                        load_difference,
                        self.dim_elapsed_time[last_index],
                        ComType.All_Gather
                    )
                    
                    last_index -= 1
                    while dim_elapsed_time_pointer <= last_index:
                        if (dimensions_involved[self.dim_elapsed_time[last_index].dim_num] and
                            self.dim_size[self.dim_elapsed_time[last_index].dim_num] > 1):
                            chunk_size //= self.dim_size[self.dim_elapsed_time[last_index].dim_num]
                        last_index -= 1
                
                if chunk_size < recommended_chunk_size:
                    # 使用默认顺序
                    result = list(range(len(self.dim_elapsed_time)))
                    self.global_chunk_size[chunk_id] = min(remaining_data_size, recommended_chunk_size)
                    chunk_size = min(remaining_data_size, recommended_chunk_size)
                    remaining_data_size -= min(remaining_data_size, recommended_chunk_size)
                    
                    self.chunk_schedule[chunk_id] = result[:]
                    self.schedule_consumer[chunk_id] = 1
                    
                    # 重新排序
                    my_reordered = [None] * len(self.dim_elapsed_time)
                    for my_dim in range(len(self.dim_elapsed_time)):
                        for search_dim in range(len(self.dim_elapsed_time)):
                            if self.dim_elapsed_time[search_dim].dim_num == my_dim:
                                my_reordered[my_dim] = self.dim_elapsed_time[search_dim]
                                break
                    
                    self.dim_elapsed_time = my_reordered
                    
                    if comm_type == ComType.All_Gather:
                        self.dim_elapsed_time.reverse()
                    
                    # 更新耗时
                    for my_dim in range(len(self.dim_elapsed_time)):
                        if not dimensions_involved[my_dim] or self.dim_size[my_dim] == 1:
                            continue
                        
                        if comm_type == ComType.Reduce_Scatter:
                            self.dim_elapsed_time[my_dim].elapsed_time += (
                                ((chunk_size / 1048576.0) *
                                 ((self.dim_size[my_dim] - 1.0) / self.dim_size[my_dim])) /
                                (self.dim_BW[my_dim] / self.dim_BW[0])
                            )
                            chunk_size //= self.dim_size[my_dim]
                        else:
                            self.dim_elapsed_time[my_dim].elapsed_time += (
                                ((chunk_size / 1048576.0) *
                                 (self.dim_size[my_dim] - 1.0)) /
                                (self.dim_BW[my_dim] / self.dim_BW[0])
                            )
                            chunk_size *= self.dim_size[my_dim]
                    
                    remaining_data_size_ref[0] = remaining_data_size
                    return result
                else:
                    self.global_chunk_size[chunk_id] = min(remaining_data_size, chunk_size)
                    remaining_data_size -= min(remaining_data_size, chunk_size)
            
            # OfflineGreedy逻辑
            elif (inter_dim_scheduling == InterDimensionScheduling.OfflineGreedy and
                  not chunk_size_calculated):
                chunk_size_calculated = True
                diff_size = 0
                
                if comm_type == ComType.Reduce_Scatter:
                    load_difference = abs(self.dim_elapsed_time[-1].elapsed_time - dim.elapsed_time)
                    diff_size = self.get_chunk_size_from_elapsed_time(
                        load_difference, dim, ComType.Reduce_Scatter
                    )
                else:
                    # 找到最后一个有效维度
                    last_index = len(self.dim_elapsed_time) - 1
                    while (not dimensions_involved[self.dim_elapsed_time[last_index].dim_num] or
                           self.dim_size[self.dim_elapsed_time[last_index].dim_num] == 1):
                        last_index -= 1
                    
                    load_difference = abs(
                        self.dim_elapsed_time[last_index].elapsed_time - dim.elapsed_time
                    )
                    diff_size = self.get_chunk_size_from_elapsed_time(
                        load_difference,
                        self.dim_elapsed_time[last_index],
                        ComType.All_Gather
                    )
                    
                    last_index -= 1
                    while dim_elapsed_time_pointer <= last_index:
                        if (dimensions_involved[self.dim_elapsed_time[last_index].dim_num] and
                            self.dim_size[self.dim_elapsed_time[last_index].dim_num] > 1):
                            diff_size //= self.dim_size[self.dim_elapsed_time[last_index].dim_num]
                        last_index -= 1
                
                if diff_size < (recommended_chunk_size // 16):
                    # 使用默认顺序
                    result = list(range(len(self.dim_elapsed_time)))
                    self.chunk_schedule[chunk_id] = result[:]
                    self.schedule_consumer[chunk_id] = 1
                    
                    # 重新排序
                    my_reordered = [None] * len(self.dim_elapsed_time)
                    for my_dim in range(len(self.dim_elapsed_time)):
                        for search_dim in range(len(self.dim_elapsed_time)):
                            if self.dim_elapsed_time[search_dim].dim_num == my_dim:
                                my_reordered[my_dim] = self.dim_elapsed_time[search_dim]
                                break
                    
                    self.dim_elapsed_time = my_reordered
                    
                    if comm_type == ComType.All_Gather:
                        self.dim_elapsed_time.reverse()
                    
                    # 更新耗时
                    for my_dim in range(len(self.dim_elapsed_time)):
                        if not dimensions_involved[my_dim] or self.dim_size[my_dim] == 1:
                            continue
                        
                        if comm_type == ComType.Reduce_Scatter:
                            self.dim_elapsed_time[my_dim].elapsed_time += (
                                ((chunk_size / 1048576.0) *
                                 ((self.dim_size[my_dim] - 1.0) / self.dim_size[my_dim])) /
                                (self.dim_BW[my_dim] / self.dim_BW[0])
                            )
                            chunk_size //= self.dim_size[my_dim]
                        else:
                            self.dim_elapsed_time[my_dim].elapsed_time += (
                                ((chunk_size / 1048576.0) *
                                 (self.dim_size[my_dim] - 1.0)) /
                                (self.dim_BW[my_dim] / self.dim_BW[0])
                            )
                            chunk_size *= self.dim_size[my_dim]
                    
                    remaining_data_size_ref[0] = remaining_data_size
                    return result
            
            # 正常调度逻辑
            result.append(dim.dim_num)
            
            if comm_type == ComType.Reduce_Scatter:
                dim.elapsed_time += (
                    ((chunk_size / 1048576.0) *
                     ((self.dim_size[dim.dim_num] - 1.0) / self.dim_size[dim.dim_num])) /
                    (self.dim_BW[dim.dim_num] / self.dim_BW[0])
                )
                chunk_size //= self.dim_size[dim.dim_num]
            else:
                dim.elapsed_time += (
                    ((chunk_size / 1048576.0) *
                     (self.dim_size[dim.dim_num] - 1.0)) /
                    (self.dim_BW[dim.dim_num] / self.dim_BW[0])
                )
                chunk_size *= self.dim_size[dim.dim_num]
        
        self.chunk_schedule[chunk_id] = result[:]
        self.schedule_consumer[chunk_id] = 1
        remaining_data_size_ref[0] = remaining_data_size
        
        return result 