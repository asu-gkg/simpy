#!/usr/bin/env python3
"""
Dumbell TCP Example - 对应 csg-htsim/sim/tests/main_dumbell_tcp.cpp

实现哑铃拓扑下的多TCP流竞争场景
"""

import sys
import argparse
import random
import time
from typing import List, Dict, Optional

# HTSimPy imports
from network_frontend.htsimpy.core.eventlist import EventList
from network_frontend.htsimpy.core.network import Packet
from network_frontend.htsimpy.core.pipe import Pipe
from network_frontend.htsimpy.core.clock import Clock
from network_frontend.htsimpy.core.logger.logfile import Logfile
from network_frontend.htsimpy.core.logger import TcpSinkLoggerSampling
from network_frontend.htsimpy.queues.base_queue import Queue
from network_frontend.htsimpy.queues.random_queue import RandomQueue
from network_frontend.htsimpy.protocols.tcp import TcpSrc, TcpSink, TcpRtxTimerScanner


def speed_from_mbps(mbps: int) -> int:
    """将Mbps转换为bps - 对应 C++ speedFromMbps"""
    return mbps * 1_000_000


def time_from_us(us: int) -> int:
    """将微秒转换为皮秒 - 对应 C++ timeFromUs"""
    return us * 1_000_000


def time_from_ms(ms: int) -> int:
    """将毫秒转换为皮秒 - 对应 C++ timeFromMs"""
    return ms * 1_000_000_000


def time_from_sec(sec: float) -> int:
    """将秒转换为皮秒 - 对应 C++ timeFromSec"""
    return int(sec * 1_000_000_000_000)


def time_as_sec(ps: int) -> float:
    """将皮秒转换为秒 - 对应 C++ timeAsSec"""
    return ps / 1_000_000_000_000


def ntoa(value) -> str:
    """将数值转换为字符串 - 对应 C++ ntoa"""
    if isinstance(value, float):
        return f"{value:.6g}"
    return str(value)


def mem_from_pkt(pkts: float) -> int:
    """将包数转换为字节数 - 对应 C++ memFromPkt"""
    import math
    return int(math.ceil(pkts * Packet.data_packet_size()))


