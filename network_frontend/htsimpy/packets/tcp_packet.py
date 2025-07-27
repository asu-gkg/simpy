"""
TCPPacket - TCP Data Packet

对应文件: tcppacket.h/cpp
功能: TCP协议数据包实现

主要类:
- TCPPacket: TCP数据包类

C++对应关系:
- TCPPacket::set() -> TCPPacket.set()
- TCPPacket::free() -> TCPPacket.free()
- TCPPacket::sendOn() -> TCPPacket.send_on()
"""

from typing import Optional
from .base_packet import BasePacket
from ..core.packet import PacketType, PacketPriority
from ..core.network import PacketSink, PacketFlow


class TCPPacket(BasePacket):
    """
    TCP数据包类 - 对应 tcppacket.h/cpp 中的 TCPPacket 类
    
    实现TCP协议的数据包格式和功能
    """
    
    def __init__(self):
        super().__init__()
        self._type = PacketType.TCP
        
        # TCP特定字段
        self._seq_no = 0
        self._ack_no = 0
        self._window_size = 0
        self._flags = 0
        self._mss = 1460  # 默认MSS
        
        # TCP标志位
        self._syn = False
        self._ack = False
        self._fin = False
        self._rst = False
        self._psh = False
        self._urg = False
    
    def set(self, flow: PacketFlow, pkt_size: int, pkt_id: int, 
            seq_no: int, ack_no: int, window_size: int, flags: int = 0) -> None:
        """
        对应 C++ 中的 TCPPacket::set()
        设置TCP数据包属性
        
        Args:
            flow: 数据包流
            pkt_size: 数据包大小
            pkt_id: 数据包ID
            seq_no: 序列号
            ack_no: 确认号
            window_size: 窗口大小
            flags: TCP标志位
        """
        super().set(flow, pkt_size, pkt_id)
        self._seq_no = seq_no
        self._ack_no = ack_no
        self._window_size = window_size
        self._flags = flags
        
        # 解析标志位
        self._syn = bool(flags & 0x02)  # SYN
        self._ack = bool(flags & 0x10)  # ACK
        self._fin = bool(flags & 0x01)  # FIN
        self._rst = bool(flags & 0x04)  # RST
        self._psh = bool(flags & 0x08)  # PSH
        self._urg = bool(flags & 0x20)  # URG
    
    def send_on(self) -> PacketSink:
        """
        对应 C++ 中的 TCPPacket::sendOn()
        发送TCP数据包到下一跳
        
        Returns:
            下一跳的PacketSink
        """
        # TODO: 实现TCP数据包发送逻辑
        pass
    
    def priority(self) -> PacketPriority:
        """
        对应 C++ 中的 TCPPacket::priority()
        获取TCP数据包优先级
        
        Returns:
            数据包优先级
        """
        # TCP数据包通常使用中等优先级
        return PacketPriority.PRIO_MID
    
    # TCP特定方法
    def set_seq_no(self, seq_no: int) -> None:
        """设置序列号"""
        self._seq_no = seq_no
    
    def set_ack_no(self, ack_no: int) -> None:
        """设置确认号"""
        self._ack_no = ack_no
    
    def set_window_size(self, window_size: int) -> None:
        """设置窗口大小"""
        self._window_size = window_size
    
    def set_flags(self, flags: int) -> None:
        """设置TCP标志位"""
        self._flags = flags
        # 重新解析标志位
        self._syn = bool(flags & 0x02)
        self._ack = bool(flags & 0x10)
        self._fin = bool(flags & 0x01)
        self._rst = bool(flags & 0x04)
        self._psh = bool(flags & 0x08)
        self._urg = bool(flags & 0x20)
    
    def set_syn(self, syn: bool) -> None:
        """设置SYN标志"""
        if syn:
            self._flags |= 0x02
        else:
            self._flags &= ~0x02
        self._syn = syn
    
    def set_ack(self, ack: bool) -> None:
        """设置ACK标志"""
        if ack:
            self._flags |= 0x10
        else:
            self._flags &= ~0x10
        self._ack = ack
    
    def set_fin(self, fin: bool) -> None:
        """设置FIN标志"""
        if fin:
            self._flags |= 0x01
        else:
            self._flags &= ~0x01
        self._fin = fin
    
    def set_rst(self, rst: bool) -> None:
        """设置RST标志"""
        if rst:
            self._flags |= 0x04
        else:
            self._flags &= ~0x04
        self._rst = rst
    
    # 属性访问器
    @property
    def seq_no(self) -> int:
        """获取序列号"""
        return self._seq_no
    
    @property
    def ack_no(self) -> int:
        """获取确认号"""
        return self._ack_no
    
    @property
    def window_size(self) -> int:
        """获取窗口大小"""
        return self._window_size
    
    @property
    def flags(self) -> int:
        """获取TCP标志位"""
        return self._flags
    
    @property
    def syn(self) -> bool:
        """获取SYN标志"""
        return self._syn
    
    @property
    def ack(self) -> bool:
        """获取ACK标志"""
        return self._ack
    
    @property
    def fin(self) -> bool:
        """获取FIN标志"""
        return self._fin
    
    @property
    def rst(self) -> bool:
        """获取RST标志"""
        return self._rst
    
    @property
    def psh(self) -> bool:
        """获取PSH标志"""
        return self._psh
    
    @property
    def urg(self) -> bool:
        """获取URG标志"""
        return self._urg
    
    def is_syn_packet(self) -> bool:
        """判断是否为SYN包"""
        return self._syn and not self._ack
    
    def is_ack_packet(self) -> bool:
        """判断是否为ACK包"""
        return self._ack and not self._syn
    
    def is_syn_ack_packet(self) -> bool:
        """判断是否为SYN-ACK包"""
        return self._syn and self._ack
    
    def is_fin_packet(self) -> bool:
        """判断是否为FIN包"""
        return self._fin
    
    def is_rst_packet(self) -> bool:
        """判断是否为RST包"""
        return self._rst
    
    def __str__(self) -> str:
        """字符串表示"""
        flags_str = []
        if self._syn:
            flags_str.append("SYN")
        if self._ack:
            flags_str.append("ACK")
        if self._fin:
            flags_str.append("FIN")
        if self._rst:
            flags_str.append("RST")
        if self._psh:
            flags_str.append("PSH")
        if self._urg:
            flags_str.append("URG")
        
        flags_str = ",".join(flags_str) if flags_str else "NONE"
        
        return (f"TCPPacket(id={self.id}, seq={self._seq_no}, ack={self._ack_no}, "
                f"window={self._window_size}, flags={flags_str})")