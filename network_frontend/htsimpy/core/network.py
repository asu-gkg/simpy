"""
Network - 网络核心类

对应文件: network.h/cpp
功能: 定义网络仿真的核心组件

主要类:
- Packet: 数据包基类
- PacketSink: 数据包接收器接口  
- PacketFlow: 数据包流
- DataReceiver: 数据接收器接口
- VirtualQueue: 虚拟队列接口
- PacketDB: 数据包内存池

严格对应C++版本的每个函数、字段和行为
"""

from abc import ABC, abstractmethod
from typing import Optional, List, TypeVar, Generic
import sys
from enum import IntEnum

# 导入依赖
from .logger.core import Logged
from .logger.traffic import TrafficLogger

# 为了避免循环导入，使用TYPE_CHECKING
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .route import Route
else:
    # 前向声明
    class Route:
        """前向声明 - 对应route.h中的Route类"""
        pass

class LosslessInputQueue:
    """前向声明 - 对应queue_lossless_input.h中的类"""
    pass

# 类型定义 - 对应C++的typedef
PacketId = int  # typedef uint32_t packetid_t
FlowId = int    # typedef uint32_t flowid_t

# 常量定义
DEFAULTDATASIZE = 9000  # 对应main_roce.cpp中的默认值: int packet_size = 9000;
FLOW_ID_DYNAMIC_BASE = 1000000000  # 对应network.cpp中的 #define FLOW_ID_DYNAMIC_BASE 1000000000
UINT32_MAX = 0xFFFFFFFF  # 对应C++的UINT32_MAX


# 枚举定义 - 对应network.h中的typedef enum
class PacketType(IntEnum):
    """对应network.h中的packet_type枚举"""
    IP = 0
    TCP = 1
    TCPACK = 2
    TCPNACK = 3
    SWIFT = 4
    SWIFTACK = 5
    STRACK = 6
    STRACKACK = 7
    NDP = 8
    NDPACK = 9
    NDPNACK = 10
    NDPPULL = 11
    NDPRTS = 12
    NDPLITE = 13
    NDPLITEACK = 14
    NDPLITEPULL = 15
    NDPLITERTS = 16
    ETH_PAUSE = 17
    TOFINO_TRIM = 18
    ROCE = 19
    ROCEACK = 20
    ROCENACK = 21
    HPCC = 22
    HPCCACK = 23
    HPCCNACK = 24
    EQDSDATA = 25
    EQDSPULL = 26
    EQDSACK = 27
    EQDSNACK = 28
    EQDSRTS = 29


class PacketDirection(IntEnum):
    """对应network.h中的packet_direction枚举"""
    NONE = 0
    UP = 1
    DOWN = 2


class PacketPriority(IntEnum):
    """对应Packet::PktPriority枚举"""
    PRIO_LO = 0
    PRIO_MID = 1
    PRIO_HI = 2
    PRIO_NONE = 3


def print_route(route: Route) -> None:
    """
    对应network.cpp中的print_route函数
    
    void print_route(const Route& route) {
        for (size_t i = 0; i < route.size(); i++) {
            PacketSink* sink = route.at(i);
            if (i > 0) 
                cout << " -> ";
            cout << sink->nodename();
        }
        cout << endl;
    }
    """
    for i in range(route.size()):
        sink = route.at(i)
        if i > 0:
            print(" -> ", end="")
        print(sink.nodename(), end="")
    print()


class DataReceiver(Logged, ABC):
    """
    数据接收器 - 对应network.h中的DataReceiver类
    
    class DataReceiver : public Logged {
     public:
        DataReceiver(const string& name) : Logged(name) {};
        virtual ~DataReceiver(){};
        virtual uint64_t cumulative_ack()=0;
        virtual uint32_t drops()=0;
    };
    """
    
    def __init__(self, name: str):
        """对应 DataReceiver(const string& name) : Logged(name) {}"""
        super().__init__(name)
    
    @abstractmethod
    def cumulative_ack(self) -> int:
        """对应 virtual uint64_t cumulative_ack()=0;"""
        pass
    
    @abstractmethod
    def drops(self) -> int:
        """对应 virtual uint32_t drops()=0;"""
        pass


