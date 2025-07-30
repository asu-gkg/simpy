"""
EventList - Discrete Event Simulation Scheduler

对应文件: eventlist.h/cpp
功能: 离散事件调度系统，管理仿真中的所有事件

主要类:
- EventList: 全局事件调度器 (单例模式)
- EventSource: 事件源基类
- TriggerTarget: 触发器目标

C++对应关系:
- EventList::doNextEvent() -> EventList.do_next_event()
- EventList::sourceIsPending() -> EventList.source_is_pending()
- EventList::now() -> EventList.now()
"""

from abc import ABC, abstractmethod
from typing import Optional, List, Tuple
import bisect
import sys

# 导入日志系统相关类
from .logger import Logged

# 对应 C++ 中的 simtime_picosec 类型 (uint64_t)
SimTime = int  # 皮秒级时间戳

# 对应 C++ 中的 triggerid_t 类型
TriggerId = int

# 特殊触发器起始时间常量
TRIGGER_START = -1


class TriggerTarget(ABC):
    """
    触发器目标 - 对应 trigger.h 中的 TriggerTarget 类
    
    所有可以被触发的对象都应该继承此类
    """
    
    @abstractmethod
    def activate(self) -> None:
        """
        对应 C++ 中的 TriggerTarget::activate()
        当触发器被激活时调用的纯虚函数
        """
        pass


class EventSource(Logged, ABC):
    """
    事件源基类 - 对应 eventlist.h/cpp 中的 EventSource 类
    
    所有需要调度事件的类都应该继承此类
    继承自 Logged 以提供日志功能
    """
    
    def __init__(self, eventlist: 'EventList', name: str):
        """对应 C++ 构造函数 EventSource(EventList& eventlist, const string& name)"""
        super().__init__(name)  # 调用 Logged 的构造函数
        self._eventlist = eventlist
    
    def __lt__(self, other):
        """
        对应 C++ 中 EventSource* 指针的比较
        在 multimap 中当时间戳相同时用于排序
        """
        if not isinstance(other, EventSource):
            return NotImplemented
        return id(self) < id(other)
    
    def __le__(self, other):
        """小于等于比较"""
        if not isinstance(other, EventSource):
            return NotImplemented
        return id(self) <= id(other)
    
    def __gt__(self, other):
        """大于比较"""
        if not isinstance(other, EventSource):
            return NotImplemented
        return id(self) > id(other)
    
    def __ge__(self, other):
        """大于等于比较"""
        if not isinstance(other, EventSource):
            return NotImplemented
        return id(self) >= id(other)
    
    @classmethod
    def create_with_name_only(cls, name: str):
        """对应 C++ 构造函数 EventSource(const string& name)"""
        # 注意：这里需要子类实现，因为需要调用 EventList::getTheEventList()
        eventlist = EventList.get_the_event_list()
        return cls(eventlist, name)
    
    @abstractmethod
    def do_next_event(self) -> None:
        """
        对应 C++ 中的 EventSource::doNextEvent()
        执行下一个事件的纯虚函数
        """
        pass
    
    def eventlist(self) -> 'EventList':
        """对应 C++ 中的 EventSource::eventlist()"""
        return self._eventlist


