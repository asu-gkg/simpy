# Dataset class - corresponds to DataSet.cc/DataSet.hh in SimAI 

from typing import Optional, Tuple
from .callable import Callable, CallData
from .common import EventType, Tick
from .stream_stat import StreamStat


class DataSet(Callable, StreamStat):
    """数据集类 - 对应C++版本的DataSet类"""
    
    # 静态ID自增计数器
    id_auto_increment = 0
    
    def __init__(self, total_streams: int):
        """
        初始化数据集
        
        Args:
            total_streams: 总流数
        """
        Callable.__init__(self)
        StreamStat.__init__(self)
        
        # 生成唯一ID
        DataSet.id_auto_increment += 1
        self.my_id = DataSet.id_auto_increment
        
        # 流相关属性
        self.total_streams = total_streams
        self.finished_streams = 0
        self.finished = False
        self.active = True
        
        # 时间相关属性
        self.finish_tick = 0
        self.creation_tick = 0
        self.comm_start_tick = 0
        self.total_comm_time = 0
        
        # 通知器
        self.notifier: Optional[Tuple[Callable, EventType]] = None
    
    def set_notifier(self, layer: Callable, event: EventType):
        """
        设置通知器
        
        Args:
            layer: 要通知的层
            event: 事件类型
        """
        self.notifier = (layer, event)
    
    def notify_stream_finished(self, data: StreamStat):
        """
        通知流完成
        
        Args:
            data: 流统计数据
        """
        self.finished_streams += 1
        
        if self.finished_streams >= self.total_streams:
            self.finished = True
            self.active = False
            self.finish_tick = data.finish_tick
            
            # 通知层
            if self.notifier:
                layer, event = self.notifier
                layer.call(event, None)
    
    def call(self, event_type: EventType, data: CallData) -> None:
        """
        处理事件 - 实现Callable接口
        
        Args:
            event_type: 事件类型
            data: 事件数据
        """
        # 这里可以添加特定的事件处理逻辑
        pass
    
    def is_finished(self) -> bool:
        """
        检查是否完成
        
        Returns:
            是否完成
        """
        return self.finished 