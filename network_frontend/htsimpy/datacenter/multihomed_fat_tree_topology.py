"""Multihomed Fat Tree topology implementation for HTSimPy."""

from typing import List, Optional, Dict, Set, Tuple
from .topology import Topology
from .host import Host
from ..core import Pipe, EventList, Route, Packet
from ..queues.base_queue import BaseQueue as Queue
from ..core.logger.logfile import Logfile
from ..queues import RandomQueue
from .constants import HOST_NIC, SWITCH_BUFFER, RANDOM_BUFFER
from ..core.logger.queue import QueueLoggerSampling


class MultihomedFatTreeTopology(Topology):
    """
    Multihomed Fat Tree topology implementation.
    
    This is a variant of the fat tree topology where servers have multiple
    connections to different leaf switches for redundancy and load balancing.
    """
    
    def __init__(
        self,
        k: int,
        logfile: Logfile,
        eventlist: EventList,
        rtt_ps: int = 1000,
        switch_speed_mbps: int = 10000,
        host_speed_mbps: int = 1000
    ):
        """
        Initialize Multihomed Fat Tree topology.
        
        Args:
            k: Number of ports per switch (must be even)
            logfile: Logfile instance for logging
            eventlist: EventList instance
            rtt_ps: Round-trip time in picoseconds
            switch_speed_mbps: Switch port speed in Mbps
            host_speed_mbps: Host NIC speed in Mbps
        """
        super().__init__()
        
        # Input validation
        if k <= 0:
            raise ValueError(f"k must be positive, got {k}")
        if k % 2 != 0:
            raise ValueError(f"k must be even for fat tree topology, got {k}")
        if rtt_ps <= 0:
            raise ValueError(f"RTT must be positive, got {rtt_ps}")
        if switch_speed_mbps <= 0:
            raise ValueError(f"Switch speed must be positive, got {switch_speed_mbps}")
        if host_speed_mbps <= 0:
            raise ValueError(f"Host speed must be positive, got {host_speed_mbps}")
            
        self.k = k
        self.logfile = logfile
        self.eventlist = eventlist
        self.rtt = rtt_ps
        self.switch_speed_mbps = switch_speed_mbps
        self.host_speed_mbps = host_speed_mbps
        
        # Calculate topology dimensions (matches C++ multihomed fat tree)
        self.num_pods = k
        self.num_core = (k // 2) ** 2  # NC = K*K/4
        self.num_agg = k * k // 2      # NK = K*K/2
        self.num_edge = k * k          # NLP = K*K
        self.num_servers = k * k * k // 3  # NSRV = K*K*K/3 (multihomed variant)
        
        # Network components - using dictionaries for sparse connectivity
        self.pipes_nc_nup: Dict[Tuple[int, int], Pipe] = {}
        self.pipes_nup_nlp: Dict[Tuple[int, int], Pipe] = {}
        self.pipes_nlp_ns: Dict[Tuple[int, int], Pipe] = {}
        self.queues_nc_nup: Dict[Tuple[int, int], RandomQueue] = {}
        self.queues_nup_nlp: Dict[Tuple[int, int], RandomQueue] = {}
        self.queues_nlp_ns: Dict[Tuple[int, int], RandomQueue] = {}
        
        # Reverse direction
        self.pipes_nup_nc: Dict[Tuple[int, int], Pipe] = {}
        self.pipes_nlp_nup: Dict[Tuple[int, int], Pipe] = {}
        self.pipes_ns_nlp: Dict[Tuple[int, int], Pipe] = {}
        self.queues_nup_nc: Dict[Tuple[int, int], RandomQueue] = {}
        self.queues_nlp_nup: Dict[Tuple[int, int], RandomQueue] = {}
        self.queues_ns_nlp: Dict[Tuple[int, int], RandomQueue] = {}
        
        self._no_of_nodes = self.num_servers
        self._link_usage: Dict[RandomQueue, int] = {}
        
        # Initialize network
        self._init_network()
        
    def HOST_POD_SWITCH1(self, src: int) -> int:
        """Get first pod switch for host.
        
        Matches C++ macro: 2*(3*src/K/2)
        """
        return 2 * (3 * src // self.k // 2)
        
    def HOST_POD_SWITCH2(self, src: int) -> int:
        """Get second pod switch for host.
        
        Matches C++ macro: 2*(3*src/K/2)+1
        """
        return 2 * (3 * src // self.k // 2) + 1
        
    def HOST_POD(self, src: int) -> int:
        """Get pod ID for host.
        
        Matches C++ macro: 3*src/(K*K)
        """
        return 3 * src // (self.k * self.k)
        
    def MIN_POD_ID(self, pod_id: int) -> int:
        """Get minimum aggregation switch ID in pod.
        
        Matches C++ macro: pod_id*K/2
        """
        return pod_id * self.k // 2
        
    def MAX_POD_ID(self, pod_id: int) -> int:
        """Get maximum aggregation switch ID in pod.
        
        Matches C++ macro: (pod_id+1)*K/2-1
        """
        return (pod_id + 1) * self.k // 2 - 1
        
    def _init_network(self) -> None:
        """Initialize the network topology."""
        # Initialize all queue and pipe arrays to None (matches C++)
        # Note: multihomed topology doesn't create switches - it's a pure queue/pipe topology
        
        # Create core to aggregation links
        for core in range(self.num_core):
            for pod in range(self.num_pods):
                agg_offset = pod * (self.k // 2) + core // (self.k // 2)
                
                # Core to aggregation
                self._create_link(
                    core, agg_offset,
                    self.pipes_nc_nup, self.queues_nc_nup,
                    f"pipe_c{core}_to_a{agg_offset}",
                    f"queue_c{core}_to_a{agg_offset}",
                    self.switch_speed_mbps
                )
                
                # Aggregation to core
                self._create_link(
                    agg_offset, core,
                    self.pipes_nup_nc, self.queues_nup_nc,
                    f"pipe_a{agg_offset}_to_c{core}",
                    f"queue_a{agg_offset}_to_c{core}",
                    self.switch_speed_mbps
                )
                
        # Create aggregation to edge links
        # Note: In multihomed topology, edge switches connect to only half of the aggregation switches
        for j in range(self.num_edge):  # NLP
            pod_id = j // self.k
            # Connect the edge switch to the aggregation switches in the same pod
            start = self.MIN_POD_ID(pod_id)
            end = self.MAX_POD_ID(pod_id)
            
            # If edge switch ID is even, connect to first half of agg switches
            # If odd, connect to second half
            if j % 2 == 0:
                end = (start + end) // 2
            else:
                start = (start + end) // 2 + 1
            
            for k in range(start, end + 1):
                    
                # Aggregation to edge (downlink)
                self._create_link(
                    k, j,
                    self.pipes_nup_nlp, self.queues_nup_nlp,
                    f"pipe_a{k}_to_e{j}",
                    f"queue_a{k}_to_e{j}",
                    self.switch_speed_mbps
                )
                
                # Edge to aggregation (uplink)
                self._create_link(
                    j, k,
                    self.pipes_nlp_nup, self.queues_nlp_nup,
                    f"pipe_e{j}_to_a{k}",
                    f"queue_e{j}_to_a{k}",
                    self.switch_speed_mbps
                )
                    
        # Create edge to server links (multihomed)
        # Each edge switch connects to 2*K/3 servers
        for j in range(self.num_edge):  # NLP
            for l in range(2 * self.k // 3):
                k = (j // 2) * 2 * self.k // 3 + l  # Server ID
                
                # Edge to server
                self._create_link(
                    j, k,
                    self.pipes_nlp_ns, self.queues_nlp_ns,
                    f"pipe_e{j}_to_s{k}",
                    f"queue_e{j}_to_s{k}",
                    self.host_speed_mbps
                )
                
                # Server to edge  
                self._create_link(
                    k, j,
                    self.pipes_ns_nlp, self.queues_ns_nlp,
                    f"pipe_s{k}_to_e{j}",
                    f"queue_s{k}_to_e{j}",
                    self.host_speed_mbps
                )
                
    def _create_link(
        self,
        src: int,
        dst: int,
        pipes_dict: Dict[Tuple[int, int], Pipe],
        queues_dict: Dict[Tuple[int, int], RandomQueue],
        pipe_name: str,
        queue_name: str,
        speed_mbps: int
    ) -> None:
        """Create a link with pipe and queue."""
        # Create queue logger
        logger = QueueLoggerSampling(1000000, self.eventlist)  # 1ms sampling
        self.logfile.addLogger(logger)
        
        # Create queue
        queue = RandomQueue(
            speed_mbps * 1000000,  # Convert to bps
            SWITCH_BUFFER * 1500 * 8,  # Convert packets to bits
            self.eventlist,
            logger,
            RANDOM_BUFFER * 1500 * 8
        )
        queue.setName(queue_name)
        queues_dict[(src, dst)] = queue
        
        # Create pipe
        pipe = Pipe(self.rtt, self.eventlist)
        pipe.setName(pipe_name)
        pipes_dict[(src, dst)] = pipe
        
    def _host_pod(self, srv: int) -> int:
        """Get pod ID for a server."""
        # In multihomed topology, servers are distributed across pods
        # Matches C++ HOST_POD macro: 3*src/(K*K)
        return 3 * srv // (self.k * self.k)
        
    def _host_pod_switches(self, srv: int) -> List[int]:
        """Get the edge switches a server is connected to."""
        # In multihomed topology, each server connects to 2 switches
        # SWITCH1 and SWITCH2
        return [self.HOST_POD_SWITCH1(srv), self.HOST_POD_SWITCH2(srv)]
        
    def get_paths(self, src: int, dest: int) -> List[Route]:
        """Get all paths from src to dest.
        
        Matches C++ MultihomedFatTreeTopology::get_paths logic.
        """
        paths = []
        
        # Check if hosts connect to same switches
        if self.HOST_POD_SWITCH1(src) == self.HOST_POD_SWITCH1(dest):
            # Direct paths through both switches the hosts share
            # C++ creates priority queues with 2*HOST_NIC speed
            from ..queues.base_queue import Queue
            from .constants import HOST_NIC, FEEDER_BUFFER
            
            # Path 1: Through first switch
            route1 = Route()
            
            # Create PQueue as in C++
            pqueue1 = Queue(
                service_rate=2 * HOST_NIC * 1000000,  # 2*HOST_NIC, convert to bps
                max_size=FEEDER_BUFFER * 1500 * 8,
                eventlist=self.eventlist,
                logger=None
            )
            pqueue1.setName(f"PQueue_{src}_{dest}")
            route1.push_back(pqueue1)
            
            # src -> edge switch 1
            if (src, self.HOST_POD_SWITCH1(src)) in self.queues_ns_nlp:
                route1.push_back(self.queues_ns_nlp[(src, self.HOST_POD_SWITCH1(src))])
                route1.push_back(self.pipes_ns_nlp[(src, self.HOST_POD_SWITCH1(src))])
                
                # edge switch 1 -> dest
                if (self.HOST_POD_SWITCH1(dest), dest) in self.queues_nlp_ns:
                    route1.push_back(self.queues_nlp_ns[(self.HOST_POD_SWITCH1(dest), dest)])
                    route1.push_back(self.pipes_nlp_ns[(self.HOST_POD_SWITCH1(dest), dest)])
                    paths.append(route1)
            
            # Path 2: Through second switch
            route2 = Route()
            
            # Create PQueue as in C++
            pqueue2 = Queue(
                service_rate=2 * HOST_NIC * 1000000,  # 2*HOST_NIC, convert to bps
                max_size=FEEDER_BUFFER * 1500 * 8,
                eventlist=self.eventlist,
                logger=None
            )
            pqueue2.setName(f"PQueue_{src}_{dest}")
            route2.push_back(pqueue2)
            
            # src -> edge switch 2
            if (src, self.HOST_POD_SWITCH2(src)) in self.queues_ns_nlp:
                route2.push_back(self.queues_ns_nlp[(src, self.HOST_POD_SWITCH2(src))])
                route2.push_back(self.pipes_ns_nlp[(src, self.HOST_POD_SWITCH2(src))])
                
                # edge switch 2 -> dest
                if (self.HOST_POD_SWITCH2(dest), dest) in self.queues_nlp_ns:
                    route2.push_back(self.queues_nlp_ns[(self.HOST_POD_SWITCH2(dest), dest)])
                    route2.push_back(self.pipes_nlp_ns[(self.HOST_POD_SWITCH2(dest), dest)])
                    paths.append(route2)
                    
            return paths
            
        elif self.HOST_POD(src) == self.HOST_POD(dest):
            # Same pod but different edge switches
            # Must go through aggregation switches
            
            pod = self.HOST_POD(src)
            # There are K/2 paths between source and destination
            for upper in range(self.MIN_POD_ID(pod), self.MAX_POD_ID(pod) + 1):
                route = Route()
                
                # Create PQueue as in C++ (with HOST_NIC speed, not 2*HOST_NIC)
                pqueue = Queue(
                    service_rate=HOST_NIC * 1000000,  # HOST_NIC, convert to bps
                    max_size=FEEDER_BUFFER * 1500 * 8,
                    eventlist=self.eventlist,
                    logger=None
                )
                pqueue.setName(f"PQueue_{src}_{dest}")
                route.push_back(pqueue)
                
                # Determine which switches to use based on upper switch position
                # This matches C++ logic where switches are divided between lower/upper half
                if upper <= (self.MIN_POD_ID(pod) + self.MAX_POD_ID(pod)) // 2:
                    sws = self.HOST_POD_SWITCH1(src)
                    swd = self.HOST_POD_SWITCH1(dest)
                else:
                    sws = self.HOST_POD_SWITCH2(src)
                    swd = self.HOST_POD_SWITCH2(dest)
                
                # src -> src_edge
                if (src, sws) in self.queues_ns_nlp:
                    route.push_back(self.queues_ns_nlp[(src, sws)])
                    route.push_back(self.pipes_ns_nlp[(src, sws)])
                    
                    # src_edge -> agg
                    if (sws, upper) in self.queues_nlp_nup:
                        route.push_back(self.queues_nlp_nup[(sws, upper)])
                        route.push_back(self.pipes_nlp_nup[(sws, upper)])
                        
                        # agg -> dest_edge
                        if (upper, swd) in self.queues_nup_nlp:
                            route.push_back(self.queues_nup_nlp[(upper, swd)])
                            route.push_back(self.pipes_nup_nlp[(upper, swd)])
                            
                            # dest_edge -> dest
                            if (swd, dest) in self.queues_nlp_ns:
                                route.push_back(self.queues_nlp_ns[(swd, dest)])
                                route.push_back(self.pipes_nlp_ns[(swd, dest)])
                                paths.append(route)
                                
            return paths
            
        else:
            # Different pods - must go through core
            pod = self.HOST_POD(src)
            pod_dest = self.HOST_POD(dest)
            
            for upper in range(self.MIN_POD_ID(pod), self.MAX_POD_ID(pod) + 1):
                # Core switches reachable from this aggregation switch
                for core in range((upper % (self.k // 2)) * self.k // 2, 
                                 ((upper % (self.k // 2)) + 1) * self.k // 2):
                    route = Route()
                    
                    # Create PQueue as in C++ (with HOST_NIC speed)
                    pqueue = Queue(
                        service_rate=HOST_NIC * 1000000,  # HOST_NIC, convert to bps
                        max_size=FEEDER_BUFFER * 1500 * 8,
                        eventlist=self.eventlist,
                        logger=None
                    )
                    pqueue.setName(f"PQueue_{src}_{dest}")
                    route.push_back(pqueue)
                    
                    # Determine source switch based on upper position
                    if upper <= (self.MIN_POD_ID(pod) + self.MAX_POD_ID(pod)) // 2:
                        sws = self.HOST_POD_SWITCH1(src)
                    else:
                        sws = self.HOST_POD_SWITCH2(src)
                    
                    # src -> src_edge
                    if (src, sws) in self.queues_ns_nlp:
                        route.push_back(self.queues_ns_nlp[(src, sws)])
                        route.push_back(self.pipes_ns_nlp[(src, sws)])
                        
                        # src_edge -> src_agg
                        if (sws, upper) in self.queues_nlp_nup:
                            route.push_back(self.queues_nlp_nup[(sws, upper)])
                            route.push_back(self.pipes_nlp_nup[(sws, upper)])
                            
                            # src_agg -> core
                            if (upper, core) in self.queues_nup_nc:
                                route.push_back(self.queues_nup_nc[(upper, core)])
                                route.push_back(self.pipes_nup_nc[(upper, core)])
                                
                                # Determine destination aggregation switch
                                upper2 = self.HOST_POD(dest) * self.k // 2 + 2 * core // self.k
                                
                                # Determine destination edge switch based on upper2 position
                                if upper2 <= (self.MIN_POD_ID(pod_dest) + self.MAX_POD_ID(pod_dest)) // 2:
                                    swd = self.HOST_POD_SWITCH1(dest)
                                else:
                                    swd = self.HOST_POD_SWITCH2(dest)
                                
                                # core -> dest_agg
                                if (core, upper2) in self.queues_nc_nup:
                                    route.push_back(self.queues_nc_nup[(core, upper2)])
                                    route.push_back(self.pipes_nc_nup[(core, upper2)])
                                    
                                    # dest_agg -> dest_edge
                                    if (upper2, swd) in self.queues_nup_nlp:
                                        route.push_back(self.queues_nup_nlp[(upper2, swd)])
                                        route.push_back(self.pipes_nup_nlp[(upper2, swd)])
                                        
                                        # dest_edge -> dest
                                        if (swd, dest) in self.queues_nlp_ns:
                                            route.push_back(self.queues_nlp_ns[(swd, dest)])
                                            route.push_back(self.pipes_nlp_ns[(swd, dest)])
                                            paths.append(route)
                                            
            return paths
        
    def get_neighbours(self, src: int) -> List[int]:
        """Get all direct neighbors of a node."""
        # For servers, neighbors are the connected edge switches
        neighbors = []
        if src < self.num_servers:
            # Check which edge switches this server connects to
            # Based on the init_network logic
            for j in range(self.num_edge):
                for l in range(2 * self.k // 3):
                    k = (j // 2) * 2 * self.k // 3 + l
                    if k == src:
                        neighbors.append(j)
        return neighbors
        
    def count_queue(self, queue: RandomQueue) -> None:
        """Count queue usage for statistics."""
        if queue in self._link_usage:
            self._link_usage[queue] += 1
        else:
            self._link_usage[queue] = 1
            
    def no_of_nodes(self) -> int:
        """Return number of nodes (servers) in topology."""
        return self._no_of_nodes
        
    def get_bidir_paths(self, src: int, dest: int, reverse: bool) -> List[Route]:
        """
        Get bidirectional paths between nodes.
        
        Args:
            src: Source node ID
            dest: Destination node ID
            reverse: Whether to get reverse path (dest to src)
            
        Returns:
            List of possible routes
        """
        if reverse:
            return self.get_paths(dest, src)
        else:
            return self.get_paths(src, dest)