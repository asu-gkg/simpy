"""
NDPPacket - NDP Protocol Packets

对应文件: ndppacket.h/cpp
功能: NDP协议完整包类型实现

主要类:
- PacketDB: 包对象池管理器
- NDPPacket: NDP数据包类 (对应 NdpPacket)
- NDPAck: NDP确认包类 (对应 NdpAck)
- NDPNack: NDP负确认包类 (对应 NdpNack)
- NDPRTS: NDP就绪发送包类 (对应 NdpRTS)
- NDPPull: NDP拉取包类 (对应 NdpPull)

严格按照C++原始实现设计，保持功能和架构一致性
"""

from typing import Optional, List, TypeVar, Generic, Union
from .base_packet import BasePacket
from ..core.packet import PacketType, PacketPriority
from ..core.network import PacketSink, PacketFlow
from ..core.route import Route

# 类型定义
seq_t = int  # 对应 C++ 的 uint64_t seq_t
simtime_picosec = int  # 对应 C++ 的 simtime_picosec

# 包方向枚举
class PacketDirection:
    NONE = 0
    FORWARD = 1
    BACKWARD = 2

T = TypeVar('T')

class PacketDB(Generic[T]):
    """
    包对象池管理器 - 对应 C++ 中的 PacketDB<T> 模板类
    
    实现包对象的重用机制，避免频繁创建/销毁对象
    """
    
    def __init__(self, packet_class):
        self._packet_class = packet_class
        self._free_packets: List[T] = []
        self._allocated_count = 0
        self._freed_count = 0
    
    def allocPacket(self) -> T:
        """分配包对象 - 对应 C++ 的 allocPacket()"""
        if self._free_packets:
            packet = self._free_packets.pop()
            # 重置包状态
            packet._reset()
        else:
            packet = self._packet_class()
        
        self._allocated_count += 1
        return packet
    
    def freePacket(self, packet: T) -> None:
        """释放包对象 - 对应 C++ 的 freePacket()"""
        if packet is not None:
            self._free_packets.append(packet)
            self._freed_count += 1
    
    def stats(self) -> dict:
        """获取对象池统计信息"""
        return {
            'allocated': self._allocated_count,
            'freed': self._freed_count,
            'pool_size': len(self._free_packets)
        }


