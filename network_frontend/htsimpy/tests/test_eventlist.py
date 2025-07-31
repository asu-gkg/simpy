"""
EventList Unit Tests

测试EventList的功能，确保与C++版本行为一致

测试覆盖：
1. 单例模式
2. 基本事件调度
3. Handle机制
4. 取消事件
5. 重新调度
6. 触发器
7. 时间管理
8. 多事件同时间戳处理
"""

import unittest
import sys
from typing import List, Optional

# 添加项目路径
sys.path.insert(0, '../..')

from network_frontend.htsimpy.core.eventlist import EventList, EventSource, TriggerTarget, SimTime


class MockEventSource(EventSource):
    """测试用的事件源"""
    def __init__(self, eventlist: EventList, name: str):
        super().__init__(eventlist, name)
        self.executed = False
        self.execution_time = -1
        self.execution_count = 0
    
    def do_next_event(self) -> None:
        """记录执行信息"""
        self.executed = True
        self.execution_time = self.eventlist().now()
        self.execution_count += 1


class MockTrigger(TriggerTarget):
    """测试用的触发器"""
    def __init__(self, name: str):
        self.name = name
        self.activated = False
        self.activation_count = 0
    
    def activate(self) -> None:
        """记录激活信息"""
        self.activated = True
        self.activation_count += 1


