# Dataset class - corresponds to DataSet.cc/DataSet.hh in SimAI 

from typing import Optional, Tuple
from .callable import Callable, CallData
from .common import EventType, Tick
from .stream_stat import StreamStat
from .int_data import IntData
from .mock_nccl_log import MockNcclLog, NcclLogLevel
from .sys import Sys


class DataSet(Callable, StreamStat):
    """数据集类 - 对应C++版本的DataSet类"""
    
    # 静态ID自增计数器 - 对应C++版本的static int id_auto_increment
    id_auto_increment = 0
    
    def __init__(self, total_streams: int):
        """
        初始化数据集 - 对应C++版本的DataSet构造函数
        
        Args:
            total_streams: 总流数
        """
        Callable.__init__(self)
        StreamStat.__init__(self)
        
        # 生成唯一ID - 对应C++版本的this->my_id = id_auto_increment++
        self.my_id = DataSet.id_auto_increment
        DataSet.id_auto_increment += 1
        
        # 流相关属性 - 对应C++版本的成员变量
        self.total_streams = total_streams
        self.finished_streams = 0
        self.finished = False
        self.active = True
        
        # 时间相关属性 - 对应C++版本的时间成员
        self.finish_tick = 0
        self.creation_tick = Sys.boostedTick()  # 对应C++版本的Sys::boostedTick()
        self.comm_start_tick = 0
        self.total_comm_time = 0
        
        # 通知器 - 对应C++版本的std::pair<Callable*, EventType>* notifier
        self.notifier: Optional[Tuple[Callable, EventType]] = None
    
    def set_notifier(self, layer: Callable, event: EventType) -> None:
        """
        设置通知器 - 对应C++版本的set_notifier方法
        
        Args:
            layer: 要通知的层
            event: 事件类型
        """
        # 对应C++版本: notifier = new std::pair<Callable*, EventType>(layer, event)
        self.notifier = (layer, event)
    
    def notify_stream_finished(self, data: Optional[StreamStat]) -> None:
        """
        通知流完成 - 对应C++版本的notify_stream_finished方法
        
        Args:
            data: 流统计数据
        """
        # 获取日志实例 - 对应C++版本的MockNcclLog::getInstance()
        nccl_log = MockNcclLog.getInstance()
        
        # 记录调试日志 - 对应C++版本的writeLog调用
        nccl_log.writeLog(
            NcclLogLevel.DEBUG, 
            "notify_stream_finished id: %d finished_streams: %d total streams: %d notify %s",
            self.my_id, 
            self.finished_streams + 1, 
            self.total_streams, 
            hex(id(self.notifier)) if self.notifier else "nullptr"
        )
        
        # 增加完成流计数 - 对应C++版本的finished_streams++
        self.finished_streams += 1
        
        # 更新统计数据 - 对应C++版本的update_stream_stats调用
        if data is not None:
            self.update_stream_stats(data)
        
        # 检查是否所有流都完成 - 对应C++版本的finished_streams == total_streams判断
        if self.finished_streams == self.total_streams:
            self.finished = True
            self.finish_tick = Sys.boostedTick()  # 对应C++版本的Sys::boostedTick()
            
            # 处理通知器 - 对应C++版本的notifier处理逻辑
            if self.notifier is not None:
                nccl_log.writeLog(NcclLogLevel.DEBUG, "notify_stream_finished notifier != nullptr ")
                
                # 计算统计平均值 - 对应C++版本的take_stream_stats_average()
                self.take_stream_stats_average()
                
                # 获取回调信息 - 对应C++版本的获取notifier内容
                callable_obj, event_type = self.notifier
                
                # 清空通知器 - 对应C++版本的delete notifier
                self.notifier = None
                
                # 调用回调 - 对应C++版本的c->call(ev, new IntData(my_id))
                callable_obj.call(event_type, IntData(self.my_id))
            else:
                nccl_log.writeLog(NcclLogLevel.ERROR, "notify_stream_finished notifier = nullptr ")
    
    def call(self, event_type: EventType, data: CallData) -> None:
        """
        处理事件 - 实现Callable接口，对应C++版本的call方法
        
        Args:
            event_type: 事件类型
            data: 事件数据
        """
        # 对应C++版本: notify_stream_finished(((StreamStat*)data))
        stream_stat_data = data if isinstance(data, StreamStat) else None
        self.notify_stream_finished(stream_stat_data)
    
    def is_finished(self) -> bool:
        """
        检查是否完成 - 对应C++版本的is_finished方法
        
        Returns:
            是否完成
        """
        return self.finished 