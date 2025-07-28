"""
Network - Network Abstraction Layer

对应文件: network.h/cpp
功能: 网络基础抽象类，定义数据包、接收器、流等核心概念

主要类:
- Packet: 数据包基类
- PacketSink: 数据包接收器
- PacketFlow: 数据包流
- DataReceiver: 数据接收器
- VirtualQueue: 虚拟队列
- PacketDB: 数据包内存管理（泛型版本）

C++对应关系:
- Packet::sendOn() -> Packet.send_on()
- PacketSink::receivePacket() -> PacketSink.receive_packet()
- PacketFlow::set_flowid() -> PacketFlow.set_flow_id()
"""

from abc import ABC, abstractmethod
from typing import Optional, List, Any, TYPE_CHECKING, Generic, TypeVar
import sys

# 导入 Logged 基类
from .logger.core import Logged

# 避免循环导入
if TYPE_CHECKING:
    from .logger import TrafficLogger
    from .route import Route

# 前向声明类型 - 对应 C++ 中的前向声明
class LosslessInputQueue:
    """前向声明 - 对应 C++ 中的 LosslessInputQueue 类"""
    pass

# 对应 C++ 中的类型定义
PacketId = int  # packetid_t
FlowId = int    # flowid_t

# 对应 C++ 中的 #define FLOW_ID_DYNAMIC_BASE 1000000000
FLOW_ID_DYNAMIC_BASE = 1000000000
DEFAULT_DATA_PACKET_SIZE = 1500  # 对应 C++ DEFAULTDATASIZE

# 对应 C++ network.h 中的数据包类型枚举
class PacketType:
    """对应 C++ 中的 packet_type 枚举"""
    IP = "IP"
    TCP = "TCP"
    TCPACK = "TCPACK"
    TCPNACK = "TCPNACK"
    SWIFT = "SWIFT"
    SWIFTACK = "SWIFTACK"
    STRACK = "STRACK"
    STRACKACK = "STRACKACK"
    NDP = "NDP"
    NDPACK = "NDPACK"
    NDPNACK = "NDPNACK"
    NDPPULL = "NDPPULL"
    NDPRTS = "NDPRTS"
    NDPLITE = "NDPLITE"
    NDPLITEACK = "NDPLITEACK"
    NDPLITEPULL = "NDPLITEPULL"
    NDPLITERTS = "NDPLITERTS"
    ETH_PAUSE = "ETH_PAUSE"
    TOFINO_TRIM = "TOFINO_TRIM"
    ROCE = "ROCE"
    ROCEACK = "ROCEACK"
    ROCENACK = "ROCENACK"
    HPCC = "HPCC"
    HPCCACK = "HPCCACK"
    HPCCNACK = "HPCCNACK"
    EQDSDATA = "EQDSDATA"
    EQDSPULL = "EQDSPULL"
    EQDSACK = "EQDSACK"
    EQDSNACK = "EQDSNACK"
    EQDSRTS = "EQDSRTS"

# 对应 C++ 中的 packet_direction 枚举
class PacketDirection:
    """对应 C++ 中的 packet_direction 枚举"""
    NONE = "NONE"
    UP = "UP"
    DOWN = "DOWN"

# 对应 C++ 中的 PktPriority 枚举
class PacketPriority:
    """对应 C++ 中的 Packet::PktPriority 枚举"""
    PRIO_LO = "PRIO_LO"
    PRIO_MID = "PRIO_MID"
    PRIO_HI = "PRIO_HI"
    PRIO_NONE = "PRIO_NONE"

# 前向声明类型
Route = List['PacketSink']


def print_route(route: Route) -> None:
    """
    对应 C++ 中的 print_route(const Route& route)
    打印路由信息
    """
    for i, sink in enumerate(route):
        if i > 0:
            print(" -> ", end="")
        print(sink.nodename(), end="")
    print()


class DataReceiver(ABC, Logged):
    """
    数据接收器 - 对应 network.h/cpp 中的 DataReceiver 类
    
    所有能够接收数据的组件都应该实现此接口
    继承自 Logged (对应C++版本)
    """
    
    def __init__(self, name: str):
        # 对应 C++ 构造函数 DataReceiver(const string& name) : Logged(name)
        Logged.__init__(self, name)
    
    @abstractmethod
    def cumulative_ack(self) -> int:
        """
        对应 C++ 中的 DataReceiver::cumulative_ack()
        返回累积确认号
        """
        pass
    
    @abstractmethod
    def drops(self) -> int:
        """
        对应 C++ 中的 DataReceiver::drops()
        返回丢包数量
        """
        pass


