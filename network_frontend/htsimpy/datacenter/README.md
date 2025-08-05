# HTSimPy Datacenter Module

This module provides comprehensive data center network simulation capabilities, including various topologies, traffic patterns, and control mechanisms.

## Overview

The datacenter module implements:

### Network Topologies
- **Fat-tree**: K-ary fat-tree topology with full bisection bandwidth
- **VL2 (Virtual Layer 2)**: Microsoft's VL2 architecture with Valiant Load Balancing
- **BCube**: Server-centric BCube topology with multiple NICs per server
- **DragonFly**: High-radix DragonFly topology with global links
- **Oversubscribed Fat-tree**: Fat-tree with oversubscription at edge
- **Star**: Simple star topology for testing
- **Generic**: Load arbitrary topologies from configuration files

### Traffic Patterns
- **Incast**: Many-to-one communication pattern
- **Short flows**: Poisson arrival process with various flow size distributions
- **All-to-all**: Full mesh communication
- **Permutation**: One-to-one mapping
- **Random**: Random source-destination pairs

### Control Mechanisms
- **FirstFit**: Path allocation using first-fit algorithm
- **Subflow Control**: Dynamic MPTCP subflow management
- **Connection Matrix**: Traffic pattern generation and management

## Quick Start

### Basic TCP Simulation

```python
from htsimpy.core.eventlist import EventList
from htsimpy.core.logger.logfile import Logfile
from htsimpy.datacenter import FatTreeTopology, ConnectionMatrix
from htsimpy.protocols.tcp import TcpSrc, TcpSink

# Create simulation environment
eventlist = EventList()
logfile = Logfile("simulation.log", eventlist)

# Create topology
topology = FatTreeTopology(
    logfile=logfile,
    eventlist=eventlist,
    k=4  # 16 hosts
)

# Create traffic pattern
connections = ConnectionMatrix(topology.no_of_nodes())
connections.setPermutation(16)  # Permutation traffic

# Create and connect flows
for src, dests in connections.connections.items():
    for dst in dests:
        tcp_src = TcpSrc(None, None, eventlist)
        tcp_sink = TcpSink()
        
        # Get paths and connect
        paths = topology.get_bidir_paths(src, dst, False)
        if paths:
            # Use first path
            route = paths[0]
            tcp_src.connect(route, route, tcp_sink, 0)

# Run simulation
eventlist.setEndtime(int(1e12))  # 1 second
while eventlist.doNextEvent():
    pass
```

### Incast Pattern

```python
from htsimpy.datacenter import Incast, TcpSrcTransfer

# Create incast coordinator
incast = Incast(bytes=100000, eventlist=eventlist)  # 100KB per sender

# Add senders
for sender in range(1, 16):  # 15 senders
    tcp_src = TcpSrc(None, None, eventlist)
    transfer = TcpSrcTransfer(tcp_src, 100000, incast)
    incast.add_flow(transfer)
    
    # Connect to receiver (node 0)
    paths = topology.get_bidir_paths(sender, 0, False)
    tcp_src.connect(paths[0], paths[0], tcp_sink, 0)

# Start incast
incast.start_incast()
```

### MPTCP with Dynamic Subflows

```python
from htsimpy.protocols.multipath_tcp import MultipathTcpSrc
from htsimpy.datacenter import SubflowControl

# Create MPTCP source
mptcp = MultipathTcpSrc(
    algo=MultipathTcpAlgorithm.COUPLED_EPSILON,
    eventlist=eventlist,
    epsilon=1.0
)

# Create subflow controller
subflow_ctrl = SubflowControl(
    scan_period=int(100e9),  # 100ms
    eventlist=eventlist,
    net_paths=net_paths,
    max_subflows=8
)

# Register MPTCP flow
subflow_ctrl.add_flow(src, dst, mptcp)

# Create initial subflows
for i in range(4):
    tcp_sub = TcpSrc(None, None, eventlist)
    mptcp.add_subflow(tcp_sub)
    # Connect subflow...
```

## Examples

The `examples/` directory contains complete simulation scripts:

