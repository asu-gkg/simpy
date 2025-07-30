"""
TCPPacket - TCP Data Packet

对应文件: tcppacket.h/cpp
功能: TCP协议数据包实现

主要类:
- TCPPacket: TCP数据包类，对应 C++ TcpPacket
- TcpAck: TCP确认包类，对应 C++ TcpAck

C++对应关系:
- TcpPacket::newpkt() -> TCPPacket.newpkt()
- TcpPacket::new_syn_pkt() -> TCPPacket.new_syn_pkt()
- TcpAck::newpkt() -> TcpAck.newpkt()
"""

from typing import Optional, List
from .base_packet import BasePacket
from ..core.network import PacketFlow, Route, Packet
import sys

# 对应 C++ 中的类型定义
seq_t = int  # typedef uint64_t seq_t


class PacketDB:
    """
    数据包数据库 - 对应 C++ PacketDB<T> 模板类
    
    简化的包复用机制
    """
    
    def __init__(self, packet_class):
        self._packet_class = packet_class
        self._free_packets = []
    
    def allocPacket(self):
        """分配数据包 - 对应 C++ PacketDB::allocPacket()"""
        if self._free_packets:
            return self._free_packets.pop()
        else:
            return self._packet_class()
    
    def freePacket(self, packet):
        """释放数据包 - 对应 C++ PacketDB::freePacket()"""
        # 注意：C++版本不重置包状态，只是放回空闲列表
        self._free_packets.append(packet)


class TCPPacket(Packet):
    """
    TCP数据包类 - 对应 tcppacket.h/cpp 中的 TcpPacket 类
    
    实现TCP协议的数据包格式和功能，完全按照 C++ 版本复现
    """
    
    # 对应 C++ static PacketDB<TcpPacket> _packetdb
    _packetdb = None
    
    def __init__(self):
        """初始化TCP数据包 - 对应 C++ TcpPacket 构造函数"""
        super().__init__()
        
        # 对应 C++ TcpPacket 成员变量
        self._seqno = 0        # seq_t _seqno
        self._data_seqno = 0   # seq_t _data_seqno
        self._syn = False      # bool _syn
        self._ts = 0           # simtime_picosec _ts
        
        # 初始化包数据库（如果还没有初始化）
        if TCPPacket._packetdb is None:
            TCPPacket._packetdb = PacketDB(TCPPacket)
    
    # 注意：C++版本没有_reset方法，我们也不应该有
    
    @staticmethod
    def newpkt(flow: PacketFlow, route: Route, seqno: seq_t, dataseqno: seq_t, size: int):
        """
        创建新的TCP数据包 - 对应 C++ TcpPacket::newpkt()
        
        Args:
            flow: 数据包流
            route: 路由
            seqno: 序列号
            dataseqno: 数据序列号
            size: 包大小
            
        Returns:
            TCP数据包实例
        """
        # 确保PacketDB已初始化
        if TCPPacket._packetdb is None:
            TCPPacket._packetdb = PacketDB(TCPPacket)
        
        p = TCPPacket._packetdb.allocPacket()
        p.set_route(flow, route, size, seqno + size - 1)  # TCP序列号是包的第一个字节，用最后一个字节标识包
        p._type = "TCP"
        p._seqno = seqno
        p._data_seqno = dataseqno
        p._syn = False
        # 确保路由信息正确设置
        p._route = route
        p._nexthop = 0
        return p
    
    @staticmethod
    def newpkt_simple(flow: PacketFlow, route: Route, seqno: seq_t, size: int):
        """
        创建新的TCP数据包（简化版本）- 对应 C++ TcpPacket::newpkt() 重载
        
        Args:
            flow: 数据包流
            route: 路由
            seqno: 序列号
            size: 包大小
            
        Returns:
            TCP数据包实例
        """
        return TCPPacket.newpkt(flow, route, seqno, 0, size)
    
    @staticmethod
    def new_syn_pkt(flow: PacketFlow, route: Route, seqno: seq_t, size: int):
        """
        创建新的SYN数据包 - 对应 C++ TcpPacket::new_syn_pkt()
        
        Args:
            flow: 数据包流
            route: 路由
            seqno: 序列号
            size: 包大小
            
        Returns:
            SYN数据包实例
        """
        p = TCPPacket.newpkt(flow, route, seqno, 0, size)
        p._syn = True
        # 确保路由信息正确设置（已经在newpkt中设置了）
        return p
    
    def free(self) -> None:
        """
        释放数据包 - 对应 C++ TcpPacket::free()
        """
        TCPPacket._packetdb.freePacket(self)
    
    def seqno(self) -> seq_t:
        """
        获取序列号 - 对应 C++ TcpPacket::seqno()
        
        Returns:
            序列号
        """
        return self._seqno
    
    def data_seqno(self) -> seq_t:
        """
        获取数据序列号 - 对应 C++ TcpPacket::data_seqno()
        
        Returns:
            数据序列号
        """
        return self._data_seqno
    
    def ts(self) -> int:
        """
        获取时间戳 - 对应 C++ TcpPacket::ts()
        
        Returns:
            时间戳
        """
        return self._ts
    
    def set_ts(self, ts: int) -> None:
        """
        设置时间戳 - 对应 C++ TcpPacket::set_ts()
        
        Args:
            ts: 时间戳
        """
        self._ts = ts
    
    def priority(self) -> str:
        """
        获取数据包优先级 - 对应 C++ TcpPacket::priority()
        
        Returns:
            优先级（低优先级）
        """
        return "PRIO_LO"
    
    def is_syn(self) -> bool:
        """判断是否为SYN包"""
        return self._syn
    
    def sendOn(self) -> None:
        """发送数据包 - 对应 C++ TcpPacket::sendOn()"""
        # 调用父类的正确路由发送机制
        self.send_on()
    
    def flags(self) -> int:
        """获取TCP标志位 - 简化实现"""
        return 0x02 if self._syn else 0
    
    def size(self) -> int:
        """获取包大小"""
        return getattr(self, '_size', 1500)