class PacketFlow(Logged):
    """
    数据包流 - 对应 network.h/cpp 中的 PacketFlow 类
    
    管理数据包的流信息和日志记录
    继承自 Logged (对应C++版本)
    """
    
    # 对应 C++ 中的 static packetid_t _max_flow_id
    _max_flow_id: FlowId = FLOW_ID_DYNAMIC_BASE
    
    def __init__(self, logger: Optional['TrafficLogger'] = None):
        """
        对应 C++ 构造函数 PacketFlow(TrafficLogger* logger)
        : Logged("PacketFlow"), _logger(logger)
        """
        Logged.__init__(self, "PacketFlow")
        self._logger = logger
        self._flow_id = PacketFlow._max_flow_id
        PacketFlow._max_flow_id += 1
    
    def set_logger(self, logger: 'TrafficLogger') -> None:
        """对应 C++ 中的 PacketFlow::set_logger()"""
        self._logger = logger
    
    def log_traffic(self, packet: 'Packet', location: 'Logged', event_type) -> None:
        """
        对应 C++ 中的 PacketFlow::logTraffic()
        记录流量日志
        
        Args:
            packet: 数据包
            location: 记录位置
            event_type: 事件类型 (对应TrafficLogger::TrafficEvent)
        """
        if self._logger:
            self._logger.logTraffic(packet, location, event_type)
    
    def set_flow_id(self, flow_id: FlowId) -> None:
        """
        对应 C++ 中的 PacketFlow::set_flowid()
        包含流ID范围检查
        """
        if flow_id >= FLOW_ID_DYNAMIC_BASE:
            print("Illegal flow ID - manually allocation must be less than dynamic base", 
                  file=sys.stderr)
            raise ValueError(f"Flow ID {flow_id} must be less than {FLOW_ID_DYNAMIC_BASE}")
        self._flow_id = flow_id
    
    @property
    def flow_id(self) -> FlowId:
        """对应 C++ 中的 PacketFlow::flow_id()"""
        return self._flow_id
    
    def log_me(self) -> bool:
        """对应 C++ 中的 PacketFlow::log_me()"""
        return self._logger is not None


class VirtualQueue(ABC):
    """
    虚拟队列 - 对应 network.h/cpp 中的 VirtualQueue 类
    
    队列的抽象接口
    """
    
    @abstractmethod
    def completed_service(self, packet: 'Packet') -> None:
        """
        对应 C++ 中的 VirtualQueue::completedService()
        数据包服务完成时的回调
        """
        pass


# 泛型类型变量，用于 PacketDB
P = TypeVar('P', bound='Packet')


class PacketDB(Generic[P]):
    """
    数据包数据库 - 对应 network.h 中的 PacketDB 模板类
    
    为了提高速度，保持所有已分配数据包的数据库
    这样我们不需要为每个新包进行malloc，可以重用旧包
    """
    
    def __init__(self):
        """对应 C++ 构造函数 PacketDB() : _alloc_count(0)"""
        self._freelist: List[P] = []  # 对应 vector<P*> _freelist
        self._alloc_count = 0
    
    def __del__(self):
        """对应 C++ 析构函数，打印统计信息"""
        # print(f"Pkt count: {self._alloc_count}")
        # print(f"Pkt mem used: {self._alloc_count * size_of_packet}")
        pass
    
    def alloc_packet(self, packet_class) -> P:
        """
        对应 C++ 中的 PacketDB::allocPacket()
        分配数据包
        """
        if not self._freelist:
            p = packet_class()
            p.inc_ref_count()
            self._alloc_count += 1
            return p
        else:
            p = self._freelist.pop()
            p.inc_ref_count()
            return p
    
    def free_packet(self, pkt: P) -> None:
        """
        对应 C++ 中的 PacketDB::freePacket()
        释放数据包
        """
        assert pkt.ref_count >= 1
        pkt.dec_ref_count()
        
        if pkt.ref_count <= 0:
            self._freelist.append(pkt)


