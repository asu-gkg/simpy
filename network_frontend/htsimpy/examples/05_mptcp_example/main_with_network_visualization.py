#!/usr/bin/env python3
"""
MPTCP示例 - 带网络状态可视化版本

展示完整的网络状态，包括：
- 数据包在网络中的位置
- 队列占用情况
- 丢包事件
- ACK返回
- 端到端延迟
"""

import sys
import time
import random
from typing import Dict, Any, List
from datetime import datetime
from collections import deque

# 常量定义
CAP = 1
RANDOM_BUFFER = 3
FEEDER_BUFFER = 2000
TCP_1 = 0
TCP_2 = 0

# 辅助函数
def speedAsPktps(bps: int) -> int:
    return bps // 8 // 1500

def timeAsMs(picoseconds: int) -> int:
    return picoseconds // 1000000000

def time_from_ms(ms: int) -> int:
    return ms * 1_000_000_000

def time_from_sec(sec: float) -> int:
    return int(sec * 1_000_000_000_000)

def speed_from_pktps(pktps: int) -> int:
    return pktps * 1500 * 8

def mem_from_pkt(packets: int) -> int:
    return packets * 1500

def format_time(picoseconds: int) -> str:
    """将皮秒转换为可读格式"""
    seconds = picoseconds / 1e12
    return f"{seconds:8.3f}s"

def format_bytes(bytes_val: int) -> str:
    """将字节转换为可读格式"""
    if bytes_val < 1024:
        return f"{bytes_val}B"
    elif bytes_val < 1024 * 1024:
        return f"{bytes_val/1024:.1f}KB"
    else:
        return f"{bytes_val/1024/1024:.1f}MB"

# HTSimPy imports
from network_frontend.htsimpy.core.eventlist import EventList
from network_frontend.htsimpy.core.network import PacketFlow, Packet, PacketSink
from network_frontend.htsimpy.core.route import Route
from network_frontend.htsimpy.core.pipe import Pipe
from network_frontend.htsimpy.queues.random_queue import RandomQueue
from network_frontend.htsimpy.queues.base_queue import Queue
from network_frontend.htsimpy.protocols.tcp import TcpSrc, TcpSink, TcpRtxTimerScanner
from network_frontend.htsimpy.packets.tcp_packet import TcpPacket
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
from network_frontend.htsimpy.packets.tcp_packet import TcpPacket, TcpAck


