#!/usr/bin/env python3
"""
最小化MPTCP测试 - 仅测试最基本的MPTCP功能
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 常量定义
RANDOM_BUFFER = 3
FEEDER_BUFFER = 2000
CAP = 1

from network_frontend.htsimpy.core.eventlist import EventList
from network_frontend.htsimpy.core.network import Packet
from network_frontend.htsimpy.core.route import Route
from network_frontend.htsimpy.core.pipe import Pipe
from network_frontend.htsimpy.core.clock import Clock
from network_frontend.htsimpy.core.logger.logfile import Logfile

def time_from_ms(ms):
    """毫秒转皮秒"""
    return ms * 1_000_000_000

def time_from_sec(sec):
    """秒转皮秒"""
    return int(sec * 1_000_000_000_000)

def speed_from_pktps(pktps):
    """包每秒转bps"""
    return pktps * 1500 * 8

def mem_from_pkt(packets):
    """包数转字节"""
    return packets * 1500

def test_minimal_setup():
    """测试最小化设置"""
    print("创建基本组件...")
    
    # 1. 创建EventList
    eventlist = EventList()
    eventlist.set_endtime(time_from_sec(1))  # 1秒仿真
    print("  ✓ EventList创建成功")
    
    # 2. 创建Clock
    clock = Clock(time_from_sec(0.1), eventlist)
    print("  ✓ Clock创建成功")
    
    # 3. 创建Logfile
    logfile = Logfile("test_output.log", eventlist)
    logfile.setStartTime(time_from_sec(0.1))
    print("  ✓ Logfile创建成功")
    
    # 4. 数据包大小
    pktsize = Packet.data_packet_size()
    print(f"  ✓ 数据包大小: {pktsize} bytes")
    
    # 5. 创建Pipe
    pipe1 = Pipe(time_from_ms(75), eventlist)  # 75ms延迟
    pipe1.setName("pipe1")
    print("  ✓ Pipe创建成功")
    
    # 6. 创建Route
    route = Route()
    print("  ✓ Route创建成功")
    
    print("\n运行仿真...")
    event_count = 0
    max_events = 20
    
    while eventlist.do_next_event() and event_count < max_events:
        event_count += 1
        if event_count % 5 == 0:
            sim_time = eventlist.now() / 1e12  # 转换为秒
            print(f"  时间: {sim_time:.3f}秒, 事件数: {event_count}")
    
    print(f"\n仿真完成！处理了 {event_count} 个事件")
    
    return True

def main():
    """主函数"""
    print("=== HTSimPy 最小化MPTCP测试 ===\n")
    
    try:
        if test_minimal_setup():
            print("\n测试成功！")
            return 0
        else:
            print("\n测试失败！")
            return 1
    except Exception as e:
        print(f"\n测试出错: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())