"""
Fat-tree topology for data center networks

Corresponds to fat_tree_topology.h/cpp in HTSim C++ implementation
Implements k-ary fat-tree topology as described in the paper:
"A Scalable, Commodity Data Center Network Architecture"
"""

from typing import List, Optional, Dict, Tuple
import math
from ..core.route import Route
from ..core.pipe import Pipe
from ..core.eventlist import EventList
from ..core.logger.logfile import Logfile
# from ..core.logger.queuelogger import QueueLoggerFactory  # TODO: implement queue logger factory
from ..queues.random_queue import RandomQueue
from ..queues.base_queue import BaseQueue, Queue
from ..core.switch import Switch
from .topology import Topology
from .firstfit import FirstFit
from .host import Host
from .constants import QueueType, LinkDirection, SwitchTier


class FatTreeTopology(Topology):
    """
    Fat-tree topology implementation
    
    Implements a k-ary fat-tree with:
    - k pods
    - k/2 aggregation switches per pod
    - k/2 ToR switches per pod
    - k/2 hosts per ToR
    - (k/2)^2 core switches
    
    Total hosts = k^3/4
    """
    
    # Class variables for tier parameters
    _tiers = 3  # Always 3 tiers in fat-tree
    _link_latencies = [10000, 10000, 10000]  # src->tor, tor->agg, agg->core (ps)
    _switch_latencies = [100000, 100000, 100000]  # tor, agg, core switch latencies (ps)
    _hosts_per_pod = 0
    
    # Tier-specific parameters
    _tier_params = {
        SwitchTier.TOR_TIER: {
            'radix_up': 2, 'radix_down': 2, 
            'queue_up': 100, 'queue_down': 100,
            'bundlesize': 1, 'downlink_speed': 10000000000,
            'oversub': 1
        },
        SwitchTier.AGG_TIER: {
            'radix_up': 2, 'radix_down': 2,
            'queue_up': 100, 'queue_down': 100,
            'bundlesize': 1, 'downlink_speed': 10000000000,
            'oversub': 1
        },
        SwitchTier.CORE_TIER: {
            'radix_up': 0, 'radix_down': 4,
            'queue_up': 0, 'queue_down': 100,
            'bundlesize': 1, 'downlink_speed': 10000000000,
            'oversub': 1
        }
    }
    
    def __init__(self,
                 no_of_nodes: int,
                 link_speed: int,
                 queue_size: int,
                 logger_factory: Optional[object],  # QueueLoggerFactory TODO
                 eventlist: EventList,
                 ff: Optional[FirstFit] = None,
                 queue_type: QueueType = QueueType.RANDOM,
                 latency: int = 1000000,  # 1us
                 switch_latency: int = 100000,  # 100ns
                 sender_queue_type: QueueType = QueueType.FAIR_PRIO):
        """
        Initialize Fat-tree topology
        
        Args:
            no_of_nodes: Number of hosts (must be k^3/4 for some even k)
            link_speed: Link speed in bps
            queue_size: Queue size in bytes
            logger_factory: Factory for queue loggers
            eventlist: Event list
            ff: FirstFit allocator
            queue_type: Type of queue to use
            latency: Link latency in picoseconds
            switch_latency: Switch latency in picoseconds
            sender_queue_type: Queue type at senders
        """
        super().__init__()
        self._no_of_nodes = no_of_nodes
        self._link_speed = link_speed
        self._queue_size = queue_size
        self._logger_factory = logger_factory
        self._eventlist = eventlist
        self.ff = ff
        self._qt = queue_type
        self._sender_qt = sender_queue_type
        self.failed_links = 0
        
        # Calculate k from number of nodes
        self.k = self._calculate_k(no_of_nodes)
        if self.k == 0:
            raise ValueError(f"Invalid number of nodes {no_of_nodes}, must be k^3/4 for even k")
            
        # Set latencies
        self._link_latencies = [latency, latency, latency]
        self._switch_latencies = [switch_latency, switch_latency, switch_latency]
        
        # Initialize topology structures
        self.hosts: List[Host] = []
        self.switches_lp: List[Switch] = []  # ToR switches
        self.switches_up: List[Switch] = []  # Aggregation switches  
        self.switches_c: List[Switch] = []   # Core switches
        
        # Pipes and queues - 3D arrays [src_switch][dst_switch][link_in_bundle]
        # Upward direction
        self.pipes_nc_nup: List[List[List[Pipe]]] = []
        self.pipes_nup_nlp: List[List[List[Pipe]]] = []
        self.pipes_nlp_ns: List[List[List[Pipe]]] = []
        self.queues_nc_nup: List[List[List[BaseQueue]]] = []
        self.queues_nup_nlp: List[List[List[BaseQueue]]] = []
        self.queues_nlp_ns: List[List[List[BaseQueue]]] = []
        
        # Downward direction
        self.pipes_nup_nc: List[List[List[Pipe]]] = []
        self.pipes_nlp_nup: List[List[List[Pipe]]] = []
        self.pipes_ns_nlp: List[List[List[Pipe]]] = []
        self.queues_nup_nc: List[List[List[BaseQueue]]] = []
        self.queues_nlp_nup: List[List[List[BaseQueue]]] = []
        self.queues_ns_nlp: List[List[List[BaseQueue]]] = []
        
        # Initialize the network
        self.init_network()
        
    def _calculate_k(self, n_nodes: int) -> int:
        """Calculate k parameter from number of nodes"""
        # n_nodes = k^3/4, so k = (4*n_nodes)^(1/3)
        k_float = math.pow(4 * n_nodes, 1/3)
        k = int(round(k_float))
        
        # Verify k is even and gives correct number of nodes
        if k % 2 == 0 and k * k * k // 4 == n_nodes:
            return k
        return 0
        
    def init_network(self):
        """Initialize the fat-tree network topology"""
        
        # Create hosts
        for i in range(self._no_of_nodes):
            host = Host(f"host_{i}")
            host.set_host_id(i)
            self.hosts.append(host)
            
        # Number of each type of switch
        n_tor = self.k * self.k // 2      # k/2 ToR per pod * k pods
        n_agg = self.k * self.k // 2      # k/2 agg per pod * k pods
        n_core = self.k * self.k // 4     # (k/2)^2 core switches
        
        # Create ToR switches
        for i in range(n_tor):
            sw = Switch(f"tor_{i}", self._eventlist)
            self.switches_lp.append(sw)
            
        # Create aggregation switches
        for i in range(n_agg):
            sw = Switch(f"agg_{i}", self._eventlist)
            self.switches_up.append(sw)
            
        # Create core switches
        for i in range(n_core):
            sw = Switch(f"core_{i}", self._eventlist)
            self.switches_c.append(sw)
            
        # Initialize connection arrays
        self._init_connection_arrays()
        
        # Create all links
        self._create_links()
        
    def _init_connection_arrays(self):
        """Initialize 3D arrays for pipes and queues"""
        k = self.k
        
        # Core to aggregation
        self.pipes_nc_nup = [[[] for _ in range(k*k//2)] for _ in range(k*k//4)]
        self.queues_nc_nup = [[[] for _ in range(k*k//2)] for _ in range(k*k//4)]
        self.pipes_nup_nc = [[[] for _ in range(k*k//4)] for _ in range(k*k//2)]
        self.queues_nup_nc = [[[] for _ in range(k*k//4)] for _ in range(k*k//2)]
        
        # Aggregation to ToR
        self.pipes_nup_nlp = [[[] for _ in range(k*k//2)] for _ in range(k*k//2)]
        self.queues_nup_nlp = [[[] for _ in range(k*k//2)] for _ in range(k*k//2)]
        self.pipes_nlp_nup = [[[] for _ in range(k*k//2)] for _ in range(k*k//2)]
        self.queues_nlp_nup = [[[] for _ in range(k*k//2)] for _ in range(k*k//2)]
        
        # ToR to hosts
        self.pipes_nlp_ns = [[[] for _ in range(self._no_of_nodes)] for _ in range(k*k//2)]
        self.queues_nlp_ns = [[[] for _ in range(self._no_of_nodes)] for _ in range(k*k//2)]
        self.pipes_ns_nlp = [[[] for _ in range(k*k//2)] for _ in range(self._no_of_nodes)]
        self.queues_ns_nlp = [[[] for _ in range(k*k//2)] for _ in range(self._no_of_nodes)]
        
    def _create_links(self):
        """Create all links in the fat-tree"""
        k = self.k
        
        # Host to ToR links
        hosts_per_tor = k // 2
        for tor_id in range(len(self.switches_lp)):
            for h in range(hosts_per_tor):
                host_id = tor_id * hosts_per_tor + h
                if host_id < self._no_of_nodes:
                    # Uplink: host -> ToR
                    pipe = Pipe(self._link_latencies[0], self._eventlist)
                    queue = self._create_queue(self._queue_size, LinkDirection.UPLINK, 
                                             SwitchTier.TOR_TIER, True)
                    self.pipes_ns_nlp[host_id][tor_id].append(pipe)
                    self.queues_ns_nlp[host_id][tor_id].append(queue)
                    
                    # Downlink: ToR -> host
                    pipe = Pipe(self._link_latencies[0], self._eventlist)
                    queue = self._create_queue(self._queue_size, LinkDirection.DOWNLINK,
                                             SwitchTier.TOR_TIER, True)
                    self.pipes_nlp_ns[tor_id][host_id].append(pipe)
                    self.queues_nlp_ns[tor_id][host_id].append(queue)
                    
        # ToR to Aggregation links
        for pod in range(k):
            for tor_in_pod in range(k // 2):
                tor_id = pod * (k // 2) + tor_in_pod
                for agg_in_pod in range(k // 2):
                    agg_id = pod * (k // 2) + agg_in_pod
                    
                    # Uplink: ToR -> Agg
                    pipe = Pipe(self._link_latencies[1], self._eventlist)
                    queue = self._create_queue(self._queue_size, LinkDirection.UPLINK,
                                             SwitchTier.AGG_TIER, False)
                    self.pipes_nlp_nup[tor_id][agg_id].append(pipe)
                    self.queues_nlp_nup[tor_id][agg_id].append(queue)
                    
                    # Downlink: Agg -> ToR
                    pipe = Pipe(self._link_latencies[1], self._eventlist)
                    queue = self._create_queue(self._queue_size, LinkDirection.DOWNLINK,
                                             SwitchTier.AGG_TIER, False)
                    self.pipes_nup_nlp[agg_id][tor_id].append(pipe)
                    self.queues_nup_nlp[agg_id][tor_id].append(queue)
                    
        # Aggregation to Core links
        for agg_id in range(len(self.switches_up)):
            pod = agg_id // (k // 2)
            agg_in_pod = agg_id % (k // 2)
            
            for core_group in range(k // 2):
                core_id = agg_in_pod * (k // 2) + core_group
                
                # Uplink: Agg -> Core
                pipe = Pipe(self._link_latencies[2], self._eventlist)
                queue = self._create_queue(self._queue_size, LinkDirection.UPLINK,
                                         SwitchTier.CORE_TIER, False)
                self.pipes_nup_nc[agg_id][core_id].append(pipe)
                self.queues_nup_nc[agg_id][core_id].append(queue)
                
                # Downlink: Core -> Agg
                pipe = Pipe(self._link_latencies[2], self._eventlist)
                queue = self._create_queue(self._queue_size, LinkDirection.DOWNLINK,
                                         SwitchTier.CORE_TIER, False)
                self.pipes_nc_nup[core_id][agg_id].append(pipe)
                self.queues_nc_nup[core_id][agg_id].append(queue)
                
    def _create_queue(self, size: int, direction: LinkDirection, 
                     tier: SwitchTier, is_tor: bool) -> BaseQueue:
        """Create a queue based on type and parameters"""
        if self._qt == QueueType.RANDOM:
            queue = RandomQueue(
                service_rate=self._link_speed,
                buffer_size=size,
                eventlist=self._eventlist,
                queuelogger=None
            )
        else:
            # Default to basic queue
            queue = Queue(
                service_rate=self._link_speed,
                maxsize=size,
                eventlist=self._eventlist,
                queuelogger=None
            )
            
        return queue
        
    def get_bidir_paths(self, src: int, dest: int, reverse: bool) -> List[Route]:
        """Get bidirectional paths between hosts"""
        if reverse:
            src, dest = dest, src
            
        if src >= self._no_of_nodes or dest >= self._no_of_nodes:
            return []
            
        if src == dest:
            return []
            
        # Get ToR switches for source and destination
        k = self.k
        hosts_per_tor = k // 2
        src_tor = src // hosts_per_tor
        dst_tor = dest // hosts_per_tor
        
        # Get pods
        src_pod = src_tor // (k // 2)
        dst_pod = dst_tor // (k // 2)
        
        paths = []
        
        if src_pod == dst_pod:
            # Same pod - route through aggregation switches in pod
            for agg_in_pod in range(k // 2):
                agg_id = src_pod * (k // 2) + agg_in_pod
                route = self._build_route(src, dest, src_tor, dst_tor, agg_id, -1)
                if route:
                    paths.append(route)
        else:
            # Different pods - must go through core
            src_agg_in_pod = src_tor % (k // 2)
            dst_agg_in_pod = dst_tor % (k // 2)
            
            # Each aggregation switch connects to k/2 core switches
            for core_offset in range(k // 2):
                core_id = src_agg_in_pod * (k // 2) + core_offset
                src_agg = src_pod * (k // 2) + src_agg_in_pod
                dst_agg = dst_pod * (k // 2) + dst_agg_in_pod
                
                route = self._build_route(src, dest, src_tor, dst_tor, src_agg, 
                                        core_id, dst_agg)
                if route:
                    paths.append(route)
                    
        return paths
        
    def _build_route(self, src_host: int, dst_host: int, src_tor: int, 
                    dst_tor: int, agg_id: int, core_id: int = -1,
                    dst_agg_id: int = -1) -> Optional[Route]:
        """Build a route through the fat-tree"""
        route = Route()
        
        # Source host
        route.push_back(self.hosts[src_host])
        
        # Host -> ToR
        if self.queues_ns_nlp[src_host][src_tor]:
            route.push_back(self.queues_ns_nlp[src_host][src_tor][0])
            route.push_back(self.pipes_ns_nlp[src_host][src_tor][0])
            route.push_back(self.switches_lp[src_tor])
        else:
            return None
            
        if src_tor == dst_tor:
            # Same ToR - direct path
            pass
        elif core_id == -1:
            # Same pod - through aggregation
            if self.queues_nlp_nup[src_tor][agg_id]:
                route.push_back(self.queues_nlp_nup[src_tor][agg_id][0])
                route.push_back(self.pipes_nlp_nup[src_tor][agg_id][0])
                route.push_back(self.switches_up[agg_id])
                
                route.push_back(self.queues_nup_nlp[agg_id][dst_tor][0])
                route.push_back(self.pipes_nup_nlp[agg_id][dst_tor][0])
                route.push_back(self.switches_lp[dst_tor])
            else:
                return None
        else:
            # Different pods - through core
            # ToR -> Agg
            if self.queues_nlp_nup[src_tor][agg_id]:
                route.push_back(self.queues_nlp_nup[src_tor][agg_id][0])
                route.push_back(self.pipes_nlp_nup[src_tor][agg_id][0])
                route.push_back(self.switches_up[agg_id])
                
                # Agg -> Core
                route.push_back(self.queues_nup_nc[agg_id][core_id][0])
                route.push_back(self.pipes_nup_nc[agg_id][core_id][0])
                route.push_back(self.switches_c[core_id])
                
                # Core -> Dst Agg
                route.push_back(self.queues_nc_nup[core_id][dst_agg_id][0])
                route.push_back(self.pipes_nc_nup[core_id][dst_agg_id][0])
                route.push_back(self.switches_up[dst_agg_id])
                
                # Dst Agg -> Dst ToR
                route.push_back(self.queues_nup_nlp[dst_agg_id][dst_tor][0])
                route.push_back(self.pipes_nup_nlp[dst_agg_id][dst_tor][0])
                route.push_back(self.switches_lp[dst_tor])
            else:
                return None
                
        # ToR -> Host
        if self.queues_nlp_ns[dst_tor][dst_host]:
            route.push_back(self.queues_nlp_ns[dst_tor][dst_host][0])
            route.push_back(self.pipes_nlp_ns[dst_tor][dst_host][0])
            route.push_back(self.hosts[dst_host])
        else:
            return None
            
        return route
        
    def get_neighbours(self, src: int) -> Optional[List[int]]:
        """Fat-tree doesn't use direct neighbor concept"""
        return None
        
    @classmethod
    def set_tier_parameters(cls, tier: int, radix_up: int, radix_down: int,
                          queue_up: int, queue_down: int, bundlesize: int,
                          downlink_speed: int, oversub: int):
        """Set parameters for a specific tier"""
        if tier in [0, 1, 2]:
            tier_enum = SwitchTier(tier)
            cls._tier_params[tier_enum] = {
                'radix_up': radix_up,
                'radix_down': radix_down,
                'queue_up': queue_up,
                'queue_down': queue_down,
                'bundlesize': bundlesize,
                'downlink_speed': downlink_speed,
                'oversub': oversub
            }
            
    def get_host(self, host_id: int) -> Optional[Host]:
        """Get a host by ID"""
        if 0 <= host_id < self._no_of_nodes:
            return self.hosts[host_id]
        return None