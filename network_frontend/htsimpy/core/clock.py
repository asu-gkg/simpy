"""
Clock - 时钟事件生成器

对应文件: clock.h/cpp
功能: 定期生成时钟事件，用于周期性任务

主要类:
- Clock: 时钟事件生成器

C++对应关系:
- Clock::Clock() -> Clock.__init__()
- Clock::doNextEvent() -> Clock.do_next_event()
"""

from typing import Optional
from .eventlist import EventList, EventSource, SimTime


class Clock(EventSource):
    """
    时钟类 - 对应 clock.h/cpp 中的 Clock 类
    
    定期触发事件，用于仿真中的周期性任务
    
    C++定义:
    class Clock : public EventSource {
    public:
        Clock(simtime_picosec period, EventList& eventlist);
        void doNextEvent();
    private:
        simtime_picosec _period;
    };
    """
    
    def __init__(self, period: SimTime, eventlist: EventList):
        """
        对应 C++ 构造函数:
        Clock::Clock(simtime_picosec period, EventList& eventlist) 
            : EventSource(eventlist,"clock"), _period(period)
        {
            eventlist.sourceIsPending(*this,period);
        }
        
        Args:
            period: 时钟周期（皮秒）
            eventlist: 事件列表
        """
        # 调用基类构造函数 - 对应 EventSource(eventlist,"clock")
        super().__init__(eventlist, "clock")
        
        # 设置周期 - 对应 _period(period)
        self._period = period
        
        # 调度第一个时钟事件 - 对应 eventlist.sourceIsPending(*this,period);
        eventlist.source_is_pending(self, period)
    
    def do_next_event(self) -> None:
        """
        对应 C++ 中的 doNextEvent():
        
        void Clock::doNextEvent() {
            eventlist().sourceIsPending(*this,eventlist().now()+_period);
        }
        
        处理时钟事件并调度下一个时钟事件
        """
        # 调度下一个时钟事件
        # 对应 eventlist().sourceIsPending(*this,eventlist().now()+_period);
        self.eventlist().source_is_pending(
            self, 
            self.eventlist().now() + self._period
        )