class NDPPacket(BasePacket):
    """
    NDP数据包类 - 严格对应 C++ 中的 NdpPacket 类
    
    实现NDP协议的数据包格式和功能
    """
    
    # 常量定义
    ACKSIZE = 64  # 对应 C++ 的 const static int ACKSIZE=64
    VALUE_NOT_SET = -1  # 对应 C++ 的 #define VALUE_NOT_SET -1
    
    # 类变量 - 包对象池
    _packetdb: PacketDB['NDPPacket'] = None
    
    @classmethod
    def _init_packetdb(cls):
        """初始化包对象池"""
        if cls._packetdb is None:
            cls._packetdb = PacketDB(cls)
    
    def __init__(self):
        super().__init__()
        self._type = PacketType.NDP
        self._reset()
    
    def _reset(self):
        """重置包状态 - 用于对象池重用"""
        # NDP特定字段
        self._seqno: seq_t = 0
        self._pacerno: seq_t = 0  # pacer序列号
        self._ts: simtime_picosec = 0  # 时间戳
        self._retransmitted: bool = False
        self._no_of_paths: int = 0
        self._last_packet: bool = False
        self._path_len: int = 0
        self._direction: int = PacketDirection.NONE
        self._trim_hop: int = 2**32 - 1  # UINT32_MAX
        self._trim_direction: int = PacketDirection.NONE
        self._is_header: bool = False
        self._bounced: bool = False
    
    @staticmethod
    def newpkt(flow: PacketFlow, seqno: seq_t, pacerno: seq_t, size: int,
               retransmitted: bool, last_packet: bool,
               destination: int = 2**32 - 1) -> 'NDPPacket':
        """
        对应 C++ 的静态工厂方法 NDPPacket::newpkt() (routeless版本)
        创建无路由信息的NDP数据包
        """
        NDPPacket._init_packetdb()
        p = NDPPacket._packetdb.allocPacket()
        
        # 设置基本属性 - 对应 C++ 的 set_attrs
        p.set_attrs(flow, size + NDPPacket.ACKSIZE, seqno + size - 1)
        p._type = PacketType.NDP
        p._is_header = False
        p._bounced = False
        p._seqno = seqno
        p._pacerno = pacerno
        p._retransmitted = retransmitted
        p._last_packet = last_packet
        p._path_len = 0
        p._direction = PacketDirection.NONE
        p.set_dst(destination)
        p._trim_hop = 2**32 - 1
        p._trim_direction = PacketDirection.NONE
        
        return p
    
    @staticmethod
    def newpkt_with_route(flow: PacketFlow, route: Route, seqno: seq_t, 
                        pacerno: seq_t, size: int, retransmitted: bool,
                        no_of_paths: int, last_packet: bool,
                        destination: int = 2**32 - 1) -> 'NDPPacket':
        """
        对应 C++ 的静态工厂方法 NDPPacket::newpkt() (带路由版本)
        创建带路由信息的NDP数据包
        """
        NDPPacket._init_packetdb()
        p = NDPPacket._packetdb.allocPacket()
        
        # 设置路由 - 对应 C++ 的 set_route
        p.set_route(flow, route, size + NDPPacket.ACKSIZE, seqno + size - 1)
        p._type = PacketType.NDP
        p._is_header = False
        p._bounced = False
        p._seqno = seqno
        p._pacerno = pacerno
        p._direction = PacketDirection.NONE
        p._retransmitted = retransmitted
        p._no_of_paths = no_of_paths
        p._last_packet = last_packet
        p._path_len = len(route) if route else 0
        p._trim_hop = 2**32 - 1
        p._trim_direction = PacketDirection.NONE
        p.set_dst(destination)
        
        return p
    
    def free(self) -> None:
        """对应 C++ 的 free() 方法 - 回收包对象到对象池"""
        if NDPPacket._packetdb:
            NDPPacket._packetdb.freePacket(self)
    
    def strip_payload(self) -> None:
        """
        对应 C++ 的 strip_payload() 方法
        剥离载荷，只保留头部信息
        """
        super().strip_payload()
        self._size = NDPPacket.ACKSIZE
        self._trim_hop = self._nexthop
        self._trim_direction = self._direction
    
    def set_route(self, route: Route) -> None:
        """
        对应 C++ 的 set_route() 方法
        设置包路由，调整trim_hop
        """
        if self._trim_hop != 2**31 - 1:  # INT32_MAX
            self._trim_hop -= len(route)
        super().set_route(route)
    
    def priority(self) -> PacketPriority:
        """
        对应 C++ 的 priority() 方法
        获取包优先级
        """
        if self._is_header:
            return PacketPriority.PRIO_HI
        else:
            return PacketPriority.PRIO_LO
    
    # 属性访问器 - 对应 C++ 的 inline 方法
    @property
    def seqno(self) -> seq_t:
        """对应 C++ 的 seqno()"""
        return self._seqno
    
    @property
    def pacerno(self) -> seq_t:
        """对应 C++ 的 pacerno()"""
        return self._pacerno
    
    def set_pacerno(self, pacerno: seq_t) -> None:
        """对应 C++ 的 set_pacerno()"""
        self._pacerno = pacerno
    
    @property
    def retransmitted(self) -> bool:
        """对应 C++ 的 retransmitted()"""
        return self._retransmitted
    
    @property
    def last_packet(self) -> bool:
        """对应 C++ 的 last_packet()"""
        return self._last_packet
    
    @property
    def trim_hop(self) -> int:
        """对应 C++ 的 trim_hop()"""
        return self._trim_hop
    
    @property
    def trim_direction(self) -> int:
        """对应 C++ 的 trim_direction()"""
        return self._trim_direction
    
    @property
    def ts(self) -> simtime_picosec:
        """对应 C++ 的 ts()"""
        return self._ts
    
    def set_ts(self, ts: simtime_picosec) -> None:
        """对应 C++ 的 set_ts()"""
        self._ts = ts
    
    @property
    def path_id(self) -> int:
        """对应 C++ 的 path_id()"""
        if hasattr(self, '_pathid') and self._pathid != 2**32 - 1:
            return self._pathid
        elif self._route:
            return self._route.path_id()
        return 0
    
    @property
    def no_of_paths(self) -> int:
        """对应 C++ 的 no_of_paths()"""
        return self._no_of_paths
    
    def __str__(self) -> str:
        """字符串表示"""
        return (f"NDPPacket(seq={self._seqno}, pacer={self._pacerno}, "
                f"size={self.size}, retrans={self._retransmitted})")


