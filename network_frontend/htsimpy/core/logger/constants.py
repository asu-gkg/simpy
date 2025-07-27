"""
Logger Constants - 日志常量

对应文件: loggers.cpp (常量定义)
功能: 定义各种协议特定的常量和标志位

包含的常量:
- NDP协议相关常量
- RoCE协议相关常量  
- HPCC协议相关常量
"""

# ========================= NDP 相关常量 =========================
# 对应 loggers.cpp 中的 NDP 常量定义

NDP_IS_ACK = 1 << 31
NDP_IS_NACK = 1 << 30
NDP_IS_PULL = 1 << 29
NDP_IS_HEADER = 1 << 28
NDP_IS_LASTDATA = 1 << 27

# ========================= RoCE 相关常量 =========================
# 对应 loggers.cpp 中的 RoCE 常量定义

ROCE_IS_ACK = 1 << 31
ROCE_IS_NACK = 1 << 30
ROCE_IS_HEADER = 1 << 28
ROCE_IS_LASTDATA = 1 << 27

# ========================= HPCC 相关常量 =========================
# 对应 loggers.cpp 中的 HPCC 常量定义

HPCC_IS_ACK = 1 << 31
HPCC_IS_NACK = 1 << 30
HPCC_IS_HEADER = 1 << 28
HPCC_IS_LASTDATA = 1 << 27