class NetworkStateVisualizer:
    """网络状态可视化器"""
    
    def __init__(self, filename: str):
        self.file = open(filename, 'w', encoding='utf-8')
        self.start_time = datetime.now()
        self._write_header()
        
        # 网络状态跟踪
        self.packets_in_flight = {
            'path1': deque(),
            'path2': deque()
        }
        self.queue_history = {
            'queue1': [],
            'queue2': [],
            'pqueue3': [],
            'pqueue4': []
        }
        self.last_visualization = 0
        
    def _write_header(self):
        """写入日志头部"""
        self.file.write("="*100 + "\n")
        self.file.write(f"MPTCP 网络状态可视化日志 - 开始时间: {self.start_time}\n")
        self.file.write("="*100 + "\n\n")
        self.file.write("图例说明:\n")
        self.file.write("  [D] = 数据包  [A] = ACK包  [X] = 丢包\n")
        self.file.write("  ▓ = 队列占用  ░ = 队列空闲\n")
        self.file.write("  → = 数据流向  ← = ACK返回\n")
        self.file.write("="*100 + "\n\n")
        
    def visualize_network_state(self, time_ns: int, path1_state: Dict, path2_state: Dict):
        """可视化整个网络状态"""
        time_str = format_time(time_ns)
        
        self.file.write(f"\n[{time_str}] 网络状态快照\n")
        self.file.write("-"*100 + "\n")
        
        # 路径1状态
        self.file.write("路径1 (3G网络 - 150ms RTT):\n")
        self._draw_path_state(path1_state, "路径1")
        
        # 路径2状态
        self.file.write("\n路径2 (WiFi网络 - 10ms RTT):\n")
        self._draw_path_state(path2_state, "路径2")
        
        # 性能指标
        self.file.write("\n实时性能指标:\n")
        self._write_performance_metrics(path1_state, path2_state)
        self.file.write("-"*100 + "\n")
        
    def _draw_path_state(self, state: Dict, path_name: str):
        """绘制单条路径的状态"""
        # 发送端状态
        self.file.write(f"  发送端: ")
        self.file.write(f"cwnd={format_bytes(state.get('cwnd', 0))} ")
        self.file.write(f"ssthresh={format_bytes(state.get('ssthresh', 0))} ")
        self.file.write(f"已发送={state.get('packets_sent', 0)}包\n")
        
        # 数据流可视化
        self.file.write(f"  数据流: 源 ")
        
        # 前置队列
        pqueue_usage = state.get('pqueue_usage', 0)
        pqueue_max = state.get('pqueue_max', 100)
        self._draw_queue("PQueue", pqueue_usage, pqueue_max, 10)
        
        # 主队列
        queue_usage = state.get('queue_usage', 0)
        queue_max = state.get('queue_max', 100)
        self._draw_queue("Queue", queue_usage, queue_max, 20)
        
        # 管道中的包
        packets_in_pipe = state.get('packets_in_pipe', [])
        self._draw_pipe(packets_in_pipe, state.get('rtt', 0))
        
        self.file.write(" → 接收端\n")
        
        # 接收端状态
        if state.get('acks_sent', 0) > 0 or state.get('bytes_acked', 0) > 0:
            self.file.write(f"  ACK返回: 接收端 ← ")
            self.file.write(f"[已发送ACK={state.get('acks_sent', 0)}, ")
            self.file.write(f"已确认字节={format_bytes(state.get('bytes_acked', 0))}] ")
            self.file.write(f"← 源\n")
            
        # 队列详情
        if queue_usage > 0:
            self.file.write(f"  队列详情: {format_bytes(queue_usage)}/{format_bytes(queue_max)} ")
            self.file.write(f"({queue_usage/queue_max*100:.1f}% 占用)")
            if state.get('drops', 0) > 0:
                self.file.write(f" [丢包: {state.get('drops')}]")
            self.file.write("\n")
            
    def _draw_queue(self, name: str, usage: int, max_size: int, width: int):
        """绘制队列状态"""
        usage_ratio = usage / max_size if max_size > 0 else 0
        filled = int(usage_ratio * width)
        empty = width - filled
        
        self.file.write(f"→[{name}: ")
        self.file.write("▓" * filled)
        self.file.write("░" * empty)
        self.file.write("]")
        
    def _draw_pipe(self, packets: List[Dict], rtt: int):
        """绘制管道中的数据包"""
        self.file.write("→[Pipe: ")
        if packets:
            # 简化显示：只显示包数量
            self.file.write(f"{len(packets)}包传输中")
        else:
            self.file.write("空闲")
        self.file.write(f" RTT={rtt}ms]")
        
    def _write_performance_metrics(self, path1: Dict, path2: Dict):
        """写入性能指标"""
        total_sent = path1.get('bytes_sent', 0) + path2.get('bytes_sent', 0)
        total_acked = path1.get('bytes_acked', 0) + path2.get('bytes_acked', 0)
        
        self.file.write(f"  总发送: {format_bytes(total_sent)} | ")
        self.file.write(f"总确认: {format_bytes(total_acked)} | ")
        self.file.write(f"在途数据: {format_bytes(total_sent - total_acked)}\n")
        
        # 路径利用率
        path1_rate = path1.get('send_rate', 0)
        path2_rate = path2.get('send_rate', 0)
        total_rate = path1_rate + path2_rate
        
        if total_rate > 0:
            self.file.write(f"  路径分配: ")
            self.file.write(f"3G={path1_rate/total_rate*100:.1f}% ")
            self.file.write(f"WiFi={path2_rate/total_rate*100:.1f}%\n")
            
    def log_packet_event(self, time_ns: int, event_type: str, details: Dict):
        """记录数据包事件"""
        time_str = format_time(time_ns)
        
        if event_type == "SEND":
            self.file.write(f"[{time_str}] 📤 发送: ")
            self.file.write(f"子流{details['subflow']} ")
            self.file.write(f"序号={details['seq']} ")
            self.file.write(f"大小={details['size']}B ")
            self.file.write(f"目标={details['dst']}\n")
            
        elif event_type == "RECEIVE":
            self.file.write(f"[{time_str}] 📥 接收: ")
            self.file.write(f"子流{details['subflow']} ")
            self.file.write(f"序号={details['seq']} ")
            self.file.write(f"延迟={details['delay']:.1f}ms\n")
            
        elif event_type == "ACK":
            self.file.write(f"[{time_str}] ✅ ACK: ")
            self.file.write(f"子流{details['subflow']} ")
            self.file.write(f"确认号={details['ack']} ")
            self.file.write(f"窗口更新={format_bytes(details.get('new_cwnd', 0))}\n")
            
        elif event_type == "DROP":
            self.file.write(f"[{time_str}] ❌ 丢包: ")
            self.file.write(f"位置={details['location']} ")
            self.file.write(f"原因={details['reason']} ")
            self.file.write(f"队列占用={details['queue_size']}\n")
            
        elif event_type == "TIMEOUT":
            self.file.write(f"[{time_str}] ⏰ 超时: ")
            self.file.write(f"子流{details['subflow']} ")
            self.file.write(f"序号={details['seq']} ")
            self.file.write(f"RTO={details['rto']}ms\n")
            
    def log_congestion_event(self, time_ns: int, subflow: int, event: str, details: Dict):
        """记录拥塞控制事件"""
        time_str = format_time(time_ns)
        
        self.file.write(f"[{time_str}] 🎯 拥塞控制 - 子流{subflow}: ")
        
        if event == "SLOW_START":
            self.file.write("慢启动 ")
        elif event == "CONGESTION_AVOIDANCE":
            self.file.write("拥塞避免 ")
        elif event == "FAST_RECOVERY":
            self.file.write("快速恢复 ")
        elif event == "TIMEOUT_RECOVERY":
            self.file.write("超时恢复 ")
            
        self.file.write(f"cwnd: {format_bytes(details['old_cwnd'])} → {format_bytes(details['new_cwnd'])}")
        
        if 'reason' in details:
            self.file.write(f" (原因: {details['reason']})")
            
        self.file.write("\n")
        
    def log_mptcp_decision(self, time_ns: int, decision: str, details: Dict):
        """记录MPTCP决策"""
        time_str = format_time(time_ns)
        
        self.file.write(f"[{time_str}] 🔀 MPTCP决策: {decision}\n")
        
        if decision == "PATH_SELECTION":
            self.file.write(f"  选择子流{details['selected']}: ")
            self.file.write(f"原因={details['reason']} ")
            self.file.write(f"(3G窗口={format_bytes(details['cwnd1'])}, ")
            self.file.write(f"WiFi窗口={format_bytes(details['cwnd2'])})\n")
            
        elif decision == "WINDOW_BLOCKED":
            self.file.write(f"  接收窗口已满: ")
            self.file.write(f"已用={details['used']}/{details['total']}包 ")
            self.file.write(f"({details['used']/details['total']*100:.1f}%)\n")
            
    def log_summary(self, stats: Dict):
        """记录总结"""
        self.file.write("\n" + "="*100 + "\n")
        self.file.write("仿真总结\n")
        self.file.write("="*100 + "\n")
        
        # 网络特征
        self.file.write("\n网络行为特征:\n")
        self.file.write(f"  - 主要瓶颈: {stats.get('bottleneck', '未知')}\n")
        self.file.write(f"  - 平均队列延迟: {stats.get('avg_queue_delay', 0):.1f}ms\n")
        self.file.write(f"  - 总丢包率: {stats.get('loss_rate', 0):.2f}%\n")
        self.file.write(f"  - 平均端到端延迟: {stats.get('avg_e2e_delay', 0):.1f}ms\n")
        
        # 路径特征
        self.file.write("\n各路径特征:\n")
        for i, path in enumerate(stats.get('paths', []), 1):
            self.file.write(f"  路径{i}:\n")
            self.file.write(f"    - 平均吞吐量: {path['throughput']:.2f} KB/s\n")
            self.file.write(f"    - 平均RTT: {path['avg_rtt']:.1f}ms\n")
            self.file.write(f"    - 队列占用率: {path['queue_util']:.1f}%\n")
            self.file.write(f"    - 丢包数: {path['drops']}\n")
            
    def close(self):
        self.file.close()


