"""
Fat-tree topology for data center networks

Corresponds to fat_tree_topology.h/cpp in HTSim C++ implementation
Implements k-ary fat-tree topology as described in the paper:
"A Scalable, Commodity Data Center Network Architecture"
"""

from typing import List, Optional, Dict, Tuple, Union, Set
import math

# Constants from C++ main.h
FEEDER_BUFFER = 1000  # Number of packets in feeder buffer
RANDOM_BUFFER = 3     # Random buffer size in packets
from ..core.route import Route
from ..core.pipe import Pipe
from ..core.eventlist import EventList
from ..core.logger.logfile import Logfile
from ..core.logger.queue import QueueLoggerFactory
from ..queues.random_queue import RandomQueue
from ..queues.base_queue import BaseQueue
from ..queues.composite_queue import CompositeQueue
from ..queues.fifo_queue import FIFOQueue
from ..core.switch import Switch
from .fat_tree_switch import FatTreeSwitch, SwitchType as FTSwitchType
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
    
    Supports:
    - Bundle sizes for link aggregation
    - Failed link handling
    - Multiple queue types
    - Path caching for performance
    """
    
    # Class variables for tier parameters
    _tiers = 3  # Always 3 tiers in fat-tree
    _link_latencies = [10000, 10000, 10000]  # src->tor, tor->agg, agg->core (ps)
    _switch_latencies = [100000, 100000, 100000]  # tor, agg, core switch latencies (ps)
    _hosts_per_pod = 0
    _bundlesize = [1, 1, 1]  # Bundle sizes per tier
    
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
                 logger_factory: Optional[QueueLoggerFactory],
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
        
        # Input validation
        if no_of_nodes <= 0:
            raise ValueError(f"Number of nodes must be positive, got {no_of_nodes}")
        if link_speed <= 0:
            raise ValueError(f"Link speed must be positive, got {link_speed}")
        if queue_size <= 0:
            raise ValueError(f"Queue size must be positive, got {queue_size}")
        if latency <= 0:
            raise ValueError(f"Latency must be positive, got {latency}")
        if switch_latency <= 0:
            raise ValueError(f"Switch latency must be positive, got {switch_latency}")
            
        self._no_of_nodes = no_of_nodes
        self._link_speed = link_speed
        self._queue_size = queue_size
        self._logger_factory = logger_factory
        self._eventlist = eventlist
        self.ff = ff
        self._qt = queue_type
        self._sender_qt = sender_queue_type
        self.failed_links = 0
        self._failed_links_set: Set[Tuple[str, int, str, int, int]] = set()  # Track failed links
        
        # Calculate k from number of nodes
        self.k = self._calculate_k(no_of_nodes)
        
        if self.k == 0:
            raise ValueError(f"Invalid number of nodes {no_of_nodes}, must be k^3/4 for even k")
            
        # Set topology parameters (matches C++ NSRV, NTOR, etc.)
        self.NSRV = self.k * self.k * self.k // 4  # Total servers
        self.NTOR = self.k * self.k // 2           # Total ToR switches
        self.NAGG = self.k * self.k // 2           # Total aggregation switches
        self.NPOD = self.k                         # Number of pods
        self.NCORE = self.k * self.k // 4          # Total core switches
        
        # Per-pod counts
        self._tor_switches_per_pod = self.k // 2
        self._agg_switches_per_pod = self.k // 2
        self._hosts_per_pod = self.k * self.k // 4
        
        # Update bundle sizes from tier parameters
        tier_map = [SwitchTier.TOR_TIER, SwitchTier.AGG_TIER, SwitchTier.CORE_TIER]
        for tier in range(self._tiers):
            self._bundlesize[tier] = self._tier_params[tier_map[tier]]['bundlesize']
            
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
        
        # Path cache for performance
        self._path_cache: Dict[Tuple[int, int], List[Route]] = {}
        self._cache_enabled = True
        
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
            sw = FatTreeSwitch(
                self._eventlist,
                f"Switch_LowerPod_{i}",
                FTSwitchType.TOR,
                i,
                self._switch_latencies[0],
                self
            )
            self.switches_lp.append(sw)
            
        # Create aggregation switches
        for i in range(n_agg):
            sw = FatTreeSwitch(
                self._eventlist,
                f"Switch_UpperPod_{i}",
                FTSwitchType.AGG,
                i,
                self._switch_latencies[1],
                self
            )
            self.switches_up.append(sw)
            
        # Create core switches
        for i in range(n_core):
            sw = FatTreeSwitch(
                self._eventlist,
                f"Switch_Core_{i}",
                FTSwitchType.CORE,
                i,
                self._switch_latencies[2],
                self
            )
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
        """Create all links in the fat-tree with bundle support"""
        k = self.k
        
        # Host to ToR links (matches C++ logic)
        for tor in range(self.NTOR):
            tier_map = [SwitchTier.TOR_TIER, SwitchTier.AGG_TIER, SwitchTier.CORE_TIER]
            link_bundles = self._tier_params[tier_map[0]]['radix_down'] // self._bundlesize[0]
            
            for l in range(link_bundles):
                srv = tor * link_bundles + l
                if srv >= self._no_of_nodes:
                    continue
                    
                for b in range(self._bundlesize[0]):  # TOR_TIER bundle size
                    # Downlink: ToR -> host
                    queue_logger = None
                    if self._logger_factory:
                        queue_logger = self._logger_factory.createQueueLogger()
                        
                    queue = self.alloc_queue(queue_logger, 
                                           self._tier_params[tier_map[0]]['queue_down'],
                                           LinkDirection.DOWNLINK, 0, True)  # TOR_TIER=0
                    queue.setName(f"LS{tor}->DST{srv}({b})")
                    
                    hop_latency = self._link_latencies[0] if self._link_latencies[0] > 0 else 1000000  # 1us default
                    pipe = Pipe(hop_latency, self._eventlist)
                    pipe.setName(f"Pipe-LS{tor}->DST{srv}({b})")
                    
                    self.queues_nlp_ns[tor][srv].append(queue)
                    self.pipes_nlp_ns[tor][srv].append(pipe)
                    
                    # Uplink: host -> ToR (use alloc_src_queue)
                    queue_logger = None
                    if self._logger_factory:
                        queue_logger = self._logger_factory.createQueueLogger()
                        
                    queue = self.alloc_src_queue(queue_logger)
                    queue.setName(f"SRC{srv}->LS{tor}({b})")
                    
                    pipe = Pipe(hop_latency, self._eventlist)
                    pipe.setName(f"Pipe-SRC{srv}->LS{tor}({b})")
                    
                    self.queues_ns_nlp[srv][tor].append(queue)
                    self.pipes_ns_nlp[srv][tor].append(pipe)
                    
                    # Set remote endpoint on the ns_nlp queue (matches C++)
                    if hasattr(queue, 'setRemoteEndpoint'):
                        queue.setRemoteEndpoint(self.switches_lp[tor])
                    
                    # Add port to switch
                    if hasattr(self.switches_lp[tor], 'addPort'):
                        assert self.switches_lp[tor].addPort(self.queues_nlp_ns[tor][srv][b]) < 96
                    
                    # Add to FirstFit if available
                    if hasattr(self, 'ff') and self.ff:
                        self.ff.add_queue(self.queues_nlp_ns[tor][srv][b])
                        self.ff.add_queue(self.queues_ns_nlp[srv][tor][b])
                    
        # ToR to Aggregation links with bundle support
        for pod in range(k):
            for tor_in_pod in range(k // 2):
                tor_id = pod * (k // 2) + tor_in_pod
                for agg_in_pod in range(k // 2):
                    agg_id = pod * (k // 2) + agg_in_pod
                    
                    # Create bundle of links
                    bundle_size = self._bundlesize[1]  # AGG_TIER is index 1
                    for bundle_idx in range(bundle_size):
                        # Uplink: ToR -> Agg
                        pipe = Pipe(self._link_latencies[1], self._eventlist)
                        queue = self._create_queue(self._queue_size, LinkDirection.UPLINK,
                                                 SwitchTier.AGG_TIER, False)
                        pipe.setName(f"pipe_tor{tor_id}_agg{agg_id}_b{bundle_idx}")
                        queue.setName(f"queue_tor{tor_id}_agg{agg_id}_b{bundle_idx}")
                        self.pipes_nlp_nup[tor_id][agg_id].append(pipe)
                        self.queues_nlp_nup[tor_id][agg_id].append(queue)
                        
                        # Downlink: Agg -> ToR
                        pipe = Pipe(self._link_latencies[1], self._eventlist)
                        queue = self._create_queue(self._queue_size, LinkDirection.DOWNLINK,
                                                 SwitchTier.AGG_TIER, False)
                        pipe.setName(f"pipe_agg{agg_id}_tor{tor_id}_b{bundle_idx}")
                        queue.setName(f"queue_agg{agg_id}_tor{tor_id}_b{bundle_idx}")
                        self.pipes_nup_nlp[agg_id][tor_id].append(pipe)
                        self.queues_nup_nlp[agg_id][tor_id].append(queue)
                    
        # Aggregation to Core links with bundle support
        for agg_id in range(len(self.switches_up)):
            pod = agg_id // (k // 2)
            agg_in_pod = agg_id % (k // 2)
            
            for core_group in range(k // 2):
                core_id = agg_in_pod * (k // 2) + core_group
                
                # Create bundle of links
                bundle_size = self._bundlesize[2]  # CORE_TIER is index 2
                for bundle_idx in range(bundle_size):
                    # Uplink: Agg -> Core
                    pipe = Pipe(self._link_latencies[2], self._eventlist)
                    queue = self._create_queue(self._queue_size, LinkDirection.UPLINK,
                                             SwitchTier.CORE_TIER, False)
                    pipe.setName(f"pipe_agg{agg_id}_core{core_id}_b{bundle_idx}")
                    queue.setName(f"queue_agg{agg_id}_core{core_id}_b{bundle_idx}")
                    self.pipes_nup_nc[agg_id][core_id].append(pipe)
                    self.queues_nup_nc[agg_id][core_id].append(queue)
                    
                    # Downlink: Core -> Agg
                    pipe = Pipe(self._link_latencies[2], self._eventlist)
                    queue = self._create_queue(self._queue_size, LinkDirection.DOWNLINK,
                                             SwitchTier.CORE_TIER, False)
                    pipe.setName(f"pipe_core{core_id}_agg{agg_id}_b{bundle_idx}")
                    queue.setName(f"queue_core{core_id}_agg{agg_id}_b{bundle_idx}")
                    self.pipes_nc_nup[core_id][agg_id].append(pipe)
                    self.queues_nc_nup[core_id][agg_id].append(queue)
                    
        # Connect all links to switches
        self._connect_links()
        
    def _connect_links(self):
        """Connect all created links to switches and set remote endpoints.
        
        Matches C++ connection logic in fat_tree_topology.cpp.
        """
        k = self.k
        
        # Connect ToR <-> Agg links
        for tor_id in range(len(self.switches_lp)):
            pod = tor_id // (k // 2)
            
            for agg_in_pod in range(k // 2):
                agg_id = pod * (k // 2) + agg_in_pod
                
                for b in range(len(self.queues_nlp_nup[tor_id][agg_id])):
                    # Add ports to switches
                    assert self.switches_lp[tor_id].addPort(self.queues_nlp_nup[tor_id][agg_id][b]) < 96
                    assert self.switches_up[agg_id].addPort(self.queues_nup_nlp[agg_id][tor_id][b]) < 64
                    
                    # Set remote endpoints (matches C++)
                    self.queues_nlp_nup[tor_id][agg_id][b].setRemoteEndpoint(self.switches_up[agg_id])
                    self.queues_nup_nlp[agg_id][tor_id][b].setRemoteEndpoint(self.switches_lp[tor_id])
                    
        # Connect Agg <-> Core links  
        for agg_id in range(len(self.switches_up)):
            agg_in_pod = agg_id % (k // 2)
            
            for core_group in range(k // 2):
                core_id = agg_in_pod * (k // 2) + core_group
                
                for b in range(len(self.queues_nup_nc[agg_id][core_id])):
                    # Add ports to switches
                    assert self.switches_up[agg_id].addPort(self.queues_nup_nc[agg_id][core_id][b]) < 64
                    assert self.switches_c[core_id].addPort(self.queues_nc_nup[core_id][agg_id][b]) < 64
                    
                    # Set remote endpoints (matches C++)
                    self.queues_nup_nc[agg_id][core_id][b].setRemoteEndpoint(self.switches_c[core_id])
                    self.queues_nc_nup[core_id][agg_id][b].setRemoteEndpoint(self.switches_up[agg_id])
                
    def _create_queue(self, size: int, direction: LinkDirection, 
                     tier: SwitchTier, is_tor: bool) -> BaseQueue:
        """Create a queue based on type and parameters.
        
        Internal method that delegates to alloc_queue for C++ compatibility.
        """
        queue_logger = None
        if self._logger_factory:
            queue_logger = self._logger_factory.createQueueLogger()
            
        # Convert tier to int for C++ compatibility
        tier_int = 0 if tier == SwitchTier.TOR_TIER else (1 if tier == SwitchTier.AGG_TIER else 2)
        
        # Get queue size from tier parameters
        tier_map = [SwitchTier.TOR_TIER, SwitchTier.AGG_TIER, SwitchTier.CORE_TIER]
        if direction == LinkDirection.DOWNLINK:
            queuesize = self._tier_params[tier_map[tier_int]]['queue_down']
        else:
            # UPLINK - use queue_up if not core tier
            if tier_int < 2:  # Not CORE_TIER
                queuesize = self._tier_params[tier_map[tier_int]]['queue_up']
            else:
                queuesize = size  # Fallback for core tier uplinks
        
        return self.alloc_queue(queue_logger, queuesize, direction, tier_int, is_tor)
        
    def alloc_queue(self, queue_logger, queuesize: int, direction: LinkDirection,
                    switch_tier: int, tor: bool = False) -> BaseQueue:
        """Allocate a queue - matches C++ alloc_queue interface.
        
        Args:
            queue_logger: Queue logger instance
            queuesize: Queue size in bytes
            direction: Link direction (UPLINK/DOWNLINK)
            switch_tier: Switch tier (0=ToR, 1=Agg, 2=Core)
            tor: True if this is a ToR switch
        """
        # Determine link speed based on tier and direction
        if direction == LinkDirection.UPLINK:
            switch_tier += 1  # Use tier above's linkspeed for uplinks
            
        # Get tier parameters
        tier_map = [SwitchTier.TOR_TIER, SwitchTier.AGG_TIER, SwitchTier.CORE_TIER]
        if switch_tier < len(tier_map):
            speed = self._tier_params[tier_map[switch_tier]]['downlink_speed']
        else:
            speed = self._link_speed  # Fallback
            
        return self.alloc_queue_with_speed(queue_logger, speed, queuesize, 
                                          direction, switch_tier, tor)
        
    def alloc_queue_with_speed(self, queue_logger, speed: int, queuesize: int,
                              direction: LinkDirection, switch_tier: int, 
                              tor: bool = False) -> BaseQueue:
        """Allocate queue with specific speed - matches C++ overload."""
        # Create queue based on type
        if self._qt == QueueType.RANDOM:
            return RandomQueue(
                bitrate=speed,
                maxsize=queuesize,
                eventlist=self._eventlist,
                logger=queue_logger,
                drop=RANDOM_BUFFER * 1500 * 8  # memFromPkt(RANDOM_BUFFER)
            )
        elif self._qt == QueueType.COMPOSITE:
            return CompositeQueue(
                service_rate=speed,
                max_size=queuesize,
                eventlist=self._eventlist,
                logger=queue_logger
            )
        elif self._qt == QueueType.ECN:
            # ECN queue support
            from ..queues.ecn_queue import ECNQueue
            return ECNQueue(
                bitrate=speed,
                maxsize=queuesize,
                eventlist=self._eventlist,
                logger=queue_logger,
                marking_threshold=15 * 1500 * 8  # memFromPkt(15)
            )
        elif self._qt == QueueType.PRIORITY:
            from ..queues.priority_queue import PriorityQueue
            return PriorityQueue(
                service_rate=speed,
                max_size=queuesize,
                eventlist=self._eventlist,
                logger=queue_logger
            )
        else:
            # Default to FIFO
            from ..queues.base_queue import Queue as FifoQueue
            return FifoQueue(
                bitrate=speed,
                maxsize=queuesize,
                eventlist=self._eventlist,
                logger=queue_logger
            )
            
    def alloc_src_queue(self, queue_logger) -> BaseQueue:
        """Allocate a source queue for hosts.
        
        Matches C++ alloc_src_queue - used at packet sources.
        """
        # Get linkspeed from ToR downlinks (symmetric)
        tier_map = [SwitchTier.TOR_TIER, SwitchTier.AGG_TIER, SwitchTier.CORE_TIER]
        linkspeed = self._tier_params[tier_map[0]]['downlink_speed']  # TOR_TIER = 0
        
        if self._sender_qt == QueueType.SWIFT_SCHEDULER:
            # FairScheduler for Swift
            from ..queues.fair_scheduler import FairScheduler
            return FairScheduler(
                linkspeed,
                self._eventlist,
                queue_logger
            )
        elif self._sender_qt == QueueType.PRIORITY:
            from ..queues.priority_queue import PriorityQueue
            return PriorityQueue(
                service_rate=linkspeed,
                max_size=FEEDER_BUFFER * 1500 * 8,  # FEEDER_BUFFER packets
                eventlist=self._eventlist,
                logger=queue_logger
            )
        elif self._sender_qt == QueueType.FAIR_PRIO:
            from ..queues.fair_prio_queue import FairPriorityQueue
            return FairPriorityQueue(
                linkspeed,
                FEEDER_BUFFER * 1500 * 8,  # FEEDER_BUFFER packets
                self._eventlist,
                queue_logger
            )
        else:
            raise ValueError(f"Invalid sender queue type: {self._sender_qt}")
        
    def fail_link(self, src_type: str, src_id: int, dst_type: str, dst_id: int, 
                  bundle_idx: int = 0) -> bool:
        """
        Mark a link as failed.
        
        Args:
            src_type: Source type ('host', 'tor', 'agg', 'core')
            src_id: Source ID
            dst_type: Destination type
            dst_id: Destination ID
            bundle_idx: Bundle index (default 0)
            
        Returns:
            True if link was failed, False if already failed or not found
        """
        link_id = (src_type, src_id, dst_type, dst_id, bundle_idx)
        if link_id not in self._failed_links_set:
            self._failed_links_set.add(link_id)
            self.failed_links += 1
            
            # Invalidate path cache since topology changed
            self._path_cache.clear()
            
            # Mark the corresponding queue/pipe as failed
            if self._mark_components_failed(src_type, src_id, dst_type, dst_id, bundle_idx):
                return True
        return False
        
    def restore_link(self, src_type: str, src_id: int, dst_type: str, dst_id: int,
                     bundle_idx: int = 0) -> bool:
        """Restore a failed link."""
        link_id = (src_type, src_id, dst_type, dst_id, bundle_idx)
        if link_id in self._failed_links_set:
            self._failed_links_set.remove(link_id)
            self.failed_links -= 1
            
            # Restore the corresponding queue/pipe
            if self._restore_components(src_type, src_id, dst_type, dst_id, bundle_idx):
                return True
        return False
        
    def _mark_components_failed(self, src_type: str, src_id: int, dst_type: str, 
                               dst_id: int, bundle_idx: int) -> bool:
        """Mark queue and pipe components as failed."""
        # Get the appropriate queue and pipe based on link type
        queue = None
        pipe = None
        
        if src_type == 'host' and dst_type == 'tor':
            if (src_id < len(self.queues_ns_nlp) and 
                dst_id < len(self.queues_ns_nlp[src_id]) and
                bundle_idx < len(self.queues_ns_nlp[src_id][dst_id])):
                queue = self.queues_ns_nlp[src_id][dst_id][bundle_idx]
                pipe = self.pipes_ns_nlp[src_id][dst_id][bundle_idx]
        elif src_type == 'tor' and dst_type == 'host':
            if (src_id < len(self.queues_nlp_ns) and
                dst_id < len(self.queues_nlp_ns[src_id]) and
                bundle_idx < len(self.queues_nlp_ns[src_id][dst_id])):
                queue = self.queues_nlp_ns[src_id][dst_id][bundle_idx]
                pipe = self.pipes_nlp_ns[src_id][dst_id][bundle_idx]
        elif src_type == 'tor' and dst_type == 'agg':
            if (src_id < len(self.queues_nlp_nup) and
                dst_id < len(self.queues_nlp_nup[src_id]) and
                bundle_idx < len(self.queues_nlp_nup[src_id][dst_id])):
                queue = self.queues_nlp_nup[src_id][dst_id][bundle_idx]
                pipe = self.pipes_nlp_nup[src_id][dst_id][bundle_idx]
        elif src_type == 'agg' and dst_type == 'tor':
            if (src_id < len(self.queues_nup_nlp) and
                dst_id < len(self.queues_nup_nlp[src_id]) and
                bundle_idx < len(self.queues_nup_nlp[src_id][dst_id])):
                queue = self.queues_nup_nlp[src_id][dst_id][bundle_idx]
                pipe = self.pipes_nup_nlp[src_id][dst_id][bundle_idx]
        elif src_type == 'agg' and dst_type == 'core':
            if (src_id < len(self.queues_nup_nc) and
                dst_id < len(self.queues_nup_nc[src_id]) and
                bundle_idx < len(self.queues_nup_nc[src_id][dst_id])):
                queue = self.queues_nup_nc[src_id][dst_id][bundle_idx]
                pipe = self.pipes_nup_nc[src_id][dst_id][bundle_idx]
        elif src_type == 'core' and dst_type == 'agg':
            if (src_id < len(self.queues_nc_nup) and
                dst_id < len(self.queues_nc_nup[src_id]) and
                bundle_idx < len(self.queues_nc_nup[src_id][dst_id])):
                queue = self.queues_nc_nup[src_id][dst_id][bundle_idx]
                pipe = self.pipes_nc_nup[src_id][dst_id][bundle_idx]
                
        if queue and pipe:
            # Mark as failed (implementation depends on queue/pipe classes)
            if hasattr(queue, 'set_failed'):
                queue.set_failed(True)
            if hasattr(pipe, 'set_failed'):
                pipe.set_failed(True)
            return True
        return False
        
    def _restore_components(self, src_type: str, src_id: int, dst_type: str,
                           dst_id: int, bundle_idx: int) -> bool:
        """Restore failed queue and pipe components."""
        # Get the appropriate queue and pipe based on link type
        queue = None
        pipe = None
        
        if src_type == 'host' and dst_type == 'tor':
            if (src_id < len(self.queues_ns_nlp) and 
                dst_id < len(self.queues_ns_nlp[src_id]) and
                bundle_idx < len(self.queues_ns_nlp[src_id][dst_id])):
                queue = self.queues_ns_nlp[src_id][dst_id][bundle_idx]
                pipe = self.pipes_ns_nlp[src_id][dst_id][bundle_idx]
        elif src_type == 'tor' and dst_type == 'host':
            if (src_id < len(self.queues_nlp_ns) and
                dst_id < len(self.queues_nlp_ns[src_id]) and
                bundle_idx < len(self.queues_nlp_ns[src_id][dst_id])):
                queue = self.queues_nlp_ns[src_id][dst_id][bundle_idx]
                pipe = self.pipes_nlp_ns[src_id][dst_id][bundle_idx]
        elif src_type == 'tor' and dst_type == 'agg':
            if (src_id < len(self.queues_nlp_nup) and
                dst_id < len(self.queues_nlp_nup[src_id]) and
                bundle_idx < len(self.queues_nlp_nup[src_id][dst_id])):
                queue = self.queues_nlp_nup[src_id][dst_id][bundle_idx]
                pipe = self.pipes_nlp_nup[src_id][dst_id][bundle_idx]
        elif src_type == 'agg' and dst_type == 'tor':
            if (src_id < len(self.queues_nup_nlp) and
                dst_id < len(self.queues_nup_nlp[src_id]) and
                bundle_idx < len(self.queues_nup_nlp[src_id][dst_id])):
                queue = self.queues_nup_nlp[src_id][dst_id][bundle_idx]
                pipe = self.pipes_nup_nlp[src_id][dst_id][bundle_idx]
        elif src_type == 'agg' and dst_type == 'core':
            if (src_id < len(self.queues_nup_nc) and
                dst_id < len(self.queues_nup_nc[src_id]) and
                bundle_idx < len(self.queues_nup_nc[src_id][dst_id])):
                queue = self.queues_nup_nc[src_id][dst_id][bundle_idx]
                pipe = self.pipes_nup_nc[src_id][dst_id][bundle_idx]
        elif src_type == 'core' and dst_type == 'agg':
            if (src_id < len(self.queues_nc_nup) and
                dst_id < len(self.queues_nc_nup[src_id]) and
                bundle_idx < len(self.queues_nc_nup[src_id][dst_id])):
                queue = self.queues_nc_nup[src_id][dst_id][bundle_idx]
                pipe = self.pipes_nc_nup[src_id][dst_id][bundle_idx]
                
        if queue and pipe:
            # Restore components (set failed to False)
            if hasattr(queue, 'set_failed'):
                queue.set_failed(False)
            if hasattr(pipe, 'set_failed'):
                pipe.set_failed(False)
            return True
        return False
        
    def check_non_null(self, route: Route) -> None:
        """Check that all elements in a route are non-null.
        
        Matches C++ check_non_null function behavior.
        """
        fail = False
        # In C++, it checks from index 1 to size-1 (skipping first and last)
        # In Python Route, we should check all queue/pipe elements
        for i in range(1, route.size() - 1):
            if route.at(i) is None:
                fail = True
                break
                
        if fail:
            # Print all components for debugging
            print("Null queue/pipe in route:")
            for i, element in enumerate(route._components):
                print(f"  [{i}]: {element}")
            assert False, "Route contains null elements"
        
    def add_switch_loggers(self, logfile, sampling_interval: int) -> None:
        """
        Add loggers to all switches.
        
        Args:
            logfile: Logfile instance for logging
            sampling_interval: Sampling interval in picoseconds
        """
        # Add loggers to ToR switches
        for switch in self.switches_lp:
            switch.add_logger(logfile, sampling_interval)
            
        # Add loggers to aggregation switches
        for switch in self.switches_up:
            switch.add_logger(logfile, sampling_interval)
            
        # Add loggers to core switches
        for switch in self.switches_c:
            switch.add_logger(logfile, sampling_interval)
        
    @classmethod
    def set_tier_parameters(cls, tier: int, radix_up: int, radix_down: int,
                           queue_up: int, queue_down: int, bundlesize: int,
                           linkspeed: int, oversub: int) -> None:
        """Set parameters for a specific tier.
        
        Args:
            tier: 0 for ToR, 1 for agg switch, 2 for core switch (matches C++)
        """
        # Map numeric tier to SwitchTier enum for internal storage
        tier_map = {0: SwitchTier.TOR_TIER, 1: SwitchTier.AGG_TIER, 2: SwitchTier.CORE_TIER}
        
        if tier not in tier_map:
            raise ValueError(f"Invalid tier {tier}. Must be 0 (ToR), 1 (Agg), or 2 (Core)")
            
        switch_tier = tier_map[tier]
        
        # Match C++ logic: no uplinks from core switches
        if tier < 2:  # CORE_TIER
            cls._tier_params[switch_tier]['radix_up'] = radix_up
            cls._tier_params[switch_tier]['queue_up'] = queue_up
        
        cls._tier_params[switch_tier]['radix_down'] = radix_down
        cls._tier_params[switch_tier]['queue_down'] = queue_down
        cls._tier_params[switch_tier]['bundlesize'] = bundlesize
        cls._tier_params[switch_tier]['downlink_speed'] = linkspeed
        cls._tier_params[switch_tier]['oversub'] = oversub
        cls._bundlesize[tier] = bundlesize
        
    def get_bidir_paths(self, src: int, dest: int, reverse: bool) -> List[Route]:
        """Get bidirectional paths between hosts.
        
        Matches C++ FatTreeTopology::get_bidir_paths logic exactly.
        """
        paths = []
        
        # Match C++ validation
        if src >= self._no_of_nodes or dest >= self._no_of_nodes:
            return paths
            
        if src == dest:
            return paths
            
        # Get ToR switches using C++ compatible methods
        src_tor = self.HOST_POD_SWITCH(src)
        dst_tor = self.HOST_POD_SWITCH(dest)
        
        # Check if same ToR switch (matches C++ if condition)
        if src_tor == dst_tor:
            # Direct path through same ToR
            route_out = Route()
            
            # Forward path: src -> ToR -> dst
            route_out.push_back(self.queues_ns_nlp[src][src_tor][0])
            route_out.push_back(self.pipes_ns_nlp[src][src_tor][0])
            
            route_out.push_back(self.queues_nlp_ns[dst_tor][dest][0])
            route_out.push_back(self.pipes_nlp_ns[dst_tor][dest][0])
            
            if reverse:
                # Reverse path for bidirectional
                route_back = Route()
                route_back.push_back(self.queues_ns_nlp[dest][dst_tor][0])
                route_back.push_back(self.pipes_ns_nlp[dest][dst_tor][0])
                route_back.push_back(self.queues_nlp_ns[src_tor][src][0])
                route_back.push_back(self.pipes_nlp_ns[src_tor][src][0])
                
                route_out.set_reverse(route_back)
                route_back.set_reverse(route_out)
            
            paths.append(route_out)
            self.check_non_null(route_out)
            return paths
            
        # Check if same pod  
        src_pod = self.HOST_POD(src)
        dst_pod = self.HOST_POD(dest)
        
        if src_pod == dst_pod:
            # Same pod - route through aggregation switches in pod
            pod = src_pod
            
            # Loop through all aggregation switches in the pod
            for upper in range(self.MIN_POD_AGG_SWITCH(pod), self.MAX_POD_AGG_SWITCH(pod) + 1):
                # Loop through bundle links
                for b_up in range(self._bundlesize[1]):  # AGG_TIER = 1
                    for b_down in range(self._bundlesize[1]):
                        route_out = Route()
                        
                        # src -> ToR
                        route_out.push_back(self.queues_ns_nlp[src][src_tor][0])
                        route_out.push_back(self.pipes_ns_nlp[src][src_tor][0])
                        
                        # ToR -> Agg (upward)
                        route_out.push_back(self.queues_nlp_nup[src_tor][upper][b_up])
                        route_out.push_back(self.pipes_nlp_nup[src_tor][upper][b_up])
                        
                        # Agg -> ToR (downward)
                        route_out.push_back(self.queues_nup_nlp[upper][dst_tor][b_down])
                        route_out.push_back(self.pipes_nup_nlp[upper][dst_tor][b_down])
                        
                        # ToR -> dst
                        route_out.push_back(self.queues_nlp_ns[dst_tor][dest][0])
                        route_out.push_back(self.pipes_nlp_ns[dst_tor][dest][0])
                        
                        if reverse:
                            # Build reverse path
                            route_back = Route()
                            
                            # dest -> ToR
                            route_back.push_back(self.queues_ns_nlp[dest][dst_tor][0])
                            route_back.push_back(self.pipes_ns_nlp[dest][dst_tor][0])
                            
                            # ToR -> Agg
                            route_back.push_back(self.queues_nlp_nup[dst_tor][upper][b_down])
                            route_back.push_back(self.pipes_nlp_nup[dst_tor][upper][b_down])
                            
                            # Agg -> ToR
                            route_back.push_back(self.queues_nup_nlp[upper][src_tor][b_up])
                            route_back.push_back(self.pipes_nup_nlp[upper][src_tor][b_up])
                            
                            # ToR -> src
                            route_back.push_back(self.queues_nlp_ns[src_tor][src][0])
                            route_back.push_back(self.pipes_nlp_ns[src_tor][src][0])
                            
                            route_out.set_reverse(route_back)
                            route_back.set_reverse(route_out)
                        
                        paths.append(route_out)
                        self.check_non_null(route_out)
        else:
            # Different pods - must go through core switches
            # Loop through all paths via core
            for upper in range(self.MIN_POD_AGG_SWITCH(src_pod), self.MAX_POD_AGG_SWITCH(src_pod) + 1):
                for upper2 in range(self.MIN_POD_AGG_SWITCH(dst_pod), self.MAX_POD_AGG_SWITCH(dst_pod) + 1):
                    # Compute core switch ID based on aggregation switches
                    # In fat tree, core switches connect specific agg switches across pods
                    agg_in_src_pod = upper % self._agg_switches_per_pod
                    agg_in_dst_pod = upper2 % self._agg_switches_per_pod
                    
                    # Each agg connects to k/2 core switches
                    # Core switch is determined by the agg switch positions
                    for c in range(self.k // 2):
                        core = agg_in_src_pod * (self.k // 2) + c
                        
                        # Check if this core connects to the dst agg
                        if (agg_in_dst_pod * (self.k // 2) <= core < (agg_in_dst_pod + 1) * (self.k // 2)):
                            # Valid path through this core
                            for b1_up in range(self._bundlesize[1]):  # src ToR -> src Agg
                                for b2_up in range(self._bundlesize[2]):  # src Agg -> Core
                                    for b2_down in range(self._bundlesize[2]):  # Core -> dst Agg
                                        for b1_down in range(self._bundlesize[1]):  # dst Agg -> dst ToR
                                            route_out = Route()
                                            
                                            # Build forward path
                                            # src -> ToR
                                            route_out.push_back(self.queues_ns_nlp[src][src_tor][0])
                                            route_out.push_back(self.pipes_ns_nlp[src][src_tor][0])
                                            
                                            # ToR -> Agg
                                            route_out.push_back(self.queues_nlp_nup[src_tor][upper][b1_up])
                                            route_out.push_back(self.pipes_nlp_nup[src_tor][upper][b1_up])
                                            
                                            # Agg -> Core
                                            route_out.push_back(self.queues_nup_nc[upper][core][b2_up])
                                            route_out.push_back(self.pipes_nup_nc[upper][core][b2_up])
                                            
                                            # Core -> Agg
                                            route_out.push_back(self.queues_nc_nup[core][upper2][b2_down])
                                            route_out.push_back(self.pipes_nc_nup[core][upper2][b2_down])
                                            
                                            # Agg -> ToR
                                            route_out.push_back(self.queues_nup_nlp[upper2][dst_tor][b1_down])
                                            route_out.push_back(self.pipes_nup_nlp[upper2][dst_tor][b1_down])
                                            
                                            # ToR -> dst
                                            route_out.push_back(self.queues_nlp_ns[dst_tor][dest][0])
                                            route_out.push_back(self.pipes_nlp_ns[dst_tor][dest][0])
                                            
                                            if reverse:
                                                # Build reverse path
                                                route_back = Route()
                                                
                                                # dest -> ToR
                                                route_back.push_back(self.queues_ns_nlp[dest][dst_tor][0])
                                                route_back.push_back(self.pipes_ns_nlp[dest][dst_tor][0])
                                                
                                                # ToR -> Agg
                                                route_back.push_back(self.queues_nlp_nup[dst_tor][upper2][b1_down])
                                                route_back.push_back(self.pipes_nlp_nup[dst_tor][upper2][b1_down])
                                                
                                                # Agg -> Core
                                                route_back.push_back(self.queues_nup_nc[upper2][core][b2_down])
                                                route_back.push_back(self.pipes_nup_nc[upper2][core][b2_down])
                                                
                                                # Core -> Agg
                                                route_back.push_back(self.queues_nc_nup[core][upper][b2_up])
                                                route_back.push_back(self.pipes_nc_nup[core][upper][b2_up])
                                                
                                                # Agg -> ToR
                                                route_back.push_back(self.queues_nup_nlp[upper][src_tor][b1_up])
                                                route_back.push_back(self.pipes_nup_nlp[upper][src_tor][b1_up])
                                                
                                                # ToR -> src
                                                route_back.push_back(self.queues_nlp_ns[src_tor][src][0])
                                                route_back.push_back(self.pipes_nlp_ns[src_tor][src][0])
                                                
                                                route_out.set_reverse(route_back)
                                                route_back.set_reverse(route_out)
                                            
                                            paths.append(route_out)
                                            self.check_non_null(route_out)
        
        print(f"pathcount {len(paths)}")
        return paths
        
    def _find_active_bundle(self, src_type: str, src_id: int, dst_type: str, 
                           dst_id: int, queues_array, pipes_array) -> int:
        """Find an active (non-failed) link in a bundle."""
        if (src_id < len(queues_array) and dst_id < len(queues_array[src_id]) and
            queues_array[src_id][dst_id]):
            # Check each link in the bundle
            for bundle_idx in range(len(queues_array[src_id][dst_id])):
                link_id = (src_type, src_id, dst_type, dst_id, bundle_idx)
                if link_id not in self._failed_links_set:
                    # Found active link
                    return bundle_idx
        return -1  # No active link found
        
    def _build_route(self, src_host: int, dst_host: int, src_tor: int, 
                    dst_tor: int, agg_id: int, core_id: int = -1,
                    dst_agg_id: int = -1) -> Optional[Route]:
        """Build a route through the fat-tree considering bundles and failures"""
        route = Route()
        
        # Source host
        route.push_back(self.hosts[src_host])
        
        # Host -> ToR (check for non-failed link in bundle)
        bundle_idx = self._find_active_bundle('host', src_host, 'tor', src_tor, 
                                            self.queues_ns_nlp, self.pipes_ns_nlp)
        if bundle_idx >= 0:
            route.push_back(self.queues_ns_nlp[src_host][src_tor][bundle_idx])
            route.push_back(self.pipes_ns_nlp[src_host][src_tor][bundle_idx])
            route.push_back(self.switches_lp[src_tor])
        else:
            return None
            
        if src_tor == dst_tor:
            # Same ToR - direct path to destination host
            bundle_idx = self._find_active_bundle('tor', dst_tor, 'host', dst_host,
                                                self.queues_nlp_ns, self.pipes_nlp_ns)
            if bundle_idx >= 0:
                route.push_back(self.queues_nlp_ns[dst_tor][dst_host][bundle_idx])
                route.push_back(self.pipes_nlp_ns[dst_tor][dst_host][bundle_idx])
            else:
                return None
        elif core_id == -1:
            # Same pod - through aggregation
            bundle_idx = self._find_active_bundle('tor', src_tor, 'agg', agg_id,
                                                self.queues_nlp_nup, self.pipes_nlp_nup)
            if bundle_idx >= 0:
                route.push_back(self.queues_nlp_nup[src_tor][agg_id][bundle_idx])
                route.push_back(self.pipes_nlp_nup[src_tor][agg_id][bundle_idx])
                route.push_back(self.switches_up[agg_id])
                
                bundle_idx = self._find_active_bundle('agg', agg_id, 'tor', dst_tor,
                                                    self.queues_nup_nlp, self.pipes_nup_nlp)
                if bundle_idx >= 0:
                    route.push_back(self.queues_nup_nlp[agg_id][dst_tor][bundle_idx])
                    route.push_back(self.pipes_nup_nlp[agg_id][dst_tor][bundle_idx])
                    route.push_back(self.switches_lp[dst_tor])
                else:
                    return None
            else:
                return None
        else:
            # Different pods - through core
            # ToR -> Agg
            bundle_idx = self._find_active_bundle('tor', src_tor, 'agg', agg_id,
                                                self.queues_nlp_nup, self.pipes_nlp_nup)
            if bundle_idx >= 0:
                route.push_back(self.queues_nlp_nup[src_tor][agg_id][bundle_idx])
                route.push_back(self.pipes_nlp_nup[src_tor][agg_id][bundle_idx])
                route.push_back(self.switches_up[agg_id])
                
                # Agg -> Core
                bundle_idx = self._find_active_bundle('agg', agg_id, 'core', core_id,
                                                    self.queues_nup_nc, self.pipes_nup_nc)
                if bundle_idx >= 0:
                    route.push_back(self.queues_nup_nc[agg_id][core_id][bundle_idx])
                    route.push_back(self.pipes_nup_nc[agg_id][core_id][bundle_idx])
                    route.push_back(self.switches_c[core_id])
                    
                    # Core -> Dst Agg
                    bundle_idx = self._find_active_bundle('core', core_id, 'agg', dst_agg_id,
                                                        self.queues_nc_nup, self.pipes_nc_nup)
                    if bundle_idx >= 0:
                        route.push_back(self.queues_nc_nup[core_id][dst_agg_id][bundle_idx])
                        route.push_back(self.pipes_nc_nup[core_id][dst_agg_id][bundle_idx])
                        route.push_back(self.switches_up[dst_agg_id])
                        
                        # Dst Agg -> Dst ToR
                        bundle_idx = self._find_active_bundle('agg', dst_agg_id, 'tor', dst_tor,
                                                            self.queues_nup_nlp, self.pipes_nup_nlp)
                        if bundle_idx >= 0:
                            route.push_back(self.queues_nup_nlp[dst_agg_id][dst_tor][bundle_idx])
                            route.push_back(self.pipes_nup_nlp[dst_agg_id][dst_tor][bundle_idx])
                            route.push_back(self.switches_lp[dst_tor])
                        else:
                            return None
                    else:
                        return None
                else:
                    return None
            else:
                return None
                
        # ToR -> Host
        bundle_idx = self._find_active_bundle('tor', dst_tor, 'host', dst_host,
                                            self.queues_nlp_ns, self.pipes_nlp_ns)
        if bundle_idx >= 0:
            route.push_back(self.queues_nlp_ns[dst_tor][dst_host][bundle_idx])
            route.push_back(self.pipes_nlp_ns[dst_tor][dst_host][bundle_idx])
            route.push_back(self.hosts[dst_host])
        else:
            return None
            
        return route
        
    def get_neighbours(self, src: int) -> Optional[List[int]]:
        """Fat-tree doesn't use direct neighbor concept"""
        return None
        
    def count_queue(self, queue: BaseQueue) -> None:
        """Count queue usage for statistics."""
        if not hasattr(self, '_link_usage'):
            self._link_usage = {}
            
        if queue not in self._link_usage:
            self._link_usage[queue] = 0
        self._link_usage[queue] += 1
        
    def no_of_nodes(self) -> int:
        """Get number of nodes in topology.
        
        Returns:
            Number of nodes (servers)
        """
        return self._no_of_nodes
        
    def print_path(self, file, src: int, route: Route) -> None:
        """Print a single path to file."""
        file.write(f"Path from host {src}:\n")
        
        if route and hasattr(route, '__len__'):
            file.write(f"  Length: {len(route)} hops\n")
            hop_num = 0
            for i, component in enumerate(route):
                if hasattr(component, 'get_name'):
                    name = component.get_name()
                    # Identify component type
                    if 'queue' in name.lower():
                        file.write(f"  Hop {hop_num}: Queue - {name}\n")
                    elif 'pipe' in name.lower():
                        file.write(f"  Hop {hop_num}: Pipe - {name}\n")
                        hop_num += 1
                    elif 'switch' in name.lower():
                        file.write(f"  Hop {hop_num}: Switch - {name}\n")
                    else:
                        file.write(f"  Component: {name}\n")
        else:
            file.write("  No route found\n")
            
        file.write("\n")
        
    def print_paths(self, file, src: int, paths: List[Route]) -> None:
        """Print all paths from a source to file."""
        file.write(f"All paths from host {src}:\n")
        file.write(f"Total paths available: {len(paths)}\n\n")
        
        for i, path in enumerate(paths):
            file.write(f"Path {i}:\n")
            self.print_path(file, src, path)
            
        # Print link usage statistics if available
        if hasattr(self, '_link_usage') and self._link_usage:
            file.write("\nLink Usage Statistics:\n")
            sorted_links = sorted(self._link_usage.items(), 
                                key=lambda x: x[1], reverse=True)
            for queue, count in sorted_links[:10]:  # Top 10 most used
                queue_name = queue.get_name() if hasattr(queue, 'get_name') else str(queue)
                file.write(f"  {queue_name}: {count} uses\n")
        
            
    def get_host(self, host_id: int) -> Optional[Host]:
        """Get a host by ID"""
        if 0 <= host_id < self._no_of_nodes:
            return self.hosts[host_id]
        return None
        
    def HOST_POD_SWITCH(self, src: int) -> int:
        """Get the ToR switch ID for a host.
        
        Matches C++ macro: src / _radix_down[TOR_TIER]
        """
        return src // self._tier_params[SwitchTier.TOR_TIER]['radix_down']
        
    def HOST_POD_ID(self, src: int) -> int:
        """Get the host's ID within its pod.
        
        Matches C++ macro logic.
        """
        if self._tiers == 3:
            return src % self._hosts_per_pod
        else:
            # Only one pod in leaf-spine
            return src
            
    def HOST_POD(self, src: int) -> int:
        """Get the pod ID for a host.
        
        Matches C++ macro: src / _hosts_per_pod
        """
        if self._tiers == 3:
            return src // self._hosts_per_pod
        else:
            # Only one pod in leaf-spine
            return 0
            
    def MIN_POD_TOR_SWITCH(self, pod_id: int) -> int:
        """Get the first ToR switch ID in a pod."""
        if self._tiers == 2:
            assert pod_id == 0
        return pod_id * self._tor_switches_per_pod
        
    def MAX_POD_TOR_SWITCH(self, pod_id: int) -> int:
        """Get the last ToR switch ID in a pod."""
        if self._tiers == 2:
            assert pod_id == 0
        return (pod_id + 1) * self._tor_switches_per_pod - 1
        
    def MIN_POD_AGG_SWITCH(self, pod_id: int) -> int:
        """Get the first aggregation switch ID in a pod."""
        if self._tiers == 2:
            assert pod_id == 0
        return pod_id * self._agg_switches_per_pod
        
    def MAX_POD_AGG_SWITCH(self, pod_id: int) -> int:
        """Get the last aggregation switch ID in a pod."""
        if self._tiers == 2:
            assert pod_id == 0
        return (pod_id + 1) * self._agg_switches_per_pod - 1
        
    def AGG_SWITCH_POD_ID(self, agg_switch_id: int) -> int:
        """Convert an aggregation switch ID to a pod ID."""
        return agg_switch_id // self._agg_switches_per_pod