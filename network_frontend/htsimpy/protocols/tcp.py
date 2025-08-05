"""
TCP Protocol Implementation

对应文件: tcp.h/cpp
功能: TCP协议实现，包括源端和接收端

主要类:
- TcpSrc: TCP源端，对应C++的TcpSrc
- TcpSink: TCP接收端，对应C++的TcpSink
- TcpRtxTimerScanner: TCP重传定时器扫描器

C++对应关系:
- TcpSrc::TcpSrc() -> TcpSrc.__init__()
- TcpSrc::connect() -> TcpSrc.connect()
- TcpSrc::receivePacket() -> TcpSrc.receive_packet()
- TcpSink::TcpSink() -> TcpSink.__init__()
- TcpSink::receivePacket() -> TcpSink.receive_packet()
"""

from typing import Optional, List, TYPE_CHECKING
from ..core.network import PacketSink, PacketFlow, DataReceiver, Packet
from ..core.eventlist import EventSource
from ..core.route import Route
from ..packets.tcp_packet import TcpPacket, TcpAck
from ..core.logger.traffic import TrafficLogger
from ..core.logger.tcp import TcpLogger
import sys

if TYPE_CHECKING:
    from .multipath_tcp import MultipathTcpSrc, MultipathTcpSink

# 常量定义 - 对应 C++ tcp.h 中的宏定义
TIME_INF = 0
KILL_THRESHOLD = 5
MODEL_RECEIVE_WINDOW = True  # 对应 C++ #define MODEL_RECEIVE_WINDOW 1


