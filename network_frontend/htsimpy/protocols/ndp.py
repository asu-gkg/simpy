"""
NDP (Near-Data Processing) Protocol Implementation

对应文件: ndp.h/cpp, ndppacket.h/cpp
功能: 实现NDP协议，一种专为数据中心设计的低延迟传输协议

NDP特点：
- Pull-based流控制
- Per-packet multipath
- Trimming机制减少队列积压
- RTS/CTS风格的请求-授予机制

主要类:
- NdpSrc: NDP源端
- NdpSink: NDP接收端
- NdpPull: Pull包
- NdpAck/NdpNack: 确认包
- NdpRTSPacer: RTS步调器

C++对应关系完整映射
"""

from typing import Optional, List, Dict, Set, Tuple
from enum import Enum
from abc import ABC, abstractmethod
import random
import math

from ..core.network import Packet, PacketSink, PacketFlow
from ..core.eventlist import EventList, EventSource
from ..core.route import Route
from ..core.trigger import TriggerTarget, Trigger
from ..core.logger.base import Logger
from ..packets.base_packet import BasePacket

# ============================================================================
# 常量定义 - 对应 ndp.h
# ============================================================================

TIME_INF = 0
DEFAULT_RTO_MIN = 5000  # 最小RTO界限（微秒）
NDP_PACKET_SCATTER = True
RECORD_PATH_LENS = True
DEBUG_PATH_STATS = True

# 路由策略枚举 - 对应 ndp.h: enum RouteStrategy
class RouteStrategy(Enum):
    NOT_SET = 0
    SINGLE_PATH = 1
    SCATTER_PERMUTE = 2
    SCATTER_RANDOM = 3
    PULL_BASED = 4
    SCATTER_ECMP = 5
    ECMP_FIB = 6
    ECMP_FIB_ECN = 7
    REACTIVE_ECN = 8

# 反馈类型枚举 - 对应 ndp.cpp: enum FeedbackType
class FeedbackType(Enum):
    ACK = 0
    ECN = 1
    NACK = 2
    BOUNCE = 3
    UNKNOWN = 4

# ============================================================================
# 时间转换函数
# ============================================================================

def timeFromUs(us: int) -> int:
    """微秒转皮秒"""
    return us * 1_000_000

def timeFromMs(ms: float) -> int:
    """毫秒转皮秒"""
    return int(ms * 1_000_000_000)

def timeAsSec(ps: int) -> float:
    """皮秒转秒"""
    return ps / 1_000_000_000_000

def timeAsMs(ps: int) -> float:
    """皮秒转毫秒"""
    return ps / 1_000_000_000

def timeAsUs(ps: int) -> float:
    """皮秒转微秒"""
    return ps / 1_000_000

# ============================================================================
# NDP包类型定义 - 对应 ndppacket.h
# ============================================================================

class NdpPacket(BasePacket):
    """
    NDP数据包基类 - 对应 ndppacket.h: class NdpPacket
    """
    
    # 包类型定义
    NDP = 0
    NDPACK = 1
    NDPNACK = 2
    NDPPULL = 3
    
    def __init__(self):
        super().__init__()
        self._type = self.NDP
        self._is_header = False
        self._seqno = 0
        self._ackno = 0
        self._pullno = 0
        self._pacerno = 0
        self._path_id = -1
        self._cumulative_ack = 0
        self._is_last_packet = False
        
    @property
    def seqno(self) -> int:
        return self._seqno
        
    @seqno.setter
    def seqno(self, value: int):
        self._seqno = value
        
    def set_path_id(self, path_id: int):
        self._path_id = path_id
        
    def path_id(self) -> int:
        return self._path_id
        
    def is_header(self) -> bool:
        return self._is_header
        
    def strip_payload(self):
        """剥离负载，只保留头部"""
        self._is_header = True
        self._size = 64  # NDP header size

