"""
EventList C++ Compatibility Tests

这个测试文件专门验证Python EventList实现与C++版本的精确对应
包括边缘情况和特定的C++行为
"""

import unittest
import sys
from typing import List

# 添加项目路径
sys.path.insert(0, '../..')

from network_frontend.htsimpy.core.eventlist import EventList, EventSource, TriggerTarget, SimTime


class TestEventSource(EventSource):
    """测试用的事件源，带执行记录"""
    
    execution_log = []  # 全局执行日志
    
    def __init__(self, eventlist: EventList, name: str):
        super().__init__(eventlist, name)
        self.name = name
    
    def do_next_event(self) -> None:
        """记录执行"""
        TestEventSource.execution_log.append((self.name, self.eventlist().now()))
    
    @classmethod
    def clear_log(cls):
        cls.execution_log.clear()


class TestCppCompatibility(unittest.TestCase):
    """测试与C++版本的兼容性"""
    
    def setUp(self):
        """每个测试前重置"""
        EventList.reset()
        TestEventSource.clear_log()
    
    def tearDown(self):
        """清理"""
        EventList.reset()
        TestEventSource.clear_log()
    
    def test_multimap_ordering(self):
        """
        测试multimap行为：相同时间戳的事件按插入顺序执行
        C++ multimap保证稳定排序
        """
        el = EventList.get_the_event_list()
        
        # 创建多个事件源
        sources = []
        for i in range(10):
            src = TestEventSource(el, f"src_{i}")
            sources.append(src)
        
        # 按特定顺序插入相同时间的事件
        for i in [5, 2, 8, 1, 9, 3, 7, 0, 4, 6]:
            EventList.source_is_pending(sources[i], 1000)
        
        # 执行所有事件
        while EventList.do_next_event():
            pass
        
        # 验证执行顺序与插入顺序相同
        expected_order = [f"src_{i}" for i in [5, 2, 8, 1, 9, 3, 7, 0, 4, 6]]
        actual_order = [name for name, _ in TestEventSource.execution_log]
        self.assertEqual(actual_order, expected_order)
    
    def test_handle_iterator_behavior(self):
        """
        测试Handle作为iterator的行为
        C++中Handle是multimap::iterator
        """
        el = EventList.get_the_event_list()
        src1 = TestEventSource(el, "src1")
        src2 = TestEventSource(el, "src2")
        
        # 获取handles
        h1 = EventList.source_is_pending_get_handle(src1, 100)
        h2 = EventList.source_is_pending_get_handle(src2, 200)
        
        # 验证handle包含正确信息
        self.assertEqual(h1.time, 100)
        self.assertEqual(h1.source, src1)
        self.assertEqual(h2.time, 200)
        self.assertEqual(h2.source, src2)
        
        # 测试null handle
        null_h = EventList.null_handle()
        self.assertFalse(null_h.is_valid())
        self.assertEqual(null_h.time, -1)
        self.assertIsNone(null_h.source)
    
    def test_cancel_by_time_exact_behavior(self):
        """
        测试cancel_by_time的精确行为
        C++版本在找不到事件时会abort()
        """
        el = EventList.get_the_event_list()
        src = TestEventSource(el, "src")
        
        # 调度多个不同时间的事件
        EventList.source_is_pending(src, 100)
        EventList.source_is_pending(src, 200)
        EventList.source_is_pending(src, 300)
        
        # 取消存在的事件
        EventList.cancel_pending_source_by_time(src, 200)
        
        # 尝试取消不存在的事件应该导致退出
        with self.assertRaises(SystemExit) as cm:
            EventList.cancel_pending_source_by_time(src, 250)
        self.assertEqual(cm.exception.code, 1)
    
    def test_endtime_boundary(self):
        """
        测试endtime边界条件
        C++：if (theEndtime == 0 || when < theEndtime)
        """
        el = EventList.get_the_event_list()
        src = TestEventSource(el, "src")
        
        # 默认endtime为0，所有事件都应该被接受
        EventList.source_is_pending(src, 999999999)
        self.assertEqual(EventList.pending_count(), 1)
        EventList.cancel_pending_source(src)
        
        # 设置endtime
        EventList.set_endtime(1000)
        
        # 边界测试
        EventList.source_is_pending(src, 999)   # < endtime，应该接受
        EventList.source_is_pending(src, 1000)  # = endtime，不应该接受
        EventList.source_is_pending(src, 1001)  # > endtime，不应该接受
        
        self.assertEqual(EventList.pending_count(), 1)
        
        # 执行事件验证
        EventList.do_next_event()
        self.assertEqual(len(TestEventSource.execution_log), 1)
        self.assertEqual(TestEventSource.execution_log[0], ("src", 999))
    
    def test_trigger_lifo_order(self):
        """
        测试触发器的LIFO顺序
        C++使用vector::pop_back()，所以是LIFO
        """
        el = EventList.get_the_event_list()
        
        class OrderedTrigger(TriggerTarget):
            activation_order = []
            
            def __init__(self, name):
                self.name = name
            
            def activate(self):
                OrderedTrigger.activation_order.append(self.name)
        
        # 清空记录
        OrderedTrigger.activation_order = []
        
        # 按顺序添加触发器
        triggers = []
        for i in range(5):
            t = OrderedTrigger(f"trigger_{i}")
            triggers.append(t)
            EventList.trigger_is_pending(t)
        
        # 执行所有触发器
        for _ in range(5):
            EventList.do_next_event()
        
        # 验证LIFO顺序（后进先出）
        expected = [f"trigger_{i}" for i in range(4, -1, -1)]
        self.assertEqual(OrderedTrigger.activation_order, expected)
    
    def test_assert_conditions(self):
        """
        测试各种断言条件，对应C++中的assert
        """
        el = EventList.get_the_event_list()
        src = TestEventSource(el, "src")
        
        # 测试时间顺序断言
        EventList._lasteventtime = 1000
        
        # assert(when >= now()) in sourceIsPending
        with self.assertRaises(AssertionError):
            EventList.source_is_pending(src, 999)
        
        # assert(when >= now()) in sourceIsPendingGetHandle
        with self.assertRaises(AssertionError):
            EventList.source_is_pending_get_handle(src, 500)
        
        # 测试handle断言
        handle = EventList.source_is_pending_get_handle(src, 2000)
        
        # 执行事件使时间前进
        EventList.do_next_event()
        self.assertEqual(EventList.now(), 2000)
        
        # assert(when >= now()) in cancelPendingSourceByHandle
        # 现在handle的时间已经是过去了
        handle2 = EventList.Handle(1500, src)  # 创建一个过去时间的handle
        with self.assertRaises(AssertionError):
            EventList.cancel_pending_source_by_handle(src, handle2)
    
    def test_empty_time_slot_cleanup(self):
        """
        测试空时间槽的清理
        当某个时间的所有事件都被处理或取消后，应该清理该时间槽
        """
        el = EventList.get_the_event_list()
        
        # 创建多个事件源
        sources = [TestEventSource(el, f"src_{i}") for i in range(5)]
        
        # 在同一时间调度多个事件
        for src in sources:
            EventList.source_is_pending(src, 1000)
        
        # 验证内部状态
        self.assertEqual(len(EventList._sorted_times), 1)
        self.assertEqual(EventList._sorted_times[0], 1000)
        self.assertEqual(len(EventList._pending_by_time[1000]), 5)
        
        # 取消部分事件
        for i in range(3):
            EventList.cancel_pending_source(sources[i])
        
        # 时间槽应该还在，但事件数减少
        self.assertEqual(len(EventList._sorted_times), 1)
        self.assertEqual(len(EventList._pending_by_time[1000]), 2)
        
        # 取消所有剩余事件
        EventList.cancel_pending_source(sources[3])
        EventList.cancel_pending_source(sources[4])
        
        # 时间槽应该被清理
        self.assertEqual(len(EventList._sorted_times), 0)
        self.assertNotIn(1000, EventList._pending_by_time)
    
    def test_multiple_time_slots(self):
        """
        测试多个时间槽的正确管理
        """
        el = EventList.get_the_event_list()
        
        # 创建不同时间的事件
        times = [300, 100, 500, 200, 400]
        sources = []
        
        for i, t in enumerate(times):
            src = TestEventSource(el, f"src_{i}")
            sources.append(src)
            EventList.source_is_pending(src, t)
        
        # 验证时间排序
        self.assertEqual(EventList._sorted_times, [100, 200, 300, 400, 500])
        
        # 按时间顺序执行
        for _ in range(5):
            EventList.do_next_event()
        
        # 验证执行顺序
        expected_log = [
            ("src_1", 100),
            ("src_3", 200),
            ("src_0", 300),
            ("src_4", 400),
            ("src_2", 500)
        ]
        self.assertEqual(TestEventSource.execution_log, expected_log)


if __name__ == '__main__':
    unittest.main(verbosity=2)