class NDPAck(BasePacket):
    """
    NDP确认包类 - 严格对应 C++ 中的 NdpAck 类
    """
    
    # 类变量 - 包对象池
    _packetdb: PacketDB['NDPAck'] = None
    
    @classmethod
    def _init_packetdb(cls):
        """初始化包对象池"""
        if cls._packetdb is None:
            cls._packetdb = PacketDB(cls)
    
    def __init__(self):
        super().__init__()
        self._type = PacketType.NDPACK
        self._reset()
    
    def _reset(self):
        """重置包状态"""
        self._pacerno: seq_t = 0
        self._ackno: seq_t = 0
        self._cumulative_ack: seq_t = 0
        self._ts: simtime_picosec = 0
        self._pullno: seq_t = 0
        self._path_id: int = 0
        self._pull: bool = True
        self._ecn_echo: bool = False
        self._is_header: bool = True
        self._bounced: bool = False
        self._path_len: int = 0
        self._direction: int = PacketDirection.NONE
    
    @staticmethod
    def newpkt(flow: PacketFlow, route: Route, pacerno: seq_t, ackno: seq_t,
               cumulative_ack: seq_t, pullno: seq_t, path_id: int,
               destination: int = 2**32 - 1) -> 'NDPAck':
        """对应 C++ 的 NdpAck::newpkt() 静态工厂方法"""
        NDPAck._init_packetdb()
        p = NDPAck._packetdb.allocPacket()
        
        p.set_route(flow, route, NDPPacket.ACKSIZE, ackno)
        p._type = PacketType.NDPACK
        p._is_header = True
        p._bounced = False
        p._pacerno = pacerno
        p._ackno = ackno
        p._cumulative_ack = cumulative_ack
        p._pull = True
        p._pullno = pullno
        p._path_id = path_id
        p._path_len = 0
        p._direction = PacketDirection.NONE
        p._ecn_echo = False
        p.set_dst(destination)
        
        return p
    
    def free(self) -> None:
        """对应 C++ 的 free() 方法"""
        if NDPAck._packetdb:
            NDPAck._packetdb.freePacket(self)
    
    def priority(self) -> PacketPriority:
        """对应 C++ 的 priority() 方法"""
        return PacketPriority.PRIO_HI
    
    # 属性访问器
    @property
    def pacerno(self) -> seq_t:
        return self._pacerno
    
    def set_pacerno(self, pacerno: seq_t) -> None:
        self._pacerno = pacerno
    
    @property
    def ackno(self) -> seq_t:
        return self._ackno
    
    @property
    def cumulative_ack(self) -> seq_t:
        return self._cumulative_ack
    
    @property
    def ts(self) -> simtime_picosec:
        return self._ts
    
    def set_ts(self, ts: simtime_picosec) -> None:
        self._ts = ts
    
    @property
    def pull(self) -> bool:
        return self._pull
    
    @property
    def pullno(self) -> seq_t:
        return self._pullno
    
    @property
    def path_id(self) -> int:
        return self._path_id
    
    def dont_pull(self) -> None:
        """对应 C++ 的 dont_pull() 方法"""
        self._pull = False
        self._pullno = 0
    
    def set_ecn_echo(self, ecn_echo: bool) -> None:
        """对应 C++ 的 set_ecn_echo() 方法"""
        self._ecn_echo = ecn_echo
    
    @property
    def ecn_echo(self) -> bool:
        """对应 C++ 的 ecn_echo() 方法"""
        return self._ecn_echo


