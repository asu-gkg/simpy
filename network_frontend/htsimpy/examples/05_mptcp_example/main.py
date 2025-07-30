#!/usr/bin/env python3
"""
MPTCP双路径示例 - 复现C++示例功能

对应文件: csg-htsim/sim/tests/main.cpp
功能: 多路径TCP仿真，使用两条不同特性的网络路径

主要特性:
- 双路径网络拓扑（3G + WiFi）
- MPTCP算法支持（UNCOUPLED, COUPLED_INC, FULLY_COUPLED, COUPLED_EPSILON）
- RandomQueue队列管理
- 完整的性能监控和日志记录

命令行参数:
- algorithm: MPTCP算法类型
- rate2: 路径2的速率（pps）
- rtt2: 路径2的RTT（ms）
- rwnd: 接收窗口大小
- run_paths: 运行路径选择（0=仅路径1, 1=仅路径2, 2=双路径）
"""

import sys
import time
import random
import argparse
from typing import Dict, Any

# HTSimPy imports
from network_frontend.htsimpy.core.eventlist import EventList
from network_frontend.htsimpy.core.network import PacketFlow
from network_frontend.htsimpy.core.route import Route
from network_frontend.htsimpy.core.pipe import Pipe
from network_frontend.htsimpy.queues.random_queue import RandomQueue
from network_frontend.htsimpy.protocols.tcp import TcpSrc, TcpSink, TcpRtxTimerScanner
from network_frontend.htsimpy.protocols.multipath_tcp import (
    MultipathTcpSrc, MultipathTcpSink,
    UNCOUPLED, FULLY_COUPLED, COUPLED_INC, COUPLED_TCP, COUPLED_EPSILON
)
from network_frontend.htsimpy.core.logger.tcp import TcpLoggerSimple, MultipathTcpLoggerSimple
from network_frontend.htsimpy.core.logger.queue import QueueLoggerSampling


def parse_arguments():
    """解析命令行参数 - 对应 C++ main() 参数解析"""
    parser = argparse.ArgumentParser(description='MPTCP双路径仿真示例')
    
    parser.add_argument('algorithm', 
                       choices=['UNCOUPLED', 'COUPLED_INC', 'FULLY_COUPLED', 'COUPLED_EPSILON'],
                       default='UNCOUPLED',
                       help='MPTCP算法类型')
    
    parser.add_argument('--epsilon', type=float, default=1.0,
                       help='COUPLED_EPSILON算法的ε参数')
    
    parser.add_argument('--rate2', type=int, default=400,
                       help='路径2速率（pps）')
    
    parser.add_argument('--rtt2', type=int, default=10,
                       help='路径2 RTT（ms）')
    
    parser.add_argument('--rwnd', type=int, default=None,
                       help='接收窗口大小')
    
    parser.add_argument('--run-paths', type=int, default=2,
                       choices=[0, 1, 2],
                       help='运行路径选择（0=仅路径1, 1=仅路径2, 2=双路径）')
    
    parser.add_argument('--duration', type=int, default=60,
                       help='仿真时长（秒）')
    
    return parser.parse_args()


def time_from_ms(ms: int) -> int:
    """毫秒转换为皮秒 - 对应 C++ timeFromMs()"""
    return ms * 1_000_000_000_000


def time_from_sec(sec: float) -> int:
    """秒转换为皮秒 - 对应 C++ timeFromSec()"""
    return int(sec * 1_000_000_000_000)


def speed_from_pktps(pktps: int) -> int:
    """包每秒转换为bps - 对应 C++ speedFromPktps()"""
    # 假设每个包1500字节
    return pktps * 1500 * 8


def mem_from_pkt(packets: int) -> int:
    """包数量转换为字节 - 对应 C++ memFromPkt()"""
    return packets * 1500


