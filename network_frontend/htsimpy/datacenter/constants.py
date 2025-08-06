"""
Constants and enumerations for datacenter module

Extracted from main.h and fat_tree_topology.h in HTSim C++ implementation
"""

from enum import Enum, auto

# Packet and buffer sizes
PACKET_SIZE = 1500  # Standard MTU size in bytes


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

# Queue and buffer sizes from C++ version
SWITCH_BUFFER = 97   # Switch buffer size in packets (matches C++ SWITCH_BUFFER)
RANDOM_BUFFER = 3    # Additional buffer for random queue
FEEDER_BUFFER = 1000 # Buffer size for feeders (matches C++ FEEDER_BUFFER)

# Default network speeds
HOST_NIC = 100000    # Host NIC speed in Mbps (100Gbps)
SWITCH_SPEED = 100000  # Switch port speed in Mbps

# Packet sizes
MTU = 1500           # Maximum transmission unit in bytes
MSS = 1460           # Maximum segment size (MTU - headers)
HEADER_SIZE = 40     # IP + TCP header size in bytes

# ECN thresholds
ECN_THRESH = 30      # ECN marking threshold in packets
ECN_BUFFER = 50      # ECN buffer threshold

# Common topology configurations
class TopologyConfig:
    """Common datacenter topology configurations"""
    # Small test topology
    SMALL_FAT_TREE_K = 4
    SMALL_FAT_TREE_HOSTS = 16  # k^3/4
    
    # Medium topology
    MEDIUM_FAT_TREE_K = 8
    MEDIUM_FAT_TREE_HOSTS = 128  # k^3/4
    
    # Large topology
    LARGE_FAT_TREE_K = 16
    LARGE_FAT_TREE_HOSTS = 1024  # k^3/4
    
    # CamCube configurations
    CAMCUBE_K_SMALL = 3
    CAMCUBE_K_MEDIUM = 5
    CAMCUBE_K_LARGE = 7

# Connection matrix patterns
class TrafficPattern(Enum):
    """Traffic patterns for connection matrix"""
    PERMUTATION = auto()
    RANDOM = auto()
    STRIDE = auto()
    INCAST = auto()
    OUTCAST = auto()
    MANY_TO_MANY = auto()
    HOTSPOT = auto()
    STAGGERED_RANDOM = auto()
    SEQUENTIAL = auto()
    BARRIER_SYNC = auto()

# Default traffic parameters
DEFAULT_FLOW_SIZE = 100000  # 100KB in bytes
DEFAULT_INCAST_DEGREE = 8   # Number of senders in incast
DEFAULT_OUTCAST_DEGREE = 8  # Number of receivers in outcast
DEFAULT_HOTSPOT_SIZE = 10   # Hosts per hotspot

# Failure types
class FailureType(Enum):
    """Types of failures in datacenter"""
    LINK_FAILURE = auto()
    SWITCH_FAILURE = auto()
    HOST_FAILURE = auto()
    RACK_FAILURE = auto()

# Monitoring intervals
QUEUE_SAMPLING_INTERVAL = 1000000    # 1ms in picoseconds
SWITCH_SAMPLING_INTERVAL = 10000000  # 10ms in picoseconds
FLOW_SAMPLING_INTERVAL = 100000000   # 100ms in picoseconds