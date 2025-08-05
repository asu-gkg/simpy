#!/usr/bin/env python3
"""
MPTCP网络可视化 - 精简版
展示MPTCP在双路径网络中的行为
"""

import sys
import time
import random
from typing import Dict, List, Optional
from datetime import datetime

# 导入HTSimPy组件
from network_frontend.htsimpy.core.eventlist import EventList
from network_frontend.htsimpy.core.network import Packet
from network_frontend.htsimpy.core.route import Route
from network_frontend.htsimpy.core.pipe import Pipe
from network_frontend.htsimpy.queues.random_queue import RandomQueue
from network_frontend.htsimpy.queues.base_queue import Queue
from network_frontend.htsimpy.protocols.tcp import TcpSrc, TcpSink, TcpRtxTimerScanner
from network_frontend.htsimpy.protocols.multipath_tcp import (
    MultipathTcpSrc, MultipathTcpSink, UNCOUPLED, COUPLED_EPSILON
)
from network_frontend.htsimpy.packets.tcp_packet import TcpPacket, TcpAck
from network_frontend.htsimpy.core.logger.logfile import Logfile
from network_frontend.htsimpy.core.clock import Clock

# 常量定义
PACKET_SIZE = 1500  # 字节
FEEDER_BUFFER = 2000  # 包
RANDOM_BUFFER = 3  # 包

# 辅助函数
def ms_to_ps(ms): return ms * 1_000_000_000
def sec_to_ps(sec): return int(sec * 1_000_000_000_000)
def ps_to_ms(ps): return ps / 1e9
def ps_to_sec(ps): return ps / 1e12
def speed_from_pktps(pktps): return pktps * 8 * PACKET_SIZE
def mem_from_pkt(pkts): return pkts * PACKET_SIZE
def format_time(ps): return f"{ps_to_sec(ps):8.3f}s"
def format_bytes(b): 
    if b < 1024: return f"{b}B"
    elif b < 1024*1024: return f"{b/1024:.1f}KB"
    else: return f"{b/1024/1024:.1f}MB"


class SimpleLogger:
    """简化的日志记录器"""
    def __init__(self, filename: str):
        self.file = open(filename, 'w', encoding='utf-8')
        self.start_time = datetime.now()
        self._write_header()
        
    def _write_header(self):
        self.file.write("="*80 + "\n")
        self.file.write(f"MPTCP仿真日志 - {self.start_time}\n")
        self.file.write("="*80 + "\n\n")
        
    def log_event(self, time_ps: int, event: str, details: str = ""):
        """记录事件"""
        time_str = format_time(time_ps)
        self.file.write(f"[{time_str}] {event}")
        if details:
            self.file.write(f" - {details}")
        self.file.write("\n")
        
    def log_state(self, time_ps: int, state: Dict):
        """记录网络状态快照"""
        self.file.write(f"\n[{format_time(time_ps)}] 网络状态:\n")
        self.file.write("-" * 60 + "\n")
        
        # 路径1状态
        p1 = state.get('path1', {})
        self.file.write(f"路径1 (3G): ")
        self.file.write(f"已发送={p1.get('sent', 0)}包, ")
        self.file.write(f"已确认={p1.get('acks', 0)}包, ")
        self.file.write(f"cwnd={format_bytes(p1.get('cwnd', 0))}\n")
        
        # 路径2状态
        p2 = state.get('path2', {})
        self.file.write(f"路径2 (WiFi): ")
        self.file.write(f"已发送={p2.get('sent', 0)}包, ")
        self.file.write(f"已确认={p2.get('acks', 0)}包, ")
        self.file.write(f"cwnd={format_bytes(p2.get('cwnd', 0))}\n")
        
        # 总体统计
        total_sent = p1.get('sent', 0) + p2.get('sent', 0)
        total_acks = p1.get('acks', 0) + p2.get('acks', 0)
        self.file.write(f"总计: 发送={total_sent}包, ACK={total_acks}包\n")
        self.file.write("-" * 60 + "\n")
        
    def close(self):
        self.file.write("\n仿真结束\n")
        self.file.close()


class MonitoredTcp:
    """TCP监控基类"""
    def __init__(self):
        self.packets_sent = 0
        self.acks_sent = 0
        self.acks_received = 0
        self.bytes_sent = 0
        