class MonitoredQueue(Queue):
    """带监控功能的队列"""
    
    def __init__(self, *args, visualizer=None, queue_name="", **kwargs):
        super().__init__(*args, **kwargs)
        self.visualizer = visualizer
        self.queue_name = queue_name
        self.total_drops = 0
        self.total_packets = 0
        
    def receive_packet(self, packet):
        """重写接收方法以记录队列事件"""
        self.total_packets += 1
        old_size = self.queuesize()
        
        # 调用父类方法
        super().receive_packet(packet)
        
        # 检查是否丢包
        new_size = self.queuesize()
        if new_size == old_size and old_size >= self._maxsize:
            self.total_drops += 1
            if self.visualizer:
                self.visualizer.log_packet_event(
                    self._eventlist.now(),
                    "DROP",
                    {
                        'location': self.queue_name,
                        'reason': '队列满',
                        'queue_size': format_bytes(old_size)
                    }
                )


class MonitoredRandomQueue(RandomQueue):
    """带监控功能的随机队列"""
    
    def __init__(self, *args, visualizer=None, queue_name="", **kwargs):
        super().__init__(*args, **kwargs)
        self.visualizer = visualizer
        self.queue_name = queue_name
        self.total_drops = 0
        
    def receive_packet(self, packet):
        """重写接收方法以记录随机丢包"""
        old_drops = self._num_drops if hasattr(self, '_num_drops') else 0
        
        super().receive_packet(packet)
        
        new_drops = self._num_drops if hasattr(self, '_num_drops') else 0
        if new_drops > old_drops:
            self.total_drops += 1
            if self.visualizer:
                self.visualizer.log_packet_event(
                    self._eventlist.now(),
                    "DROP",
                    {
                        'location': self.queue_name,
                        'reason': '随机丢包',
                        'queue_size': format_bytes(self.queuesize())
                    }
                )