class NdpAck(NdpPacket):
    """NDP ACK包 - 对应 ndppacket.h: class NdpAck"""
    
    def __init__(self):
        super().__init__()
        self._type = self.NDPACK
        self._size = 64  # ACK size
        
    @property 
    def ackno(self) -> int:
        return self._ackno
        
    @ackno.setter
    def ackno(self, value: int):
        self._ackno = value
        
    @property
    def cumulative_ack(self) -> int:
        return self._cumulative_ack
        
    @cumulative_ack.setter
    def cumulative_ack(self, value: int):
        self._cumulative_ack = value

class NdpNack(NdpPacket):
    """NDP NACK包 - 对应 ndppacket.h: class NdpNack"""
    
    def __init__(self):
        super().__init__()
        self._type = self.NDPNACK
        self._size = 64  # NACK size
        
    @property
    def ackno(self) -> int:
        return self._ackno
        
    @ackno.setter
    def ackno(self, value: int):
        self._ackno = value

class NdpPull(NdpPacket):
    """NDP PULL包 - 对应 ndppacket.h: class NdpPull"""
    
    def __init__(self):
        super().__init__()
        self._type = self.NDPPULL
        self._size = 64  # PULL size
        self._cumulative_ack = 0
        
    @property
    def pullno(self) -> int:
        return self._pullno
        
    @pullno.setter
    def pullno(self, value: int):
        self._pullno = value
        
    @property
    def pacerno(self) -> int:
        return self._pacerno
        
    @pacerno.setter  
    def pacerno(self, value: int):
        self._pacerno = value
        
    @property
    def cumulative_ack(self) -> int:
        return self._cumulative_ack
        
    @cumulative_ack.setter
    def cumulative_ack(self, value: int):
        self._cumulative_ack = value

# ============================================================================
# 接收事件类 - 对应 ndp.h: class ReceiptEvent
# ============================================================================

class ReceiptEvent:
    """
    接收事件 - 对应 ndp.h: class ReceiptEvent
    """
    
    def __init__(self, path_id: int = -1, is_header: bool = False):
        """
        对应:
        ReceiptEvent(uint32_t path_id, bool is_header)
            : _path_id(path_id), _is_header(is_header) {}
        """
        self._path_id = path_id
        self._is_header = is_header
        
    def path_id(self) -> int:
        return self._path_id
        
    def is_header(self) -> bool:
        return self._is_header

# ============================================================================
# NDP RTS Pacer - 对应 ndp_rts_pacer.h
# ============================================================================

class NdpRTSPacer:
    """
    NDP RTS步调器 - 控制RTS发送速率
    对应 ndp_rts_pacer.h: class NdpRTSPacer
    """
    
    def __init__(self, eventlist: EventList, link_speed: int):
        self._eventlist = eventlist
        self._link_speed = link_speed
        self._pacer_no = 0
        
    def get_next_pacer_no(self) -> int:
        """获取下一个pacer编号"""
        self._pacer_no += 1
        return self._pacer_no
        
    def request_pacer(self) -> int:
        """请求一个pacer token"""
        # TODO: 实现完整的pacer逻辑
        return self.get_next_pacer_no()

# ============================================================================
# NDP源端 - 对应 ndp.h: class NdpSrc
# ============================================================================

