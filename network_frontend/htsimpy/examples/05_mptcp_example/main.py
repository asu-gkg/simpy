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

# 常量定义 - 对应C++宏定义
CAP = 1  # 对应 C++ #define CAP 1
RANDOM_BUFFER = 3  # 对应 C++ #define RANDOM_BUFFER 3
FEEDER_BUFFER = 2000  # 对应 C++ #define FEEDER_BUFFER 2000
TCP_1 = 0  # 对应 C++ #define TCP_1 0
TCP_2 = 0  # 对应 C++ #define TCP_2 0

# 辅助函数 - 精确对应C++版本
def speedAsPktps(bps: int) -> int:
    """对应 C++ speedAsPktps() - 将比特率转换为包速率（包/秒）"""
    return bps // 8 // 1500

def timeAsMs(picoseconds: int) -> int:
    """对应 C++ timeAsMs() - 皮秒转毫秒"""
    return picoseconds // 1000000000

# HTSimPy imports
from network_frontend.htsimpy.core.eventlist import EventList
from network_frontend.htsimpy.core.network import PacketFlow, Packet
from network_frontend.htsimpy.core.route import Route
from network_frontend.htsimpy.core.pipe import Pipe
from network_frontend.htsimpy.queues.random_queue import RandomQueue
from network_frontend.htsimpy.queues.base_queue import Queue  # 对应C++的Queue
from network_frontend.htsimpy.protocols.tcp import TcpSrc, TcpSink, TcpRtxTimerScanner
from network_frontend.htsimpy.protocols.multipath_tcp import (
    MultipathTcpSrc, MultipathTcpSink,
    UNCOUPLED, FULLY_COUPLED, COUPLED_INC, COUPLED_TCP, COUPLED_EPSILON
)
from network_frontend.htsimpy.core.logger.tcp import TcpLoggerSimple, MultipathTcpLoggerSimple
from network_frontend.htsimpy.core.logger.queue import QueueLoggerSampling, QueueLoggerSimple
from network_frontend.htsimpy.core.logger.sink import TcpSinkLoggerSampling
from network_frontend.htsimpy.core.logger.memory import MemoryLoggerSampling
from network_frontend.htsimpy.core.logger.logfile import Logfile
from network_frontend.htsimpy.core.clock import Clock


def parse_arguments():
    """解析命令行参数 - 对应 C++ main() 参数解析"""
    # 对应 C++ exit_error函数
    def exit_error(progr):
        print(f"Usage {progr} [UNCOUPLED(DEFAULT)|COUPLED_INC|FULLY_COUPLED|COUPLED_EPSILON] rate rtt")
        sys.exit(1)
    
    # 模拟C++的参数解析方式
    algo = UNCOUPLED  # 默认算法
    epsilon = 1.0
    crt = 2  # 当前参数索引
    
    # 处理算法参数 - 对应 C++ if (argc>1)
    if len(sys.argv) > 1:
        if sys.argv[1] == "UNCOUPLED":
            algo = UNCOUPLED
        elif sys.argv[1] == "COUPLED_INC":
            algo = COUPLED_INC
        elif sys.argv[1] == "FULLY_COUPLED":
            algo = FULLY_COUPLED
        elif sys.argv[1] == "COUPLED_TCP":
            algo = COUPLED_TCP
        elif sys.argv[1] == "COUPLED_EPSILON":
            algo = COUPLED_EPSILON
            if len(sys.argv) > 2:
                epsilon = float(sys.argv[2])
                crt += 1
                print(f"Using epsilon {epsilon}")
        else:
            exit_error(sys.argv[0])
    
    # 处理rate2参数 - 对应 C++ if (argc>crt)
    if len(sys.argv) > crt:
        rate2_str = sys.argv[crt]
        # 处理带单位的输入，如 "400pktps"
        if rate2_str.endswith("pktps"):
            rate2 = int(rate2_str[:-5])
        else:
            rate2 = int(rate2_str)
        crt += 1
    else:
        rate2 = 400
    
    # 处理rtt2参数
    if len(sys.argv) > crt:
        rtt2_str = sys.argv[crt]
        # 处理带单位的输入，如 "10000ms"
        if rtt2_str.endswith("ms"):
            rtt2 = int(rtt2_str[:-2])
        else:
            rtt2 = int(rtt2_str)
        crt += 1
    else:
        rtt2 = 10
    
    # 处理rwnd参数
    if len(sys.argv) > crt:
        rwnd = int(sys.argv[crt])
        crt += 1
    else:
        rwnd = None
    
    # 处理run_paths参数
    if len(sys.argv) > crt:
        run_paths = int(sys.argv[crt])
        crt += 1
    else:
        run_paths = 2
    
    # 创建一个类似argparse结果的对象
    class Args:
        pass
    
    args = Args()
    args.algorithm = sys.argv[1] if len(sys.argv) > 1 else "UNCOUPLED"
    args.epsilon = epsilon
    args.rate2 = rate2
    args.rtt2 = rtt2
    args.rwnd = rwnd
    args.run_paths = run_paths
    args.duration = 60  # C++中硬编码为60秒
    
    # 算法值设置
    algorithm_map = {
        'UNCOUPLED': UNCOUPLED,
        'FULLY_COUPLED': FULLY_COUPLED,
        'COUPLED_INC': COUPLED_INC,
        'COUPLED_TCP': COUPLED_TCP,
        'COUPLED_EPSILON': COUPLED_EPSILON
    }
    args.algo_value = algorithm_map.get(args.algorithm, UNCOUPLED)
    
    return args