class PacketFlow(Logged):
    """
    数据包流 - 对应network.h/cpp中的PacketFlow类
    
    class PacketFlow : public Logged {
        friend class Packet;
     public:
        PacketFlow(TrafficLogger* logger);
        virtual ~PacketFlow() {};
        void set_logger(TrafficLogger* logger);
        void logTraffic(Packet& pkt, Logged& location, TrafficLogger::TrafficEvent ev);
        void set_flowid(flowid_t id);
        inline flowid_t flow_id() const {return _flow_id;}
        bool log_me() const {return _logger != NULL;}
     protected:
        static packetid_t _max_flow_id;
        flowid_t _flow_id;
        TrafficLogger* _logger;
    };
    """
    
    # 静态成员变量 - 对应 static packetid_t _max_flow_id;
    # network.cpp: flowid_t PacketFlow::_max_flow_id = FLOW_ID_DYNAMIC_BASE;
    _max_flow_id: FlowId = FLOW_ID_DYNAMIC_BASE
    
    def __init__(self, logger: Optional[TrafficLogger]):
        """
        对应PacketFlow::PacketFlow(TrafficLogger* logger)
            : Logged("PacketFlow"),
              _logger(logger)
        {
            _flow_id = _max_flow_id++;
        }
        """
        super().__init__("PacketFlow")
        self._logger = logger
        self._flow_id = PacketFlow._max_flow_id
        PacketFlow._max_flow_id += 1
    
    def set_logger(self, logger: TrafficLogger) -> None:
        """
        对应 void PacketFlow::set_logger(TrafficLogger *logger) {
            _logger = logger;
        }
        """
        self._logger = logger
    
    def logTraffic(self, pkt: 'Packet', location: Logged, ev) -> None:
        """
        对应 void PacketFlow::logTraffic(Packet& pkt, Logged& location, TrafficLogger::TrafficEvent ev) {
            if (_logger)
                _logger->logTraffic(pkt, location, ev);
        }
        """
        if self._logger:
            self._logger.logTraffic(pkt, location, ev)
    
    def set_flowid(self, id: FlowId) -> None:
        """
        对应 void PacketFlow::set_flowid(flowid_t id) {
            if (id >= FLOW_ID_DYNAMIC_BASE) {
                cerr << "Illegal flow ID - manually allocation must be less than dynamic base\n";
                assert(0);
            }
            _flow_id = id;
        }
        """
        if id >= FLOW_ID_DYNAMIC_BASE:
            print("Illegal flow ID - manually allocation must be less than dynamic base", file=sys.stderr)
            sys.exit(1)  # 对应 C++ 的 assert(0)
        self._flow_id = id
    
    def flow_id(self) -> FlowId:
        """对应 inline flowid_t flow_id() const {return _flow_id;}"""
        return self._flow_id
    
    def log_me(self) -> bool:
        """对应 bool log_me() const {return _logger != NULL;}"""
        return self._logger is not None


class VirtualQueue(ABC):
    """
    虚拟队列 - 对应network.h中的VirtualQueue类
    
    class VirtualQueue {
     public:
        VirtualQueue() { }
        virtual ~VirtualQueue() {}
        virtual void completedService(Packet& pkt) = 0;
    };
    """
    
    def __init__(self):
        """对应 VirtualQueue() { }"""
        pass
    
    @abstractmethod
    def completedService(self, pkt: 'Packet') -> None:
        """对应 virtual void completedService(Packet& pkt) = 0;"""
        pass