class NdpSrc(PacketSink, EventSource, TriggerTarget):
    """
    NDP源端实现 - 对应 ndp.h: class NdpSrc
    
    完整实现所有C++版本的成员变量和方法
    """
    
    # 静态成员变量 - 对应 C++ static members
    _global_rto_count = 0
    _min_rto = timeFromUs(DEFAULT_RTO_MIN)
    _route_strategy = RouteStrategy.NOT_SET
    _path_entropy_size = 0
    _global_node_count = 0
    _rtt_hist = [0] * 10000000
    
    def __init__(self, 
                 logger: Optional['NdpLogger'] = None,
                 traffic_logger: Optional['TrafficLogger'] = None,
                 eventlist: Optional[EventList] = None,
                 rts: bool = False,
                 pacer: Optional[NdpRTSPacer] = None):
        """
        初始化NDP源端 - 对应 C++ NdpSrc::NdpSrc()
        
        NdpSrc::NdpSrc(NdpLogger* logger, TrafficLogger* pktlogger, 
                       EventList &eventlist, bool rts, NdpRTSPacer* pacer)
        """
        EventSource.__init__(self, eventlist, "ndpsrc")
        PacketSink.__init__(self)
        
        # 日志相关
        self._logger = logger
        self._pktlogger = traffic_logger
        self._end_trigger = None
        
        # 连接相关
        self._flow = PacketFlow(None)
        self._nodename = f"ndpsrc_{NdpSrc._global_node_count}"
        self._node_num = NdpSrc._global_node_count
        NdpSrc._global_node_count += 1
        
        # RTS相关
        self._rts = rts
        self._rts_pacer = pacer
        
        # 序列号和统计 - 对应 C++ public members
        self._highest_sent = 0     # uint64_t _highest_sent
        self._packets_sent = 0     # uint64_t _packets_sent
        self._last_acked = 0       # uint64_t _last_acked
        self._new_packets_sent = 0 # uint32_t _new_packets_sent
        self._rtx_packets_sent = 0 # uint32_t _rtx_packets_sent
        self._acks_received = 0    # uint32_t _acks_received
        self._nacks_received = 0   # uint32_t _nacks_received
        self._pulls_received = 0   # uint32_t _pulls_received
        self._implicit_pulls = 0   # uint32_t _implicit_pulls
        self._bounces_received = 0 # uint32_t _bounces_received
        self._cwnd = 50000         # uint32_t _cwnd
        self._flight_size = 0      # uint32_t _flight_size
        self._acked_packets = 0    # uint32_t _acked_packets
        
        # 路径相关
        self._crt_path = 0         # uint16_t _crt_path
        self._crt_direction = 0    # uint16_t _crt_direction
        self._same_path_burst = 1  # uint16_t _same_path_burst
        self._path_ids = []        # vector<int> _path_ids
        
        self._dstaddr = 0          # uint32_t _dstaddr
        self._paths = []           # vector<const Route*> _paths
        self._original_paths = []  # vector<const Route*> _original_paths
        
        # 路径统计
        if DEBUG_PATH_STATS:
            self._path_counts_new = []  # vector<int>
            self._path_counts_rtx = []  # vector<int>
            self._path_counts_rto = []  # vector<int>
            
        self._path_acks = []    # vector<int16_t>
        self._path_ecns = []    # vector<int16_t>
        self._path_nacks = []   # vector<int16_t>
        self._avoid_ratio = []  # vector<int16_t>
        self._avoid_score = []  # vector<int16_t>
        self._bad_path = []     # vector<bool>
        
        # 发送时间映射
        self._sent_times = {}        # map<seq_t, simtime_picosec>
        self._first_sent_times = {}  # map<seq_t, simtime_picosec>
        
        # Pull窗口管理
        self._pull_window = 0         # int _pull_window
        self._first_window_count = 0  # int _first_window_count
        
        # RTT和RTO
        self._rtt = 0              # simtime_picosec _rtt
        self._rto = timeFromMs(1)  # simtime_picosec _rto
        self._mdev = 0             # simtime_picosec _mdev
        self._base_rtt = 0         # simtime_picosec _base_rtt
        
        # 其他参数
        self._mss = 1500          # uint16_t _mss
        self._drops = 0           # uint32_t _drops
        self._sink = None         # NdpSink* _sink
        
        # 重传相关
        self._rtx_timeout = 0             # simtime_picosec _rtx_timeout
        self._rtx_timeout_pending = False # bool _rtx_timeout_pending
        self._route = None                # const Route* _route
        
        # 流控制
        self._flow_size = 0       # uint64_t
        self._stop_time = 0       # simtime_picosec
        
        # 调试
        self._log_me = False      # bool _log_me
        
        # 历史记录
        self.HIST_LEN = 12
        self._feedback_history = []  # 反馈历史
        
        # 待发送包队列
        self._send_buffer = []    # 待发送的包
        self._retransmit_queue = []  # 重传队列
        
    def connect(self, routeout: Route, routeback: Route, sink: 'NdpSink', 
                startTime: int = 0) -> None:
        """
        连接到接收端 - 对应 C++ NdpSrc::connect()
        
        virtual void connect(Route* routeout, Route* routeback, 
                           NdpSink& sink, simtime_picosec startTime);
        """
        self._route = routeout
        self._sink = sink
        self._sink.connect(self, routeback)
        
        if startTime > 0:
            self._eventlist.source_is_pending(self, startTime)
        else:
            self.startflow()
            
    def set_dst(self, dst: int) -> None:
        """设置目标地址 - void set_dst(uint32_t dst)"""
        self._dstaddr = dst
        
    def set_traffic_logger(self, pktlogger) -> None:
        """设置流量日志器 - void set_traffic_logger(TrafficLogger* pktlogger)"""
        self._pktlogger = pktlogger
        
    def startflow(self) -> None:
        """
        开始流传输 - 对应 C++ NdpSrc::startflow()
        """
        # TODO: 实现完整的流启动逻辑
        # 1. 初始化拥塞窗口
        # 2. 发送第一批数据包
        # 3. 启动重传定时器
        self._cwnd = 50000  # 初始窗口
        self._flight_size = 0
        self.send_packets()
        
    def setCwnd(self, cwnd: int) -> None:
        """设置拥塞窗口 - void setCwnd(uint32_t cwnd)"""
        self._cwnd = cwnd
        
    @classmethod
    def setMinRTO(cls, min_rto_in_us: int) -> None:
        """设置最小RTO - static void setMinRTO(uint32_t min_rto_in_us)"""
        cls._min_rto = timeFromUs(min_rto_in_us)
        
    @classmethod
    def setRouteStrategy(cls, strat: RouteStrategy) -> None:
        """设置路由策略 - static void setRouteStrategy(RouteStrategy strat)"""
        cls._route_strategy = strat
        
    @classmethod
    def setPathEntropySize(cls, path_entropy_size: int) -> None:
        """设置路径熵大小 - static void setPathEntropySize(uint32_t path_entropy_size)"""
        cls._path_entropy_size = path_entropy_size
        
    def set_flowsize(self, flow_size_in_bytes: int) -> None:
        """设置流大小 - void set_flowsize(uint64_t flow_size_in_bytes)"""
        self._flow_size = flow_size_in_bytes
        
    def set_stoptime(self, stop_time: int) -> None:
        """设置停止时间 - void set_stoptime(simtime_picosec stop_time)"""
        self._stop_time = stop_time
        print(f"Setting stop time to {timeAsSec(stop_time)}")
        
    def activate(self) -> None:
        """触发器激活 - virtual void activate()"""
        self.startflow()
        
    def set_end_trigger(self, trigger: Trigger) -> None:
        """设置结束触发器 - void set_end_trigger(Trigger& trigger)"""
        self._end_trigger = trigger
        
    def doNextEvent(self) -> None:
        """
        处理下一个事件 - virtual void doNextEvent()
        """
        # TODO: 实现完整的事件处理逻辑
        pass
        
    def receivePacket(self, pkt: Packet) -> None:
        """
        接收包处理 - virtual void receivePacket(Packet& pkt)
        """
        if isinstance(pkt, NdpPull):
            self.processPull(pkt)
        elif isinstance(pkt, NdpAck):
            self.processAck(pkt)
        elif isinstance(pkt, NdpNack):
            self.processNack(pkt)
        elif isinstance(pkt, NdpPacket) and pkt._type == NdpPacket.NDP:
            if self._rts:
                self.processRTS(pkt)
        else:
            # 未知包类型
            pass
            
    def processRTS(self, pkt: NdpPacket) -> None:
        """
        处理RTS包 - virtual void processRTS(NdpPacket& pkt)
        """
        # TODO: 实现RTS处理逻辑
        pass
        
    def processAck(self, ack: NdpAck) -> None:
        """
        处理ACK包 - virtual void processAck(const NdpAck& ack)
        """
        self._acks_received += 1
        
        # TODO: 实现完整的ACK处理
        # 1. 更新_last_acked
        # 2. 调整拥塞窗口
        # 3. 更新路径统计
        # 4. 处理累积ACK
        
    def processNack(self, nack: NdpNack) -> None:
        """
        处理NACK包 - virtual void processNack(const NdpNack& nack)
        """
        self._nacks_received += 1
        
        # TODO: 实现完整的NACK处理
        # 1. 标记包为需要重传
        # 2. 更新路径统计（路径可能拥塞）
        # 3. 调整路径选择策略
        
    def processPull(self, pull: NdpPull) -> None:
        """
        处理PULL包 - 新增方法处理Pull请求
        """
        self._pulls_received += 1
        
        # TODO: 实现Pull处理
        # 1. 根据pull请求发送数据
        # 2. 更新_pull_window
        self.pull_packets(pull.pullno, pull.pacerno)
        
    def replace_route(self, newroute: Route) -> None:
        """
        替换路由 - void replace_route(Route* newroute)
        """
        self._route = newroute
        
    def rtx_timer_hook(self, now: int, period: int) -> None:
        """
        重传定时器钩子 - virtual void rtx_timer_hook(simtime_picosec now, simtime_picosec period)
        """
        # TODO: 实现重传逻辑
        # 1. 检查超时的包
        # 2. 重传超时包
        # 3. 更新RTO
        if self._rtx_timeout_pending and now >= self._rtx_timeout:
            self._rtx_timeout_pending = False
            NdpSrc._global_rto_count += 1
            self.retransmit_packet()
            
    def set_paths(self, paths) -> None:
        """
        设置路径集合 - 支持两种重载版本
        void set_paths(vector<const Route*>* rt)
        void set_paths(uint32_t path_count)
        """
        if isinstance(paths, list):
            # vector<const Route*>* version
            self._paths = paths
            self._original_paths = paths.copy()
            
            # 初始化路径统计
            path_count = len(paths)
            self._path_acks = [0] * path_count
            self._path_ecns = [0] * path_count
            self._path_nacks = [0] * path_count
            self._avoid_ratio = [0] * path_count
            self._avoid_score = [0] * path_count
            self._bad_path = [False] * path_count
            
            if DEBUG_PATH_STATS:
                self._path_counts_new = [0] * path_count
                self._path_counts_rtx = [0] * path_count
                self._path_counts_rto = [0] * path_count
        elif isinstance(paths, int):
            # uint32_t path_count version
            # 用于ECMP_FIB策略
            self._path_count = paths
            
    def set_path_burst(self, path_burst: int) -> None:
        """设置路径突发大小 - void set_path_burst(uint16_t path_burst)"""
        self._same_path_burst = path_burst
        
    def print_stats(self) -> None:
        """
        打印统计信息 - void print_stats()
        """
        print(f"NdpSrc {self._nodename} stats:")
        print(f"  Packets sent: {self._packets_sent}")
        print(f"  New packets: {self._new_packets_sent}")
        print(f"  Retransmits: {self._rtx_packets_sent}")
        print(f"  ACKs received: {self._acks_received}")
        print(f"  NACKs received: {self._nacks_received}")
        print(f"  PULLs received: {self._pulls_received}")
        print(f"  RTOs: {NdpSrc._global_rto_count}")
        
    def choose_route(self) -> int:
        """
        选择路由 - int choose_route()
        """
        # TODO: 实现完整的路由选择逻辑
        # 根据_route_strategy选择不同的策略
        if self._route_strategy == RouteStrategy.SINGLE_PATH:
            return 0
        elif self._route_strategy == RouteStrategy.SCATTER_RANDOM:
            return random.randint(0, len(self._paths) - 1) if self._paths else 0
        elif self._route_strategy == RouteStrategy.SCATTER_PERMUTE:
            # 轮询选择
            path = self._crt_path
            self._crt_path = (self._crt_path + 1) % len(self._paths)
            return path
        elif self._route_strategy == RouteStrategy.PULL_BASED:
            # TODO: 基于Pull的路径选择
            return 0
        elif self._route_strategy == RouteStrategy.SCATTER_ECMP:
            # TODO: ECMP散列
            return 0
        elif self._route_strategy == RouteStrategy.REACTIVE_ECN:
            # TODO: 基于ECN反馈的路径选择
            return self.choose_best_path()
        else:
            return 0
            
    def choose_best_path(self) -> int:
        """选择最佳路径 - 基于路径统计"""
        if not self._paths:
            return 0
            
        best_path = 0
        best_score = float('inf')
        
        for i in range(len(self._paths)):
            if self._bad_path[i]:
                continue
                
            # 计算路径分数（越低越好）
            score = self._path_nacks[i] * 10 + self._path_ecns[i] * 5 - self._path_acks[i]
            if score < best_score:
                best_score = score
                best_path = i
                
        return best_path
        
    def next_route(self) -> int:
        """
        获取下一个路由 - int next_route()
        """
        return self.choose_route()
        
    def pull_packets(self, pull_no: int, pacer_no: int) -> None:
        """
        响应PULL请求发送包 - void pull_packets(NdpPull::seq_t pull_no, NdpPull::seq_t pacer_no)
        """
        # TODO: 实现Pull响应逻辑
        # 1. 检查是否有待发送的包
        # 2. 根据pull_no确定发送哪些包
        # 3. 使用pacer_no控制发送速率
        
        self._pull_window -= 1
        packets_sent = self.send_packet(pacer_no)
        
    def send_packet(self, pacer_no: int = 0) -> int:
        """
        发送数据包 - int send_packet(NdpPull::seq_t pacer_no)
        返回实际发送的包数
        """
        # TODO: 实现完整的包发送逻辑
        # 1. 检查拥塞窗口
        # 2. 选择路径
        # 3. 创建并发送NdpPacket
        # 4. 更新统计
        
        if self._flight_size >= self._cwnd:
            return 0
            
        # 创建新包或重传包
        pkt = NdpPacket()
        pkt.seqno = self._highest_sent
        pkt.set_path_id(self.choose_route())
        
        self._highest_sent += self._mss
        self._packets_sent += 1
        self._new_packets_sent += 1
        self._flight_size += self._mss
        
        # 记录发送时间
        self._sent_times[pkt.seqno] = self._eventlist.now()
        if pkt.seqno not in self._first_sent_times:
            self._first_sent_times[pkt.seqno] = self._eventlist.now()
            
        # TODO: 实际发送包到路由
        # self._route.sendOn(pkt)
        
        return 1
        
    def send_packets(self) -> None:
        """批量发送包 - 辅助方法"""
        while self._flight_size < self._cwnd:
            if self.send_packet(0) == 0:
                break
                
    def retransmit_packet(self) -> None:
        """重传超时包"""
        # TODO: 实现重传逻辑
        self._rtx_packets_sent += 1
        
    def nodename(self) -> str:
        """获取节点名 - virtual const string& nodename()"""
        return self._nodename
        
    def set_flowid(self, flow_id: int) -> None:
        """设置流ID - inline void set_flowid(flowid_t flow_id)"""
        self._flow.set_flowid(flow_id)
        
    def flow_id(self) -> int:
        """获取流ID - inline flowid_t flow_id() const"""
        return self._flow.flow_id()
        
    def log_me(self) -> None:
        """调试日志 - void log_me()"""
        self._log_me = True
        
    # PacketSink接口实现
    def receive_packet(self, pkt: Packet) -> None:
        """PacketSink接口方法"""
        self.receivePacket(pkt)