1. **main_tcp.py**: Basic TCP simulation with various traffic patterns
2. **main_incast.py**: Incast traffic pattern demonstration
3. **main_shortflows.py**: Short flows with different workloads
4. **main_mptcp.py**: Multipath TCP with dynamic subflow control
5. **main_topologies.py**: Topology comparison under same workload

Run examples:
```bash
cd examples
python main_tcp.py -k 8 -c 64 --pattern permutation
python main_incast.py -k 4 -n 15 -b 100000
python main_mptcp.py -k 8 -s 4 --dynamic
```

## Topology Details

### Fat-tree
- K-ary fat-tree: K pods, K/2 switches per pod, K/2 hosts per edge switch
- Total hosts: K³/4
- Full bisection bandwidth
- Multiple equal-cost paths

### VL2
- Clos network architecture
- Valiant Load Balancing (VLB)
- Intermediate switches for path diversity
- Designed for data center virtualization

### BCube
- Server-centric topology
- Servers have multiple NICs (K+1 for BCube_k)
- Recursive structure
- High path diversity and fault tolerance

### DragonFly
- High-radix routers
- Global links between groups
- Minimal diameter
- Good for large-scale deployments

## Traffic Patterns

### Connection Matrix
Supports various traffic patterns:
- **Permutation**: Each source has one destination
- **Random**: Random source-destination pairs
- **Stride**: Fixed stride pattern
- **Hotspot**: Multiple sources to few destinations
- **All-to-all**: Full mesh

### Flow Size Distributions
For short flows:
- **Web Search**: 50% < 10KB, 45% 10KB-1MB, 5% > 1MB
- **Data Mining**: 20% < 10KB, 50% 10KB-1MB, 30% > 1MB
- **Cache**: 90% < 1KB, 9% 1KB-100KB, 1% > 100KB

## Performance Considerations

1. **Path Selection**: Use FirstFit for better load balancing
2. **Queue Sizes**: Adjust based on BDP and incast degree
3. **Topology Choice**: 
   - Fat-tree: Good for uniform traffic
   - VL2: Better for virtualized environments
   - BCube: High fault tolerance requirements
   - DragonFly: Large scale deployments

## API Reference

### Topology Base Class

```python
class Topology(ABC):
    @abstractmethod
    def get_bidir_paths(src: int, dest: int, reverse: bool) -> List[Route]
        """Get paths between nodes"""
    
    @abstractmethod
    def no_of_nodes() -> int
        """Get total number of hosts"""
    
    @abstractmethod
    def get_host(host_id: int) -> Optional[Host]
        """Get host by ID"""
```

### Connection Matrix

```python
class ConnectionMatrix:
    def setPermutation(count: int)
        """Create permutation traffic"""
    
    def setRandom(count: int)
        """Create random traffic"""
    
    def add_connection(src: int, dst: int)
        """Add a connection"""
```

### Traffic Generators

```python
class Incast:
    def add_flow(flow: TcpSrcTransfer)
        """Add a flow to incast"""
    
    def start_incast()
        """Start all flows"""

class ShortFlows:
    def __init__(lambda_rate: float, ...)
        """Create with arrival rate"""
```

## Contributing

When adding new topologies:
1. Inherit from `Topology` base class
2. Implement all abstract methods
3. Follow naming conventions from C++ implementation
4. Add comprehensive docstrings
5. Include usage example

## References

1. [Fat-tree: A Scalable, Commodity Data Center Network Architecture](http://ccr.sigcomm.org/online/files/p63-alfares.pdf)
2. [VL2: A Scalable and Flexible Data Center Network](https://www.microsoft.com/en-us/research/wp-content/uploads/2016/02/vl2-sigcomm09-final.pdf)
3. [BCube: A High Performance, Server-centric Network Architecture](https://www.microsoft.com/en-us/research/wp-content/uploads/2016/02/bcube_sigcomm09.pdf)
4. [Technology-Driven, Highly-Scalable Dragonfly Topology](https://static.googleusercontent.com/media/research.google.com/en//pubs/archive/34926.pdf)