class PacketSink(ABC):
    """
    数据包接收器 - 对应network.h中的PacketSink类
    
    class PacketSink {
    public:
        PacketSink() { _remoteEndpoint = NULL; }
        virtual ~PacketSink() {}
        virtual void receivePacket(Packet& pkt) =0;
        virtual void receivePacket(Packet& pkt,VirtualQueue* previousHop) {
            receivePacket(pkt);
        };
        virtual void setRemoteEndpoint(PacketSink* q) {_remoteEndpoint = q;};
        virtual void setRemoteEndpoint2(PacketSink* q) {_remoteEndpoint = q;q->setRemoteEndpoint(this);};
        PacketSink* getRemoteEndpoint() {return _remoteEndpoint;}
        virtual const string& nodename()=0;
        PacketSink* _remoteEndpoint;
    };
    """
    
    def __init__(self):
        """对应 PacketSink() { _remoteEndpoint = NULL; }"""
        self._remoteEndpoint: Optional['PacketSink'] = None
    
    def setRemoteEndpoint(self, q: Optional['PacketSink']) -> None:
        """
        对应 virtual void setRemoteEndpoint(PacketSink* q) {_remoteEndpoint = q;};
        设置远程端点
        """
        self._remoteEndpoint = q
    
    def setRemoteEndpoint2(self, q: Optional['PacketSink']) -> None:
        """
        对应 virtual void setRemoteEndpoint2(PacketSink* q) {_remoteEndpoint = q;q->setRemoteEndpoint(this);};
        设置双向远程端点
        """
        self._remoteEndpoint = q
        if q is not None:
            q.setRemoteEndpoint(self)
    
    def getRemoteEndpoint(self) -> Optional['PacketSink']:
        """
        对应 PacketSink* getRemoteEndpoint() {return _remoteEndpoint;}
        获取远程端点
        """
        return self._remoteEndpoint
    
    @abstractmethod
    def receivePacket(self, pkt: 'Packet', previousHop: Optional[VirtualQueue] = None) -> None:
        """
        对应两个重载函数：
        virtual void receivePacket(Packet& pkt) =0;
        virtual void receivePacket(Packet& pkt,VirtualQueue* previousHop) {
            receivePacket(pkt);
        };
        """
        pass
    
    def setRemoteEndpoint(self, q: 'PacketSink') -> None:
        """对应 virtual void setRemoteEndpoint(PacketSink* q) {_remoteEndpoint = q;};"""
        self._remoteEndpoint = q
    
    def setRemoteEndpoint2(self, q: 'PacketSink') -> None:
        """对应 virtual void setRemoteEndpoint2(PacketSink* q) {_remoteEndpoint = q;q->setRemoteEndpoint(this);};"""
        self._remoteEndpoint = q
        q.setRemoteEndpoint(self)
    
    def getRemoteEndpoint(self) -> Optional['PacketSink']:
        """对应 PacketSink* getRemoteEndpoint() {return _remoteEndpoint;}"""
        return self._remoteEndpoint
    
    @abstractmethod
    def nodename(self) -> str:
        """对应 virtual const string& nodename()=0;"""
        pass


