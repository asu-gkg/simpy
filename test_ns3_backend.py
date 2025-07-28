#!/usr/bin/env python3
"""
测试NS3后端在Mock模式下的运行
"""

import sys
import os
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def test_ns3_backend():
    """测试NS3后端"""
    # 设置环境变量
    os.environ['AS_LOG_LEVEL'] = 'INFO'
    
    # 构造测试参数
    test_args = [
        'test_ns3_backend.py',
        '-t', '1',  # 单线程
        '-w', 'examples/microAllReduce.txt',  # 工作负载文件
        '-n', 'examples/topo_8gpu.txt',  # 网络拓扑文件（需要创建）
        '-c', 'examples/network.conf'  # 网络配置文件（需要创建）
    ]
    
    # 创建简单的测试拓扑文件
    os.makedirs('examples', exist_ok=True)
    
    with open('examples/topo_8gpu.txt', 'w') as f:
        f.write("8 8 0 0 7 A100\n")  # 8个节点，8个GPU/服务器，0个NVSwitch，0个交换机，7条链路
        # 添加链路定义（全连接）
        for i in range(7):
            f.write(f"{i} {i+1} 100Gbps 1us\n")
    
    # 创建简单的网络配置文件
    with open('examples/network.conf', 'w') as f:
        f.write("ENABLE_QCN 1\n")
        f.write("USE_DYNAMIC_PFC_THRESHOLD 1\n")
        f.write("CLAMP_TARGET_RATE 0\n")
        f.write("PAUSE_TIME 5\n")
        f.write("DATA_RATE 100Gbps\n")
        f.write("LINK_DELAY 1us\n")
        f.write("PACKET_PAYLOAD_SIZE 1000\n")
        f.write("ENABLE_TRACE 0\n")
        f.write("SIMULATOR_STOP_TIME 3.01\n")
    
    # 导入并运行NS3后端
    try:
        from network_frontend.ns3.AstraSimNetwork import main
        
        logging.info("开始运行NS3后端...")
        exit_code = main(test_args)
        
        if exit_code == 0:
            logging.info("✅ NS3后端运行成功")
        else:
            logging.error(f"❌ NS3后端运行失败，退出码: {exit_code}")
            
    except Exception as e:
        logging.error(f"❌ NS3后端测试失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_ns3_backend()