def time_from_ms(ms: int) -> int:
    """毫秒转换为皮秒 - 对应 C++ timeFromMs()"""
    return ms * 1_000_000_000


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
        
        # 创建时钟 - 对应 C++ Clock c(timeFromSec(50/100.), eventlist);
        self.clock = Clock(time_from_sec(50/100.0), self.eventlist)
        
        # 设置数据包大小 - 对应 C++ Packet::data_packet_size()
        self.pktsize = Packet.data_packet_size()
        
        # 创建日志文件 - 对应 C++ Logfile
        self._setup_logfile()
        
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
        # C++: rwnd = 3 * timeAsSec(max(RTT1,RTT2)) * (speedAsPktps(SERVICE1)+speedAsPktps(SERVICE2));
        if self.args.rwnd is None:
            max_rtt = max(self.rtt1, self.rtt2)
            # timeAsSec: 将皮秒转换为秒
            rtt_sec = max_rtt / 1e12
            # speedAsPktps: bits/sec -> packets/sec (假设1500字节/包)
            pktps1 = self.service1 / 8 / 1500
            pktps2 = self.service2 / 8 / 1500
            self.rwnd = int(3 * rtt_sec * (pktps1 + pktps2))
        else:
            self.rwnd = self.args.rwnd
        
        # MPTCP算法 - 对应 C++ algo 设置
        self.algorithm = self.args.algo_value
        
        print(f"仿真参数配置:")
        print(f"  路径1: {self.service1//1000000}Mbps, RTT={self.rtt1//1000000000}ms, 缓冲区={self.buffer1}字节")
        print(f"  路径2: {self.service2//1000000}Mbps, RTT={self.rtt2//1000000000}ms, 缓冲区={self.buffer2}字节")
        print(f"  MPTCP算法: {self.args.algorithm}")
        print(f"  接收窗口: {self.rwnd}")
        print(f"  运行路径: {self.args.run_paths}")
        print()
    
    def _setup_logfile(self):
        """设置日志文件 - 对应 C++ Logfile设置"""
        # 对应 C++: stringstream filename(ios_base::out);
        # filename << "../data/logout." << speedAsPktps(SERVICE2) << "pktps." <<timeAsMs(RTT2) << "ms." << rwnd << "rwnd";
        # 使用绝对路径或相对于项目根目录的路径
        filename = f"data/logout.{speedAsPktps(self.service2)}pktps.{timeAsMs(self.rtt2)}ms.{self.rwnd}rwnd"
        print(f"Outputting to {filename}")
        
        # 对应 C++: Logfile logfile(filename.str(),eventlist);
        self.logfile = Logfile(filename, self.eventlist)
        
        # 对应 C++: logfile.setStartTime(timeFromSec(0.5));
        self.logfile.setStartTime(time_from_sec(0.5))
    
    def _setup_loggers(self):
        """设置日志记录器 - 对应 C++ 日志器设置"""
        # 队列日志记录器 - 对应 C++ QueueLoggerSimple 和 QueueLoggerSampling
        self.logQueue = QueueLoggerSimple()
        self.logfile.addLogger(self.logQueue)
        
        self.logPQueue = QueueLoggerSimple()
        self.logfile.addLogger(self.logPQueue)
        
        # MPTCP日志记录器 - 对应 C++ MultipathTcpLoggerSimple
        self.mlogger = MultipathTcpLoggerSimple()
        self.logfile.addLogger(self.mlogger)
        
        # TCP日志记录器 - 对应 C++ TcpLoggerSimple
        # C++: TcpLoggerSimple* logTcp = new TcpLoggerSimple();
        # C++: logfile.addLogger(*logTcp);
        self.tcpLogger = TcpLoggerSimple()
        self.logfile.addLogger(self.tcpLogger)
        
        # Sink日志记录器 - 对应 C++ TcpSinkLoggerSampling
        self.sinkLogger = TcpSinkLoggerSampling(time_from_ms(1000), self.eventlist)
        self.logfile.addLogger(self.sinkLogger)
        
        # 内存日志记录器 - 对应 C++ MemoryLoggerSampling
        self.memoryLogger = MemoryLoggerSampling(time_from_ms(10), self.eventlist)
        self.logfile.addLogger(self.memoryLogger)
        
        # 队列采样日志记录器 - 对应 C++ QueueLoggerSampling qs1, qs2
        self.qs1 = QueueLoggerSampling(time_from_ms(1000), self.eventlist)
        self.logfile.addLogger(self.qs1)
        
        self.qs2 = QueueLoggerSampling(time_from_ms(1000), self.eventlist)
        self.logfile.addLogger(self.qs2)
    
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
            logger=self.qs1,
            drop=mem_from_pkt(RANDOM_BUFFER)  # 对应 C++ memFromPkt(RANDOM_BUFFER)
        )
        self.queues['queue1'].setName("Queue1")
        self.logfile.writeName(self.queues['queue1'])
        
        self.queues['queue2'] = RandomQueue(
            bitrate=self.service2,
            maxsize=self.buffer2,
            eventlist=self.eventlist,
            logger=self.qs2,
            drop=mem_from_pkt(RANDOM_BUFFER)  # 对应 C++ memFromPkt(RANDOM_BUFFER)
        )
        self.queues['queue2'].setName("Queue2")
        self.logfile.writeName(self.queues['queue2'])
        
        # 创建前置队列 - 对应 C++ Queue (不是RandomQueue)
        self.queues['pqueue2'] = Queue(
            bitrate=self.service2 * 2,
            maxsize=mem_from_pkt(FEEDER_BUFFER),
            eventlist=self.eventlist,
            logger=None
        )
        self.queues['pqueue2'].setName("PQueue2")
        self.logfile.writeName(self.queues['pqueue2'])
        
        self.queues['pqueue3'] = Queue(
            bitrate=self.service1 * 2,
            maxsize=mem_from_pkt(FEEDER_BUFFER),
            eventlist=self.eventlist,
            logger=None
        )
        self.queues['pqueue3'].setName("PQueue3")
        self.logfile.writeName(self.queues['pqueue3'])
        
        self.queues['pqueue4'] = Queue(
            bitrate=self.service2 * 2,
            maxsize=mem_from_pkt(FEEDER_BUFFER),
            eventlist=self.eventlist,
            logger=None
        )
        self.queues['pqueue4'].setName("PQueue4")
        self.logfile.writeName(self.queues['pqueue4'])
        
        # 创建返回队列 - 对应 C++ queue_back
        self.queues['queue_back'] = Queue(
            bitrate=max(self.service1, self.service2) * 4,
            maxsize=mem_from_pkt(1000),
            eventlist=self.eventlist,
            logger=None
        )
        self.queues['queue_back'].setName("queue_back")
        self.logfile.writeName(self.queues['queue_back'])
        
        print(f"  队列1: {self.queues['queue1'].nodename()}")
        print(f"  队列2: {self.queues['queue2'].nodename()}")
        
    def _create_mptcp_connection(self):
        """
        创建MPTCP连接 - 对应 C++ MPTCP连接设置
        """
        print("创建MPTCP连接...")
        
        # 创建MPTCP源端和接收端 - 对应 C++ MultipathTcpSrc/Sink
        # C++: mtcp = new MultipathTcpSrc(algo, eventlist, &mlogger, rwnd);
        # 注意：如果是COUPLED_EPSILON，需要设置epsilon参数
        self.mptcp_src = MultipathTcpSrc(
            cc_type=self.algorithm,
            eventlist=self.eventlist,
            logger=self.mlogger,  # 使用mlogger而不是mptcp_logger
            rwnd=self.rwnd
        )
        
        # 如果是COUPLED_EPSILON算法，设置epsilon参数
        if self.algorithm == COUPLED_EPSILON:
            self.mptcp_src._e = self.args.epsilon
        self.mptcp_src.setName("MPTCPFlow")
        self.logfile.writeName(self.mptcp_src)
        
        # C++: mtcp_sink = new MultipathTcpSink(eventlist);
        self.mptcp_sink = MultipathTcpSink(self.eventlist)
        self.mptcp_sink.setName("mptcp_sink")
        self.logfile.writeName(self.mptcp_sink)
        
        # 注意：connect要在添加子流之后调用，参考C++代码
        # 这里先不连接，等子流创建后再连接
        
        print(f"  MPTCP算法: {self.args.algorithm}")
        print(f"  接收窗口: {self.rwnd}")
        
    def _create_subflows(self):
        """
        创建TCP子流 - 对应 C++ TCP子流创建
        """
        print("创建TCP子流...")
        
        # 注意：C++中先创建了Subflow1，然后是Subflow2，最后才连接MPTCP
        
        # 对应 C++ for (int i=0;i<TCP_1;i++) - TCP_1 = 0
        for i in range(TCP_1):
            pass  # 空循环，因为 TCP_1 = 0
        
        # 对应 C++ for (int i=0;i<TCP_2;i++) - TCP_2 = 0
        for i in range(TCP_2):
            pass  # 空循环，因为 TCP_2 = 0
        
        # MTCP flow 1 - 对应 C++ line 253-291
        # C++: tcpSrc = new TcpSrc(NULL,NULL,eventlist);
        tcpSrc = TcpSrc(None, None, self.eventlist)
        tcpSrc.setName("Subflow1")
        tcpSrc._ssthresh = int(self.rtt1 / 1e12 * self.service1 / 8 / 1500 * 1000)
        self.logfile.writeName(tcpSrc)
        
        tcpSnk = TcpSink()
        tcpSnk.setName("Subflow1Sink")
        self.logfile.writeName(tcpSnk)
        
        tcpSrc._cap = CAP  # 对应 C++ tcpSrc->_cap = CAP;
        self.rtx_scanner.registerTcp(tcpSrc)
        
        # tell it the route
        routeout = Route()
        routeout.push_back(self.queues['pqueue3'])
        routeout.push_back(self.queues['queue1'])
        routeout.push_back(self.pipes['pipe1'])
        routeout.push_back(tcpSnk)
        
        routein = Route()
        routein.push_back(self.pipes['pipe1'])
        routein.push_back(tcpSrc)
        
        extrastarttime = 50 * random.random()  # 对应 C++ extrastarttime = 50*drand();
        
        # join multipath connection - 对应 C++ if (run_paths!=1)
        if self.args.run_paths != 1:
            self.mptcp_src.addSubflow(tcpSrc)
            self.mptcp_sink.addSubflow(tcpSnk)
            
            tcpSrc.connect(routeout, routein, tcpSnk, time_from_ms(extrastarttime))
            self.sinkLogger.monitorMultipathSink(tcpSnk)
            
            self.memoryLogger.monitorTcpSink(tcpSnk)
            self.memoryLogger.monitorTcpSource(tcpSrc)
            
            self.tcp_sources.append(tcpSrc)
            self.tcp_sinks.append(tcpSnk)
        
        # MTCP flow 2 - 对应 C++ line 293-329
        # C++: tcpSrc = new TcpSrc(NULL,NULL,eventlist);
        tcpSrc = TcpSrc(None, None, self.eventlist)
        tcpSrc.setName("Subflow2")
        tcpSrc._ssthresh = int(self.rtt2 / 1e12 * self.service2 / 8 / 1500 * 1000)
        self.logfile.writeName(tcpSrc)
        
        tcpSnk = TcpSink()
        tcpSnk.setName("Subflow2Sink")
        self.logfile.writeName(tcpSnk)
        
        self.rtx_scanner.registerTcp(tcpSrc)
        
        # tell it the route
        routeout = Route()
        routeout.push_back(self.queues['pqueue4'])
        routeout.push_back(self.queues['queue2'])
        routeout.push_back(self.pipes['pipe2'])
        routeout.push_back(tcpSnk)
        
        routein = Route()
        routein.push_back(self.pipes['pipe2'])
        routein.push_back(tcpSrc)
        
        extrastarttime = 50 * random.random()
        
        if self.args.run_paths != 0:  # 对应 C++ if (run_paths!=0)
            # join multipath connection
            self.mptcp_src.addSubflow(tcpSrc)
            self.mptcp_sink.addSubflow(tcpSnk)
            
            tcpSrc.connect(routeout, routein, tcpSnk, time_from_ms(extrastarttime))
            self.sinkLogger.monitorMultipathSink(tcpSnk)
            
            self.memoryLogger.monitorTcpSink(tcpSnk)
            self.memoryLogger.monitorTcpSource(tcpSrc)
            
            self.tcp_sources.append(tcpSrc)
            self.tcp_sinks.append(tcpSnk)
        
        tcpSrc._cap = CAP  # 对应 C++ tcpSrc->_cap = CAP; (注意这在第二个子流的最后)
        
        # 现在连接MPTCP - 对应 C++ mtcp->connect(mtcp_sink);
        self.mptcp_src.connect(self.mptcp_sink)
        
        # 监控MPTCP - 对应 C++ memoryLogger监控
        self.memoryLogger.monitorMultipathTcpSink(self.mptcp_sink)
        self.memoryLogger.monitorMultipathTcpSource(self.mptcp_src)
        
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
        # 记录设置到日志文件 - 对应 C++ line 338-349
        # Record the setup
        pktsize = self.pktsize
        self.logfile.write(f"# pktsize={pktsize} bytes")
        self.logfile.write(f"# bottleneckrate1={speedAsPktps(self.service1)} pkt/sec")
        self.logfile.write(f"# bottleneckrate2={speedAsPktps(self.service2)} pkt/sec")
        self.logfile.write(f"# buffer1={self.queues['queue1']._maxsize//pktsize} pkt")
        # C++中buffer2被注释掉了: //logfile.write("# buffer2="+ntoa((double)(queue2._maxsize)/((double)pktsize))+" pkt");
        rtt = self.rtt1 / 1e12  # timeAsSec
        self.logfile.write(f"# rtt={rtt}")
        rtt = self.rtt2 / 1e12  # timeAsSec
        self.logfile.write(f"# rtt={rtt}")
        self.logfile.write(f"# numflows={2}")  # 对应 C++ NUMFLOWS
        self.logfile.write(f"# targetwnd={30}")  # 对应 C++ targetwnd
        
        print("\n" + "=" * 50)
        print("仿真结果:")
        print("=" * 50)
        
        # MPTCP总体性能
        print(f"\nMPTCP总体性能:")
        print(f"  算法: {self.args.algorithm}")
        print(f"  子流数量: {len(self.tcp_sources)}")
        
        # 输出一些统计信息
        if hasattr(self.mptcp_sink, 'cumulative_ack'):
            print(f"  累积确认: {self.mptcp_sink.cumulative_ack()}")
        if hasattr(self.mptcp_sink, 'data_ack'):
            print(f"  数据确认: {self.mptcp_sink.data_ack()}")
        
        # 各子流性能
        for i, tcpSrc in enumerate(self.tcp_sources, 1):
            print(f"\n子流{i}性能:")
            if hasattr(tcpSrc, '_cwnd'):
                print(f"  拥塞窗口: {tcpSrc._cwnd}")
            if hasattr(tcpSrc, '_packets_sent'):
                print(f"  发送包数: {tcpSrc._packets_sent}")
        
        # 队列统计
        for name, queue in self.queues.items():
            if 'queue' in name.lower() and hasattr(queue, '_num_drops'):
                print(f"\n{name}统计:")
                print(f"  队列大小: {queue.queuesize()} bytes")
                print(f"  最大容量: {queue._maxsize} bytes")
                if hasattr(queue, '_num_drops'):
                    print(f"  丢包数: {queue._num_drops}")


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