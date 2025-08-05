"""
VL2 (Virtual Layer 2) topology for data center networks

Corresponds to vl2_topology.h/cpp in HTSim C++ implementation
Implements the VL2 architecture from Microsoft Research.
"""

from typing import List, Optional, Dict
from ..core.route import Route
from ..core.pipe import Pipe
from ..core.eventlist import EventList
from ..core.logger.logfile import Logfile
from ..queues.random_queue import RandomQueue
from ..queues.base_queue import BaseQueue
from .topology import Topology
from .firstfit import FirstFit
from .host import Host
from .constants import PACKET_SIZE, DEFAULT_BUFFER_SIZE


# VL2 specific constants - from main.h
NT2A = 2  # Number of connections from a ToR to aggregation switches

# Default VL2 configuration
DEFAULT_NI = 4   # Number of intermediate switches
DEFAULT_NA = 8   # Number of aggregation switches  
DEFAULT_NT = 16  # Number of ToR switches
DEFAULT_NS = 20  # Number of servers per ToR


class VL2Topology(Topology):
    """
    VL2 (Virtual Layer 2) topology implementation
    
    Three-tier architecture:
    - Intermediate switches (core layer)
    - Aggregation switches
    - ToR (Top of Rack) switches
    - Servers/hosts
    
    Key features:
    - Valiant Load Balancing (VLB)
    - Multiple paths between any pair of hosts
    - Clos network structure
    """
    
    def __init__(self,
                logfile: Logfile,
                eventlist: EventList,
                firstfit: Optional[FirstFit] = None,
                rtt: int = 1000000,  # 1us default
                ni: int = DEFAULT_NI,
                na: int = DEFAULT_NA,
                nt: int = DEFAULT_NT,
                ns: int = DEFAULT_NS,
                link_speed: int = 10000000000):  # 10Gbps default
        """
        Initialize VL2 topology
        
        Args:
            logfile: Logfile for logging
            eventlist: Event list
            firstfit: Optional FirstFit allocator
            rtt: Round-trip time in picoseconds
            ni: Number of intermediate switches
            na: Number of aggregation switches
            nt: Number of ToR switches
            ns: Number of servers per ToR
            link_speed: Link speed in bps
        """
        super().__init__()
        self.logfile = logfile
        self.eventlist = eventlist
        self.ff = firstfit
        self._rtt = rtt
        self._link_speed = link_speed
        
        # VL2 parameters
        self.NI = ni
        self.NA = na
        self.NT = nt
        self.NS = ns
        
        # Total number of nodes
        self._no_of_nodes = self.NT * self.NS
        
        # Network components - using 2D arrays as in C++
        # Intermediate to Aggregation
        self.pipes_ni_na = [[None for _ in range(na)] for _ in range(ni)]
        self.pipes_na_ni = [[None for _ in range(ni)] for _ in range(na)]
        self.queues_ni_na = [[None for _ in range(na)] for _ in range(ni)]
        self.queues_na_ni = [[None for _ in range(ni)] for _ in range(na)]
        
        # Aggregation to ToR
        self.pipes_na_nt = [[None for _ in range(nt)] for _ in range(na)]
        self.pipes_nt_na = [[None for _ in range(na)] for _ in range(nt)]
        self.queues_na_nt = [[None for _ in range(nt)] for _ in range(na)]
        self.queues_nt_na = [[None for _ in range(na)] for _ in range(nt)]
        
        # ToR to Servers
        self.pipes_nt_ns = [[None for _ in range(ns)] for _ in range(nt)]
        self.pipes_ns_nt = [[None for _ in range(nt)] for _ in range(ns)]
        self.queues_nt_ns = [[None for _ in range(ns)] for _ in range(nt)]
        self.queues_ns_nt = [[None for _ in range(nt)] for _ in range(ns)]
        
        # Hosts
        self.hosts: List[Host] = []
        
        # Initialize the network
        self.init_network()
        
    def init_network(self):
        """Initialize the VL2 network topology"""
        
        # Create hosts
        for tor in range(self.NT):
            for server in range(self.NS):
                host_id = self._host_id(server, tor)
                host = Host(f"host_{host_id}")
                host.set_host_id(host_id)
                self.hosts.append(host)
                
        # Create all pipes and queues
        # Intermediate to Aggregation links (full mesh)
        for i in range(self.NI):
            for a in range(self.NA):
                # Forward direction (NI -> NA)
                self.pipes_ni_na[i][a] = Pipe(self._rtt // 6, self.eventlist)
                self.queues_ni_na[i][a] = self._create_queue(f"q_ni{i}_na{a}")
                
                # Reverse direction (NA -> NI)
                self.pipes_na_ni[a][i] = Pipe(self._rtt // 6, self.eventlist)
                self.queues_na_ni[a][i] = self._create_queue(f"q_na{a}_ni{i}")
                
        # Aggregation to ToR links
        for a in range(self.NA):
            for t in range(self.NT):
                # Check if this ToR connects to this aggregation switch
                if self._tor_connects_to_agg(t, a):
                    # Forward direction (NA -> NT)
                    self.pipes_na_nt[a][t] = Pipe(self._rtt // 6, self.eventlist)
                    self.queues_na_nt[a][t] = self._create_queue(f"q_na{a}_nt{t}")
                    
                    # Reverse direction (NT -> NA)
                    self.pipes_nt_na[t][a] = Pipe(self._rtt // 6, self.eventlist)
                    self.queues_nt_na[t][a] = self._create_queue(f"q_nt{t}_na{a}")
                    
        # ToR to Server links
        for t in range(self.NT):
            for s in range(self.NS):
                # Forward direction (NT -> NS)
                self.pipes_nt_ns[t][s] = Pipe(self._rtt // 6, self.eventlist)
                self.queues_nt_ns[t][s] = self._create_queue(f"q_nt{t}_ns{s}")
                
                # Reverse direction (NS -> NT)  
                self.pipes_ns_nt[s][t] = Pipe(self._rtt // 6, self.eventlist)
                self.queues_ns_nt[s][t] = self._create_queue(f"q_ns{s}_nt{t}")
                
    def _create_queue(self, name: str) -> RandomQueue:
        """Create a queue with standard parameters"""
        queue = RandomQueue(
            bitrate=self._link_speed,
            maxsize=DEFAULT_BUFFER_SIZE * PACKET_SIZE,
            eventlist=self.eventlist,
            logger=None
        )
        queue.setName(name)
        
        if self.logfile:
            self.logfile.write_name(queue)
            
        if self.ff:
            self.ff.add_queue(queue)
            
        return queue
        
    def get_paths(self, src: int, dest: int) -> List[Route]:
        """Get paths using default direction"""
        return self.get_bidir_paths(src, dest, False)
        
    def get_bidir_paths(self, src: int, dest: int, reverse: bool) -> List[Route]:
        """
        Get bidirectional paths between hosts in VL2
        
        VL2 uses Valiant Load Balancing - traffic goes through a random
        intermediate switch regardless of source/destination location.
        """
        if reverse:
            src, dest = dest, src
            
        if src >= self._no_of_nodes or dest >= self._no_of_nodes:
            return []
            
        if src == dest:
            return []
            
        paths = []
        
        # Get ToR switches for source and destination
        src_tor = self._host_tor(src)
        dst_tor = self._host_tor(dest)
        
        # Get aggregation switches connected to source and destination ToRs
        src_aggs = self._get_agg_switches_for_tor(src_tor)
        dst_aggs = self._get_agg_switches_for_tor(dst_tor)
        
        # VL2 uses 2-hop routing through intermediate switches
        # Path: src -> src_tor -> src_agg -> intermediate -> dst_agg -> dst_tor -> dst
        
        for src_agg in src_aggs:
            for dst_agg in dst_aggs:
                # Try all intermediate switches
                for inter in range(self.NI):
                    route = self._build_vl2_route(src, dest, src_tor, dst_tor,
                                                 src_agg, dst_agg, inter)
                    if route:
                        paths.append(route)
                        
        return paths
        
    def _build_vl2_route(self, src_host: int, dst_host: int,
                        src_tor: int, dst_tor: int,
                        src_agg: int, dst_agg: int,
                        inter: int) -> Optional[Route]:
        """Build a VL2 route through the network"""
        route = Route()
        
        # Source host to source ToR
        src_server = self._host_tor_id(src_host)
        if (self.queues_ns_nt[src_server][src_tor] is None or
            self.pipes_ns_nt[src_server][src_tor] is None):
            return None
            
        route.push_back(self.hosts[src_host])
        route.push_back(self.queues_ns_nt[src_server][src_tor])
        route.push_back(self.pipes_ns_nt[src_server][src_tor])
        
        # Source ToR to source aggregation
        if (self.queues_nt_na[src_tor][src_agg] is None or
            self.pipes_nt_na[src_tor][src_agg] is None):
            return None
            
        route.push_back(self.queues_nt_na[src_tor][src_agg])
        route.push_back(self.pipes_nt_na[src_tor][src_agg])
        
        # Source aggregation to intermediate
        if (self.queues_na_ni[src_agg][inter] is None or
            self.pipes_na_ni[src_agg][inter] is None):
            return None
            
        route.push_back(self.queues_na_ni[src_agg][inter])
        route.push_back(self.pipes_na_ni[src_agg][inter])
        
        # Intermediate to destination aggregation
        if (self.queues_ni_na[inter][dst_agg] is None or
            self.pipes_ni_na[inter][dst_agg] is None):
            return None
            
        route.push_back(self.queues_ni_na[inter][dst_agg])
        route.push_back(self.pipes_ni_na[inter][dst_agg])
        
        # Destination aggregation to destination ToR
        if (self.queues_na_nt[dst_agg][dst_tor] is None or
            self.pipes_na_nt[dst_agg][dst_tor] is None):
            return None
            
        route.push_back(self.queues_na_nt[dst_agg][dst_tor])
        route.push_back(self.pipes_na_nt[dst_agg][dst_tor])
        
        # Destination ToR to destination host
        dst_server = self._host_tor_id(dst_host)
        if (self.queues_nt_ns[dst_tor][dst_server] is None or
            self.pipes_nt_ns[dst_tor][dst_server] is None):
            return None
            
        route.push_back(self.queues_nt_ns[dst_tor][dst_server])
        route.push_back(self.pipes_nt_ns[dst_tor][dst_server])
        route.push_back(self.hosts[dst_host])
        
        return route
        
    def get_neighbours(self, src: int) -> Optional[List[int]]:
        """VL2 doesn't use direct neighbor concept"""
        return None
        
    # Helper functions matching C++ macros
    def _host_id(self, hid: int, tid: int) -> int:
        """HOST_ID macro - get global host ID from server and ToR IDs"""
        return tid * self.NS + hid
        
    def _host_tor(self, host: int) -> int:
        """HOST_TOR macro - get ToR ID for a host"""
        return host // self.NS
        
    def _host_tor_id(self, host: int) -> int:
        """HOST_TOR_ID macro - get server ID within ToR"""
        return host % self.NS
        
    def _tor_agg1(self, tor: int) -> int:
        """TOR_AGG1 macro - primary aggregation switch for ToR"""
        return tor % self.NA
        
    def _tor_agg2(self, tor: int) -> int:
        """TOR_AGG2 macro - secondary aggregation switch for ToR"""
        return (10 * self.NA - tor - 1) % self.NA
        
    def _tor_connects_to_agg(self, tor: int, agg: int) -> bool:
        """Check if a ToR connects to an aggregation switch"""
        return agg == self._tor_agg1(tor) or agg == self._tor_agg2(tor)
        
    def _get_agg_switches_for_tor(self, tor: int) -> List[int]:
        """Get aggregation switches connected to a ToR"""
        return [self._tor_agg1(tor), self._tor_agg2(tor)]
        
    def get_host(self, host_id: int) -> Optional[Host]:
        """Get a host by ID"""
        if 0 <= host_id < self._no_of_nodes:
            return self.hosts[host_id]
        return None