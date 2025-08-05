"""
Short flows traffic generator for data center networks

Corresponds to shortflows.h/cpp in HTSim C++ implementation
Generates short-lived flows following a Poisson arrival process.
"""

import random
import math
from typing import List, Dict, Optional, Tuple, TYPE_CHECKING
from ..core.eventlist import EventSource, EventList
from ..core.route import Route
from ..core.logger.logfile import Logfile
from .connection_matrix import ConnectionMatrix, Connection
from .incast import TcpSrcTransfer

if TYPE_CHECKING:
    from ..protocols.tcp import TcpSrc, TcpSink


class ShortFlow:
    """
    Represents a short-lived TCP flow
    """
    
    def __init__(self, src: TcpSrcTransfer, snk: 'TcpSink'):
        """
        Initialize short flow
        
        Args:
            src: TCP source transfer
            snk: TCP sink
        """
        self.src = src
        self.snk = snk


class ShortFlows(EventSource):
    """
    Short flows traffic generator
    
    Generates short-lived TCP flows according to a Poisson process.
    Common in data center workloads where most flows are small (mice)
    mixed with a few large flows (elephants).
    
    Key features:
    - Poisson arrival process with rate lambda
    - Reuses connections when possible
    - Randomly selects source-destination pairs from traffic matrix
    - Fixed or variable flow sizes
    """
    
    def __init__(self,
                 lambda_rate: float,
                 eventlist: EventList,
                 net_paths: Dict[int, Dict[int, List[Route]]],
                 connection_matrix: ConnectionMatrix,
                 logfile: Optional[Logfile] = None,
                 tcp_generator: Optional[callable] = None,
                 flow_size_generator: Optional[callable] = None):
        """
        Initialize short flows generator
        
        Args:
            lambda_rate: Arrival rate (flows per second)
            eventlist: Event list
            net_paths: Network paths indexed by [src][dst]
            connection_matrix: Connection matrix defining traffic patterns
            logfile: Optional logfile for logging
            tcp_generator: Function to generate TCP sources/sinks
            flow_size_generator: Function to generate flow sizes
        """
        super().__init__(eventlist, "ShortFlows")
        
        self._lambda = lambda_rate
        self._net_paths = net_paths
        self._traffic_matrix = connection_matrix.get_all_connections()
        self._logfile = logfile
        self._tcp_generator = tcp_generator
        self._flow_size_generator = flow_size_generator or self._default_flow_size
        
        # Connection pool indexed by [src][dst]
        self._connections: Dict[int, Dict[int, List[ShortFlow]]] = {}
        
        # Statistics
        self._total_flows_created = 0
        self._total_flows_started = 0
        self._active_flows = 0
        
        # Schedule first event
        self.eventlist.sourceIsPendingRel(self, int(1e12))  # 1ms
        
    def _default_flow_size(self) -> int:
        """Default flow size generator - returns 70KB"""
        return 70000
        
    def _exponential(self, rate: float) -> float:
        """Generate exponential random variable"""
        return -math.log(1 - random.random()) / rate
        
    def create_connection(self, src: int, dst: int, 
                         starttime: int) -> Optional[ShortFlow]:
        """
        Create a new short flow connection
        
        Args:
            src: Source node ID
            dst: Destination node ID  
            starttime: Start time in picoseconds
            
        Returns:
            Created ShortFlow or None if creation fails
        """
        if not self._tcp_generator:
            print(f"Warning: No TCP generator configured for ShortFlows")
            return None
            
        # Get paths for this src-dst pair
        if src not in self._net_paths or dst not in self._net_paths[src]:
            print(f"Warning: No paths found for {src}->{dst}")
            return None
            
        paths = self._net_paths[src][dst]
        if not paths:
            return None
            
        # Create TCP source and sink
        flow_size = self._flow_size_generator()
        tcp_src, tcp_sink = self._tcp_generator(src, dst, flow_size)
        
        if not tcp_src or not tcp_sink:
            return None
            
        # Create transfer wrapper
        transfer = TcpSrcTransfer(tcp_src, flow_size)
        
        # Name the flow
        if src not in self._connections:
            self._connections[src] = {}
        if dst not in self._connections[src]:
            self._connections[src][dst] = []
            
        pos = len(self._connections[src][dst])
        
        tcp_src.setName(f"sf_{src}_{dst}({pos})")
        tcp_sink.setName(f"sf_sink_{src}_{dst}({pos})")
        
        if self._logfile:
            self._logfile.write_name(tcp_src)
            self._logfile.write_name(tcp_sink)
            
        # Select random path
        choice = random.randint(0, len(paths) - 1)
        route_out = Route()
        
        # Copy the selected path
        for element in paths[choice]._elements:
            route_out.push_back(element)
        route_out.push_back(tcp_sink)
        
        # Create return path
        route_in = Route()
        route_in.push_back(tcp_src)
        
        # Connect and start
        tcp_src.connect(route_out, route_in, tcp_sink, starttime)
        
        # Create and store flow
        flow = ShortFlow(transfer, tcp_sink)
        self._connections[src][dst].append(flow)
        
        self._total_flows_created += 1
        
        return flow
        
    def doNextEvent(self):
        """Handle next event - start a new flow"""
        self.run()
        
        # Schedule next arrival
        next_arrival = int(self._exponential(self._lambda) * 1e12)  # Convert to ps
        self.eventlist.sourceIsPendingRel(self, next_arrival)
        
    def run(self):
        """Start a new short flow"""
        if not self._traffic_matrix:
            return
            
        # Randomly choose connection to activate
        pos = random.randint(0, len(self._traffic_matrix) - 1)
        conn = self._traffic_matrix[pos]
        
        # Look for inactive connection to reuse
        flow = None
        if (conn.src in self._connections and 
            conn.dst in self._connections[conn.src]):
            for f in self._connections[conn.src][conn.dst]:
                if not f.src.is_active():
                    flow = f
                    break
                    
        if flow is None or flow.src.is_active():
            # Need to create new connection
            flow = self.create_connection(conn.src, conn.dst, 
                                        self.eventlist.now())
            if not flow:
                return
        else:
            # Reuse existing connection
            flow_size = self._flow_size_generator()
            flow.src.reset(flow_size, restart=True)
            
        self._total_flows_started += 1
        self._active_flows += 1
        
    def get_stats(self) -> Dict[str, int]:
        """Get statistics about short flows"""
        return {
            'total_created': self._total_flows_created,
            'total_started': self._total_flows_started,
            'active_flows': self._active_flows,
            'connection_pairs': sum(len(dst_dict) for dst_dict in 
                                  self._connections.values())
        }
        
    def set_lambda(self, lambda_rate: float):
        """Update arrival rate"""
        self._lambda = lambda_rate
        
    def get_lambda(self) -> float:
        """Get current arrival rate"""
        return self._lambda