class NDPNack(BasePacket):
    """
    NDP负确认包类 - 严格对应 C++ 中的 NdpNack 类
    """
    
    # 类变量 - 包对象池
    _packetdb: PacketDB['NDPNack'] = None
    
    @classmethod
    def _init_packetdb(cls):
        if cls._packetdb is None:
            cls._packetdb = PacketDB(cls)
    
    def __init__(self):
        super().__init__()
        self._type = PacketType.NDPNACK
        self._reset()
    
    def _reset(self):
        """重置包状态"""
        self._pacerno: seq_t = 0
        self._ackno: seq_t = 0
        self._cumulative_ack: seq_t = 0
        self._ts: simtime_picosec = 0
        self._pullno: seq_t = 0
        self._path_id: int = 0
        self._pull: bool = True
        self._ecn_echo: bool = False
        self._is_header: bool = True
        self._bounced: bool = False
        self._path_len: int = 0
        self._direction: int = PacketDirection.NONE
    
    @staticmethod
    def newpkt(flow: PacketFlow, route: Route, pacerno: seq_t, ackno: seq_t,
               cumulative_ack: seq_t, pullno: seq_t, path_id: int,
               destination: int = 2**32 - 1) -> 'NDPNack':
        """对应 C++ 的 NdpNack::newpkt() 静态工厂方法"""
        NDPNack._init_packetdb()
        p = NDPNack._packetdb.allocPacket()
        
        p.set_route(flow, route, NDPPacket.ACKSIZE, ackno)
        p._type = PacketType.NDPNACK
        p._is_header = True
        p._bounced = False
        p._pacerno = pacerno
        p._ackno = ackno
        p._cumulative_ack = cumulative_ack
        p._pull = True
        p._direction = PacketDirection.NONE
        p._pullno = pullno
        p._path_id = path_id
        p._path_len = 0
        p._ecn_echo = False
        p.set_dst(destination)
        
        return p
    
    def free(self) -> None:
        if NDPNack._packetdb:
            NDPNack._packetdb.freePacket(self)
    
    def priority(self) -> PacketPriority:
        """对应 C++ 的 priority() 方法 - NACK使用低优先级"""
        return PacketPriority.PRIO_LO
    
    # 属性访问器 (与NDPAck相同的接口)
    @property
    def pacerno(self) -> seq_t:
        return self._pacerno
    
    def set_pacerno(self, pacerno: seq_t) -> None:
        self._pacerno = pacerno
    
    @property
    def ackno(self) -> seq_t:
        return self._ackno
    
    @property
    def cumulative_ack(self) -> seq_t:
        return self._cumulative_ack
    
    @property
    def ts(self) -> simtime_picosec:
        return self._ts
    
    def set_ts(self, ts: simtime_picosec) -> None:
        self._ts = ts
    
    @property
    def pull(self) -> bool:
        return self._pull
    
    @property
    def pullno(self) -> seq_t:
        return self._pullno
    
    @property
    def path_id(self) -> int:
        return self._path_id
    
    def dont_pull(self) -> None:
        self._pull = False
        self._pullno = 0
    
    def set_ecn_echo(self, ecn_echo: bool) -> None:
        self._ecn_echo = ecn_echo
    
    @property
    def ecn_echo(self) -> bool:
        return self._ecn_echo