class Packet(ABC):
    """
    数据包基类 - 对应network.h/cpp中的Packet类
    
    严格对应C++的所有成员变量、函数和行为
    """
    
    # 静态成员变量 - 对应network.cpp中的初始化
    _data_packet_size: int = DEFAULTDATASIZE  # int Packet::_data_packet_size = DEFAULTDATASIZE;
    _packet_size_fixed: bool = False  # bool Packet::_packet_size_fixed = false;
    _defaultFlow: Optional[PacketFlow] = None  # PacketFlow Packet::_defaultFlow(nullptr);
    
    def __init__(self):
        """
        对应构造函数：
        Packet() {_is_header = false; _bounced = false; _type = IP; _flags = 0; 
                _refcount = 0; _dst = UINT32_MAX; _pathid = UINT32_MAX; 
                _direction = NONE; _ingressqueue = NULL;}
        """
        self._is_header = False
        self._bounced = False
        self._type = PacketType.IP
        self._flags = 0
        self._refcount = 0
        self._dst = UINT32_MAX
        self._pathid = UINT32_MAX
        self._direction = PacketDirection.NONE
        self._ingressqueue: Optional[LosslessInputQueue] = None
        
        # 其他成员变量（从protected部分）
        self._size = 0
        self._oldsize = 0
        self._route: Optional[Route] = None
        self._nexthop = 0
        self._oldnexthop = 0
        self._next_routed_hop: Optional[PacketSink] = None
        self._id: PacketId = 0
        self._flow: Optional[PacketFlow] = None
        self._path_len = 0
    
    def free(self) -> None:
        """
        对应 virtual void free();
        network.cpp: void Packet::free() {}
        """
        pass
    
    @staticmethod
    def set_packet_size(packet_size: int) -> None:
        """
        对应 static void set_packet_size(int packet_size) {
            assert(_packet_size_fixed == false);
            _data_packet_size = packet_size;
        }
        """
        assert Packet._packet_size_fixed == False
        Packet._data_packet_size = packet_size
    
    @staticmethod
    def data_packet_size() -> int:
        """
        对应 static int data_packet_size() {
            _packet_size_fixed = true;
            return _data_packet_size;
        }
        """
        Packet._packet_size_fixed = True
        return Packet._data_packet_size
    
    def sendOn(self) -> PacketSink:
        """
        对应 virtual PacketSink* sendOn();
        完整实现network.cpp中的sendOn函数
        """
        nextsink = None
        
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
            assert False
        
        nextsink.receivePacket(self)  # type: ignore
        return nextsink
    
    def previousHop(self) -> Optional[PacketSink]:
        """对应 virtual PacketSink* previousHop() {if (_nexthop>=2) return _route->at(_nexthop-2); else return NULL;}"""
        if self._nexthop >= 2:
            return self._route.at(self._nexthop - 2)
        else:
            return None
    
    def currentHop(self) -> Optional[PacketSink]:
        """对应 virtual PacketSink* currentHop() {if (_nexthop>=1) return _route->at(_nexthop-1); else return NULL;}"""
        if self._nexthop >= 1:
            return self._route.at(self._nexthop - 1)
        else:
            return None
    
    def sendOn2(self, crtSink: VirtualQueue) -> PacketSink:
        """
        对应 virtual PacketSink* sendOn2(VirtualQueue* crtSink);
        完整实现network.cpp中的sendOn2函数
        """
        nextsink = None
        
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
            assert False
        
        nextsink.receivePacket(self, crtSink)  # type: ignore
        return nextsink
    
    def size(self) -> int:
        """对应 uint16_t size() const {return _size;}"""
        return self._size
    
    def set_size(self, i: int) -> None:
        """对应 void set_size(int i) {_size = i;}"""
        self._size = i
    
    def type(self) -> PacketType:
        """对应 packet_type type() const {return _type;};"""
        return self._type
    
    def header_only(self) -> bool:
        """对应 bool header_only() const {return _is_header;}"""
        return self._is_header
    
    def bounced(self) -> bool:
        """对应 bool bounced() const {return _bounced;}"""
        return self._bounced
    
    def flow(self) -> PacketFlow:
        """
        对应 PacketFlow& flow() const {return *_flow;}
        注意：需要处理_flow为None的情况
        """
        if self._flow is None:
            # 初始化默认流
            if Packet._defaultFlow is None:
                Packet._defaultFlow = PacketFlow(None)
            return Packet._defaultFlow
        return self._flow
    
    def id(self) -> PacketId:
        """对应 inline const packetid_t id() const {return _id;}"""
        return self._id
    
    def flow_id(self) -> FlowId:
        """对应 inline uint32_t flow_id() const {return _flow->flow_id();}"""
        return self.flow().flow_id()
    
    def dst(self) -> int:
        """对应 inline uint32_t dst() const {return _dst;}"""
        return self._dst
    
    def set_dst(self, dst: int) -> None:
        """对应 inline void set_dst(uint32_t dst) { _dst = dst;}"""
        self._dst = dst
    
    def pathid(self) -> int:
        """对应 inline uint32_t pathid() {return _pathid;}"""
        return self._pathid
    
    def set_pathid(self, p: int) -> None:
        """对应 inline void set_pathid(uint32_t p) { _pathid = p;}"""
        self._pathid = p
    
    def route(self) -> Optional[Route]:
        """对应 const Route* route() const {return _route;}"""
        return self._route
    
    def reverse_route(self) -> Optional[Route]:
        """对应 const Route* reverse_route() const {return _route->reverse();}"""
        if self._route:
            return self._route.reverse()
        return None
    
    def set_next_hop(self, snk: PacketSink) -> None:
        """对应 inline void set_next_hop(PacketSink* snk) { _next_routed_hop = snk;}"""
        self._next_routed_hop = snk
    
    def strip_payload(self) -> None:
        """对应 virtual void strip_payload() { assert(!_is_header); _is_header = true;};"""
        assert not self._is_header
        self._is_header = True
    
    def bounce(self) -> None:
        """
        对应 virtual void bounce();
        完整实现network.cpp中的bounce函数
        """
        assert not self._bounced
        assert self._route  # we only implement return-to-sender on regular routes
        self._bounced = True
        self._is_header = True
        self._nexthop = self._route.size() - self._nexthop
    
    def unbounce(self, pktsize: int) -> None:
        """
        对应 virtual void unbounce(uint16_t pktsize);
        完整实现network.cpp中的unbounce函数
        """
        assert self._bounced
        assert self._route
        
        # clear the packet for retransmission
        self._bounced = False
        self._is_header = False
        self._size = pktsize
        self._nexthop = 0
    
    def path_len(self) -> int:
        """对应 inline uint32_t path_len() const {return _path_len;}"""
        return self._path_len
    
    def go_up(self) -> None:
        """
        对应 virtual void go_up(){ 
            if (_direction == NONE) _direction = UP; 
            else if (_direction == DOWN) abort();
        }
        """
        if self._direction == PacketDirection.NONE:
            self._direction = PacketDirection.UP
        elif self._direction == PacketDirection.DOWN:
            sys.exit(1)  # abort()
    
    def go_down(self) -> None:
        """
        对应 virtual void go_down(){ 
            if (_direction == UP) _direction = DOWN; 
            else if (_direction == NONE) abort();
        }
        """
        if self._direction == PacketDirection.UP:
            self._direction = PacketDirection.DOWN
        elif self._direction == PacketDirection.NONE:
            sys.exit(1)  # abort()
    
    def set_direction(self, d: PacketDirection) -> None:
        """
        对应 virtual void set_direction(packet_direction d)
        """
        if d == self._direction:
            return
        if (self._direction == PacketDirection.NONE) or \
           (self._direction == PacketDirection.UP and d == PacketDirection.DOWN):
            self._direction = d
        else:
            print(f"Current direction is {self._direction} trying to change it to {d}")
            sys.exit(1)  # abort()
    
    @abstractmethod
    def priority(self) -> PacketPriority:
        """对应 virtual PktPriority priority() const = 0;"""
        pass
    
    def get_direction(self) -> PacketDirection:
        """对应 virtual packet_direction get_direction() {return _direction;}"""
        return self._direction
    
    def inc_ref_count(self) -> None:
        """对应 void inc_ref_count() { _refcount++;};"""
        self._refcount += 1
    
    def dec_ref_count(self) -> None:
        """对应 void dec_ref_count() { _refcount--;};"""
        self._refcount -= 1
    
    def ref_count(self) -> int:
        """对应 int ref_count() {return _refcount;};"""
        return self._refcount
    
    def flags(self) -> int:
        """对应 inline uint32_t flags() const {return _flags;}"""
        return self._flags
    
    def set_flags(self, f: int) -> None:
        """对应 inline void set_flags(uint32_t f) {_flags = f;}"""
        self._flags = f
    
    def nexthop(self) -> int:
        """对应 uint32_t nexthop() const {return _nexthop;}"""
        return self._nexthop
    
    def set_route(self, *args) -> None:
        """
        对应三个重载的set_route函数：
        virtual void set_route(const Route &route);
        virtual void set_route(const Route *route=nullptr);
        virtual void set_route(PacketFlow& flow, const Route &route, int pkt_size, packetid_t id);
        """
        if len(args) == 1:
            # set_route(const Route &route) 或 set_route(const Route *route)
            route = args[0]
            self._route = route
            self._nexthop = 0
        elif len(args) == 4:
            # set_route(PacketFlow& flow, const Route &route, int pkt_size, packetid_t id)
            flow, route, pkt_size, id = args
            self._flow = flow
            self._size = pkt_size
            self._oldsize = pkt_size
            self._id = id
            self._nexthop = 0
            self._oldnexthop = 0
            self._route = route  # 对应 C++ _route = &route;
            self._is_header = 0
            self._flags = 0
        else:
            raise ValueError("Invalid arguments for set_route")
    
    def set_ingress_queue(self, t: LosslessInputQueue) -> None:
        """对应 void set_ingress_queue(LosslessInputQueue* t){assert(!_ingressqueue); _ingressqueue = t;}"""
        assert not self._ingressqueue
        self._ingressqueue = t
    
    def get_ingress_queue(self) -> LosslessInputQueue:
        """对应 LosslessInputQueue* get_ingress_queue(){assert(_ingressqueue); return _ingressqueue;}"""
        assert self._ingressqueue
        return self._ingressqueue
    
    def clear_ingress_queue(self) -> None:
        """对应 void clear_ingress_queue(){assert(_ingressqueue); _ingressqueue = NULL;}"""
        assert self._ingressqueue
        self._ingressqueue = None
    
    def str(self) -> str:
        """
        对应 string Packet::str() const
        完整实现network.cpp中的str函数，包括C++中的bug
        """
        type_map = {
            PacketType.IP: "IP",
            PacketType.TCP: "TCP",
            PacketType.TCPACK: "TCPACK",
            PacketType.SWIFT: "SWIFT",
            PacketType.SWIFTACK: "SWIFTACK",
            PacketType.STRACK: "SWIFT",  # C++中的bug：返回"SWIFT"而不是"STRACK"
            PacketType.STRACKACK: "SWIFTACK",  # C++中的bug：返回"SWIFTACK"而不是"STRACKACK"
            PacketType.TCPNACK: "TCPNACK",
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
            PacketType.EQDSNACK: "EQDSNACK",
            PacketType.EQDSACK: "EQDSACK",
            PacketType.EQDSPULL: "EQDSPULL",
            PacketType.EQDSRTS: "EQDSRTS"
        }
        return type_map.get(self._type, "")
    
    def set_attrs(self, flow: PacketFlow, pkt_size: int, id: PacketId) -> None:
        """
        对应 protected: void set_attrs(PacketFlow& flow, int pkt_size, packetid_t id);
        完整实现network.cpp中的set_attrs函数
        """
        self._flow = flow
        self._size = pkt_size
        self._oldsize = pkt_size
        self._id = id
        self._nexthop = 0
        self._oldnexthop = 0
        self._route = None  # 对应 _route = 0
        self._is_header = False  # 对应 _is_header = 0
        self._flags = 0
        self._next_routed_hop = None  # 对应 _next_routed_hop = 0