class DumbellTcpSimulation:
    """哑铃拓扑TCP仿真"""
    
    def __init__(self, args):
        """初始化仿真参数"""
        self.cnt = args.conns  # 连接数
        self.qs = args.qs      # 队列大小
        self.seed = args.seed  # 随机种子
        
        # 设置随机种子
        random.seed(self.seed)
        
        # 创建事件列表
        self.eventlist = EventList()
        self.eventlist.set_endtime(time_from_sec(5))  # 5秒仿真时间
        
        # 创建时钟
        self.clock = Clock(time_from_sec(50/100.), self.eventlist)
        
        # 设置包大小
        Packet.set_packet_size(9000)
        
        # 网络参数
        self.SERVICE1 = speed_from_mbps(10000)  # 10Gbps
        self.RTT1 = time_from_us(10)           # 10微秒RTT
        self.BUFFER = mem_from_pkt(self.qs)     # 缓冲区大小
        
        # 创建日志文件
        self.logfile = Logfile("logout.dat", self.eventlist)
        self.logfile.setStartTime(0)
        
    def build_network(self):
        """构建哑铃网络拓扑"""
        print(f"Building dumbell topology with {self.cnt} connections")
        
        # 创建管道 - 对应 C++ 中的 pipe1 和 pipe2
        self.pipe1 = Pipe(self.RTT1, self.eventlist)
        self.pipe1.setName("pipe1")
        self.logfile.writeName(self.pipe1)
        
        self.pipe2 = Pipe(self.RTT1, self.eventlist)
        self.pipe2.setName("pipe2")
        self.logfile.writeName(self.pipe2)
        
        # 创建瓶颈队列 - 对应 C++ 中的 queue3
        self.queue3 = RandomQueue(
            self.SERVICE1, 
            self.BUFFER, 
            self.eventlist,
            logger=None,
            drop=mem_from_pkt(5)
        )
        self.queue3.setName("Queue3")
        self.logfile.writeName(self.queue3)
        
        # 创建受限队列 - 对应 C++ 中的 queue4
        # 注意：第一个流使用这个队列，带宽和缓冲区都是1/3
        self.queue4 = RandomQueue(
            self.SERVICE1 // 3,  # 1/3带宽
            self.BUFFER // 3,    # 1/3缓冲区
            self.eventlist,
            logger=None,
            drop=mem_from_pkt(0)
        )
        self.queue4.setName("Queue4")
        self.logfile.writeName(self.queue4)
        
    def create_tcp_flows(self):
        """创建TCP流"""
        # TCP重传扫描器
        tcpRtxScanner = TcpRtxTimerScanner(time_from_ms(10), self.eventlist)
        
        # TCP接收端日志记录器
        sinkLogger = TcpSinkLoggerSampling(time_from_ms(100), self.eventlist)
        self.logfile.addLogger(sinkLogger)
        
        # 创建多个TCP连接
        for i in range(self.cnt):
            # 创建TCP源
            tcpSrc = TcpSrc(None, None, self.eventlist)
            tcpSrc.setName(f"TCP{i}")
            self.logfile.writeName(tcpSrc)
            
            # 创建TCP接收端
            tcpSnk = TcpSink()
            tcpSnk.setName(f"TCPSink{i}")
            self.logfile.writeName(tcpSnk)
            
            # 注册到重传扫描器
            tcpRtxScanner.registerTcp(tcpSrc)
            
            # 创建路由
            routeout = []
            
            # 第一个连接使用受限队列queue4，其他使用标准队列
            if i == 0:
                routeout.append(self.queue4)
            else:
                # 创建一个标准队列，容量是缓冲区的10倍
                normalQueue = Queue(
                    self.SERVICE1, 
                    self.BUFFER * 10, 
                    self.eventlist,
                    logger=None
                )
                routeout.append(normalQueue)
            
            # 所有流都经过瓶颈队列queue3和pipe1
            routeout.append(self.queue3)
            routeout.append(self.pipe1)
            routeout.append(tcpSnk)
            
            # 返回路由只包含pipe2
            routein = [self.pipe2, tcpSrc]
            
            # 连接TCP源和接收端，使用随机启动时间（0-1ms）
            start_time = random.random() * time_from_ms(1)
            tcpSrc.connect(routeout, routein, tcpSnk, start_time)
            
            # 监控接收端
            sinkLogger.monitorSink(tcpSnk)
            
    def record_setup(self):
        """记录仿真设置"""
        pktsize = Packet.data_packet_size()
        self.logfile.write(f"# pktsize={pktsize} bytes")
        
        rtt = time_as_sec(self.RTT1)
        self.logfile.write(f"# rtt={rtt}")
        
        # 记录其他参数
        self.logfile.write(f"# queue_size={self.qs} packets")
        self.logfile.write(f"# no_of_conns={self.cnt}")
        self.logfile.write(f"# random_seed={self.seed}")
        self.logfile.write(f"# bottleneck_speed={self.SERVICE1/1e9:.1f}Gbps")
        
    def run(self):
        """运行仿真"""
        print(f"Running dumbell TCP simulation with {self.cnt} connections")
        print(f"Queue size: {self.qs} packets")
        print(f"Random seed: {self.seed}")
        print(f"Simulation time: 5 seconds")
        
        # 构建网络
        self.build_network()
        
        # 创建TCP流
        self.create_tcp_flows()
        
        # 记录设置
        self.record_setup()
        
        # 运行仿真
        print("\nStarting simulation...")
        event_count = 0
        start_time = self.eventlist.now()
        
        while self.eventlist.do_next_event():
            event_count += 1
            if event_count % 100000 == 0:
                current_time = self.eventlist.now()
                progress = (current_time - start_time) / (self.eventlist.get_endtime() - start_time) * 100
                print(f"Progress: {progress:.1f}%, events: {event_count}")
        
        print(f"\nSimulation completed. Total events: {event_count}")
        print(f"Output written to: logout.dat")


def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description='Dumbell TCP Simulation - Multiple TCP flows competing over a bottleneck link'
    )
    
    parser.add_argument(
        '-qs', '--qs',
        type=int,
        default=100,
        help='Queue size in packets (default: 100)'
    )
    
    parser.add_argument(
        '-conns', '--conns',
        type=int,
        default=10,
        help='Number of TCP connections (default: 10)'
    )
    
    parser.add_argument(
        '-seed', '--seed',
        type=int,
        default=None,
        help='Random seed (default: current time)'
    )
    
    args = parser.parse_args()
    
    # 如果没有指定种子，使用当前时间
    if args.seed is None:
        args.seed = int(time.time())
    
    return args


def main():
    """主函数"""
    args = parse_arguments()
    
    # 打印参数
    print("Dumbell TCP Simulation")
    print("=" * 40)
    print(f"queue_size {args.qs}")
    print(f"no_of_conns {args.conns}")
    print(f"random seed {args.seed}")
    print("=" * 40)
    
    # 创建并运行仿真
    sim = DumbellTcpSimulation(args)
    sim.run()


if __name__ == "__main__":
    main()