class NDPRTS(BasePacket):
    """
    NDP就绪发送包类 - 严格对应 C++ 中的 NdpRTS 类
    """
    
    # 类变量 - 包对象池
    _packetdb: PacketDB['NDPRTS'] = None
    
    @classmethod
    def _init_packetdb(cls):
        if cls._packetdb is None:
            cls._packetdb = PacketDB(cls)
    
    def __init__(self):
        super().__init__()
        self._type = PacketType.NDPRTS
        self._reset()
    
    def _reset(self):
        """重置包状态"""
        self._ts: simtime_picosec = 0
        self._grants: seq_t = 0
        self._path_id: int = 0
        self._is_header: bool = True
        self._bounced: bool = False
        self._direction: int = PacketDirection.NONE
    
    @staticmethod
    def newpkt(flow: PacketFlow, grants: int,
               destination: int = 2**32 - 1) -> 'NDPRTS':
        """对应 C++ 的 NdpRTS::newpkt() 静态工厂方法 (无路由版本)"""
        NDPRTS._init_packetdb()
        p = NDPRTS._packetdb.allocPacket()
        
        p.set_attrs(flow, NDPPacket.ACKSIZE, 0)
        p._type = PacketType.NDPRTS
        p._is_header = True
        p._bounced = False
        p._grants = grants
        p._path_id = 0
        p._direction = PacketDirection.NONE
        p.set_dst(destination)
        
        return p
    
    @staticmethod
    def newpkt_with_route(flow: PacketFlow, route: Route, grants: int,
                         destination: int = 2**32 - 1) -> 'NDPRTS':
        """对应 C++ 的 NdpRTS::newpkt() 静态工厂方法 (带路由版本)"""
        NDPRTS._init_packetdb()
        p = NDPRTS._packetdb.allocPacket()
        
        p.set_route(flow, route, NDPPacket.ACKSIZE, 0)
        assert p.route()
        
        p._type = PacketType.NDPRTS
        p._is_header = True
        p._bounced = False
        p._grants = grants
        p._path_id = 0
        p._direction = PacketDirection.NONE
        p.set_dst(destination)
        
        return p
    
    def free(self) -> None:
        if NDPRTS._packetdb:
            NDPRTS._packetdb.freePacket(self)
    
    def priority(self) -> PacketPriority:
        """对应 C++ 的 priority() 方法"""
        return PacketPriority.PRIO_HI
    
    # 属性访问器
    @property
    def grants(self) -> seq_t:
        """对应 C++ 的 grants()"""
        return self._grants
    
    def set_grants(self, grants: seq_t) -> None:
        """对应 C++ 的 set_grants()"""
        self._grants = grants
    
    @property
    def path_id(self) -> int:
        """对应 C++ 的 path_id()"""
        return self._path_id
    
    def set_ts(self, ts: simtime_picosec) -> None:
        """对应 C++ 的 set_ts()"""
        self._ts = ts