# PacketDB模板类的Python实现
P = TypeVar('P', bound=Packet)

class PacketDB(Generic[P]):
    """
    数据包内存池 - 对应network.h中的PacketDB模板类
    
    template<class P>
    class PacketDB {
     public:
        PacketDB() : _alloc_count(0) {}
        ~PacketDB() {}
        P* allocPacket() {...}
        void freePacket(P* pkt) {...}
     protected:
        vector<P*> _freelist;
        int _alloc_count;
    };
    """
    
    def __init__(self):
        """对应 PacketDB() : _alloc_count(0) {}"""
        self._alloc_count = 0
        self._freelist: List[P] = []  # 对应 vector<P*> _freelist
    
    def __del__(self):
        """对应析构函数，输出统计信息（但被注释掉了）"""
        # cout << "Pkt count: " << _alloc_count << endl;
        # cout << "Pkt mem used: " << _alloc_count * sizeof(P) << endl;
        pass
    
    def allocPacket(self, packet_class) -> P:
        """
        对应 P* allocPacket()
        注意：需要传入数据包类，因为Python没有C++的模板机制
        """
        if not self._freelist:  # 对应 if (_freelist.empty())
            p = packet_class()  # 对应 P* p = new P();
            p.inc_ref_count()
            self._alloc_count += 1
            return p
        else:
            p = self._freelist.pop()  # 对应 _freelist.back() 和 _freelist.pop_back()
            p.inc_ref_count()
            return p
    
    def freePacket(self, pkt: P) -> None:
        """
        对应 void freePacket(P* pkt)
        """
        assert pkt.ref_count() >= 1
        pkt.dec_ref_count()
        
        if pkt.ref_count() == 0:  # 对应 if (!pkt->ref_count())
            self._freelist.append(pkt)  # 对应 _freelist.push_back(pkt)


# 初始化静态成员变量 - 对应network.cpp中的初始化
# PacketFlow Packet::_defaultFlow(nullptr);
Packet._defaultFlow = PacketFlow(None)