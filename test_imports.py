#!/usr/bin/env python3
"""
测试HTSimPy的基本导入
"""

import sys
import traceback

def test_imports():
    """测试所有必要的导入"""
    
    imports = [
        ("EventList", "from network_frontend.htsimpy.core.eventlist import EventList"),
        ("Packet", "from network_frontend.htsimpy.core.network import Packet"),
        ("Route", "from network_frontend.htsimpy.core.route import Route"),
        ("Pipe", "from network_frontend.htsimpy.core.pipe import Pipe"),
        ("Clock", "from network_frontend.htsimpy.core.clock import Clock"),
        ("Queue", "from network_frontend.htsimpy.queues.base_queue import Queue"),
        ("RandomQueue", "from network_frontend.htsimpy.queues.random_queue import RandomQueue"),
        ("TcpSrc", "from network_frontend.htsimpy.protocols.tcp import TcpSrc, TcpSink"),
        ("MultipathTcpSrc", "from network_frontend.htsimpy.protocols.multipath_tcp import MultipathTcpSrc"),
        ("Logfile", "from network_frontend.htsimpy.core.logger.base import Logfile"),
    ]
    
    print("测试HTSimPy模块导入...")
    print("=" * 60)
    
    failed = []
    
    for name, import_stmt in imports:
        try:
            print(f"导入 {name}...", end=" ")
            exec(import_stmt)
            print("✓")
        except Exception as e:
            print(f"✗ 错误: {type(e).__name__}: {e}")
            failed.append((name, e))
    
    print("\n" + "=" * 60)
    
    if failed:
        print(f"\n失败的导入 ({len(failed)}):")
        for name, err in failed:
            print(f"\n{name}:")
            print(f"  错误: {err}")
            traceback.print_exc()
    else:
        print("\n所有导入成功！")
    
    return len(failed) == 0

def test_basic_functionality():
    """测试基本功能"""
    print("\n\n测试基本功能...")
    print("=" * 60)
    
    try:
        # 测试EventList
        print("1. 创建EventList...", end=" ")
        from network_frontend.htsimpy.core.eventlist import EventList
        eventlist = EventList()
        print("✓")
        
        # 测试Packet
        print("2. 获取数据包大小...", end=" ")
        from network_frontend.htsimpy.core.network import Packet
        pktsize = Packet.data_packet_size()
        print(f"✓ (大小: {pktsize} bytes)")
        
        # 测试Route
        print("3. 创建Route...", end=" ")
        from network_frontend.htsimpy.core.route import Route
        route = Route()
        print("✓")
        
        # 测试Clock
        print("4. 创建Clock...", end=" ")
        from network_frontend.htsimpy.core.clock import Clock
        clock = Clock(1000000000, eventlist)  # 1ms周期
        print("✓")
        
        print("\n基本功能测试通过！")
        return True
        
    except Exception as e:
        print(f"\n✗ 错误: {type(e).__name__}: {e}")
        traceback.print_exc()
        return False

def main():
    """主函数"""
    print("=== HTSimPy 导入和基本功能测试 ===\n")
    
    # 测试导入
    import_success = test_imports()
    
    # 如果导入成功，测试基本功能
    if import_success:
        test_basic_functionality()
    else:
        print("\n由于导入失败，跳过功能测试。")

if __name__ == "__main__":
    main()