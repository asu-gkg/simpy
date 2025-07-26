# NetworkStat class - corresponds to NetworkStat.hh in SimAI

from typing import List


class NetworkStat:
    """网络统计类 - 对应C++版本的NetworkStat类"""
    
    def __init__(self):
        """初始化网络统计"""
        self.net_message_latency: List[float] = []
        self.net_message_counter = 0
    
    def update_network_stat(self, other: 'NetworkStat'):
        """
        更新网络统计
        
        Args:
            other: 要合并的网络统计
        """
        # 扩展列表
        if len(self.net_message_latency) < len(other.net_message_latency):
            diff = len(other.net_message_latency) - len(self.net_message_latency)
            self.net_message_latency.extend([0.0] * diff)
        
        # 累加延迟
        for i, latency in enumerate(other.net_message_latency):
            if i < len(self.net_message_latency):
                self.net_message_latency[i] += latency
        
        self.net_message_counter += 1
    
    def take_network_stat_average(self):
        """计算网络统计平均值"""
        for i in range(len(self.net_message_latency)):
            self.net_message_latency[i] /= self.net_message_counter 