class FlowSizeGenerators:
    """
    Collection of flow size generators for different workloads
    """
    
    @staticmethod
    def fixed_size(size: int) -> callable:
        """Generate fixed size flows"""
        def generator():
            return size
        return generator
        
    @staticmethod
    def uniform(min_size: int, max_size: int) -> callable:
        """Generate uniformly distributed flow sizes"""
        def generator():
            return random.randint(min_size, max_size)
        return generator
        
    @staticmethod
    def web_search() -> callable:
        """
        Generate flow sizes following web search workload
        Based on "The Nature of Datacenter Traffic" paper
        """
        def generator():
            r = random.random()
            if r < 0.5:
                # 50% are < 10KB
                return random.randint(1000, 10000)
            elif r < 0.95:
                # 45% are 10KB - 1MB  
                return random.randint(10000, 1000000)
            else:
                # 5% are > 1MB
                return random.randint(1000000, 10000000)
        return generator
        
    @staticmethod
    def data_mining() -> callable:
        """
        Generate flow sizes following data mining workload
        More large flows than web search
        """
        def generator():
            r = random.random()
            if r < 0.2:
                # 20% are < 10KB
                return random.randint(1000, 10000)
            elif r < 0.7:
                # 50% are 10KB - 1MB
                return random.randint(10000, 1000000)
            else:
                # 30% are > 1MB
                return random.randint(1000000, 100000000)
        return generator
        
    @staticmethod
    def cache_follower() -> callable:
        """
        Generate flow sizes for cache/memcached workloads
        Mostly small requests with occasional large transfers
        """
        def generator():
            r = random.random()
            if r < 0.9:
                # 90% are small (< 1KB)
                return random.randint(100, 1000)
            elif r < 0.99:
                # 9% are medium (1KB - 100KB)
                return random.randint(1000, 100000)
            else:
                # 1% are large (> 100KB)
                return random.randint(100000, 10000000)
        return generator