class TcpAck(Packet):
    """
    TCP确认包类 - 对应 tcppacket.h/cpp 中的 TcpAck 类
    
    实现TCP协议的确认包格式和功能，完全按照 C++ 版本复现
    """
    
    # 对应 C++ const static int ACKSIZE=40
    ACKSIZE = 40
    
    # 对应 C++ static PacketDB<TcpAck> _packetdb
    _packetdb = None
    
    def __init__(self):
        """初始化TCP确认包 - 对应 C++ TcpAck 构造函数"""
        super().__init__()
        
        # 对应 C++ TcpAck 成员变量
        self._seqno = 0       # seq_t _seqno
        self._ackno = 0       # seq_t _ackno
        self._data_ackno = 0  # seq_t _data_ackno
        self._ts = 0          # simtime_picosec _ts
        
        # 初始化包数据库（如果还没有初始化）
        if TcpAck._packetdb is None:
            TcpAck._packetdb = PacketDB(TcpAck)
    
    # 注意：C++版本没有_reset方法，我们也不应该有
    
    @staticmethod
    def newpkt(flow: PacketFlow, route: Route, seqno: seq_t, ackno: seq_t, dackno: seq_t):
        """
        创建新的TCP确认包 - 对应 C++ TcpAck::newpkt()
        
        Args:
            flow: 数据包流
            route: 路由
            seqno: 序列号
            ackno: 确认号
            dackno: 数据确认号
            
        Returns:
            TCP确认包实例
        """
        # 确保PacketDB已初始化
        if TcpAck._packetdb is None:
            TcpAck._packetdb = PacketDB(TcpAck)
        
        p = TcpAck._packetdb.allocPacket()
        p.set_route(flow, route, TcpAck.ACKSIZE, ackno)
        p._type = "TCPACK"
        p._seqno = seqno
        p._ackno = ackno
        p._data_ackno = dackno
        # 确保路由信息正确设置
        p._route = route
        p._nexthop = 0
        return p
    
    @staticmethod
    def newpkt_simple(flow: PacketFlow, route: Route, seqno: seq_t, ackno: seq_t):
        """
        创建新的TCP确认包（简化版本）- 对应 C++ TcpAck::newpkt() 重载
        
        Args:
            flow: 数据包流
            route: 路由
            seqno: 序列号
            ackno: 确认号
            
        Returns:
            TCP确认包实例
        """
        return TcpAck.newpkt(flow, route, seqno, ackno, 0)
    
    def free(self) -> None:
        """
        释放确认包 - 对应 C++ TcpAck::free()
        """
        TcpAck._packetdb.freePacket(self)
    
    def seqno(self) -> seq_t:
        """
        获取序列号 - 对应 C++ TcpAck::seqno()
        
        Returns:
            序列号
        """
        return self._seqno
    
    def ackno(self) -> seq_t:
        """
        获取确认号 - 对应 C++ TcpAck::ackno()
        
        Returns:
            确认号
        """
        return self._ackno
    
    def data_ackno(self) -> seq_t:
        """
        获取数据确认号 - 对应 C++ TcpAck::data_ackno()
        
        Returns:
            数据确认号
        """
        return self._data_ackno
    
    def ts(self) -> int:
        """
        获取时间戳 - 对应 C++ TcpAck::ts()
        
        Returns:
            时间戳
        """
        return self._ts
    
    def set_ts(self, ts: int) -> None:
        """
        设置时间戳 - 对应 C++ TcpAck::set_ts()
        
        Args:
            ts: 时间戳
        """
        self._ts = ts
    
    def priority(self) -> str:
        """
        获取数据包优先级 - 对应 C++ TcpAck::priority()
        
        Returns:
            优先级（高优先级）
        """
        return "PRIO_HI"
    
    def flow(self):
        """获取数据包流"""
        return getattr(self, '_flow', None)
    
    def sendOn(self) -> None:
        """发送确认包 - 对应 C++ TcpAck::sendOn()"""
        # 调用父类的正确路由发送机制
        self.send_on()
    
    def set_dst(self, dst: int) -> None:
        """设置目标地址"""
        self._dst = dst
    
    def set_flags(self, flags: int) -> None:
        """设置标志位"""
        self._flags = flags
    
    def flags(self) -> int:
        """获取标志位"""
        return getattr(self, '_flags', 0)


# 为了兼容性，提供一个别名
TCPPacket = TCPPacket