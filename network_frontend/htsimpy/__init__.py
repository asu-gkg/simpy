"""
HTSimPy - Python implementation of htsim network simulator for SimAI integration

This module provides a Python implementation of the htsim network simulator,
designed to integrate with the SimAI system through the AstraNetworkAPI interface.

Main components:
- EventList: Discrete event simulation scheduler (对应 eventlist.h/cpp)
- Network: Network abstraction layer (对应 network.h/cpp)
- Packet: Base packet classes (对应各种 *packet.h 文件)
- Protocols: NDP, TCP, Swift, RoCE, HPCC implementations
- Queues: Various queue implementations
- Topology: Network topology builders
"""

__version__ = "0.1.0"
__author__ = "HTSimPy Team"

# Core components
from .core.eventlist import EventList, EventSource
from .core.network import Packet, PacketSink, PacketFlow
from .core.packet import PacketType, PacketDirection, PacketPriority
from .core.route import Route
from .core.routetable import RouteTable
from .core.config import SimulationConfig
from .core.logger import Logger

# Queue components
from .queues.fifo_queue import FIFOQueue

# API interface
from .api.htsimpy_network import HTSimPyNetwork
from .api.config_parser import HTSimPyConfig

__all__ = [
    # Core components
    'EventList', 'EventSource',
    'Packet', 'PacketSink', 'PacketFlow',
    'PacketType', 'PacketDirection', 'PacketPriority',
    'Route', 'RouteTable', 'SimulationConfig', 'Logger',
    
    # Queue components
    'FIFOQueue',
    
    # API interface
    'HTSimPyNetwork', 'HTSimPyConfig',
]