class NDPPull(BasePacket):
    """
    NDP拉取包类 - 严格对应 C++ 中的 NdpPull 类
    """
    
    # 类变量 - 包对象池
    _packetdb: PacketDB['NDPPull'] = None
    
    @classmethod
    def _init_packetdb(cls):
        if cls._packetdb is None:
            cls._packetdb = PacketDB(cls)
    
    def __init__(self):
        super().__init__()
        self._type = PacketType.NDPPULL
        self._reset()
    
    def _reset(self):
        """重置包状态"""
        self._pacerno: seq_t = 0
        self._ackno: seq_t = 0
        self._cumulative_ack: seq_t = 0
        self._pullno: seq_t = 0
        self._path_id: int = 0
        self._is_header: bool = True
        self._bounced: bool = False
        self._path_len: int = 0
        self._direction: int = PacketDirection.NONE
    
    @staticmethod
    def newpkt_from_ack(ack: NDPAck) -> 'NDPPull':
        """对应 C++ 的 NdpPull::newpkt(NdpAck* ack) 静态工厂方法"""
        NDPPull._init_packetdb()
        p = NDPPull._packetdb.allocPacket()
        
        assert ack.route()
        p.set_route(ack.flow(), ack.route(), NDPPacket.ACKSIZE, ack.ackno)
        
        assert p.route()
        p._type = PacketType.NDPPULL
        p._is_header = True
        p._bounced = False
        p._ackno = ack.ackno
        p._cumulative_ack = ack.cumulative_ack
        p._pullno = ack.pullno
        p._path_len = 0
        p._direction = PacketDirection.NONE
        p.set_dst(ack.dst())
        
        return p
    
    @staticmethod
    def newpkt_from_nack(nack: NDPNack) -> 'NDPPull':
        """对应 C++ 的 NdpPull::newpkt(NdpNack* nack) 静态工厂方法"""
        NDPPull._init_packetdb()
        p = NDPPull._packetdb.allocPacket()
        
        assert nack.route()
        p.set_route(nack.flow(), nack.route(), NDPPacket.ACKSIZE, nack.ackno)
        
        assert p.route()
        p._type = PacketType.NDPPULL
        p._is_header = True
        p._bounced = False
        p._ackno = nack.ackno
        p._cumulative_ack = nack.cumulative_ack
        p._pullno = nack.pullno
        p._path_len = 0
        p._direction = PacketDirection.NONE
        p.set_dst(nack.dst())
        
        return p
    
    @staticmethod
    def newpkt_from_rts(rts: NDPRTS, cumack: seq_t, pullno: seq_t) -> 'NDPPull':
        """对应 C++ 的 NdpPull::newpkt(NdpRTS* rts, seq_t cumack, seq_t pullno)"""
        NDPPull._init_packetdb()
        p = NDPPull._packetdb.allocPacket()
        
        p.set_attrs(rts.flow(), NDPPacket.ACKSIZE, 0)
        
        p._type = PacketType.NDPPULL
        p._is_header = True
        p._bounced = False
        p._ackno = cumack
        p._cumulative_ack = cumack
        p._pullno = pullno
        p._path_len = 0
        p._direction = PacketDirection.NONE
        p.set_dst(rts.dst())
        
        return p
    
    @staticmethod
    def newpkt_from_rts_with_route(rts: NDPRTS, route: Route, cumack: seq_t,
                                  pullno: seq_t, destination: int = 2**32 - 1) -> 'NDPPull':
        """对应 C++ 的 NdpPull::newpkt(NdpRTS* rts, const route_t& route, ...)"""
        NDPPull._init_packetdb()
        p = NDPPull._packetdb.allocPacket()
        
        p.set_route(rts.flow(), route, NDPPacket.ACKSIZE, 0)
        
        assert p.route()
        p._type = PacketType.NDPPULL
        p._is_header = True
        p._bounced = False
        p._ackno = cumack
        p._cumulative_ack = cumack
        p._pullno = pullno
        p._path_len = 0
        p.set_dst(destination)
        p._direction = PacketDirection.NONE
        
        return p
    
    @staticmethod
    def newpkt(flow: PacketFlow, route: Route, cumack: seq_t, pullno: seq_t,
               destination: int = 2**32 - 1) -> 'NDPPull':
        """对应 C++ 的 NdpPull::newpkt(PacketFlow& flow, const route_t& route, ...)"""
        NDPPull._init_packetdb()
        p = NDPPull._packetdb.allocPacket()
        
        p.set_route(flow, route, NDPPacket.ACKSIZE, 0)
        
        assert p.route()
        p._type = PacketType.NDPPULL
        p._is_header = True
        p._bounced = False
        p._ackno = cumack
        p._cumulative_ack = cumack
        p._pullno = pullno
        p._path_len = 0
        p.set_dst(destination)
        p._direction = PacketDirection.NONE
        
        return p
    
    def free(self) -> None:
        if NDPPull._packetdb:
            NDPPull._packetdb.freePacket(self)
    
    def priority(self) -> PacketPriority:
        """对应 C++ 的 priority() 方法"""
        return PacketPriority.PRIO_HI
    
    # 属性访问器
    @property
    def pacerno(self) -> seq_t:
        return self._pacerno
    
    def set_pacerno(self, pacerno: seq_t) -> None:
        self._pacerno = pacerno
    
    @property
    def ackno(self) -> seq_t:
        return self._ackno
    
    @property
    def cumulative_ack(self) -> seq_t:
        return self._cumulative_ack
    
    @property
    def pullno(self) -> seq_t:
        return self._pullno
    
    @property
    def path_id(self) -> int:
        return self._path_id