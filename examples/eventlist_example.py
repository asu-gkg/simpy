#!/usr/bin/env python3
"""
EventList 使用示例 - 简单易懂的离散事件仿真演示

这个示例展示了如何使用 EventList 来调度和执行事件
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
import rich
from network_frontend.htsimpy.core.eventlist import EventList, EventSource, TriggerTarget, SimTime

# 定义时间常量，方便理解
SECOND = 1_000_000_000_000  # 1秒 = 1万亿皮秒
MILLISECOND = 1_000_000_000  # 1毫秒 = 10亿皮秒
MICROSECOND = 1_000_000      # 1微秒 = 100万皮秒


class SimpleEventSource(EventSource):
    """
    简单事件源示例 - 模拟一个定时器
    """
    
    def __init__(self, eventlist: EventList, name: str, message: str):
        super().__init__(eventlist, name)
        self.message = message
        self.count = 0
    
    def do_next_event(self) -> None:
        """当事件被触发时执行"""
        self.count += 1
        current_time = self.eventlist().now()
        print(f"[{current_time / MICROSECOND:.1f}μs] {self._name}: {self.message} (第{self.count}次)")
        
        # 如果还没执行够3次，继续调度下一次事件
        # if self.count < 3:
        #     # 1秒后再次触发
        #     self.eventlist().source_is_pending_rel(self, SECOND)


class TriggerExample(TriggerTarget):
    """
    触发器示例 - 立即执行的事件
    """
    
    def __init__(self, name: str):
        self.name = name
    
    def activate(self) -> None:
        """触发器被激活时立即执行"""
        current_time = EventList.now()
        print(f"[{current_time / MICROSECOND:.1f}μs] 🔥 触发器 '{self.name}' 被激活!")


def main():
    """主函数 - 演示 EventList 的基本用法"""
    print("=== EventList 使用示例 ===\n")
    
    # 1. 获取全局事件调度器实例
    eventlist = EventList.get_the_event_list()
    print(f"当前时间: {eventlist.now() / MICROSECOND:.1f}μs")
    rich.inspect(eventlist)
    # # 2. 创建一些事件源
    timer1 = SimpleEventSource(eventlist, "定时器A", "Hello from Timer A!")
    timer2 = SimpleEventSource(eventlist, "定时器B", "Hello from Timer B!")
    
    # # 3. 调度事件 - 使用绝对时间
    print("\n--- 调度事件 ---")
    current_time = eventlist.now()
    
    # # 1秒后触发定时器A
    eventlist.source_is_pending(timer1, current_time + SECOND)
    print(f"调度定时器A在 {current_time + SECOND / MICROSECOND:.1f}μs")
    
    # # 2秒后触发定时器B
    eventlist.source_is_pending(timer2, current_time + 2 * SECOND)
    print(f"调度定时器B在 {current_time + 2 * SECOND / MICROSECOND:.1f}μs")
    
    # 4. 添加触发器 - 立即执行
    print("\n--- 添加触发器 ---")
    trigger1 = TriggerExample("紧急通知")
    trigger2 = TriggerExample("系统检查")
    
    eventlist.trigger_is_pending(trigger1)
    eventlist.trigger_is_pending(trigger2)
    print("添加了两个触发器")
    
    # 5. 执行事件循环
    print("\n--- 开始事件循环 ---")
    step = 0
    while eventlist.do_next_event():
        step += 1
        print(f"当前时间: {eventlist.now() / MICROSECOND:.1f}μs")
        print(f"步骤 {step}: 执行了一个事件")
        
        # 限制执行步数，避免无限循环
        if step >= 2:
            print("达到最大步数限制，停止执行")
            break
    
    print(f"\n仿真结束，最终时间: {eventlist.now() / MICROSECOND:.1f}μs")


def example_with_handles():
    """演示使用句柄来取消事件的示例"""
    print("\n\n=== 使用句柄取消事件示例 ===\n")
    
    # 重置事件列表（仅用于演示）
    EventList.reset()
    eventlist = EventList.get_the_event_list()
    
    class CancellableTimer(EventSource):
        def __init__(self, eventlist: EventList, name: str):
            super().__init__(eventlist, name)
            self.handle = None
        
        def do_next_event(self) -> None:
            current_time = self.eventlist().now()
            print(f"[{current_time / MICROSECOND:.1f}μs] ⏰ {self._name} 被触发!")
    
    # 创建定时器
    timer = CancellableTimer(eventlist, "可取消定时器")
    
    # 使用句柄调度事件
    current_time = eventlist.now()
    handle = eventlist.source_is_pending_get_handle(timer, current_time + 2 * SECOND)
    print(f"调度定时器在 {current_time + 2 * SECOND / MICROSECOND:.1f}μs")
    
    # 等待1秒
    eventlist.source_is_pending_rel(timer, SECOND)
    
    # 取消事件
    print("1秒后取消定时器...")
    eventlist.cancel_pending_source_by_handle(timer, handle)
    
    # 执行事件循环
    print("执行事件循环:")
    step = 0
    while eventlist.do_next_event() and step < 5:
        step += 1
        print(f"步骤 {step}: 执行了一个事件")
    
    print("定时器被成功取消，没有触发")


if __name__ == "__main__":
    # main()
    example_with_handles() 