class TestEventList(unittest.TestCase):
    """EventList单元测试"""
    
    def setUp(self):
        """每个测试前重置EventList"""
        EventList.reset()
    
    def tearDown(self):
        """每个测试后清理"""
        EventList.reset()
    
    def test_singleton_pattern(self):
        """测试单例模式 - 对应C++的单例实现"""
        # 第一次创建应该成功
        el1 = EventList()
        self.assertIsNotNone(el1)
        self.assertEqual(EventList._instance_count, 1)
        
        # 第二次创建应该失败并退出
        with self.assertRaises(SystemExit):
            el2 = EventList()
    
    def test_get_the_event_list(self):
        """测试获取全局事件列表"""
        el1 = EventList.get_the_event_list()
        el2 = EventList.get_the_event_list()
        self.assertIs(el1, el2)  # 应该是同一个实例
    
    def test_basic_event_scheduling(self):
        """测试基本事件调度"""
        el = EventList.get_the_event_list()
        
        # 创建事件源
        src1 = MockEventSource(el, "test1")
        src2 = MockEventSource(el, "test2")
        
        # 调度事件
        EventList.source_is_pending(src1, 100)
        EventList.source_is_pending(src2, 50)
        
        # 验证事件数量
        self.assertEqual(EventList.pending_count(), 2)
        
        # 执行第一个事件（应该是src2，时间50）
        result = EventList.do_next_event()
        self.assertTrue(result)
        self.assertTrue(src2.executed)
        self.assertFalse(src1.executed)
        self.assertEqual(EventList.now(), 50)
        
        # 执行第二个事件（应该是src1，时间100）
        result = EventList.do_next_event()
        self.assertTrue(result)
        self.assertTrue(src1.executed)
        self.assertEqual(EventList.now(), 100)
        
        # 没有更多事件
        result = EventList.do_next_event()
        self.assertFalse(result)
    
    def test_handle_mechanism(self):
        """测试Handle机制 - 对应C++的multimap iterator"""
        el = EventList.get_the_event_list()
        src = MockEventSource(el, "test_handle")
        
        # 获取handle
        handle = EventList.source_is_pending_get_handle(src, 200)
        self.assertTrue(handle.is_valid())
        self.assertEqual(handle.time, 200)
        self.assertEqual(handle.source, src)
        
        # 使用handle取消事件
        EventList.cancel_pending_source_by_handle(src, handle)
        self.assertEqual(EventList.pending_count(), 0)
        
        # 执行事件应该返回False
        result = EventList.do_next_event()
        self.assertFalse(result)
        self.assertFalse(src.executed)
    
    def test_cancel_by_time(self):
        """测试按时间取消事件"""
        el = EventList.get_the_event_list()
        src = MockEventSource(el, "test_cancel")
        
        # 调度事件
        EventList.source_is_pending(src, 300)
        self.assertEqual(EventList.pending_count(), 1)
        
        # 按时间取消
        EventList.cancel_pending_source_by_time(src, 300)
        self.assertEqual(EventList.pending_count(), 0)
        
        # 尝试取消不存在的事件应该abort（SystemExit）
        with self.assertRaises(SystemExit):
            EventList.cancel_pending_source_by_time(src, 400)
    
    def test_cancel_pending_source(self):
        """测试通用取消方法"""
        el = EventList.get_the_event_list()
        src1 = MockEventSource(el, "src1")
        src2 = MockEventSource(el, "src2")
        
        # 调度多个事件
        EventList.source_is_pending(src1, 100)
        EventList.source_is_pending(src2, 200)
        EventList.source_is_pending(src1, 300)  # src1的第二个事件
        
        self.assertEqual(EventList.pending_count(), 3)
        
        # 取消src1的所有事件（应该只取消第一个找到的）
        EventList.cancel_pending_source(src1)
        self.assertEqual(EventList.pending_count(), 2)
        
        # 执行剩余事件
        EventList.do_next_event()  # src2 at 200
        self.assertTrue(src2.executed)
        
        EventList.do_next_event()  # src1 at 300
        self.assertTrue(src1.executed)
        self.assertEqual(src1.execution_time, 300)
    
    def test_reschedule(self):
        """测试重新调度"""
        el = EventList.get_the_event_list()
        src = MockEventSource(el, "test_reschedule")
        
        # 初始调度
        EventList.source_is_pending(src, 500)
        
        # 重新调度到更早时间
        EventList.reschedule_pending_source(src, 100)
        
        # 执行事件
        EventList.do_next_event()
        self.assertTrue(src.executed)
        self.assertEqual(src.execution_time, 100)
    
    def test_triggers(self):
        """测试触发器 - 触发器应该立即执行，无时间流逝"""
        el = EventList.get_the_event_list()
        
        # 创建触发器和事件源
        trigger1 = MockTrigger("trigger1")
        trigger2 = MockTrigger("trigger2")
        src = MockEventSource(el, "src")
        
        # 设置当前时间
        EventList._lasteventtime = 1000
        
        # 调度事件和触发器
        EventList.source_is_pending(src, 2000)
        EventList.trigger_is_pending(trigger1)
        EventList.trigger_is_pending(trigger2)
        
        # 执行第一个事件（应该是trigger2，LIFO顺序）
        result = EventList.do_next_event()
        self.assertTrue(result)
        self.assertTrue(trigger2.activated)
        self.assertFalse(trigger1.activated)
        self.assertEqual(EventList.now(), 1000)  # 时间不应该改变
        
        # 执行第二个事件（应该是trigger1）
        result = EventList.do_next_event()
        self.assertTrue(result)
        self.assertTrue(trigger1.activated)
        self.assertEqual(EventList.now(), 1000)  # 时间仍然不变
        
        # 执行第三个事件（应该是src）
        result = EventList.do_next_event()
        self.assertTrue(result)
        self.assertTrue(src.executed)
        self.assertEqual(EventList.now(), 2000)  # 现在时间前进了
    
    def test_multiple_events_same_time(self):
        """测试同一时间多个事件 - 模拟C++ multimap行为"""
        el = EventList.get_the_event_list()
        
        sources = []
        for i in range(5):
            src = MockEventSource(el, f"src{i}")
            sources.append(src)
            EventList.source_is_pending(src, 1000)  # 所有事件同一时间
        
        # 执行所有事件
        for i in range(5):
            result = EventList.do_next_event()
            self.assertTrue(result)
            self.assertEqual(EventList.now(), 1000)
        
        # 验证所有事件都执行了
        for src in sources:
            self.assertTrue(src.executed)
            self.assertEqual(src.execution_time, 1000)
    
    def test_endtime(self):
        """测试结束时间设置"""
        el = EventList.get_the_event_list()
        src = MockEventSource(el, "test_endtime")
        
        # 设置结束时间
        EventList.set_endtime(1000)
        
        # 尝试调度超过结束时间的事件
        EventList.source_is_pending(src, 500)   # 应该成功
        EventList.source_is_pending(src, 1500)  # 应该被忽略
        
        self.assertEqual(EventList.pending_count(), 1)
        
        # 执行事件
        EventList.do_next_event()
        self.assertEqual(src.execution_count, 1)
    
    def test_relative_scheduling(self):
        """测试相对时间调度"""
        el = EventList.get_the_event_list()
        src = MockEventSource(el, "test_rel")
        
        # 设置当前时间
        EventList._lasteventtime = 1000
        
        # 相对当前时间调度
        EventList.source_is_pending_rel(src, 500)
        
        # 执行事件
        EventList.do_next_event()
        self.assertTrue(src.executed)
        self.assertEqual(src.execution_time, 1500)
    
    def test_invalid_handle_operations(self):
        """测试无效handle操作"""
        el = EventList.get_the_event_list()
        src = MockEventSource(el, "test_invalid")
        
        # 创建无效handle
        invalid_handle = EventList.null_handle()
        self.assertFalse(invalid_handle.is_valid())
        
        # 尝试使用无效handle应该抛出异常
        with self.assertRaises(RuntimeError):
            EventList.cancel_pending_source_by_handle(src, invalid_handle)
        
        # 创建有效handle但取消后再使用
        handle = EventList.source_is_pending_get_handle(src, 100)
        EventList.cancel_pending_source_by_handle(src, handle)
        
        # 再次使用同一个handle应该失败
        with self.assertRaises(RuntimeError):
            EventList.cancel_pending_source_by_handle(src, handle)
    
    def test_past_event_scheduling(self):
        """测试尝试调度过去的事件"""
        el = EventList.get_the_event_list()
        src = MockEventSource(el, "test_past")
        
        # 设置当前时间
        EventList._lasteventtime = 1000
        
        # 尝试调度过去的事件应该断言失败
        with self.assertRaises(AssertionError):
            EventList.source_is_pending(src, 500)
        
        with self.assertRaises(AssertionError):
            EventList.source_is_pending_get_handle(src, 999)


class TestEventSourceComparison(unittest.TestCase):
    """测试EventSource的比较操作"""
    
    def setUp(self):
        """每个测试前重置EventList"""
        EventList.reset()
        self.el = EventList.get_the_event_list()
    
    def tearDown(self):
        """每个测试后清理"""
        EventList.reset()
    
    def test_event_source_comparison(self):
        """测试EventSource的比较操作符"""
        src1 = MockEventSource(self.el, "src1")
        src2 = MockEventSource(self.el, "src2")
        
        # 每个对象应该与自己相等
        self.assertFalse(src1 < src1)
        self.assertTrue(src1 <= src1)
        self.assertFalse(src1 > src1)
        self.assertTrue(src1 >= src1)
        
        # 不同对象的比较基于id
        if id(src1) < id(src2):
            self.assertTrue(src1 < src2)
            self.assertTrue(src1 <= src2)
            self.assertFalse(src1 > src2)
            self.assertFalse(src1 >= src2)
        else:
            self.assertFalse(src1 < src2)
            self.assertFalse(src1 <= src2)
            self.assertTrue(src1 > src2)
            self.assertTrue(src1 >= src2)


if __name__ == '__main__':
    # 运行测试
    unittest.main(verbosity=2)