class RouteWithReverse:
    """
    带反向路由的路由类
    对应 C++ 中路由的 reverse() 方法
    """
    
    def __init__(self, forward_route: Route):
        self._forward = forward_route
        self._reverse = None
    
    def __getitem__(self, index):
        return self._forward[index]
    
    def __len__(self):
        return len(self._forward)
    
    def at(self, index):
        """对应 C++ 中的 at() 方法"""
        return self._forward[index]
    
    def size(self):
        """对应 C++ 中的 size() 方法"""
        return len(self._forward)
    
    def reverse(self) -> 'RouteWithReverse':
        """对应 C++ 中的 Route::reverse() 方法"""
        if self._reverse is None:
            reversed_route = list(reversed(self._forward))
            self._reverse = RouteWithReverse(reversed_route)
        return self._reverse


class Packet(ABC):
    """
    数据包基类 - 对应 network.h/cpp 中的 Packet 类
    
    所有数据包类型的基类，定义了数据包的基本属性和行为
    """
    
    # 对应 C++ 中的静态成员变量
    _data_packet_size: int = DEFAULT_DATA_PACKET_SIZE
    _packet_size_fixed: bool = False
    _default_flow: Optional[PacketFlow] = None
    
    def __init__(self):
        # 对应 C++ 构造函数中的初始化
        # _is_header = false; _bounced = false; _type = IP; _flags = 0; 
        # _refcount = 0; _dst = UINT32_MAX; _pathid = UINT32_MAX; 
        # _direction = NONE; _ingressqueue = NULL;
        self._is_header = False
        self._bounced = False
        self._type = PacketType.IP
        self._flags = 0
        self._refcount = 0
        self._dst = 0xFFFFFFFF  # UINT32_MAX
        self._pathid = 0xFFFFFFFF  # UINT32_MAX
        self._direction = PacketDirection.NONE
        self._ingress_queue = None
        
        # 路由相关
        self._route: Optional[RouteWithReverse] = None
        self._nexthop = 0
        self._oldnexthop = 0
        self._next_routed_hop: Optional['PacketSink'] = None
        
        # 数据包属性
        self._size = 0
        self._oldsize = 0
        self._id = 0
        self._flow: Optional[PacketFlow] = None
        self._path_len = 0
    
    def free(self) -> None:
        """
        对应 C++ 中的 Packet::free()
        释放数据包资源
        """
        # C++版本中free()是空实现，由子类重写
        pass
    
    @classmethod
    def set_packet_size(cls, packet_size: int) -> None:
        """
        对应 C++ 中的 Packet::set_packet_size()
        设置默认数据包大小
        """
        if cls._packet_size_fixed:
            raise RuntimeError("Packet size has already been used and cannot be changed")
        cls._data_packet_size = packet_size
    
    @classmethod
    def data_packet_size(cls) -> int:
        """
        对应 C++ 中的 Packet::data_packet_size()
        获取数据包大小
        """
        cls._packet_size_fixed = True
        return cls._data_packet_size
    
    def send_on(self) -> 'PacketSink':
        """
        对应 C++ 中的 Packet::sendOn()
        发送数据包到下一跳
        
        完整实现路由逻辑，包括bounce机制
        """
        if self._route:
            if self._bounced:
                # 反弹包，使用反向路由 - 现在使用正确的反向路由机制
                assert self._nexthop > 0
                assert self._nexthop < self._route.size()
                assert self._nexthop < self._route.reverse().size()
                nextsink = self._route.reverse().at(self._nexthop)
                self._nexthop += 1
            else:
                # 正常路由
                assert self._nexthop < self._route.size()
                nextsink = self._route.at(self._nexthop)
                self._nexthop += 1
        elif self._next_routed_hop:
            nextsink = self._next_routed_hop
        else:
            raise RuntimeError("No route or next hop available")
        
        # 发送到下一跳
        nextsink.receive_packet(self)
        return nextsink
    
    def send_on2(self, crt_sink: VirtualQueue) -> 'PacketSink':
        """
        对应 C++ 中的 Packet::sendOn2()
        带虚拟队列参数的发送方法
        """
        if self._route:
            if self._bounced:
                assert self._nexthop > 0
                assert self._nexthop < self._route.size()
                assert self._nexthop < self._route.reverse().size()
                nextsink = self._route.reverse().at(self._nexthop)
                self._nexthop += 1
            else:
                assert self._nexthop < self._route.size()
                nextsink = self._route.at(self._nexthop)
                self._nexthop += 1
        elif self._next_routed_hop:
            nextsink = self._next_routed_hop
        else:
            raise RuntimeError("No route or next hop available")
        
        # 假设PacketSink有接受VirtualQueue参数的receivePacket重载
        nextsink.receive_packet(self, crt_sink)
        return nextsink
    
    def previous_hop(self) -> Optional['PacketSink']:
        """对应 C++ 中的 Packet::previousHop()"""
        if self._nexthop >= 2 and self._route:
            return self._route.at(self._nexthop - 2)
        return None
    
    def current_hop(self) -> Optional['PacketSink']:
        """对应 C++ 中的 Packet::currentHop()"""
        if self._nexthop >= 1 and self._route:
            return self._route.at(self._nexthop - 1)
        return None
    
    def route(self) -> Optional[RouteWithReverse]:
        """对应 C++ 中的 Packet::route()"""
        return self._route
    
    def reverse_route(self) -> Optional[RouteWithReverse]:
        """对应 C++ 中的 Packet::reverse_route()"""
        if self._route:
            return self._route.reverse()
        return None
    
    def set_next_hop(self, snk: 'PacketSink') -> None:
        """对应 C++ 中的 Packet::set_next_hop()"""
        self._next_routed_hop = snk
    
    def strip_payload(self) -> None:
        """
        对应 C++ 中的 Packet::strip_payload()
        移除数据包负载，只保留头部
        """
        assert not self._is_header
        self._is_header = True
    
    def bounce(self) -> None:
        """
        对应 C++ 中的 Packet::bounce()
        数据包反弹 - 回发给发送者
        """
        assert not self._bounced
        assert self._route, "We only implement return-to-sender on regular routes"
        self._bounced = True
        self._is_header = True
        self._nexthop = self._route.size() - self._nexthop
    
    def unbounce(self, pkt_size: int) -> None:
        """
        对应 C++ 中的 Packet::unbounce()
        取消数据包反弹，为重传清理数据包
        """
        assert self._bounced
        assert self._route, "We only implement return-to-sender on regular routes"
        
        # 清理数据包用于重传
        self._bounced = False
        self._is_header = False
        self._size = pkt_size
        self._nexthop = 0
    
    def go_up(self) -> None:
        """对应 C++ 中的 Packet::go_up()"""
        if self._direction == PacketDirection.NONE:
            self._direction = PacketDirection.UP
        elif self._direction == PacketDirection.DOWN:
            raise RuntimeError("Invalid direction transition")
    
    def go_down(self) -> None:
        """对应 C++ 中的 Packet::go_down()"""
        if self._direction == PacketDirection.UP:
            self._direction = PacketDirection.DOWN
        elif self._direction == PacketDirection.NONE:
            raise RuntimeError("Invalid direction transition")
    
    def set_direction(self, direction: str) -> None:
        """对应 C++ 中的 Packet::set_direction()"""
        if direction == self._direction:
            return
        if (self._direction == PacketDirection.NONE) or \
           (self._direction == PacketDirection.UP and direction == PacketDirection.DOWN):
            self._direction = direction
        else:
            print(f"Current direction is {self._direction} trying to change it to {direction}")
            raise RuntimeError("Invalid direction transition")
    
    @abstractmethod
    def priority(self) -> str:
        """
        对应 C++ 中的 Packet::priority()
        获取数据包优先级
        """
        pass
    
    def inc_ref_count(self) -> None:
        """对应 C++ 中的 Packet::inc_ref_count()"""
        self._refcount += 1
    
    def dec_ref_count(self) -> None:
        """对应 C++ 中的 Packet::dec_ref_count()"""
        self._refcount -= 1
        if self._refcount <= 0:
            self.free()
    
    def set_attrs(self, flow: PacketFlow, pkt_size: int, packet_id: PacketId) -> None:
        """
        对应 C++ 中的 Packet::set_attrs()
        后期绑定路由时使用
        
        精确对应C++版本的字段设置顺序和值
        """
        self._flow = flow
        self._size = pkt_size
        self._oldsize = pkt_size
        self._id = packet_id
        self._nexthop = 0
        self._oldnexthop = 0
        # //_detour = NULL;  // C++版本中已注释
        self._route = None  # 对应 C++ 中的 _route = 0
        self._is_header = False  # 对应 C++ 中的 _is_header = 0
        self._flags = 0
        self._next_routed_hop = None  # 对应 C++ 中的 _next_routed_hop = 0
    
    def set_route(self, route_or_flow, route: Optional[List['PacketSink']] = None, 
                pkt_size: Optional[int] = None, packet_id: Optional[PacketId] = None) -> None:
        """
        对应 C++ 中的多个 Packet::set_route() 重载
        """
        if isinstance(route_or_flow, PacketFlow) and route is not None:
            # set_route(PacketFlow& flow, const Route &route, int pkt_size, packetid_t id)
            # 精确对应C++版本的字段设置顺序
            self._flow = route_or_flow  # 对应 _flow = &flow
            self._size = pkt_size
            self._oldsize = pkt_size
            self._id = packet_id
            self._nexthop = 0
            self._oldnexthop = 0
            # //_detour = NULL;  // C++版本中已注释
            self._route = RouteWithReverse(route)  # 对应 _route = &route
            self._is_header = False  # 对应 _is_header = 0
            self._flags = 0
            # C++版本没有设置_path_len，但这是有益的改进
            self._path_len = len(route)
        elif isinstance(route_or_flow, list) or route_or_flow.__class__.__name__ == 'Route':
            # set_route(const Route &route) 或 set_route(const Route *route)
            self._route = RouteWithReverse(route_or_flow)
            self._nexthop = 0
            self._path_len = len(route_or_flow) if route_or_flow else 0  # 对应 C++ 中路径长度设置
        elif route_or_flow is None:
            # set_route(const Route *route=nullptr)
            self._route = None
            self._nexthop = 0
            self._path_len = 0  # 对应 C++ 中路径长度设置
        else:
            raise ValueError("Invalid arguments for set_route")
    
    def set_ingress_queue(self, ingress_queue: Optional[LosslessInputQueue]) -> None:
        """对应 C++ 中的 Packet::set_ingress_queue()"""
        assert self._ingress_queue is None
        self._ingress_queue = ingress_queue
    
    def get_ingress_queue(self) -> LosslessInputQueue:
        """对应 C++ 中的 Packet::get_ingress_queue()"""
        assert self._ingress_queue is not None
        return self._ingress_queue
    
    def clear_ingress_queue(self) -> None:
        """对应 C++ 中的 Packet::clear_ingress_queue()"""
        assert self._ingress_queue is not None
        self._ingress_queue = None
    
    def str(self) -> str:
        """
        对应 C++ 中的 Packet::str()
        返回数据包类型的字符串表示，精确对应C++版本的switch语句
        
        注意：C++版本中STRACK和STRACKACK的case有bug，返回了错误的字符串
        我们这里修复了这个bug，返回正确的字符串
        """
        # 创建映射表，对应C++版本的switch语句（修复了C++版本的bug）
        type_map = {
            PacketType.IP: "IP",
            PacketType.TCP: "TCP", 
            PacketType.TCPACK: "TCPACK",
            PacketType.TCPNACK: "TCPNACK",
            PacketType.SWIFT: "SWIFT",
            PacketType.SWIFTACK: "SWIFTACK",
            PacketType.STRACK: "STRACK",  # C++版本错误返回"SWIFT"
            PacketType.STRACKACK: "STRACKACK",  # C++版本错误返回"SWIFTACK"
            PacketType.NDP: "NDP",
            PacketType.NDPACK: "NDPACK",
            PacketType.NDPNACK: "NDPNACK", 
            PacketType.NDPPULL: "NDPPULL",
            PacketType.NDPRTS: "NDPRTS",
            PacketType.NDPLITE: "NDPLITE",
            PacketType.NDPLITEACK: "NDPLITEACK",
            PacketType.NDPLITERTS: "NDPLITERTS",
            PacketType.NDPLITEPULL: "NDPLITEPULL",
            PacketType.ETH_PAUSE: "ETHPAUSE",
            PacketType.TOFINO_TRIM: "TofinoTrimPacket",
            PacketType.ROCE: "ROCE",
            PacketType.ROCEACK: "ROCEACK",
            PacketType.ROCENACK: "ROCENACK",
            PacketType.HPCC: "HPCC",
            PacketType.HPCCACK: "HPCCACK",
            PacketType.HPCCNACK: "HPCCNACK",
            PacketType.EQDSDATA: "EQDSDATA",
            PacketType.EQDSPULL: "EQDSPULL",
            PacketType.EQDSACK: "EQDSACK",
            PacketType.EQDSNACK: "EQDSNACK",
            PacketType.EQDSRTS: "EQDSRTS"
        }
        return type_map.get(self._type, self._type)
    
    # 属性访问器
    @property
    def size(self) -> int:
        """对应 C++ 中的 Packet::size()"""
        return self._size
    
    def set_size(self, size: int) -> None:
        """对应 C++ 中的 Packet::set_size()"""
        self._size = size
    
    @property
    def type(self) -> str:
        """对应 C++ 中的 Packet::type()"""
        return self._type
    
    @property
    def header_only(self) -> bool:
        """对应 C++ 中的 Packet::header_only()"""
        return self._is_header
    
    @property
    def bounced(self) -> bool:
        """对应 C++ 中的 Packet::bounced()"""
        return self._bounced
    
    def flow(self) -> PacketFlow:
        """对应 C++ 中的 Packet::flow()"""
        if self._flow is None:
            if Packet._default_flow is None:
                Packet._default_flow = PacketFlow(None)
            return Packet._default_flow
        return self._flow
    
    @property
    def id(self) -> PacketId:
        """对应 C++ 中的 Packet::id()"""
        return self._id
    
    @property
    def flow_id(self) -> FlowId:
        """对应 C++ 中的 Packet::flow_id()"""
        return self.flow().flow_id
    
    @property
    def dst(self) -> int:
        """对应 C++ 中的 Packet::dst()"""
        return self._dst
    
    def set_dst(self, value: int) -> None:
        """对应 C++ 中的 Packet::set_dst()"""
        self._dst = value
    
    @property
    def pathid(self) -> int:
        """对应 C++ 中的 Packet::pathid()"""
        return self._pathid
    
    def set_pathid(self, value: int) -> None:
        """对应 C++ 中的 Packet::set_pathid()"""
        self._pathid = value
    
    @property
    def direction(self) -> str:
        """对应 C++ 中的 Packet::get_direction()"""
        return self._direction
    
    @property
    def flags(self) -> int:
        """对应 C++ 中的 Packet::flags()"""
        return self._flags
    
    def set_flags(self, value: int) -> None:
        """对应 C++ 中的 Packet::set_flags()"""
        self._flags = value
    
    @property
    def nexthop(self) -> int:
        """对应 C++ 中的 Packet::nexthop()"""
        return self._nexthop
    
    @property
    def path_len(self) -> int:
        """对应 C++ 中的 Packet::path_len()"""
        return self._path_len
    
    @property
    def ref_count(self) -> int:
        """对应 C++ 中的 Packet::ref_count()"""
        return self._refcount


