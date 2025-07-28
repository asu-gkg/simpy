#!/usr/bin/env python3
"""
测试NS3 Python绑定是否可用
"""

import sys
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def test_ns3_import():
    """测试NS3模块导入"""
    try:
        logging.info("尝试导入NS3核心模块...")
        import ns.core
        logging.info("✅ ns.core 导入成功")
        
        import ns.network
        logging.info("✅ ns.network 导入成功")
        
        import ns.internet
        logging.info("✅ ns.internet 导入成功")
        
        import ns.point_to_point
        logging.info("✅ ns.point_to_point 导入成功")
        
        import ns.applications
        logging.info("✅ ns.applications 导入成功")
        
        return True
        
    except ImportError as e:
        logging.error(f"❌ NS3导入失败: {e}")
        return False

def test_ns3_basic_simulation():
    """测试基本的NS3仿真功能"""
    try:
        import ns.core
        import ns.network
        import ns.internet
        import ns.point_to_point
        
        logging.info("\n开始测试NS3基本仿真功能...")
        
        # 创建两个节点
        nodes = ns.network.NodeContainer()
        nodes.Create(2)
        logging.info("✅ 创建了2个节点")
        
        # 创建点对点链路
        pointToPoint = ns.point_to_point.PointToPointHelper()
        pointToPoint.SetDeviceAttribute("DataRate", ns.core.StringValue("5Mbps"))
        pointToPoint.SetChannelAttribute("Delay", ns.core.StringValue("2ms"))
        
        devices = pointToPoint.Install(nodes)
        logging.info("✅ 创建了点对点链路")
        
        # 安装网络协议栈
        stack = ns.internet.InternetStackHelper()
        stack.Install(nodes)
        logging.info("✅ 安装了网络协议栈")
        
        # 分配IP地址
        address = ns.internet.Ipv4AddressHelper()
        address.SetBase(ns.network.Ipv4Address("10.1.1.0"), ns.network.Ipv4Mask("255.255.255.0"))
        interfaces = address.Assign(devices)
        logging.info("✅ 分配了IP地址")
        
        # 测试获取当前仿真时间
        current_time = ns.core.Simulator.Now().GetNanoSeconds()
        logging.info(f"✅ 当前仿真时间: {current_time} ns")
        
        # 调度一个简单的事件
        def hello_callback():
            logging.info(f"✅ 回调函数执行，仿真时间: {ns.core.Simulator.Now().GetSeconds()} s")
            
        ns.core.Simulator.Schedule(ns.core.Seconds(1.0), hello_callback)
        logging.info("✅ 调度了一个事件")
        
        # 运行仿真（很短的时间）
        ns.core.Simulator.Stop(ns.core.Seconds(2.0))
        logging.info("开始运行仿真...")
        ns.core.Simulator.Run()
        ns.core.Simulator.Destroy()
        logging.info("✅ 仿真运行完成")
        
        return True
        
    except Exception as e:
        logging.error(f"❌ NS3仿真测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_ns3_version():
    """测试NS3版本信息"""
    try:
        import ns.core
        
        # 尝试获取版本信息
        logging.info("\n尝试获取NS3版本信息...")
        
        # NS3不同版本可能有不同的方式获取版本
        if hasattr(ns.core, 'Version'):
            version = ns.core.Version()
            logging.info(f"NS3版本: {version}")
        else:
            logging.info("无法获取NS3版本信息，但模块已加载")
            
        return True
        
    except Exception as e:
        logging.error(f"获取版本信息失败: {e}")
        return False

def check_ns3_installation():
    """检查NS3安装建议"""
    logging.info("\n=== NS3安装检查 ===")
    
    # 检查是否在虚拟环境中
    if hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
        logging.info("✅ 检测到虚拟环境")
    else:
        logging.warning("⚠️  未检测到虚拟环境")
    
    # 提供安装建议
    logging.info("\n如果NS3未安装，请尝试以下方法：")
    logging.info("1. 使用pip安装预编译版本（如果可用）：")
    logging.info("   pip install ns3")
    logging.info("   或")
    logging.info("   uv pip install ns3")
    logging.info("\n2. 从源码编译NS3并启用Python绑定：")
    logging.info("   wget https://www.nsnam.org/releases/ns-allinone-3.39.tar.bz2")
    logging.info("   tar -xjf ns-allinone-3.39.tar.bz2")
    logging.info("   cd ns-allinone-3.39/ns-3.39")
    logging.info("   ./ns3 configure --enable-python-bindings")
    logging.info("   ./ns3 build")
    logging.info("\n3. 设置PYTHONPATH环境变量：")
    logging.info("   export PYTHONPATH=$PYTHONPATH:/path/to/ns-3.39/build/bindings/python")

def main():
    """主测试函数"""
    logging.info("=== 开始测试NS3 Python绑定 ===\n")
    
    # 测试导入
    import_success = test_ns3_import()
    
    if import_success:
        # 测试版本
        test_ns3_version()
        
        # 测试基本仿真
        sim_success = test_ns3_basic_simulation()
        
        if sim_success:
            logging.info("\n🎉 所有测试通过！NS3 Python绑定工作正常。")
        else:
            logging.warning("\n⚠️  NS3模块可以导入，但仿真功能可能有问题。")
    else:
        logging.error("\n❌ NS3 Python绑定不可用。")
        check_ns3_installation()
    
    # 测试我们的common.py模块
    logging.info("\n=== 测试common.py模块 ===")
    try:
        from network_frontend.ns3.common import NS3_AVAILABLE, ns
        if NS3_AVAILABLE:
            logging.info("✅ common.py模块正常，NS3可用")
        else:
            logging.info("✅ common.py模块正常，运行在Mock模式")
    except Exception as e:
        logging.error(f"❌ common.py模块测试失败: {e}")

if __name__ == "__main__":
    main()