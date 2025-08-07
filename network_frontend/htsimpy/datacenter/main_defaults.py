"""
Default parameter settings for datacenter simulations

Corresponds to default values in main_roce.cpp, main_ndp.cpp, etc.
"""

from ..core.network import Packet
from ..queues.lossless_input_queue import LosslessInputQueue
from ..queues.lossless_output_queue import LosslessOutputQueue

def init_lossless_defaults():
    """
    Initialize default settings for lossless queues
    
    Corresponds to main_roce.cpp lines 304-305:
    LosslessInputQueue::_high_threshold = Packet::data_packet_size()*high_pfc;
    LosslessInputQueue::_low_threshold = Packet::data_packet_size()*low_pfc;
    
    Where high_pfc = 15 and low_pfc = 12 (line 69)
    """
    # PFC thresholds from main_roce.cpp
    high_pfc = 15  # packets
    low_pfc = 12   # packets
    
    # Set thresholds based on packet size
    high_threshold = Packet.data_packet_size() * high_pfc
    low_threshold = Packet.data_packet_size() * low_pfc
    
    # Set for both input and output queues
    LosslessInputQueue.set_thresholds(low_threshold, high_threshold)
    LosslessOutputQueue.set_thresholds(low_threshold, high_threshold)


# Default values from main_roce.cpp
DEFAULT_QUEUE_SIZE_PACKETS = 15  # DEFAULT_QUEUE_SIZE in main_roce.cpp line 38
DEFAULT_NODES = 432              # DEFAULT_NODES in main_roce.cpp line 37
DEFAULT_PACKET_SIZE = 9000       # int packet_size = 9000; line 55
DEFAULT_LINK_SPEED_MBPS = 10000  # Typical for datacenter (10Gbps)
DEFAULT_HOP_LATENCY_US = 1       # uint32_t RTT = 1; line 36
DEFAULT_SWITCH_LATENCY_US = 0    # simtime_picosec switch_latency = timeFromUs((uint32_t)0); line 62

# Queue size in bytes
DEFAULT_QUEUE_SIZE_BYTES = DEFAULT_QUEUE_SIZE_PACKETS * DEFAULT_PACKET_SIZE