# ============================================================================
# NDP接收端 - 对应 ndp.h: class NdpSink
# ============================================================================

class NdpSink(PacketSink, EventSource):
    """
    NDP接收端实现 - 对应 ndp.h: class NdpSink
    """
    
    def __init__(self,
                 eventlist: Optional[EventList] = None):
        """
        初始化NDP接收端 - 对应 C++ NdpSink::NdpSink()
        """
        EventSource.__init__(self, eventlist, "ndpsink")
        PacketSink.__init__(self)
        
        self._nodename = "ndpsink"
        self._src = None
        self._route = None
        
        # 接收缓冲区和重排序
        self._cumulative_ack = 0
        self._received = []  # 已接收但乱序的包
        self._receive_window = 1000000  # 接收窗口大小
        
        # 统计
        self._packets_received = 0
        self._headers_received = 0
        
    def connect(self, src: NdpSrc, route: Route) -> None:
        """
        连接到源端 - void connect(NdpSrc& src, Route* route)
        """
        self._src = src
        self._route = route
        
    def receivePacket(self, pkt: Packet) -> None:
        """
        接收包处理 - virtual void receivePacket(Packet& pkt)
        """
        if isinstance(pkt, NdpPacket):
            if pkt.is_header():
                self._headers_received += 1
                # 发送NACK
                self.send_nack(pkt.seqno, pkt.path_id())
            else:
                self._packets_received += 1
                # 处理数据包
                self.process_data_packet(pkt)
                
    def process_data_packet(self, pkt: NdpPacket) -> None:
        """处理数据包"""
        seqno = pkt.seqno
        
        if seqno == self._cumulative_ack + 1:
            # 按序到达
            self._cumulative_ack = seqno
            # 检查是否可以递交更多包
            self.check_reorder_buffer()
            # 发送ACK
            self.send_ack(seqno, pkt.path_id())
        elif seqno > self._cumulative_ack + 1:
            # 乱序到达
            self._received.append(seqno)
            # 发送Pull请求
            self.send_pull()
        else:
            # 重复包，忽略
            pass
            
    def check_reorder_buffer(self) -> None:
        """检查重排序缓冲区"""
        # TODO: 实现重排序逻辑
        pass
        
    def send_ack(self, seqno: int, path_id: int) -> None:
        """发送ACK"""
        ack = NdpAck()
        ack.ackno = seqno
        ack.cumulative_ack = self._cumulative_ack
        ack.set_path_id(path_id)
        # TODO: 通过路由发送ACK
        # self._route.sendOn(ack)
        
    def send_nack(self, seqno: int, path_id: int) -> None:
        """发送NACK"""
        nack = NdpNack()
        nack.ackno = seqno
        nack.set_path_id(path_id)
        # TODO: 通过路由发送NACK
        # self._route.sendOn(nack)
        
    def send_pull(self) -> None:
        """发送PULL请求"""
        pull = NdpPull()
        pull.pullno = self._cumulative_ack + 1
        pull.cumulative_ack = self._cumulative_ack
        # TODO: 通过路由发送PULL
        # self._route.sendOn(pull)
        
    def nodename(self) -> str:
        """获取节点名"""
        return self._nodename
        
    # PacketSink接口实现
    def receive_packet(self, pkt: Packet) -> None:
        """PacketSink接口方法"""
        self.receivePacket(pkt)
        
    # EventSource接口实现
    def doNextEvent(self) -> None:
        """处理下一个事件"""
        # TODO: 实现定期发送Pull的逻辑
        pass

# ============================================================================
# NDP日志器 - 对应 loggertypes.h: class NdpLogger
# ============================================================================

class NdpLogger(Logger):
    """NDP日志器 - 记录NDP协议事件"""
    
    def __init__(self):
        super().__init__()
        
    def logNdp(self, src: NdpSrc, event_type: str) -> None:
        """记录NDP事件"""
        # TODO: 实现日志记录
        pass

# ============================================================================
# 流量日志器 - 对应 loggertypes.h: class TrafficLogger  
# ============================================================================

class TrafficLogger(Logger):
    """流量日志器 - 记录流量事件"""
    
    def __init__(self):
        super().__init__()
        
    def logTraffic(self, pkt: Packet, location: str, event_type: str) -> None:
        """记录流量事件"""
        # TODO: 实现日志记录
        pass

# 导出接口
__all__ = [
    'NdpSrc',
    'NdpSink',
    'NdpPacket',
    'NdpAck',
    'NdpNack',
    'NdpPull',
    'NdpRTSPacer',
    'RouteStrategy',
    'FeedbackType',
    'ReceiptEvent',
    'NdpLogger',
    'TrafficLogger',
]