class MonitoredTcpSrc(TcpSrc, MonitoredTcp):
    """带监控的TCP发送端"""
    def __init__(self, logger, pktlogger, eventlist, monitor=None, path_id=0):
        TcpSrc.__init__(self, logger, pktlogger, eventlist)
        MonitoredTcp.__init__(self)
        self.monitor = monitor
        self.path_id = path_id
        
    def send_packets(self):
        old_sent = self._highest_sent
        super().send_packets()
        
        if self._highest_sent > old_sent:
            self.packets_sent += 1
            self.bytes_sent += (self._highest_sent - old_sent)
            
            if self.monitor:
                self.monitor.log_event(
                    self._eventlist.now(),
                    f"发送数据包",
                    f"路径{self.path_id}, seq={self._highest_sent}"
                )
                
    def receivePacket(self, pkt):
        if isinstance(pkt, TcpAck):
            self.acks_received += 1
            if self.monitor:
                self.monitor.log_event(
                    self._eventlist.now(),
                    f"收到ACK",
                    f"路径{self.path_id}, ack={pkt.ackno() if hasattr(pkt, 'ackno') else 'N/A'}"
                )
        super().receivePacket(pkt)


class MonitoredTcpSink(TcpSink, MonitoredTcp):
    """带监控的TCP接收端"""
    def __init__(self, monitor=None, path_id=0):
        TcpSink.__init__(self)
        MonitoredTcp.__init__(self)
        self.monitor = monitor
        self.path_id = path_id
        
    def send_ack(self, ts, marked):
        self.acks_sent += 1
        if self.monitor and self.acks_sent % 10 == 0:  # 每10个ACK记录一次
            self.monitor.log_event(
                ts,
                f"发送ACK",
                f"路径{self.path_id}, 累计={self.acks_sent}"
            )
        super().send_ack(ts, marked)


