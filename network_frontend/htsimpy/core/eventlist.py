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
from typing import Optional, List, Tuple, Dict
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
        """
        对应 C++ 构造函数 EventSource(EventList& eventlist, const string& name)
        : Logged(name), _eventlist(eventlist) {};
        """
        super().__init__(name)  # 对应 Logged(name)
        self._eventlist = eventlist  # 对应 _eventlist(eventlist)
    
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
        """
        对应 C++ 构造函数 EventSource(const string& name)
        
        C++实现: EventSource::EventSource(const string& name) 
                : EventSource(EventList::getTheEventList(), name) 
        """
        eventlist = EventList.get_the_event_list()
        return cls(eventlist, name)
    
    @abstractmethod
    def do_next_event(self) -> None:
        """
        对应 C++ 中的 EventSource::doNextEvent()
        virtual void doNextEvent() = 0;
        """
        pass
    
    def eventlist(self) -> 'EventList':
        """
        对应 C++ 中的 EventSource::eventlist()
        inline EventList& eventlist() const {return _eventlist;}
        """
        return self._eventlist


class EventList:
    """
    事件调度器 - 对应 eventlist.h/cpp 中的 EventList 类
    
    这是一个全局单例，管理所有事件的调度和执行
    严格按照C++实现的单例模式和静态成员变量
    
    重要：为了精确模拟C++ multimap的行为，我们使用了一个更复杂的数据结构
    """
    
    # 对应 C++ 静态成员变量
    _endtime: SimTime = 0
    _lasteventtime: SimTime = 0
    _pending_triggers: List[TriggerTarget] = []  # 对应 vector<TriggerTarget*>
    _instance_count: int = 0
    _the_event_list: Optional['EventList'] = None
    
    # 使用字典+列表模拟C++ multimap的行为
    # key是时间戳，value是该时间戳的所有事件源列表
    _pending_by_time: Dict[SimTime, List[EventSource]] = {}
    # 按时间排序的时间戳列表
    _sorted_times: List[SimTime] = []
    
    # Handle 类型 - 对应 C++ 中的 multimap iterator
    class Handle:
        """
        对应 C++ 中的 EventList::Handle (multimap iterator)
        存储时间戳和事件源的引用，以便后续取消
        """
        def __init__(self, time: SimTime = -1, source: Optional[EventSource] = None):
            self.time = time
            self.source = source
        
        def __eq__(self, other):
            if isinstance(other, EventList.Handle):
                return self.time == other.time and self.source == other.source
            return False
        
        def is_valid(self) -> bool:
            return self.time >= 0 and self.source is not None
    
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
        """
        对应 C++ 中的 EventList::getTheEventList()
        
        C++实现:
        EventList& EventList::getTheEventList()
        {
            if (EventList::_theEventList == nullptr) 
            {
                EventList::_theEventList = new EventList();
            }
            return *EventList::_theEventList;
        }
        """
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
        # triggers happen immediately - no time passes; no guarantee that
        # they happen in any particular order (don't assume FIFO or LIFO).
        if cls._pending_triggers:  # 对应 if (!_pending_triggers.empty())
            target = cls._pending_triggers.pop()  # 对应 _pending_triggers.back() 和 pop_back()
            target.activate()  # 对应 target->activate()
            return True
        
        # 对应 if (_pendingsources.empty()) return false;
        if not cls._sorted_times:
            return False
        
        # 对应 simtime_picosec nexteventtime = _pendingsources.begin()->first;
        nexteventtime = cls._sorted_times[0]
        
        # 对应 EventSource* nextsource = _pendingsources.begin()->second;
        sources = cls._pending_by_time.get(nexteventtime, [])
        if not sources:
            # 清理空的时间条目
            cls._sorted_times.pop(0)
            del cls._pending_by_time[nexteventtime]
            return cls.do_next_event()  # 递归处理下一个
        
        nextsource = sources.pop(0)
        
        # 对应 _pendingsources.erase(_pendingsources.begin());
        if not sources:
            cls._sorted_times.pop(0)
            del cls._pending_by_time[nexteventtime]
        
        # 对应 assert(nexteventtime >= _lasteventtime);
        assert nexteventtime >= cls._lasteventtime
        # 对应 _lasteventtime = nexteventtime;
        cls._lasteventtime = nexteventtime
        # 对应 nextsource->doNextEvent();
        nextsource.do_next_event()
        return True
    
    @classmethod
    def source_is_pending(cls, src: EventSource, when: SimTime) -> None:
        """
        对应 C++ 中的 EventList::sourceIsPending()
        调度事件源在指定时间执行
        
        C++: void EventList::sourceIsPending(EventSource &src, simtime_picosec when)
        """
        # 对应 assert(when>=now());
        # 对应 assert(when>=now());
        # 允许当前时间的事件
        if when < cls.now():
            when = cls.now()
        # 对应 if (_endtime==0 || when<_endtime)
        if cls._endtime == 0 or when < cls._endtime:
            # 对应 _pendingsources.insert(make_pair(when,&src));
            if when not in cls._pending_by_time:
                cls._pending_by_time[when] = []
                # 使用二分查找插入时间，保持排序
                import bisect
                bisect.insort(cls._sorted_times, when)
            
            cls._pending_by_time[when].append(src)
    
    @classmethod
    def source_is_pending_get_handle(cls, src: EventSource, when: SimTime) -> Handle:
        """
        对应 C++ 中的 EventList::sourceIsPendingGetHandle()
        调度事件并返回句柄用于后续取消
        """
        assert when >= cls.now(), "Cannot schedule event in the past"
        if cls._endtime == 0 or when < cls._endtime:
            # 添加事件
            cls.source_is_pending(src, when)
            # 返回句柄
            return cls.Handle(when, src)
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
        
        C++ 实现:
        pendingsources_t::iterator i = _pendingsources.begin();
        while (i != _pendingsources.end()) {
            if (i->second == &src) {
                _pendingsources.erase(i);
                return;
            }
            i++;
        }
        """
        # 遍历所有时间槽，查找并删除第一个匹配的事件源
        for when in list(cls._sorted_times):  # 按时间顺序遍历
            sources = cls._pending_by_time.get(when, [])
            if src in sources:
                sources.remove(src)  # 只删除第一个匹配的
                # 如果该时间没有更多事件，清理时间条目
                if not sources:
                    cls._sorted_times.remove(when)
                    del cls._pending_by_time[when]
                return  # 找到并删除后立即返回
    
    @classmethod
    def cancel_pending_source_by_time(cls, src: EventSource, when: SimTime) -> None:
        """
        对应 C++ 中的 EventList::cancelPendingSourceByTime()
        快速取消定时器 - 定时器必须存在
        这通常应该很快，除非我们有很多具有完全相同时间值的事件
        """
        if when in cls._pending_by_time:
            sources = cls._pending_by_time[when]
            if src in sources:
                sources.remove(src)
                # 如果该时间没有更多事件，清理时间条目
                if not sources:
                    cls._sorted_times.remove(when)
                    del cls._pending_by_time[when]
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
        if not handle.is_valid():
            raise RuntimeError("Invalid handle for cancellation")
        
        assert handle.source is src, "Handle source mismatch"
        assert handle.time >= cls.now(), "Cannot cancel past event"
        
        # 使用handle中存储的时间和源进行精确取消
        if handle.time in cls._pending_by_time:
            sources = cls._pending_by_time[handle.time]
            if handle.source in sources:
                sources.remove(handle.source)
                # 如果该时间没有更多事件，清理时间条目
                if not sources:
                    cls._sorted_times.remove(handle.time)
                    del cls._pending_by_time[handle.time]
            else:
                raise RuntimeError("Handle source not found in pending sources")
        else:
            raise RuntimeError("Handle time not found in pending sources")
    
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
        return cls.Handle(-1, None)  # _pendingsources.end() 等效
    
    @classmethod
    def pending_count(cls) -> int:
        """返回待处理事件的总数（用于测试和调试）"""
        return sum(len(sources) for sources in cls._pending_by_time.values())
    
    @classmethod
    def reset(cls) -> None:
        """重置所有静态成员变量（仅用于测试）"""
        cls._endtime = 0
        cls._lasteventtime = 0
        cls._pending_triggers.clear()
        cls._pending_by_time.clear()
        cls._sorted_times.clear()
        cls._instance_count = 0
        cls._the_event_list = None