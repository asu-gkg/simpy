"""
Packet Types and Enums

对应文件: 各种 *packet.h 文件中的枚举定义
功能: 定义数据包类型、方向、优先级等枚举

主要枚举:
- PacketType: 对应 network.h 中的 packet_type 枚举
- PacketDirection: 对应 network.h 中的 packet_direction 枚举  
- PacketPriority: 对应 network.h 中的 Packet::PktPriority 枚举

C++对应关系:
- packet_type -> PacketType
- packet_direction -> PacketDirection
- Packet::PktPriority -> PacketPriority
"""

from enum import Enum, IntEnum


class PacketType(IntEnum):
    """
    数据包类型枚举 - 对应 network.h 中的 packet_type 枚举
    
    定义了所有支持的数据包类型
    """
    # 基础协议
    IP = 0
    TCP = 1
    TCPACK = 2
    TCPNACK = 3
    
    # Swift协议
    SWIFT = 4
    SWIFTACK = 5
    
    # STrack协议
    STRACK = 6
    STRACKACK = 7
    
    # NDP协议
    NDP = 8
    NDPACK = 9
    NDPNACK = 10
    NDPPULL = 11
    NDPRTS = 12
    
    # NDP Lite协议
    NDPLITE = 13
    NDPLITEACK = 14
    NDPLITEPULL = 15
    NDPLITERTS = 16
    
    # 以太网暂停
    ETH_PAUSE = 17
    
    # Tofino修剪
    TOFINO_TRIM = 18
    
    # RoCE协议
    ROCE = 19
    ROCEACK = 20
    ROCENACK = 21
    
    # HPCC协议
    HPCC = 22
    HPCCACK = 23
    HPCCNACK = 24
    
    # EQDS协议
    EQDSDATA = 25
    EQDSPULL = 26
    EQDSACK = 27
    EQDSNACK = 28
    EQDSRTS = 29


class PacketDirection(IntEnum):
    """
    数据包方向枚举 - 对应 network.h 中的 packet_direction 枚举
    """
    NONE = 0
    UP = 1
    DOWN = 2


class PacketPriority(IntEnum):
    """
    数据包优先级枚举 - 对应 network.h 中的 Packet::PktPriority 枚举
    """
    PRIO_LO = 0      # 低优先级
    PRIO_MID = 1     # 中优先级
    PRIO_HI = 2      # 高优先级
    PRIO_NONE = 3    # 无优先级（不经过优先级队列）


# 数据包类型到名称的映射
PACKET_TYPE_NAMES = {
    PacketType.IP: "IP",
    PacketType.TCP: "TCP",
    PacketType.TCPACK: "TCP_ACK",
    PacketType.TCPNACK: "TCP_NACK",
    PacketType.SWIFT: "SWIFT",
    PacketType.SWIFTACK: "SWIFT_ACK",
    PacketType.STRACK: "STRACK",
    PacketType.STRACKACK: "STRACK_ACK",
    PacketType.NDP: "NDP",
    PacketType.NDPACK: "NDP_ACK",
    PacketType.NDPNACK: "NDP_NACK",
    PacketType.NDPPULL: "NDP_PULL",
    PacketType.NDPRTS: "NDP_RTS",
    PacketType.NDPLITE: "NDP_LITE",
    PacketType.NDPLITEACK: "NDP_LITE_ACK",
    PacketType.NDPLITEPULL: "NDP_LITE_PULL",
    PacketType.NDPLITERTS: "NDP_LITE_RTS",
    PacketType.ETH_PAUSE: "ETH_PAUSE",
    PacketType.TOFINO_TRIM: "TOFINO_TRIM",
    PacketType.ROCE: "ROCE",
    PacketType.ROCEACK: "ROCE_ACK",
    PacketType.ROCENACK: "ROCE_NACK",
    PacketType.HPCC: "HPCC",
    PacketType.HPCCACK: "HPCC_ACK",
    PacketType.HPCCNACK: "HPCC_NACK",
    PacketType.EQDSDATA: "EQDS_DATA",
    PacketType.EQDSPULL: "EQDS_PULL",
    PacketType.EQDSACK: "EQDS_ACK",
    PacketType.EQDSNACK: "EQDS_NACK",
    PacketType.EQDSRTS: "EQDS_RTS",
}


def get_packet_type_name(packet_type: PacketType) -> str:
    """
    获取数据包类型的名称
    
    Args:
        packet_type: 数据包类型枚举值
        
    Returns:
        数据包类型的字符串名称
    """
    return PACKET_TYPE_NAMES.get(packet_type, f"UNKNOWN_{packet_type.value}")


def is_ack_packet(packet_type: PacketType) -> bool:
    """
    判断是否为ACK数据包
    
    Args:
        packet_type: 数据包类型
        
    Returns:
        如果是ACK数据包返回True，否则返回False
    """
    return packet_type in [
        PacketType.TCPACK, PacketType.SWIFTACK, PacketType.STRACKACK,
        PacketType.NDPACK, PacketType.NDPLITEACK, PacketType.ROCEACK,
        PacketType.HPCCACK, PacketType.EQDSACK
    ]


def is_nack_packet(packet_type: PacketType) -> bool:
    """
    判断是否为NACK数据包
    
    Args:
        packet_type: 数据包类型
        
    Returns:
        如果是NACK数据包返回True，否则返回False
    """
    return packet_type in [
        PacketType.TCPNACK, PacketType.NDPNACK, PacketType.NDPLITENACK,
        PacketType.ROCENACK, PacketType.HPCCNACK, PacketType.EQDSNACK
    ]


def is_pull_packet(packet_type: PacketType) -> bool:
    """
    判断是否为PULL数据包
    
    Args:
        packet_type: 数据包类型
        
    Returns:
        如果是PULL数据包返回True，否则返回False
    """
    return packet_type in [
        PacketType.NDPPULL, PacketType.NDPLITEPULL, PacketType.EQDSPULL
    ]


def is_rts_packet(packet_type: PacketType) -> bool:
    """
    判断是否为RTS数据包
    
    Args:
        packet_type: 数据包类型
        
    Returns:
        如果是RTS数据包返回True，否则返回False
    """
    return packet_type in [
        PacketType.NDPRTS, PacketType.NDPLITERTS, PacketType.EQDSRTS
    ]