class MptcpSimulation:
    """MPTCP仿真主类"""
    
    def __init__(self, duration: int = 30, rwnd: Optional[int] = None):
        self.duration = duration
        self.rwnd = rwnd if rwnd else 254  # 默认接收窗口
        
        # 网络参数
        self.path1_rate = 166  # pkt/s (3G)
        self.path1_rtt = 150   # ms
        self.path2_rate = 400  # pkt/s (WiFi)
        self.path2_rtt = 10    # ms
        
        # 初始化组件
        self.eventlist = EventList()
        self.eventlist.set_endtime(sec_to_ps(duration))
        self.clock = Clock(sec_to_ps(0.5), self.eventlist)
        
        # 日志
        self.logger = SimpleLogger("mptcp_simple.log")
        self.logfile = Logfile("mptcp_simple.dat", self.eventlist)
        
        # 网络组件容器
        self.components = {}
        self.tcp_sources = []
        self.tcp_sinks = []
        
    def create_network(self):
        """创建网络拓扑"""
        self.logger.log_event(0, "创建网络拓扑")
        
        # 创建管道
        self.components['pipe1'] = Pipe(ms_to_ps(self.path1_rtt/2), self.eventlist)
        self.components['pipe2'] = Pipe(ms_to_ps(self.path2_rtt/2), self.eventlist)
        
        # 创建队列
        # 路径1队列
        self.components['queue1'] = RandomQueue(
            speed_from_pktps(self.path1_rate),
            mem_from_pkt(300),
            self.eventlist,
            None,
            4500
        )
        self.components['pqueue1'] = Queue(
            speed_from_pktps(self.path1_rate) * 10,
            mem_from_pkt(FEEDER_BUFFER),
            self.eventlist,
            None
        )
        
        # 路径2队列
        self.components['queue2'] = RandomQueue(
            speed_from_pktps(self.path2_rate),
            mem_from_pkt(20),
            self.eventlist,
            None,
            4500
        )
        self.components['pqueue2'] = Queue(
            speed_from_pktps(self.path2_rate) * 10,
            mem_from_pkt(FEEDER_BUFFER),
            self.eventlist,
            None
        )
        
    def create_mptcp(self):
        """创建MPTCP连接"""
        self.logger.log_event(0, "创建MPTCP连接", f"接收窗口={self.rwnd}包")
        
        # MPTCP源和汇聚点
        self.mptcp_src = MultipathTcpSrc(
            UNCOUPLED,
            self.eventlist,
            None,
            self.rwnd
        )
        self.mptcp_sink = MultipathTcpSink(self.eventlist)
        
        # 重传定时器
        self.rtx_scanner = TcpRtxTimerScanner(ms_to_ps(10), self.eventlist)
        
    def create_subflows(self):
        """创建TCP子流"""
        self.logger.log_event(0, "创建TCP子流")
        
        # 子流1 (3G)
        src1 = MonitoredTcpSrc(None, None, self.eventlist, self.logger, 1)
        src1._ssthresh = 20000
        sink1 = MonitoredTcpSink(self.logger, 1)
        
        # 路由配置
        route_out1 = Route()
        route_out1.push_back(self.components['pqueue1'])
        route_out1.push_back(self.components['queue1'])
        route_out1.push_back(self.components['pipe1'])
        route_out1.push_back(sink1)
        
        route_back1 = Route()
        route_back1.push_back(self.components['pipe1'])
        route_back1.push_back(src1)
        
        # 连接
        self.mptcp_src.addSubflow(src1)
        self.mptcp_sink.addSubflow(sink1)
        src1.connect(route_out1, route_back1, sink1, 0)
        self.rtx_scanner.registerTcp(src1)
        
        self.tcp_sources.append(src1)
        self.tcp_sinks.append(sink1)
        
        # 子流2 (WiFi)
        src2 = MonitoredTcpSrc(None, None, self.eventlist, self.logger, 2)
        src2._ssthresh = 5000
        sink2 = MonitoredTcpSink(self.logger, 2)
        
        # 路由配置
        route_out2 = Route()
        route_out2.push_back(self.components['pqueue2'])
        route_out2.push_back(self.components['queue2'])
        route_out2.push_back(self.components['pipe2'])
        route_out2.push_back(sink2)
        
        route_back2 = Route()
        route_back2.push_back(self.components['pipe2'])
        route_back2.push_back(src2)
        
        # 连接
        self.mptcp_src.addSubflow(src2)
        self.mptcp_sink.addSubflow(sink2)
        src2.connect(route_out2, route_back2, sink2, ms_to_ps(random.random() * 50))
        self.rtx_scanner.registerTcp(src2)
        
        self.tcp_sources.append(src2)
        self.tcp_sinks.append(sink2)
        
        # 连接MPTCP
        self.mptcp_src.connect(self.mptcp_sink)
        
    def collect_state(self) -> Dict:
        """收集当前网络状态"""
        state = {}
        
        if len(self.tcp_sources) > 0 and len(self.tcp_sinks) > 0:
            # 路径1
            src1, sink1 = self.tcp_sources[0], self.tcp_sinks[0]
            state['path1'] = {
                'sent': src1.packets_sent,
                'acks': sink1.acks_sent,
                'cwnd': src1._cwnd,
                'ssthresh': src1._ssthresh
            }
            
        if len(self.tcp_sources) > 1 and len(self.tcp_sinks) > 1:
            # 路径2
            src2, sink2 = self.tcp_sources[1], self.tcp_sinks[1]
            state['path2'] = {
                'sent': src2.packets_sent,
                'acks': sink2.acks_sent,
                'cwnd': src2._cwnd,
                'ssthresh': src2._ssthresh
            }
            
        return state
        
    def run(self):
        """运行仿真"""
        print(f"\n开始MPTCP仿真 (时长: {self.duration}秒)")
        print(f"路径1: 3G网络, {self.path1_rate}pkt/s, RTT={self.path1_rtt}ms")
        print(f"路径2: WiFi网络, {self.path2_rate}pkt/s, RTT={self.path2_rtt}ms")
        print(f"接收窗口: {self.rwnd}包")
        print("查看 mptcp_simple.log 了解详细过程\n")
        
        # 设置网络
        self.create_network()
        self.create_mptcp()
        self.create_subflows()
        
        # 运行事件循环
        start_time = time.time()
        event_count = 0
        last_log_time = 0
        log_interval = sec_to_ps(5)  # 每5秒记录一次状态
        
        while self.eventlist.do_next_event():
            event_count += 1
            current_time = self.eventlist.now()
            
            # 定期记录状态
            if current_time - last_log_time >= log_interval:
                state = self.collect_state()
                self.logger.log_state(current_time, state)
                last_log_time = current_time
                
                # 显示进度
                progress = ps_to_sec(current_time) / self.duration * 100
                print(f"进度: {progress:.0f}%")
                
        # 最终统计
        end_time = time.time()
        final_state = self.collect_state()
        
        print(f"\n仿真完成!")
        print(f"执行时间: {end_time - start_time:.2f}秒")
        print(f"总事件数: {event_count}")
        
        # 显示最终统计
        if 'path1' in final_state:
            p1 = final_state['path1']
            print(f"\n路径1 (3G): 发送={p1['sent']}包, ACK={p1['acks']}包")
            
        if 'path2' in final_state:
            p2 = final_state['path2']
            print(f"路径2 (WiFi): 发送={p2['sent']}包, ACK={p2['acks']}包")
            
        # 关闭日志
        self.logger.close()


def main():
    """主函数"""
    # 可以通过命令行参数调整
    duration = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    rwnd = int(sys.argv[2]) if len(sys.argv) > 2 else None
    
    # 运行仿真
    sim = MptcpSimulation(duration, rwnd)
    sim.run()


if __name__ == "__main__":
    main()