class MptcpSimulation:
    """
    MPTCP仿真类 - 对应 C++ main() 函数功能
    
    管理整个MPTCP仿真的设置和运行
    """
    
    def __init__(self, args):
        """
        初始化仿真 - 对应 C++ main() 初始化部分
        
        Args:
            args: 命令行参数
        """
        self.args = args
        
        # 设置仿真参数 - 对应 C++ 参数设置
        self._setup_simulation_params()
        
        # 创建事件调度器 - 对应 C++ EventList
        self.eventlist = EventList()
        self.eventlist.set_endtime(time_from_sec(args.duration))
        
        # 创建日志记录器 - 对应 C++ 日志器
        self._setup_loggers()
        
        # 网络组件
        self.pipes = {}
        self.queues = {}
        self.tcp_sources = []
        self.tcp_sinks = []
        
        # MPTCP组件
        self.mptcp_src = None
        self.mptcp_sink = None
        
        # 重传定时器扫描器 - 对应 C++ TcpRtxTimerScanner
        self.rtx_scanner = TcpRtxTimerScanner(time_from_ms(10), self.eventlist)
        
    def _setup_simulation_params(self):
        """设置仿真参数 - 对应 C++ 参数计算"""
        # 路径1参数 - 对应 C++ SERVICE1, RTT1 等
        self.service1 = speed_from_pktps(166)  # 3G网络
        self.rtt1 = time_from_ms(150)
        self.buffer1 = mem_from_pkt(3 + int(self.rtt1 / 1e12 * self.service1 / 8 / 1500 * 12))
        
        # 路径2参数 - 对应 C++ SERVICE2, RTT2 等
        self.service2 = speed_from_pktps(self.args.rate2)  # WiFi网络
        self.rtt2 = time_from_ms(self.args.rtt2)
        bufsize = int(self.rtt2 / 1e12 * self.service2 / 8 / 1500 * 4)
        bufsize = max(bufsize, 10)
        self.buffer2 = mem_from_pkt(3 + bufsize)
        
        # 接收窗口 - 对应 C++ rwnd 计算
        if self.args.rwnd is None:
            max_rtt = max(self.rtt1, self.rtt2)
            total_bw = (self.service1 + self.service2) / 8 / 1500  # pps
            self.rwnd = int(3 * max_rtt / 1e12 * total_bw)
        else:
            self.rwnd = self.args.rwnd
        
        # MPTCP算法 - 对应 C++ algo 设置
        algorithm_map = {
            'UNCOUPLED': UNCOUPLED,
            'FULLY_COUPLED': FULLY_COUPLED,
            'COUPLED_INC': COUPLED_INC,
            'COUPLED_TCP': COUPLED_TCP,
            'COUPLED_EPSILON': COUPLED_EPSILON
        }
        self.algorithm = algorithm_map[self.args.algorithm]
        
        print(f"仿真参数配置:")
        print(f"  路径1: {self.service1//1000000}Mbps, RTT={self.rtt1//1000000000000}ms, 缓冲区={self.buffer1}字节")
        print(f"  路径2: {self.service2//1000000}Mbps, RTT={self.rtt2//1000000000000}ms, 缓冲区={self.buffer2}字节")
        print(f"  MPTCP算法: {self.args.algorithm}")
        print(f"  接收窗口: {self.rwnd}")
        print(f"  运行路径: {self.args.run_paths}")
        print()
    
    def _setup_loggers(self):
        """设置日志记录器 - 对应 C++ 日志器设置"""
        # 队列日志记录器 - 对应 C++ QueueLoggerSampling
        self.queue_logger1 = QueueLoggerSampling(time_from_ms(1000), self.eventlist)
        self.queue_logger2 = QueueLoggerSampling(time_from_ms(1000), self.eventlist)
        
        # TCP日志记录器 - 对应 C++ TcpLoggerSimple
        self.tcp_logger = TcpLoggerSimple()
        
        # MPTCP日志记录器 - 对应 C++ MultipathTcpLoggerSimple
        self.mptcp_logger = MultipathTcpLoggerSimple()
    
    def _create_network_topology(self):
        """
        创建网络拓扑 - 对应 C++ 网络组件创建
        
        拓扑结构:
        源端 -> PQueue -> RandomQueue -> Pipe -> 接收端
        """
        print("创建网络拓扑...")
        
        # 创建管道 - 对应 C++ Pipe
        self.pipes['pipe1'] = Pipe(self.rtt1 // 2, self.eventlist)
        self.pipes['pipe1'].setName("pipe1")
        
        self.pipes['pipe2'] = Pipe(self.rtt2 // 2, self.eventlist)
        self.pipes['pipe2'].setName("pipe2")
        
        self.pipes['pipe_back'] = Pipe(time_from_ms(0.1), self.eventlist)
        self.pipes['pipe_back'].setName("pipe_back")
        
        # 创建随机队列 - 对应 C++ RandomQueue
        self.queues['queue1'] = RandomQueue(
            bitrate=self.service1,
            maxsize=self.buffer1,
            eventlist=self.eventlist,
            logger=self.queue_logger1,
            random_drop_size=mem_from_pkt(3)
        )
        self.queues['queue1'].setName("Queue1")
        
        self.queues['queue2'] = RandomQueue(
            bitrate=self.service2,
            maxsize=self.buffer2,
            eventlist=self.eventlist,
            logger=self.queue_logger2,
            random_drop_size=mem_from_pkt(3)
        )
        self.queues['queue2'].setName("Queue2")
        
        # 创建前置队列 - 对应 C++ PQueue
        self.queues['pqueue3'] = RandomQueue(
            bitrate=self.service1 * 2,
            maxsize=mem_from_pkt(2000),
            eventlist=self.eventlist
        )
        self.queues['pqueue3'].setName("PQueue3")
        
        self.queues['pqueue4'] = RandomQueue(
            bitrate=self.service2 * 2,
            maxsize=mem_from_pkt(2000),
            eventlist=self.eventlist
        )
        self.queues['pqueue4'].setName("PQueue4")
        
        print(f"  队列1: {self.queues['queue1'].nodename()}")
        print(f"  队列2: {self.queues['queue2'].nodename()}")
        
    def _create_mptcp_connection(self):
        """
        创建MPTCP连接 - 对应 C++ MPTCP连接设置
        """
        print("创建MPTCP连接...")
        
        # 创建MPTCP源端和接收端 - 对应 C++ MultipathTcpSrc/Sink
        self.mptcp_src = MultipathTcpSrc(
            cc_type=self.algorithm,
            eventlist=self.eventlist,
            logger=self.mptcp_logger,
            rwnd=self.rwnd
        )
        self.mptcp_src.setName("MPTCPFlow")
        
        self.mptcp_sink = MultipathTcpSink(self.eventlist)
        self.mptcp_sink.setName("mptcp_sink")
        
        # 连接MPTCP源端和接收端
        self.mptcp_src.connect(self.mptcp_sink)
        
        print(f"  MPTCP算法: {self.args.algorithm}")
        print(f"  接收窗口: {self.rwnd}")
        
    def _create_subflows(self):
        """
        创建TCP子流 - 对应 C++ TCP子流创建
        """
        print("创建TCP子流...")
        
        # 子流1 - 路径1 (3G网络) - 对应 C++ Subflow1
        if self.args.run_paths != 1:  # 不是仅路径2
            tcp_src1 = TcpSrc(None, None, self.eventlist)
            tcp_src1.setName("Subflow1")
            tcp_src1.set_ssthresh(int(self.rtt1 / 1e12 * self.service1 / 8 / 1500 * 1000))
            tcp_src1.set_cap(1)  # 对应 C++ CAP
            
            tcp_sink1 = TcpSink()
            tcp_sink1.setName("Subflow1Sink")
            
            # 注册重传扫描器
            self.rtx_scanner.register_tcp(tcp_src1)
            
            # 创建路由 - 对应 C++ route 设置
            route_out1 = Route()
            route_out1.push_back(self.queues['pqueue3'])
            route_out1.push_back(self.queues['queue1'])
            route_out1.push_back(self.pipes['pipe1'])
            route_out1.push_back(tcp_sink1)
            
            route_in1 = Route()
            route_in1.push_back(self.pipes['pipe1'])
            route_in1.push_back(tcp_src1)
            
            # 连接子流
            start_time = random.random() * 50  # 对应 C++ extrastarttime
            tcp_src1.connect(route_out1, route_in1, tcp_sink1, time_from_ms(start_time))
            
            # 添加到MPTCP连接
            self.mptcp_src.addSubflow(tcp_src1)
            self.mptcp_sink.addSubflow(tcp_sink1)
            
            self.tcp_sources.append(tcp_src1)
            self.tcp_sinks.append(tcp_sink1)
            
            print(f"  子流1: 3G路径 (RTT={self.rtt1//1000000000000}ms)")
        
        # 子流2 - 路径2 (WiFi网络) - 对应 C++ Subflow2
        if self.args.run_paths != 0:  # 不是仅路径1
            tcp_src2 = TcpSrc(None, None, self.eventlist)
            tcp_src2.setName("Subflow2")
            tcp_src2.set_ssthresh(int(self.rtt2 / 1e12 * self.service2 / 8 / 1500 * 1000))
            tcp_src2.set_cap(1)  # 对应 C++ CAP
            
            tcp_sink2 = TcpSink()
            tcp_sink2.setName("Subflow2Sink")
            
            # 注册重传扫描器
            self.rtx_scanner.register_tcp(tcp_src2)
            
            # 创建路由 - 对应 C++ route 设置
            route_out2 = Route()
            route_out2.push_back(self.queues['pqueue4'])
            route_out2.push_back(self.queues['queue2'])
            route_out2.push_back(self.pipes['pipe2'])
            route_out2.push_back(tcp_sink2)
            
            route_in2 = Route()
            route_in2.push_back(self.pipes['pipe2'])
            route_in2.push_back(tcp_src2)
            
            # 连接子流
            start_time = random.random() * 50  # 对应 C++ extrastarttime
            tcp_src2.connect(route_out2, route_in2, tcp_sink2, time_from_ms(start_time))
            
            # 添加到MPTCP连接
            self.mptcp_src.addSubflow(tcp_src2)
            self.mptcp_sink.addSubflow(tcp_sink2)
            
            self.tcp_sources.append(tcp_src2)
            self.tcp_sinks.append(tcp_sink2)
            
            print(f"  子流2: WiFi路径 (RTT={self.rtt2//1000000000000}ms)")
        
        print(f"  总子流数: {len(self.tcp_sources)}")
    
    def run_simulation(self):
        """
        运行仿真 - 对应 C++ while (eventlist.doNextEvent())
        """
        print(f"\n开始仿真（时长: {self.args.duration}秒）...")
        print("=" * 50)
        
        start_time = time.time()
        event_count = 0
        
        # 运行事件循环 - 对应 C++ main() 仿真循环
        while self.eventlist.do_next_event():
            event_count += 1
            
            # 定期输出进度
            if event_count % 10000 == 0:
                sim_time = self.eventlist.now() / 1e12  # 转换为秒
                progress = sim_time / self.args.duration * 100
                print(f"\r进度: {progress:.1f}% (仿真时间: {sim_time:.2f}s, 事件: {event_count})", end="")
        
        end_time = time.time()
        print(f"\n仿真完成！")
        print(f"执行时间: {end_time - start_time:.2f}秒")
        print(f"总事件数: {event_count}")
        
    def print_results(self):
        """打印仿真结果 - 对应 C++ 结果输出"""
        print("\n" + "=" * 50)
        print("仿真结果:")
        print("=" * 50)
        
        # MPTCP总体性能
        print(f"\nMPTCP总体性能:")
        print(f"  算法: {self.args.algorithm}")
        print(f"  子流数量: {len(self.mptcp_src._subflows)}")
        print(f"  累积确认: {self.mptcp_sink.cumulative_ack()}")
        print(f"  数据确认: {self.mptcp_sink.data_ack()}")
        
        # 各子流性能
        subflows = self.mptcp_src._subflows
        for i, subflow in enumerate(subflows, 1):
            print(f"\n子流{i}性能:")
            print(f"  拥塞窗口: {subflow._cwnd}")
            print(f"  发送包数: {subflow._packets_sent}")
        
        # 队列统计
        for name, queue in self.queues.items():
            if hasattr(queue, 'num_drops'):
                print(f"\n{name}统计:")
                print(f"  队列大小: {queue.queuesize()}/{queue.maxsize()}字节")
                print(f"  丢包数: {queue.num_drops()}")


def main():
    """主函数 - 对应 C++ main()"""
    print("=== HTSimPy MPTCP双路径仿真示例 ===")
    print("复现 csg-htsim/sim/tests/main.cpp 功能\n")
    
    # 解析命令行参数
    args = parse_arguments()
    
    # 设置随机种子 - 对应 C++ srand(time(NULL))
    random.seed(int(time.time()))
    
    try:
        # 创建仿真实例
        sim = MptcpSimulation(args)
        
        # 建立网络拓扑
        sim._create_network_topology()
        
        # 创建MPTCP连接
        sim._create_mptcp_connection()
        
        # 创建TCP子流
        sim._create_subflows()
        
        # 运行仿真
        sim.run_simulation()
        
        # 输出结果
        sim.print_results()
        
    except KeyboardInterrupt:
        print("\n用户中断仿真")
    except Exception as e:
        print(f"仿真出错: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()