class TcpSrc(PacketSink, EventSource):
    """
    TCP源端 - 对应 tcp.h/cpp 中的 TcpSrc 类
    
    实现TCP协议的发送端功能，完全按照 C++ 版本复现
    """
    
    def __init__(self, logger, pktlogger, eventlist):
        """
        初始化TCP源端 - 对应 C++ TcpSrc::TcpSrc()
        
        Args:
            logger: TCP日志记录器
            pktlogger: 流量日志记录器
            eventlist: 事件调度器
        """
        EventSource.__init__(self, eventlist, "tcp")
        PacketSink.__init__(self)
        
        # 对应 C++ 成员变量初始化
        self._logger = logger
        self._flow = PacketFlow(pktlogger)
        
        # 数据包相关 - 对应 C++ Packet::data_packet_size()
        self._mss = Packet.data_packet_size()  # 对应 C++ _mss = Packet::data_packet_size()
        self._maxcwnd = 0xffffffff  # 对应 C++ 200*_mss 或 0xffffffff
        
        # 序列号和确认号 - 对应 C++ TcpSrc 序列号成员
        self._highest_sent = 0  # uint64_t _highest_sent (seqno is in bytes)
        self._packets_sent = 0  # uint64_t _packets_sent
        self._last_acked = 0   # uint64_t _last_acked
        
        # 拥塞控制变量 - 对应 C++ TcpSrc 拥塞控制成员
        self._cwnd = 10 * self._mss      # uint32_t _cwnd
        self._ssthresh = 100 * self._mss # uint32_t _ssthresh
        self._dupacks = 0                # uint16_t _dupacks
        self._unacked = 0                # uint32_t _unacked
        self._effcwnd = 0                # uint32_t _effcwnd
        
        # RTT和重传相关 - 对应 C++ TcpSrc RTT成员
        self._rtt = 0                         # simtime_picosec _rtt
        self._rto = self.time_from_ms(3000)   # simtime_picosec _rto
        self._mdev = 0                        # simtime_picosec _mdev
        self._base_rtt = TIME_INF             # simtime_picosec _base_rtt
        self._rtt_avg = self.time_from_ms(0)  # simtime_picosec _rtt_avg
        self._rtt_cum = self.time_from_ms(0)  # simtime_picosec _rtt_cum
        
        # 状态变量 - 对应 C++ TcpSrc 状态成员
        self._established = False    # bool _established
        self._in_fast_recovery = False # bool _in_fast_recovery
        self._cap = 0               # int _cap
        self._app_limited = -1      # int32_t _app_limited
        self._sawtooth = 0          # int _sawtooth
        
        # 流量控制 - 对应 C++ TcpSrc 流量控制成员
        self._flow_size = (1 << 63) # uint64_t _flow_size
        self._recoverq = 0          # uint64_t _recoverq
        self._drops = 0             # uint32_t _drops
        
        # 连接相关 - 对应 C++ TcpSrc 连接成员
        self._sink = None           # TcpSink* _sink
        self._route = None          # const Route* _route
        self._dst = -1              # int _dst
        
        # MPTCP相关 - 对应 C++ TcpSrc MPTCP成员
        self._mSrc = None           # MultipathTcpSrc* _mSrc
        self._subflow_id = -1       # int _subflow_id
        
        # RFC2988重传定时器 - 对应 C++ TcpSrc 定时器成员
        self._RFC2988_RTO_timeout = TIME_INF  # simtime_picosec _RFC2988_RTO_timeout
        self._rtx_timeout_pending = False     # bool _rtx_timeout_pending
        self._last_ping = TIME_INF            # simtime_picosec _last_ping
        
        # 路由替换相关 - 对应 C++ TcpSrc 路由成员
        self._old_route = None                      # const Route* _old_route
        self._last_packet_with_old_route = 0        # uint64_t _last_packet_with_old_route
        
        # 节点名称 - 对应 C++ TcpSrc::nodename()
        self._nodename = "tcpsrc"
        
        # 对应 C++ #ifdef PACKET_SCATTER
        self._crt_path = 0              # uint16_t _crt_path
        self.DUPACK_TH = 3              # uint16_t DUPACK_TH
        self._paths = None              # vector<const Route*>* _paths
        
    @staticmethod
    def time_from_ms(ms: int) -> int:
        """毫秒转换为皮秒 - 对应 C++ timeFromMs()"""
        return ms * 1_000_000_000
        
    @staticmethod
    def time_from_sec(sec: float) -> int:
        """秒转换为皮秒 - 对应 C++ timeFromSec()"""
        return int(sec * 1_000_000_000_000)
    
    def nodename(self) -> str:
        """
        获取节点名称 - 对应 C++ TcpSrc::nodename()
        
        Returns:
            节点名称字符串
        """
        return self._nodename
    
    def setName(self, name: str) -> None:
        """设置节点名称"""
        self._nodename = name
    
    def get_id(self) -> int:
        """获取事件源ID"""
        return super().get_id()
    
    def str(self) -> str:
        """获取字符串表示"""
        return str(self.get_id())
    
    def connect(self, routeout: Route, routeback: Route, sink: 'TcpSink', starttime: int = 0) -> None:
        """
        建立TCP连接 - 对应 C++ TcpSrc::connect()
        
        Args:
            routeout: 前向路由
            routeback: 返回路由  
            sink: TCP接收端
            starttime: 连接开始时间
        """
        self._route = routeout
        assert self._route is not None
        
        self._sink = sink
        self._flow.set_id(self.get_id())  # 设置流ID
        
        # 连接接收端
        sink.connect(self, routeback)
        
        # 调度连接开始事件 - 使用相对时间调度
        if starttime > 0:
            self._eventlist.source_is_pending_rel(self, starttime)
        else:
            # 立即开始
            self._eventlist.source_is_pending_rel(self, 0)
    
    def startflow(self) -> None:
        """
        开始流传输 - 对应 C++ TcpSrc::startflow()
        """
        self._unacked = self._cwnd
        self._established = False
        self.send_packets()
    
    def joinMultipathConnection(self, multipathSrc) -> None:
        """
        加入多路径TCP连接 - 对应 C++ TcpSrc::joinMultipathConnection()
        
        Args:
            multipathSrc: MPTCP源端对象
        """
        self._mSrc = multipathSrc
    
    def set_ssthresh(self, s: int) -> None:
        """设置慢启动阈值 - 对应 C++ TcpSrc::set_ssthresh()"""
        self._ssthresh = s
    
    def set_cwnd(self, s: int) -> None:
        """设置拥塞窗口 - 对应 C++ TcpSrc::set_cwnd()"""
        self._cwnd = s
    
    def set_cap(self, cap: int) -> None:
        """设置容量限制 - 对应 C++ TcpSrc::set_cap()"""
        self._cap = cap
    
    def set_dst(self, d: int) -> None:
        """设置目标地址 - 对应 C++ TcpSrc::set_dst()"""
        self._dst = d
    
    def get_dst(self) -> int:
        """获取目标地址 - 对应 C++ TcpSrc::get_dst()"""
        return self._dst
    
    def set_flowsize(self, flow_size_in_bytes: int) -> None:
        """
        设置流大小 - 对应 C++ TcpSrc::set_flowsize()
        
        Args:
            flow_size_in_bytes: 流大小（字节）
        """
        self._flow_size = flow_size_in_bytes + self._mss
    
    def getFlowId(self) -> int:
        """获取流ID - 对应 C++ TcpSrc::getFlowId()"""
        return self._flow.flow_id()
    
    def effective_window(self) -> int:
        """
        获取有效窗口大小 - 对应 C++ TcpSrc::effective_window()
        
        Returns:
            有效窗口大小
        """
        return self._ssthresh if self._in_fast_recovery else self._cwnd
    
    def receivePacket(self, pkt) -> None:
        """
        接收数据包（ACK等）- 对应 C++ TcpSrc::receivePacket()
        
        Args:
            pkt: 接收到的数据包
        """
        if not isinstance(pkt, TcpAck):
            return
        
        ts = pkt.ts()
        seqno = pkt.ackno()
        
        # 记录流量日志
        pkt.flow().logTraffic(pkt, self, TrafficLogger.TrafficEvent.PKT_RCVDESTROY)
        
        # 释放数据包
        pkt.free()
        
        if seqno < self._last_acked:
            return
        
        # 处理SYN/ACK
        if seqno == 1:
            self._established = True
        elif seqno > 1 and not self._established:
            pass  # Should be _established
        
        # 计算RTT - 对应 C++ TcpSrc::receivePacket() RTT计算
        m = self._eventlist.now() - ts
        
        if m != 0:
            if self._rtt > 0:
                abs_diff = abs(m - self._rtt)
                self._mdev = 3 * self._mdev // 4 + abs_diff // 4
                self._rtt = 7 * self._rtt // 8 + m // 8
                self._rto = self._rtt + 4 * self._mdev
            else:
                self._rtt = m
                self._mdev = m // 2
                self._rto = self._rtt + 4 * self._mdev
            
            if self._base_rtt == TIME_INF or self._base_rtt > m:
                self._base_rtt = m
        
        # 限制RTO最小值
        if self._rto < self.time_from_sec(0.25):
            self._rto = self.time_from_sec(0.25)
        
        # 检查流是否完成
        if seqno >= self._flow_size:
            pass  # Flow finished
        
        # 处理新的ACK
        if seqno > self._last_acked:
            if self._old_route and seqno >= self._last_packet_with_old_route:
                self._old_route = None
            
            self._RFC2988_RTO_timeout = self._eventlist.now() + self._rto
            self._last_ping = self._eventlist.now()
            
            if seqno >= self._highest_sent:
                self._highest_sent = seqno
                self._RFC2988_RTO_timeout = TIME_INF
                self._last_ping = TIME_INF
            
            if not self._in_fast_recovery:
                # 正常ACK处理
                self._last_acked = seqno
                self._dupacks = 0
                self.inflate_window()
                
                if self._cwnd > self._maxcwnd:
                    self._cwnd = self._maxcwnd
                
                self._unacked = self._cwnd
                self._effcwnd = self._cwnd
                
                if self._logger:
                    self._logger.logTcp(self, "TCP_RCV")
                
                self.send_packets()
                return
            
            # 快速恢复中的ACK处理
            if seqno >= self._recoverq:
                # 退出快速恢复
                flightsize = self._highest_sent - seqno
                self._cwnd = min(self._ssthresh, flightsize + self._mss)
                self._unacked = self._cwnd
                self._effcwnd = self._cwnd
                self._last_acked = seqno
                self._dupacks = 0
                self._in_fast_recovery = False
                
                if self._logger:
                    self._logger.logTcp(self, "TCP_RCV_FR_END")
                
                self.send_packets()
                return
            
            # 快速恢复中的部分ACK
            new_data = seqno - self._last_acked
            self._last_acked = seqno
            if new_data < self._cwnd:
                self._cwnd -= new_data
            else:
                self._cwnd = 0
            self._cwnd += self._mss
            
            if self._logger:
                self._logger.logTcp(self, "TCP_RCV_FR")
            
            self.retransmit_packet()
            self.send_packets()
            return
        
        # 处理重复ACK
        if self._in_fast_recovery:
            self._cwnd += self._mss
            if self._cwnd > self._maxcwnd:
                self._cwnd = self._maxcwnd
            
            self._unacked = min(self._ssthresh, self._highest_sent - self._recoverq + self._mss)
            if self._last_acked + self._cwnd >= self._highest_sent + self._mss:
                self._effcwnd = self._unacked
            
            if self._logger:
                self._logger.logTcp(self, "TCP_RCV_DUP_FR")
            
            self.send_packets()
            return
        
        # 重复ACK计数
        self._dupacks += 1
        
        # 对应 C++ if (_dupacks!=DUPACK_TH)
        if self._dupacks != self.DUPACK_TH:
            if self._logger:
                self._logger.logTcp(self, "TCP_RCV_DUP")
            self.send_packets()
            return
        
        # DUPACK_TH个重复ACK - 开始快速恢复
        if self._last_acked < self._recoverq:
            if self._logger:
                self._logger.logTcp(self, "TCP_RCV_3DUPNOFR")
            return
        
        # 开始快速恢复
        self._drops += 1
        self.deflate_window()
        
        if self._sawtooth > 0:
            self._rtt_avg = self._rtt_cum // self._sawtooth
        else:
            self._rtt_avg = self.time_from_ms(0)
        
        self._sawtooth = 0
        self._rtt_cum = self.time_from_ms(0)
        
        self.retransmit_packet()
        self._cwnd = self._ssthresh + 3 * self._mss
        self._unacked = self._ssthresh
        self._effcwnd = 0
        self._in_fast_recovery = True
        self._recoverq = self._highest_sent
        
        if self._logger:
            self._logger.logTcp(self, "TCP_RCV_DUP_FASTXMIT")
    
    def deflate_window(self) -> None:
        """
        缩小拥塞窗口 - 对应 C++ TcpSrc::deflate_window()
        """
        if self._mSrc is None:
            self._ssthresh = max(self._cwnd // 2, 2 * self._mss)
        else:
            self._ssthresh = self._mSrc.deflate_window(self._cwnd, self._mss)
    
    def inflate_window(self) -> None:
        """
        增大拥塞窗口 - 对应 C++ TcpSrc::inflate_window()
        """
        newly_acked = (self._last_acked + self._cwnd) - self._highest_sent
        
        # 保守处理
        if newly_acked > self._mss:
            newly_acked = self._mss
        if newly_acked < 0:
            return
        
        if self._cwnd < self._ssthresh:
            # 慢启动
            increase = min(self._ssthresh - self._cwnd, newly_acked)
            self._cwnd += increase
            newly_acked -= increase
        else:
            # 拥塞避免
            pkts = self._cwnd // self._mss
            
            # 计算队列分数
            if self._rtt > 0:
                queued_fraction = 1 - (self._base_rtt / self._rtt)
            else:
                queued_fraction = 0
            
            if queued_fraction >= 0.5 and self._mSrc and self._cap:
                return
            
            if self._mSrc is None:
                self._cwnd += (newly_acked * self._mss) // self._cwnd
            else:
                self._cwnd = self._mSrc.inflate_window(self._cwnd, newly_acked, self._mss)
            
            if pkts != self._cwnd // self._mss:
                self._rtt_cum += self._rtt
                self._sawtooth += 1
    
    def send_packets(self) -> None:
        """
        发送数据包 - 对应 C++ TcpSrc::send_packets()
        """
        c = self._cwnd
        
        if not self._established:
            # 发送SYN包 - 对应C++ TcpPacket::new_syn_pkt
            if self._route and len(self._route) > 0:
                p = TcpPacket.new_syn_pkt(self._flow, self._route, 1, 1)  # 对应 C++ new_syn_pkt(_flow, *_route, 1, 1)
                if self._dst >= 0:
                    p.set_dst(self._dst)
                p.set_ts(self._eventlist.now())
                self._highest_sent = 1
                
                p.sendOn()  # 实际发送SYN包
                
                if self._RFC2988_RTO_timeout == TIME_INF:
                    self._RFC2988_RTO_timeout = self._eventlist.now() + self._rto
            return
        
        # 应用限速处理
        if self._app_limited >= 0 and self._rtt > 0:
            d = self._app_limited * self._rtt // 1000000000
            if c > d:
                c = d
            if c == 0:
                pass  # 可以设置_RFC2988_RTO_timeout = TIME_INF
        
        # 发送数据包循环
        while (self._last_acked + c >= self._highest_sent + self._mss and 
               self._highest_sent <= self._flow_size + 1):
            
            # MPTCP数据序列控制 - 对应 C++ MODEL_RECEIVE_WINDOW部分
            data_seq = 0
            if self._mSrc:
                # 对应 C++ if (_mSrc && !_mSrc->getDataSeq(&data_seq,this)) break;
                success, seq = self._mSrc.getDataSeq(self)
                if not success:
                    break  # 没有更多数据可发送
                data_seq = seq
            
            # 创建并发送实际的数据包 - 对应C++ TcpPacket::newpkt
            if self._route and len(self._route) > 0:
                p = TcpPacket.newpkt(self._flow, self._route, self._highest_sent + 1, data_seq, self._mss)
                if self._dst >= 0:
                    p.set_dst(self._dst)
                p.set_ts(self._eventlist.now())
                
                pass  # 删除调试输出
                p.sendOn()  # 实际发送数据包
                
                self._highest_sent += self._mss
                self._packets_sent += self._mss
                
                if self._RFC2988_RTO_timeout == TIME_INF:
                    self._RFC2988_RTO_timeout = self._eventlist.now() + self._rto
            else:
                break  # 没有路由就退出循环
    
    def retransmit_packet(self) -> None:
        """
        重传数据包 - 对应 C++ TcpSrc::retransmit_packet()
        """
        # 输出重传信息 - 对应 C++ cout << "At " << now...
        now = self._eventlist.now()
        print(f"At {now//1000000000} RTO {self._rto//1000000000} MDEV {self._mdev//1000000000} "
              f"RTT {self._rtt//1000000000} SEQ {self._last_acked // self._mss} HSENT {self._highest_sent} "
              f"CWND {self._cwnd//self._mss} FAST RECOVERY? {1 if self._in_fast_recovery else 0} "
              f"Flow ID {self.nodename()}")
        
        if not self._established:
            assert self._highest_sent == 1
            # 重传SYN包
            if self._route and len(self._route) > 0:
                p = TcpPacket.new_syn_pkt(self._flow, self._route, 1, 1)  # 对应 C++ new_syn_pkt(_flow, *_route, 1, 1)
                if self._dst >= 0:
                    p.set_dst(self._dst)
                p.set_ts(self._eventlist.now())
                
                pass  # 删除调试输出
                p.sendOn()
            return
        
        data_seq = 0  # 简化版本暂不处理 MODEL_RECEIVE_WINDOW
        
        # 重传数据包
        if self._route and len(self._route) > 0:
            p = TcpPacket.newpkt(self._flow, self._route, self._last_acked + 1, data_seq, self._mss)
            if self._dst >= 0:
                p.set_dst(self._dst)
            p.set_ts(self._eventlist.now())
            
            pass  # 删除调试输出
            p.sendOn()
            
            self._packets_sent += self._mss
            
            if self._RFC2988_RTO_timeout == TIME_INF:
                self._RFC2988_RTO_timeout = self._eventlist.now() + self._rto
    
    def rtx_timer_hook(self, now: int, period: int) -> None:
        """
        重传定时器钩子 - 对应 C++ TcpSrc::rtx_timer_hook()
        
        Args:
            now: 当前时间
            period: 扫描周期
        """
        if now <= self._RFC2988_RTO_timeout or self._RFC2988_RTO_timeout == TIME_INF:
            return
        
        if self._highest_sent == 0:
            return
        
        pass  # 删除调试输出
        
        if not self._rtx_timeout_pending:
            self._rtx_timeout_pending = True
            
            # 计算定时器差异
            too_late = now - self._RFC2988_RTO_timeout
            
            # 防止溢出
            while too_late > period:
                too_late >>= 1
            
            # 计算重传偏移
            rtx_off = (period - too_late) // 200
            
            self._eventlist.source_is_pending_rel(self, rtx_off)
            
            # 重置RTO定时器 - RFC 2988 5.5 & 5.6
            self._rto *= 2
            self._RFC2988_RTO_timeout = now + self._rto
    
    def do_next_event(self) -> None:
        """
        处理定时器事件 - 对应 C++ TcpSrc::doNextEvent()
        """
        if self._rtx_timeout_pending:
            self._rtx_timeout_pending = False
            
            if self._logger:
                self._logger.logTcp(self, "TCP_TIMEOUT")
            
            if self._in_fast_recovery:
                flightsize = self._highest_sent - self._last_acked
                self._cwnd = min(self._ssthresh, flightsize + self._mss)
            
            self.deflate_window()
            
            self._cwnd = self._mss
            self._unacked = self._cwnd
            self._effcwnd = self._cwnd
            self._in_fast_recovery = False
            self._recoverq = self._highest_sent
            
            if self._established:
                self._highest_sent = self._last_acked + self._mss
            
            self._dupacks = 0
            
            self.retransmit_packet()
            
            if self._sawtooth > 0:
                self._rtt_avg = self._rtt_cum // self._sawtooth
            else:
                self._rtt_avg = self.time_from_ms(0)
            
            self._sawtooth = 0
            self._rtt_cum = self.time_from_ms(0)
            
            if self._mSrc:
                self._mSrc.window_changed()
        else:
            # 对应 C++ else { startflow(); }
            self.startflow()
    
    def replace_route(self, newroute: Route) -> None:
        """
        替换路由 - 对应 C++ TcpSrc::replace_route()
        
        Args:
            newroute: 新路由
        """
        if self._route:
            if self._route == newroute:
                return
            self._old_route = self._route
        self._route = newroute
        self._last_packet_with_old_route = self._highest_sent
    
    def set_app_limit(self, pktps: int) -> None:
        """
        设置应用层速率限制 - 对应 C++ TcpSrc::set_app_limit()
        
        Args:
            pktps: 每秒数据包数
        """
        if self._app_limited == 0 and pktps:
            self._cwnd = self._mss
        self._ssthresh = 100 * self._mss
        self._app_limited = pktps
        self.send_packets()
    
    def set_paths(self, paths: List[Route]) -> None:
        """
        设置多路径 - 对应 C++ TcpSrc::set_paths() (ifdef PACKET_SCATTER)
        
        Args:
            paths: 路由列表
        """
        self._paths = []
        for route in paths:
            t = Route(route)
            t.push_back(self._sink)
            self._paths.append(t)
        self.DUPACK_TH = 3 + len(paths)


class TcpSink(PacketSink, DataReceiver):
    """
    TCP接收端 - 对应 tcp.h/cpp 中的 TcpSink 类
    
    实现TCP协议的接收端功能，完全按照 C++ 版本复现
    """
    
    def __init__(self):
        """
        初始化TCP接收端 - 对应 C++ TcpSink::TcpSink()
        """
        PacketSink.__init__(self)
        DataReceiver.__init__(self, "TCPsink")
        
        # 对应 C++ TcpSink 成员变量
        self._cumulative_ack = 0  # TcpAck::seq_t _cumulative_ack
        self._packets = 0         # uint64_t _packets
        self._drops = 0           # uint32_t _drops
        self._src = None          # TcpSrc* _src
        self._route = None        # const Route* _route
        self._received = []       # list<TcpAck::seq_t> _received
        self._dst = -1            # int _dst
        self._crt_path = 0        # uint16_t _crt_path
        
        # MPTCP相关 - 对应 C++ TcpSink MPTCP成圱
        self._mSink = None        # MultipathTcpSink* _mSink
        
        # 节点名称 - 对应 C++ TcpSink::nodename()
        self._nodename = "tcpsink"
        
        # 对应 C++ #ifdef PACKET_SCATTER
        self._paths = None  # vector<const Route*>* _paths
    
    def nodename(self) -> str:
        """
        获取节点名称 - 对应 C++ TcpSink::nodename()
        
        Returns:
            节点名称字符串
        """
        return self._nodename
    
    def setName(self, name: str) -> None:
        """设置节点名称"""
        self._nodename = name
    
    def set_dst(self, d: int) -> None:
        """设置目标地址 - 对应 C++ TcpSink::set_dst()"""
        self._dst = d
    
    def get_dst(self) -> int:
        """获取目标地址 - 对应 C++ TcpSink::get_dst()"""
        return self._dst
    
    def joinMultipathConnection(self, multipathSink) -> None:
        """
        加入多路径TCP连接 - 对应 C++ TcpSink::joinMultipathConnection()
        
        Args:
            multipathSink: MPTCP接收端对象
        """
        self._mSink = multipathSink
    
    def connect(self, src: TcpSrc, route: Route) -> None:
        """
        连接到TCP源端 - 对应 C++ TcpSink::connect()
        
        Args:
            src: TCP源端
            route: 返回路由
        """
        self._src = src
        self._route = route
        self._cumulative_ack = 0
        self._drops = 0
    
    def set_route(self, route: Route) -> None:
        """
        设置路由 - 用于设置返回路由
        
        Args:
            route: 路由对象
        """
        self._route = route
    
    def cumulative_ack(self) -> int:
        """
        获取累积确认号 - 对应 C++ TcpSink::cumulative_ack()
        
        Returns:
            累积确认号
        """
        return self._cumulative_ack + len(self._received) * 1000
    
    def data_ack(self) -> int:
        """获取数据确认号"""
        return self._cumulative_ack
    
    def drops(self) -> int:
        """
        获取丢包数 - 对应 C++ TcpSink::drops()
        
        Returns:
            丢包数
        """
        return self._src._drops if self._src else self._drops
    
    def receivePacket(self, pkt) -> None:
        """
        接收数据包 - 对应 C++ TcpSink::receivePacket()
        
        Args:
            pkt: 接收到的数据包
        """
        if not isinstance(pkt, TcpPacket):
            return
        
        seqno = pkt.seqno()
        ts = pkt.ts()
        marked = (pkt.flags() & 0x08) != 0  # ECN_CE标志
        
        # C++中没有特殊处理SYN包，直接继续正常处理
        
        # MPTCP处理
        if self._mSink is not None:
            self._mSink.receive_packet(pkt)
        
        size = pkt.size()
        # 记录流量日志
        pkt.flow().logTraffic(pkt, self, TrafficLogger.TrafficEvent.PKT_RCVDESTROY)
        pkt.free()
        
        self._packets += size
        
        if seqno == self._cumulative_ack + 1:
            # 期望的下一个序列号
            self._cumulative_ack = seqno + size - 1
            
            # 检查是否有额外的已接收包可以确认
            while (len(self._received) > 0 and 
                self._received[0] == self._cumulative_ack + 1):
                self._received.pop(0)
                self._cumulative_ack += size
        
        elif seqno < self._cumulative_ack + 1:
            # 旧的数据包，忽略
            pass
        
        else:
            # 乱序数据包
            if len(self._received) == 0:
                self._received.append(seqno)
                # 在此模拟器中，这是一个丢包（没有重排序）
                self._drops += (1000 + seqno - self._cumulative_ack - 1) // 1000
            elif seqno > self._received[-1]:
                # 最常见情况
                self._received.append(seqno)
            else:
                # 不常见情况 - 填补空洞
                inserted = False
                for i in range(len(self._received)):
                    if seqno == self._received[i]:
                        break  # 重复重传
                    if seqno < self._received[i]:
                        self._received.insert(i, seqno)
                        inserted = True
                        break
                if not inserted:
                    self._received.append(seqno)
        
        self.send_ack(ts, marked)
    
    def send_ack(self, ts: int, marked: bool) -> None:
        """
        发送ACK - 对应 C++ TcpSink::send_ack()
        
        Args:
            ts: 时间戳
            marked: 是否标记ECN
        """
        rt = self._route
        
        # 对应 C++ #ifdef PACKET_SCATTER
        if self._paths:
            # 对应 C++ #ifdef RANDOM_PATH
            # self._crt_path = random.randint(0, len(self._paths)-1)
            rt = self._paths[self._crt_path]
            self._crt_path = (self._crt_path + 1) % len(self._paths)
        
        data_ack_value = self._mSink.data_ack() if self._mSink else 0
        
        # 发送实际的ACK包 - 对应C++ TcpAck::newpkt
        if rt and len(rt) > 0:
            ack = TcpAck.newpkt(self._src._flow, rt, 0, self._cumulative_ack, data_ack_value)
            
            if self._dst >= 0:
                ack.set_dst(self._dst)
            
            ack.flow().logTraffic(ack, self, TrafficLogger.TrafficEvent.PKT_CREATESEND)
            ack.set_ts(ts)
            
            if marked:
                ack.set_flags(0x40)  # ECN_ECHO
            else:
                ack.set_flags(0)
            
            ack.sendOn()  # 实际发送ACK包
    
    def set_paths(self, paths: List[Route]) -> None:
        """
        设置多路径 - 对应 C++ TcpSink::set_paths() (ifdef PACKET_SCATTER)
        
        Args:
            paths: 路由列表
        """
        self._paths = []
        for route in paths:
            t = Route(route)
            t.push_back(self._src)
            self._paths.append(t)


class TcpRtxTimerScanner(EventSource):
    """
    TCP重传定时器扫描器 - 对应 tcp.h/cpp 中的 TcpRtxTimerScanner 类
    
    定期扫描所有TCP源的重传定时器
    """
    
    def __init__(self, scanPeriod: int, eventlist):
        """
        初始化重传定时器扫描器 - 对应 C++ TcpRtxTimerScanner::TcpRtxTimerScanner()
        
        Args:
            scanPeriod: 扫描周期
            eventlist: 事件调度器
        """
        EventSource.__init__(self, eventlist, "RtxScanner")
        self._scanPeriod = scanPeriod
        self._tcps = []  # list<TcpSrc*> _tcps
        
        # 调度第一次扫描
        self._eventlist.source_is_pending_rel(self, scanPeriod)
    
    def registerTcp(self, tcpsrc: TcpSrc) -> None:
        """
        注册TCP源 - 对应 C++ TcpRtxTimerScanner::registerTcp()
        
        Args:
            tcpsrc: TCP源端对象
        """
        self._tcps.append(tcpsrc)
    
    def do_next_event(self) -> None:
        """
        扫描所有TCP源的重传定时器 - 对应 C++ TcpRtxTimerScanner::doNextEvent()
        """
        now = self._eventlist.now()
        
        for tcpsrc in self._tcps:
            tcpsrc.rtx_timer_hook(now, self._scanPeriod)
        
        # 调度下一次扫描
        self._eventlist.source_is_pending_rel(self, self._scanPeriod)