#!/usr/bin/env python3
"""
基础MPTCP测试 - 验证核心组件是否可以运行
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from network_frontend.htsimpy.core.eventlist import EventList
from network_frontend.htsimpy.core.network import Packet
from network_frontend.htsimpy.core.clock import Clock

def test_basic_components():
    """测试基本组件"""
    print("1. 测试EventList...")
    eventlist = EventList()
    print(f"   当前时间: {eventlist.now()}")
    
    print("\n2. 测试Packet...")
    pktsize = Packet.data_packet_size()
    print(f"   数据包大小: {pktsize} bytes")
    
    print("\n3. 测试Clock...")
    clock = Clock(1000000000000, eventlist)  # 1秒周期
    print(f"   时钟创建成功")
    
    print("\n4. 测试事件调度...")
    eventlist.set_endtime(5000000000000)  # 5秒
    
    # 运行几个事件
    count = 0
    while eventlist.do_next_event() and count < 10:
        count += 1
        print(f"   事件 {count}: 时间 = {eventlist.now() / 1e12:.3f}秒")
    
    print(f"\n基本组件测试完成！")

def main():
    """主函数"""
    print("=== HTSimPy 基础组件测试 ===\n")
    
    try:
        test_basic_components()
        print("\n测试成功！")
        return 0
    except Exception as e:
        print(f"\n测试失败: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())