class PacketSink(ABC):
    """
    数据包接收器 - 对应 network.h/cpp 中的 PacketSink 类
    
    所有能够接收数据包的组件都应该继承此类
    """
    
    def __init__(self, name: str = "PacketSink"):
        self._name = name
        self._remote_endpoint: Optional['PacketSink'] = None
    
    @abstractmethod
    def receive_packet(self, packet: Packet, virtual_queue: Optional[VirtualQueue] = None) -> None:
        """
        对应 C++ 中的 PacketSink::receivePacket()
        接收数据包
        
        Args:
            packet: 接收的数据包
            virtual_queue: 可选的虚拟队列参数（对应C++的重载版本）
        """
        pass
    
    @abstractmethod
    def nodename(self) -> str:
        """
        对应 C++ 中的 PacketSink::nodename()
        返回节点名称 - 必须由子类实现
        """
        pass
    
    def set_remote_endpoint(self, endpoint: 'PacketSink') -> None:
        """
        对应 C++ 中的 PacketSink::setRemoteEndpoint()
        设置远程端点
        """
        self._remote_endpoint = endpoint
    
    def set_remote_endpoint2(self, endpoint: 'PacketSink') -> None:
        """
        对应 C++ 中的 PacketSink::setRemoteEndpoint2()
        双向设置远程端点
        """
        self._remote_endpoint = endpoint
        endpoint.set_remote_endpoint(self)
    
    def get_remote_endpoint(self) -> Optional['PacketSink']:
        """对应 C++ 中的 PacketSink::getRemoteEndpoint()"""
        return self._remote_endpoint


# 在模块末尾初始化静态成员变量，对应 C++ network.cpp 中的初始化
# int Packet::_data_packet_size = DEFAULTDATASIZE;
# bool Packet::_packet_size_fixed = false;
# PacketFlow Packet::_defaultFlow(nullptr);
Packet._data_packet_size = DEFAULT_DATA_PACKET_SIZE
Packet._packet_size_fixed = False
Packet._default_flow = PacketFlow(None)

# 对应 C++ 中的 flowid_t PacketFlow::_max_flow_id = FLOW_ID_DYNAMIC_BASE;
PacketFlow._max_flow_id = FLOW_ID_DYNAMIC_BASE