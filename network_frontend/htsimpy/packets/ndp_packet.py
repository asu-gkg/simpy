"""
NDPPacket - NDP Data Packet

对应文件: ndppacket.h/cpp
功能: NDP协议数据包实现

主要类:
- NDPPacket: NDP数据包类

C++对应关系:
- NDPPacket::set() -> NDPPacket.set()
- NDPPacket::free() -> NDPPacket.free()
- NDPPacket::sendOn() -> NDPPacket.send_on()
"""

from typing import Optional
from .base_packet import BasePacket
from ..core.packet import PacketType, PacketPriority
from ..core.network import PacketSink, PacketFlow


class NDPPacket(BasePacket):
    """
    NDP数据包类 - 对应 ndppacket.h/cpp 中的 NDPPacket 类
    
    实现NDP (Network Data Plane) 协议的数据包格式和功能
    """
    
    def __init__(self):
        super().__init__()
        self._type = PacketType.NDP
        
        # NDP特定字段
        self._seq_no = 0
        self._ack_no = 0
        self._window_size = 0
        self._flags = 0
        self._pull_no = 0
        self._rts_no = 0
        
        # NDP标志位
        self._is_pull = False
        self._is_rts = False
        self._is_ack = False
        self._is_nack = False
    
    def set(self, flow: PacketFlow, pkt_size: int, pkt_id: int, 
            seq_no: int, ack_no: int, window_size: int, flags: int = 0) -> None:
        """
        对应 C++ 中的 NDPPacket::set()
        设置NDP数据包属性
        
        Args:
            flow: 数据包流
            pkt_size: 数据包大小
            pkt_id: 数据包ID
            seq_no: 序列号
            ack_no: 确认号
            window_size: 窗口大小
            flags: NDP标志位
        """
        super().set(flow, pkt_size, pkt_id)
        self._seq_no = seq_no
        self._ack_no = ack_no
        self._window_size = window_size
        self._flags = flags
        
        # 解析标志位
        self._is_pull = bool(flags & 0x01)
        self._is_rts = bool(flags & 0x02)
        self._is_ack = bool(flags & 0x04)
        self._is_nack = bool(flags & 0x08)
    
    def send_on(self) -> PacketSink:
        """
        对应 C++ 中的 NDPPacket::sendOn()
        发送NDP数据包到下一跳
        
        Returns:
            下一跳的PacketSink
        """
        # TODO: 实现NDP数据包发送逻辑
        pass
    
    def priority(self) -> PacketPriority:
        """
        对应 C++ 中的 NDPPacket::priority()
        获取NDP数据包优先级
        
        Returns:
            数据包优先级
        """
        # NDP数据包通常使用中等优先级
        return PacketPriority.PRIO_MID
    
    # NDP特定方法
    def set_seq_no(self, seq_no: int) -> None:
        """设置序列号"""
        self._seq_no = seq_no
    
    def set_ack_no(self, ack_no: int) -> None:
        """设置确认号"""
        self._ack_no = ack_no
    
    def set_window_size(self, window_size: int) -> None:
        """设置窗口大小"""
        self._window_size = window_size
    
    def set_pull_no(self, pull_no: int) -> None:
        """设置PULL号"""
        self._pull_no = pull_no
    
    def set_rts_no(self, rts_no: int) -> None:
        """设置RTS号"""
        self._rts_no = rts_no
    
    def set_flags(self, flags: int) -> None:
        """设置NDP标志位"""
        self._flags = flags
        # 重新解析标志位
        self._is_pull = bool(flags & 0x01)
        self._is_rts = bool(flags & 0x02)
        self._is_ack = bool(flags & 0x04)
        self._is_nack = bool(flags & 0x08)
    
    def set_pull(self, is_pull: bool) -> None:
        """设置PULL标志"""
        if is_pull:
            self._flags |= 0x01
        else:
            self._flags &= ~0x01
        self._is_pull = is_pull
    
    def set_rts(self, is_rts: bool) -> None:
        """设置RTS标志"""
        if is_rts:
            self._flags |= 0x02
        else:
            self._flags &= ~0x02
        self._is_rts = is_rts
    
    def set_ack(self, is_ack: bool) -> None:
        """设置ACK标志"""
        if is_ack:
            self._flags |= 0x04
        else:
            self._flags &= ~0x04
        self._is_ack = is_ack
    
    def set_nack(self, is_nack: bool) -> None:
        """设置NACK标志"""
        if is_nack:
            self._flags |= 0x08
        else:
            self._flags &= ~0x08
        self._is_nack = is_nack
    
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
    def pull_no(self) -> int:
        """获取PULL号"""
        return self._pull_no
    
    @property
    def rts_no(self) -> int:
        """获取RTS号"""
        return self._rts_no
    
    @property
    def flags(self) -> int:
        """获取NDP标志位"""
        return self._flags
    
    @property
    def is_pull(self) -> bool:
        """获取PULL标志"""
        return self._is_pull
    
    @property
    def is_rts(self) -> bool:
        """获取RTS标志"""
        return self._is_rts
    
    @property
    def is_ack(self) -> bool:
        """获取ACK标志"""
        return self._is_ack
    
    @property
    def is_nack(self) -> bool:
        """获取NACK标志"""
        return self._is_nack
    
    def is_data_packet(self) -> bool:
        """
        判断是否为数据包
        
        Returns:
            如果是数据包返回True，否则返回False
        """
        return not (self._is_pull or self._is_rts or self._is_ack or self._is_nack)
    
    def is_pull_packet(self) -> bool:
        """判断是否为PULL包"""
        return self._is_pull
    
    def is_rts_packet(self) -> bool:
        """判断是否为RTS包"""
        return self._is_rts
    
    def is_ack_packet(self) -> bool:
        """判断是否为ACK包"""
        return self._is_ack
    
    def is_nack_packet(self) -> bool:
        """判断是否为NACK包"""
        return self._is_nack
    
    def __str__(self) -> str:
        """字符串表示"""
        flags_str = []
        if self._is_pull:
            flags_str.append("PULL")
        if self._is_rts:
            flags_str.append("RTS")
        if self._is_ack:
            flags_str.append("ACK")
        if self._is_nack:
            flags_str.append("NACK")
        
        flags_str = ",".join(flags_str) if flags_str else "DATA"
        
        return (f"NDPPacket(id={self.id}, seq={self._seq_no}, ack={self._ack_no}, "
                f"window={self._window_size}, flags={flags_str})")