"""
Constants and enumerations for datacenter module

Extracted from main.h and fat_tree_topology.h in HTSim C++ implementation
"""

from enum import Enum, auto


class QueueType(Enum):
    """Queue types for datacenter networks"""
    UNDEFINED = auto()
    RANDOM = auto()
    ECN = auto()
    COMPOSITE = auto()
    PRIORITY = auto()
    CTRL_PRIO = auto()
    FAIR_PRIO = auto()
    LOSSLESS = auto()
    LOSSLESS_INPUT = auto()
    LOSSLESS_INPUT_ECN = auto()
    COMPOSITE_ECN = auto()
    COMPOSITE_ECN_LB = auto()
    SWIFT_SCHEDULER = auto()
    ECN_PRIO = auto()
    AEOLUS = auto()
    AEOLUS_ECN = auto()


class LinkDirection(Enum):
    """Link direction in datacenter networks"""
    UPLINK = auto()
    DOWNLINK = auto()


class SwitchTier(Enum):
    """Switch tiers in Fat-tree topology"""
    TOR_TIER = 0    # Top of Rack
    AGG_TIER = 1    # Aggregation
    CORE_TIER = 2   # Core


# Default network parameters
HOST_NIC_SPEED = 100000  # Host NIC speed in Mbps (100Gbps)
CORE_TO_HOST_RATIO = 4   # Oversubscription ratio

# Default buffer sizes (in packets)
DEFAULT_BUFFER_SIZE = 100
RANDOM_BUFFER = 3
FEEDER_BUFFER = 2000

# Common datacenter configurations
DEFAULT_PACKET_SIZE = 1500  # bytes
DEFAULT_MSS = 1460         # bytes (TCP MSS)
DEFAULT_HEADER_SIZE = 40   # bytes (IP + TCP headers)

# Fat-tree specific constants
DEFAULT_K = 4  # k-parameter for k-ary fat-tree (k must be even)

# Timing constants
LINK_LATENCY_MODERN = 10000      # 10ns in picoseconds
SWITCH_LATENCY_MODERN = 100000   # 100ns in picoseconds
PROPAGATION_DELAY = 1000000      # 1μs in picoseconds per 200m