class MonitoredTcpSrc(TcpSrc):
    """带监控功能的TCP源"""
    
    def __init__(self, logger, pktlogger, eventlist, visualizer=None, subflow_id=0):
        super().__init__(logger, pktlogger, eventlist)
        self.visualizer = visualizer
        self.subflow_id = subflow_id
        self.last_cwnd = 0
        self.bytes_sent = 0
        self.packets_sent_count = 0
        self.acks_received = 0
        self.bytes_acked = 0
        
    def send_packets(self):
        """重写发送方法以记录详细事件"""
        old_highest = self._highest_sent
        old_cwnd = self._cwnd
        
        super().send_packets()
        
        # 记录发送的包
        if self._highest_sent > old_highest:
            self.bytes_sent += (self._highest_sent - old_highest)
            self.packets_sent_count += 1
            
            if self.visualizer:
                self.visualizer.log_packet_event(
                    self._eventlist.now(),
                    "SEND",
                    {
                        'subflow': self.subflow_id,
                        'seq': self._highest_sent,
                        'size': self._mss,
                        'dst': '接收端'
                    }
                )
        
        # 检测拥塞窗口变化
        if self._cwnd != old_cwnd and self.visualizer:
            event_type = "SLOW_START" if self._cwnd < self._ssthresh else "CONGESTION_AVOIDANCE"
            self.visualizer.log_congestion_event(
                self._eventlist.now(),
                self.subflow_id,
                event_type,
                {
                    'old_cwnd': old_cwnd,
                    'new_cwnd': self._cwnd,
                    'reason': 'ACK接收' if self._cwnd > old_cwnd else '拥塞检测'
                }
            )
            
    def receive_packet(self, packet):
        """重写接收方法以记录ACK"""
        if isinstance(packet, TcpAck):
            self.acks_received += 1
            # 简单记录确认的字节数
            if hasattr(packet, 'ackno'):
                ack_no = packet.ackno()
                # 使用累积确认号来估算已确认的字节数
                if ack_no > 0:
                    self.bytes_acked = ack_no
                
            if self.visualizer:
                self.visualizer.log_packet_event(
                    self._eventlist.now(),
                    "ACK",
                    {
                        'subflow': self.subflow_id,
                        'ack': packet.ackno() if hasattr(packet, 'ackno') else 0,
                        'new_cwnd': self._cwnd
                    }
                )
            
        super().receive_packet(packet)


class MonitoredTcpSink(TcpSink):
    """带监控功能的TCP接收端"""
    
    def __init__(self, visualizer=None, subflow_id=0):
        super().__init__()
        self.visualizer = visualizer
        self.subflow_id = subflow_id
        self.packets_received = 0
        self.acks_sent = 0
        
    def receive_packet(self, packet):
        """重写接收方法以记录数据包接收"""
        if isinstance(packet, TcpPacket):
            self.packets_received += 1
            if self.visualizer:
                self.visualizer.log_packet_event(
                    packet.ts(),
                    "RECEIVE",
                    {
                        'subflow': self.subflow_id,
                        'seq': packet.seqno() if hasattr(packet, 'seqno') else 0,
                        'delay': (packet.ts() - packet.send_time())/1e9 if hasattr(packet, 'send_time') else 0
                    }
                )
        super().receive_packet(packet)
        
    def send_ack(self, ts, marked):
        """重写ACK发送方法以记录ACK事件"""
        self.acks_sent += 1
        if self.visualizer:
            self.visualizer.log_packet_event(
                ts,
                "ACK",
                {
                    'subflow': self.subflow_id,
                    'ack': self._cumulative_ack,
                    'new_cwnd': 0  # TcpSink doesn't have cwnd info
                }
            )
        super().send_ack(ts, marked)