class EventList:
    """
    事件调度器 - 对应 eventlist.h/cpp 中的 EventList 类
    
    这是一个全局单例，管理所有事件的调度和执行
    严格按照C++实现的单例模式和静态成员变量
    """
    
    # 对应 C++ 静态成员变量
    _endtime: SimTime = 0
    _lasteventtime: SimTime = 0
    _pendingsources: List[Tuple[SimTime, EventSource]] = []  # 对应 multimap<simtime_picosec, EventSource*>
    _pending_triggers: List[TriggerTarget] = []  # 对应 vector<TriggerTarget*>
    _instance_count: int = 0
    _the_event_list: Optional['EventList'] = None
    
    # Handle 类型 - 对应 C++ 中的 multimap iterator
    class Handle:
        """对应 C++ 中的 EventList::Handle (multimap iterator)"""
        def __init__(self, index: int = -1):
            self.index = index
        
        def __eq__(self, other):
            if isinstance(other, EventList.Handle):
                return self.index == other.index
            return False
        
        def is_valid(self) -> bool:
            return self.index >= 0
    
    def __init__(self):
        """对应 C++ 构造函数，确保单例模式"""
        if EventList._instance_count != 0:
            print("There should be only one instance of EventList. Abort.", file=sys.stderr)
            sys.exit(1)  # 对应 C++ 中的 abort()
        
        EventList._the_event_list = self
        EventList._instance_count += 1
    
    # 禁用拷贝构造函数和赋值运算符
    def __copy__(self):
        raise RuntimeError("EventList cannot be copied")
    
    def __deepcopy__(self, memo):
        raise RuntimeError("EventList cannot be copied")
    
    @classmethod
    def get_the_event_list(cls) -> 'EventList':
        """对应 C++ 中的 EventList::getTheEventList()"""
        if cls._the_event_list is None:
            cls._the_event_list = cls()
        return cls._the_event_list
    
    @classmethod
    def set_endtime(cls, endtime: SimTime) -> None:
        """对应 C++ 中的 EventList::setEndtime()"""
        cls._endtime = endtime
    
    @classmethod
    def do_next_event(cls) -> bool:
        """
        对应 C++ 中的 EventList::doNextEvent()
        执行下一个事件，返回是否还有事件需要处理
        
        触发器立即发生 - 无时间流逝；不保证以任何特定顺序发生
        （不要假设 FIFO 或 LIFO）
        """
        # 触发器优先执行，立即执行 - 无时间流逝
        if cls._pending_triggers:
            target = cls._pending_triggers.pop()  # 对应 C++ 的 pop_back()
            target.activate()
            return True
        
        if not cls._pendingsources:
            return False
        
        # 获取最早的事件（multimap按key排序，所以第一个是最早的）
        nexteventtime, nextsource = cls._pendingsources.pop(0)  # 对应 C++ 的 begin() 和 erase()
        
        assert nexteventtime >= cls._lasteventtime, "Event time must be >= current time"
        # 在调用 doNextEvent 之前设置时间，以便 this::now() 准确
        cls._lasteventtime = nexteventtime
        nextsource.do_next_event()
        return True
    
    @classmethod
    def source_is_pending(cls, src: EventSource, when: SimTime) -> None:
        """
        对应 C++ 中的 EventList::sourceIsPending()
        调度事件源在指定时间执行
        """
        assert when >= cls.now(), "Cannot schedule event in the past"
        if cls._endtime == 0 or when < cls._endtime:
            # 插入到有序列表中，保持时间顺序（模拟 multimap 的行为）
            bisect.insort(cls._pendingsources, (when, src))
    
    @classmethod
    def source_is_pending_get_handle(cls, src: EventSource, when: SimTime) -> Handle:
        """
        对应 C++ 中的 EventList::sourceIsPendingGetHandle()
        调度事件并返回句柄用于后续取消
        """
        assert when >= cls.now(), "Cannot schedule event in the past"
        if cls._endtime == 0 or when < cls._endtime:
            entry = (when, src)
            bisect.insort(cls._pendingsources, entry)
            # 返回插入位置作为句柄
            handle_index = cls._pendingsources.index(entry)
            return cls.Handle(handle_index)
        return cls.null_handle()
    
    @classmethod
    def source_is_pending_rel(cls, src: EventSource, timefromnow: SimTime) -> None:
        """
        对应 C++ 中的 EventList::sourceIsPendingRel()
        相对当前时间调度事件
        """
        cls.source_is_pending(src, cls.now() + timefromnow)
    
    @classmethod
    def cancel_pending_source(cls, src: EventSource) -> None:
        """
        对应 C++ 中的 EventList::cancelPendingSource()
        取消待执行的事件源
        """
        for i, (when, source) in enumerate(cls._pendingsources):
            if source is src:
                cls._pendingsources.pop(i)
                return
    
    @classmethod
    def cancel_pending_source_by_time(cls, src: EventSource, when: SimTime) -> None:
        """
        对应 C++ 中的 EventList::cancelPendingSourceByTime()
        快速取消定时器 - 定时器必须存在
        这通常应该很快，除非我们有很多具有完全相同时间值的事件
        """
        # 查找具有指定时间的所有事件
        for i, (event_time, source) in enumerate(cls._pendingsources):
            if event_time == when and source is src:
                cls._pendingsources.pop(i)
                return
        # 如果没找到，按C++逻辑应该abort
        sys.exit(1)  # 对应 C++ 的 abort()
    
    @classmethod
    def cancel_pending_source_by_handle(cls, src: EventSource, handle: Handle) -> None:
        """
        对应 C++ 中的 EventList::cancelPendingSourceByHandle()
        如果我们经常取消定时器，按句柄取消它们。但要小心 - 
        取消已经被取消或已经过期的句柄是未定义的行为
        """
        if not handle.is_valid() or handle.index >= len(cls._pendingsources):
            raise RuntimeError("Invalid handle for cancellation")
        
        when, source = cls._pendingsources[handle.index]
        assert source is src, "Handle source mismatch"
        assert handle.index < len(cls._pendingsources), "Handle out of range"
        assert when >= cls.now(), "Cannot cancel past event"
        
        cls._pendingsources.pop(handle.index)
    
    @classmethod
    def reschedule_pending_source(cls, src: EventSource, when: SimTime) -> None:
        """
        对应 C++ 中的 EventList::reschedulePendingSource()
        重新调度待执行的事件
        """
        cls.cancel_pending_source(src)
        cls.source_is_pending(src, when)
    
    @classmethod
    def trigger_is_pending(cls, target: TriggerTarget) -> None:
        """
        对应 C++ 中的 EventList::triggerIsPending()
        添加待触发的触发器目标
        """
        cls._pending_triggers.append(target)
    
    @classmethod
    def now(cls) -> SimTime:
        """
        对应 C++ 中的 EventList::now()
        获取当前仿真时间
        """
        return cls._lasteventtime
    
    @classmethod
    def null_handle(cls) -> Handle:
        """对应 C++ 中的 EventList::nullHandle()"""
        return cls.Handle(-1)  # _pendingsources.end() 等效