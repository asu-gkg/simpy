# StreamStat.py - corresponds to StreamStat.hh in SimAI
# This file contains stream statistics tracking classes

from typing import List, Dict, Any
from .common import BusType
from .callable import CallData
from .network_stat import NetworkStat
from .shared_bus_stat import SharedBusStat


class StreamStat(SharedBusStat, NetworkStat):
    """流统计类 - 对应C++版本的StreamStat类"""
    
    def __init__(self):
        """初始化流统计"""
        SharedBusStat.__init__(self, BusType.Shared, 0, 0, 0, 0)
        NetworkStat.__init__(self)
        
        self.queuing_delay: List[float] = []
        self.stream_stat_counter = 0
    
    def update_stream_stats(self, stream_stat: 'StreamStat'):
        """
        更新流统计
        
        Args:
            stream_stat: 要更新的流统计
        """
        self.update_bus_stats(BusType.Both, stream_stat)
        self.update_network_stat(stream_stat)
        
        # 扩展队列延迟列表
        if len(self.queuing_delay) < len(stream_stat.queuing_delay):
            diff = len(stream_stat.queuing_delay) - len(self.queuing_delay)
            self.queuing_delay.extend([0.0] * diff)
        
        # 累加队列延迟
        for i, tick in enumerate(stream_stat.queuing_delay):
            if i < len(self.queuing_delay):
                self.queuing_delay[i] += tick
        
        self.stream_stat_counter += 1
    
    def take_stream_stats_average(self):
        """计算流统计平均值"""
        self.take_bus_stats_average()
        self.take_network_stat_average()
        
        # 计算队列延迟平均值
        for i in range(len(self.queuing_delay)):
            self.queuing_delay[i] /= self.stream_stat_counter 