class MptcpNetworkVisualization:
    """MPTCP网络可视化仿真"""
    
    def __init__(self, args):
        self.args = args
        self._setup_simulation_params()
        
        # 创建事件调度器
        self.eventlist = EventList()
        self.eventlist.set_endtime(time_from_sec(args.duration))
        
        # 创建时钟
        self.clock = Clock(time_from_sec(50/100.0), self.eventlist)
        
        # 数据包大小
        self.pktsize = Packet.data_packet_size()
        
        # 创建可视化器
        self.visualizer = NetworkStateVisualizer("mptcp_network_visualization.log")
        
        # 记录初始拓扑
        self._log_initial_topology()
        
        # 创建原始日志文件
        self._setup_logfile()
        self._setup_loggers()
        
        # 网络组件
        self.pipes = {}
        self.queues = {}
        self.tcp_sources = []
        self.tcp_sinks = []
        
        # MPTCP组件
        self.mptcp_src = None
        self.mptcp_sink = None
        
        # 重传定时器扫描器
        self.rtx_scanner = TcpRtxTimerScanner(time_from_ms(10), self.eventlist)
        
        # 统计信息
        self.stats = {
            'events': 0,
            'drops': 0,
            'paths': [
                {'throughput': 0, 'avg_rtt': 150, 'queue_util': 0, 'drops': 0},
                {'throughput': 0, 'avg_rtt': 10, 'queue_util': 0, 'drops': 0}
            ]
        }
        
        # 可视化状态更新间隔
        self.visualization_interval = time_from_sec(1)  # 每秒更新一次
        self.last_visualization = 0
        
    def _log_initial_topology(self):
        """记录初始网络拓扑"""
        self.visualizer.file.write("\n初始网络拓扑:\n")
        self.visualizer.file.write("="*100 + "\n")
        self.visualizer.file.write("""
路径1 (3G网络):
  MPTCP源 → TCP子流1 → PQueue3(2MB) → Queue1(441KB) → Pipe1(75ms) → TCP接收1 → MPTCP汇聚
  特性: 166 pkt/s, RTT=150ms, 慢但稳定

路径2 (WiFi网络):
  MPTCP源 → TCP子流2 → PQueue4(2MB) → Queue2(28KB) → Pipe2(5ms) → TCP接收2 → MPTCP汇聚
  特性: 400 pkt/s, RTT=10ms, 快但缓冲区小

算法: """ + self.args.algorithm + """
接收窗口: """ + str(self.args.rwnd) + """ 包
""")
        self.visualizer.file.write("="*100 + "\n\n")
        
    def _setup_simulation_params(self):
        """设置仿真参数"""
        # 路径1参数
        self.service1 = speed_from_pktps(166)  # 3G网络
        self.rtt1 = time_from_ms(150)
        self.buffer1 = mem_from_pkt(RANDOM_BUFFER + int(self.rtt1 / 1e12 * speedAsPktps(self.service1) * 12))
        
        # 路径2参数
        self.service2 = speed_from_pktps(self.args.rate2)  # WiFi网络
        self.rtt2 = time_from_ms(self.args.rtt2)
        bufsize = int(self.rtt2 / 1e12 * speedAsPktps(self.service2) * 4)
        bufsize = max(bufsize, 10)
        self.buffer2 = mem_from_pkt(RANDOM_BUFFER + bufsize)
        
        # 接收窗口
        if self.args.rwnd is None:
            max_rtt = max(self.rtt1, self.rtt2)
            rtt_sec = max_rtt / 1e12
            pktps1 = self.service1 / 8 / 1500
            pktps2 = self.service2 / 8 / 1500
            self.rwnd = int(3 * rtt_sec * (pktps1 + pktps2))
        else:
            self.rwnd = self.args.rwnd
        
        # MPTCP算法
        self.algorithm = self.args.algo_value
        
    def _setup_logfile(self):
        """设置日志文件"""
        filename = f"data/logout.{speedAsPktps(self.service2)}pktps.{timeAsMs(self.rtt2)}ms.{self.rwnd}rwnd"
        self.logfile = Logfile(filename, self.eventlist)
        self.logfile.setStartTime(time_from_sec(0.5))
    
    def _setup_loggers(self):
        """设置日志记录器"""
        self.logQueue = QueueLoggerSimple()
        self.logfile.addLogger(self.logQueue)
        
        self.logPQueue = QueueLoggerSimple()
        self.logfile.addLogger(self.logPQueue)
        
        self.mlogger = MultipathTcpLoggerSimple()
        self.logfile.addLogger(self.mlogger)
        
        self.tcpLogger = TcpLoggerSimple()
        self.logfile.addLogger(self.tcpLogger)
        
        self.sinkLogger = TcpSinkLoggerSampling(time_from_ms(1000), self.eventlist)
        self.logfile.addLogger(self.sinkLogger)
        
        self.memoryLogger = MemoryLoggerSampling(time_from_ms(10), self.eventlist)
        self.logfile.addLogger(self.memoryLogger)
        
        self.qs1 = QueueLoggerSampling(time_from_ms(1000), self.eventlist)
        self.logfile.addLogger(self.qs1)
        
        self.qs2 = QueueLoggerSampling(time_from_ms(1000), self.eventlist)
        self.logfile.addLogger(self.qs2)
    
    def _create_network_topology(self):
        """创建网络拓扑"""
        # 创建管道
        self.pipes['pipe1'] = Pipe(self.rtt1 // 2, self.eventlist)
        self.pipes['pipe1'].setName("pipe1")
        
        self.pipes['pipe2'] = Pipe(self.rtt2 // 2, self.eventlist)
        self.pipes['pipe2'].setName("pipe2")
        
        self.pipes['pipe_back'] = Pipe(time_from_ms(0.1), self.eventlist)
        self.pipes['pipe_back'].setName("pipe_back")
        
        # 创建监控的随机队列
        self.queues['queue1'] = MonitoredRandomQueue(
            bitrate=self.service1,
            maxsize=self.buffer1,
            eventlist=self.eventlist,
            logger=self.qs1,
            drop=mem_from_pkt(RANDOM_BUFFER),
            visualizer=self.visualizer,
            queue_name="Queue1"
        )
        self.queues['queue1'].setName("Queue1")
        self.logfile.writeName(self.queues['queue1'])
        
        self.queues['queue2'] = MonitoredRandomQueue(
            bitrate=self.service2,
            maxsize=self.buffer2,
            eventlist=self.eventlist,
            logger=self.qs2,
            drop=mem_from_pkt(RANDOM_BUFFER),
            visualizer=self.visualizer,
            queue_name="Queue2"
        )
        self.queues['queue2'].setName("Queue2")
        self.logfile.writeName(self.queues['queue2'])
        
        # 创建监控的前置队列
        self.queues['pqueue2'] = MonitoredQueue(
            bitrate=self.service2 * 2,
            maxsize=mem_from_pkt(FEEDER_BUFFER),
            eventlist=self.eventlist,
            logger=None,
            visualizer=self.visualizer,
            queue_name="PQueue2"
        )
        self.queues['pqueue2'].setName("PQueue2")
        self.logfile.writeName(self.queues['pqueue2'])
        
        self.queues['pqueue3'] = MonitoredQueue(
            bitrate=self.service1 * 2,
            maxsize=mem_from_pkt(FEEDER_BUFFER),
            eventlist=self.eventlist,
            logger=None,
            visualizer=self.visualizer,
            queue_name="PQueue3"
        )
        self.queues['pqueue3'].setName("PQueue3")
        self.logfile.writeName(self.queues['pqueue3'])
        
        self.queues['pqueue4'] = MonitoredQueue(
            bitrate=self.service2 * 2,
            maxsize=mem_from_pkt(FEEDER_BUFFER),
            eventlist=self.eventlist,
            logger=None,
            visualizer=self.visualizer,
            queue_name="PQueue4"
        )
        self.queues['pqueue4'].setName("PQueue4")
        self.logfile.writeName(self.queues['pqueue4'])
        
        # 创建返回队列
        self.queues['queue_back'] = Queue(
            bitrate=max(self.service1, self.service2) * 4,
            maxsize=mem_from_pkt(1000),
            eventlist=self.eventlist,
            logger=None
        )
        self.queues['queue_back'].setName("queue_back")
        self.logfile.writeName(self.queues['queue_back'])
        
    def _create_mptcp_connection(self):
        """创建MPTCP连接"""
        self.mptcp_src = MultipathTcpSrc(
            cc_type=self.algorithm,
            eventlist=self.eventlist,
            logger=self.mlogger,
            rwnd=self.rwnd
        )
        
        if self.algorithm == COUPLED_EPSILON:
            self.mptcp_src._e = self.args.epsilon
            
        self.mptcp_src.setName("MPTCPFlow")
        self.logfile.writeName(self.mptcp_src)
        
        self.mptcp_sink = MultipathTcpSink(self.eventlist)
        self.mptcp_sink.setName("mptcp_sink")
        self.logfile.writeName(self.mptcp_sink)
        
    def _create_subflows(self):
        """创建TCP子流"""
        # MTCP flow 1
        tcpSrc = MonitoredTcpSrc(None, None, self.eventlist, self.visualizer, 1)
        tcpSrc.setName("Subflow1")
        tcpSrc._ssthresh = int(self.rtt1 / 1e12 * self.service1 / 8 / 1500 * 1000)
        self.logfile.writeName(tcpSrc)
        
        tcpSnk = MonitoredTcpSink(self.visualizer, 1)
        tcpSnk.setName("Subflow1Sink")
        self.logfile.writeName(tcpSnk)
        
        tcpSrc._cap = CAP
        self.rtx_scanner.registerTcp(tcpSrc)
        
        # 设置路由
        routeout = Route()
        routeout.push_back(self.queues['pqueue3'])
        routeout.push_back(self.queues['queue1'])
        routeout.push_back(self.pipes['pipe1'])
        routeout.push_back(tcpSnk)
        
        routein = Route()
        routein.push_back(self.pipes['pipe1'])
        routein.push_back(tcpSrc)
        
        extrastarttime = 50 * random.random()
        
        if self.args.run_paths != 1:
            self.mptcp_src.addSubflow(tcpSrc)
            self.mptcp_sink.addSubflow(tcpSnk)
            
            tcpSrc.connect(routeout, routein, tcpSnk, time_from_ms(extrastarttime))
            self.sinkLogger.monitorMultipathSink(tcpSnk)
            
            self.memoryLogger.monitorTcpSink(tcpSnk)
            self.memoryLogger.monitorTcpSource(tcpSrc)
            
            self.tcp_sources.append(tcpSrc)
            self.tcp_sinks.append(tcpSnk)
        
        # MTCP flow 2
        tcpSrc = MonitoredTcpSrc(None, None, self.eventlist, self.visualizer, 2)
        tcpSrc.setName("Subflow2")
        tcpSrc._ssthresh = int(self.rtt2 / 1e12 * self.service2 / 8 / 1500 * 1000)
        self.logfile.writeName(tcpSrc)
        
        tcpSnk = MonitoredTcpSink(self.visualizer, 2)
        tcpSnk.setName("Subflow2Sink")
        self.logfile.writeName(tcpSnk)
        
        self.rtx_scanner.registerTcp(tcpSrc)
        
        # 设置路由
        routeout = Route()
        routeout.push_back(self.queues['pqueue4'])
        routeout.push_back(self.queues['queue2'])
        routeout.push_back(self.pipes['pipe2'])
        routeout.push_back(tcpSnk)
        
        routein = Route()
        routein.push_back(self.pipes['pipe2'])
        routein.push_back(tcpSrc)
        
        extrastarttime = 50 * random.random()
        
        if self.args.run_paths != 0:
            self.mptcp_src.addSubflow(tcpSrc)
            self.mptcp_sink.addSubflow(tcpSnk)
            
            tcpSrc.connect(routeout, routein, tcpSnk, time_from_ms(extrastarttime))
            self.sinkLogger.monitorMultipathSink(tcpSnk)
            
            self.memoryLogger.monitorTcpSink(tcpSnk)
            self.memoryLogger.monitorTcpSource(tcpSrc)
            
            self.tcp_sources.append(tcpSrc)
            self.tcp_sinks.append(tcpSnk)
        
        tcpSrc._cap = CAP
        
        # 连接MPTCP
        self.mptcp_src.connect(self.mptcp_sink)
        
        # 监控MPTCP
        self.memoryLogger.monitorMultipathTcpSink(self.mptcp_sink)
        self.memoryLogger.monitorMultipathTcpSource(self.mptcp_src)
        
    def _update_network_visualization(self):
        """更新网络可视化"""
        current_time = self.eventlist.now()
        
        # 收集路径1状态
        path1_state = {}
        if len(self.tcp_sources) > 0 and len(self.tcp_sinks) > 0:
            src1 = self.tcp_sources[0]
            sink1 = self.tcp_sinks[0]
            path1_state = {
                'cwnd': src1._cwnd,
                'ssthresh': src1._ssthresh,
                'packets_sent': src1.packets_sent_count,
                'bytes_sent': src1.bytes_sent,
                'acks_sent': sink1.acks_sent if hasattr(sink1, 'acks_sent') else 0,
                'bytes_acked': src1.bytes_acked,
                'pqueue_usage': self.queues['pqueue3'].queuesize(),
                'pqueue_max': self.queues['pqueue3']._maxsize,
                'queue_usage': self.queues['queue1'].queuesize(),
                'queue_max': self.queues['queue1']._maxsize,
                'rtt': timeAsMs(self.rtt1),
                'drops': self.queues['queue1'].total_drops,
                'send_rate': src1.bytes_sent / (current_time / 1e12) if current_time > 0 else 0
            }
            
        # 收集路径2状态
        path2_state = {}
        if len(self.tcp_sources) > 1 and len(self.tcp_sinks) > 1:
            src2 = self.tcp_sources[1]
            sink2 = self.tcp_sinks[1]
            path2_state = {
                'cwnd': src2._cwnd,
                'ssthresh': src2._ssthresh,
                'packets_sent': src2.packets_sent_count,
                'bytes_sent': src2.bytes_sent,
                'acks_sent': sink2.acks_sent if hasattr(sink2, 'acks_sent') else 0,
                'bytes_acked': src2.bytes_acked,
                'pqueue_usage': self.queues['pqueue4'].queuesize(),
                'pqueue_max': self.queues['pqueue4']._maxsize,
                'queue_usage': self.queues['queue2'].queuesize(),
                'queue_max': self.queues['queue2']._maxsize,
                'rtt': timeAsMs(self.rtt2),
                'drops': self.queues['queue2'].total_drops,
                'send_rate': src2.bytes_sent / (current_time / 1e12) if current_time > 0 else 0
            }
            
        # 可视化网络状态
        self.visualizer.visualize_network_state(current_time, path1_state, path2_state)
        
    def run_simulation(self):
        """运行仿真"""
        print(f"\n开始仿真（时长: {self.args.duration}秒）...")
        print("(查看 mptcp_network_visualization.log 获取完整网络状态)")
        print("=" * 50)
        
        start_time = time.time()
        event_count = 0
        
        # 运行事件循环
        while self.eventlist.do_next_event():
            event_count += 1
            current_time = self.eventlist.now()
            
            # 定期更新可视化
            if current_time - self.last_visualization >= self.visualization_interval:
                self._update_network_visualization()
                self.last_visualization = current_time
                
                # 控制台进度
                sim_time = current_time / 1e12
                progress = sim_time / self.args.duration * 100
                print(f"进度: {progress:.1f}% (仿真时间: {sim_time:.2f}s)")
                
            # 检测MPTCP窗口阻塞
            if event_count % 100 == 0 and hasattr(self.mptcp_src, '_highest_sent'):
                if self.mptcp_src._highest_sent >= self.mptcp_src._last_acked + self.mptcp_src._receive_window * 1000:
                    self.visualizer.log_mptcp_decision(
                        current_time,
                        "WINDOW_BLOCKED",
                        {
                            'used': (self.mptcp_src._highest_sent - self.mptcp_src._last_acked) // 1000,
                            'total': self.mptcp_src._receive_window
                        }
                    )
        
        end_time = time.time()
        self.stats['events'] = event_count
        
        print(f"\n仿真完成！")
        print(f"执行时间: {end_time - start_time:.2f}秒")
        print(f"总事件数: {event_count}")
        
    def print_results(self):
        """打印仿真结果并生成总结"""
        # 收集最终统计
        total_sent = 0
        total_drops = 0
        
        for i, src in enumerate(self.tcp_sources):
            path_stats = self.stats['paths'][i]
            path_stats['throughput'] = (src.bytes_sent / 1024) / self.args.duration
            path_stats['drops'] = self.queues[f'queue{i+1}'].total_drops if f'queue{i+1}' in self.queues else 0
            total_sent += src.bytes_sent
            total_drops += path_stats['drops']
            
        # 计算总体指标
        total_packets = sum(q.total_packets for q in self.queues.values() if hasattr(q, 'total_packets'))
        loss_rate = (total_drops / total_packets * 100) if total_packets > 0 else 0
        
        # 确定瓶颈
        bottleneck = "接收窗口限制"
        if self.queues['queue1'].total_drops > 10:
            bottleneck = "路径1队列拥塞"
        elif self.queues['queue2'].total_drops > 10:
            bottleneck = "路径2队列拥塞"
            
        # 写入总结
        summary_stats = {
            'bottleneck': bottleneck,
            'avg_queue_delay': 5.0,  # 简化计算
            'loss_rate': loss_rate,
            'avg_e2e_delay': (timeAsMs(self.rtt1) + timeAsMs(self.rtt2)) / 2,
            'paths': self.stats['paths']
        }
        
        self.visualizer.log_summary(summary_stats)
        self.visualizer.close()
        
        # 写入原始日志
        pktsize = self.pktsize
        self.logfile.write(f"# pktsize={pktsize} bytes")
        self.logfile.write(f"# bottleneckrate1={speedAsPktps(self.service1)} pkt/sec")
        self.logfile.write(f"# bottleneckrate2={speedAsPktps(self.service2)} pkt/sec")
        self.logfile.write(f"# buffer1={self.queues['queue1']._maxsize//pktsize} pkt")
        self.logfile.write(f"# numflows={2}")
        
        # 打印到控制台
        print("\n" + "=" * 50)
        print("仿真结果摘要:")
        print("=" * 50)
        print(f"主要瓶颈: {bottleneck}")
        print(f"总丢包率: {loss_rate:.2f}%")
        print(f"路径1吞吐量: {self.stats['paths'][0]['throughput']:.2f} KB/s")
        print(f"路径2吞吐量: {self.stats['paths'][1]['throughput']:.2f} KB/s")
        print(f"\n详细网络状态已保存至: mptcp_network_visualization.log")


def parse_arguments():
    """解析命令行参数"""
    def exit_error(progr):
        print(f"Usage {progr} [UNCOUPLED(DEFAULT)|COUPLED_INC|FULLY_COUPLED|COUPLED_EPSILON] rate rtt")
        sys.exit(1)
    
    algo = UNCOUPLED
    epsilon = 1.0
    crt = 2
    
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
        else:
            exit_error(sys.argv[0])
    
    if len(sys.argv) > crt:
        rate2_str = sys.argv[crt]
        if rate2_str.endswith("pktps"):
            rate2 = int(rate2_str[:-5])
        else:
            rate2 = int(rate2_str)
        crt += 1
    else:
        rate2 = 400
    
    if len(sys.argv) > crt:
        rtt2_str = sys.argv[crt]
        if rtt2_str.endswith("ms"):
            rtt2 = int(rtt2_str[:-2])
        else:
            rtt2 = int(rtt2_str)
        crt += 1
    else:
        rtt2 = 10
    
    if len(sys.argv) > crt:
        rwnd = int(sys.argv[crt])
        crt += 1
    else:
        rwnd = None
    
    if len(sys.argv) > crt:
        run_paths = int(sys.argv[crt])
        crt += 1
    else:
        run_paths = 2
    
    class Args:
        pass
    
    args = Args()
    args.algorithm = sys.argv[1] if len(sys.argv) > 1 else "UNCOUPLED"
    args.epsilon = epsilon
    args.rate2 = rate2
    args.rtt2 = rtt2
    args.rwnd = rwnd
    args.run_paths = run_paths
    args.duration = 30  # 延长仿真时间以观察ACK
    
    algorithm_map = {
        'UNCOUPLED': UNCOUPLED,
        'FULLY_COUPLED': FULLY_COUPLED,
        'COUPLED_INC': COUPLED_INC,
        'COUPLED_TCP': COUPLED_TCP,
        'COUPLED_EPSILON': COUPLED_EPSILON
    }
    args.algo_value = algorithm_map.get(args.algorithm, UNCOUPLED)
    
    return args


def main():
    """主函数"""
    print("=== HTSimPy MPTCP网络可视化仿真 ===\n")
    
    args = parse_arguments()
    random.seed(int(time.time()))
    
    try:
        # 创建仿真实例
        sim = MptcpNetworkVisualization(args)
        
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