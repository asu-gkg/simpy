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
from .constants import PACKET_SIZE, DEFAULT_BUFFER_SIZE, SWITCH_BUFFER, RANDOM_BUFFER, FEEDER_BUFFER, HOST_NIC, CORE_TO_HOST


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
        
    # Helper macros from C++
    def HOST_TOR(self, host: int) -> int:
        """Get ToR switch ID for a host"""
        return host // self.NS
        
    def HOST_TOR_ID(self, host: int) -> int:
        """Get host ID within its ToR switch"""
        return host % self.NS
        
    def TOR_AGG1(self, tor: int) -> int:
        """Get first aggregation switch for a ToR"""
        return tor % self.NA
        
    def TOR_AGG2(self, tor: int) -> int:
        """Get second aggregation switch for a ToR
        Uses the TOR_AGG2 macro from main.h"""
        # C++ uses complex macro: (10*NA - tor - 1)%NA
        # This provides a different agg switch than TOR_AGG1
        return (10 * self.NA - tor - 1) % self.NA
        
    def _host_id(self, server: int, tor: int) -> int:
        """Calculate global host ID from server and ToR IDs"""
        return tor * self.NS + server
        
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
                self.pipes_ni_na[i][a] = Pipe(self._rtt, self.eventlist)  # C++ uses full RTT
                self.queues_ni_na[i][a] = self._create_core_queue(f"Queue-ni-na-{i}-{a}")
                
                # Reverse direction (NA -> NI)
                self.pipes_na_ni[a][i] = Pipe(self._rtt, self.eventlist)  # C++ uses full RTT
                self.queues_na_ni[a][i] = self._create_core_queue(f"Queue-na-ni-{a}-{i}")
                
        # Aggregation to ToR links
        for a in range(self.NA):
            for t in range(self.NT):
                # Check if this ToR connects to this aggregation switch
                if self._tor_connects_to_agg(t, a):
                    # Forward direction (NA -> NT)
                    self.pipes_na_nt[a][t] = Pipe(self._rtt, self.eventlist)
                    self.queues_na_nt[a][t] = self._create_core_queue(f"Queue-na-nt-{a}-{t}")
                    
                    # Reverse direction (NT -> NA)
                    self.pipes_nt_na[t][a] = Pipe(self._rtt, self.eventlist)
                    self.queues_nt_na[t][a] = self._create_core_queue(f"Queue-nt-na-{t}-{a}")
                    
        # ToR to Server links
        for t in range(self.NT):
            for s in range(self.NS):
                # Forward direction (NT -> NS)
                self.pipes_nt_ns[t][s] = Pipe(self._rtt, self.eventlist)
                self.queues_nt_ns[t][s] = self._create_queue(f"Queue-nt-ns-{t}-{s}")
                
                # Reverse direction (NS -> NT)  
                self.pipes_ns_nt[s][t] = Pipe(self._rtt, self.eventlist)
                self.queues_ns_nt[s][t] = self._create_queue(f"Queue-ns-nt-{s}-{t}")
                
    def _create_queue(self, name: str, speed_multiplier: int = 1) -> RandomQueue:
        """Create a queue with standard parameters"""
        queue = RandomQueue(
            bitrate=HOST_NIC * 1000000 * speed_multiplier,  # Convert Mbps to bps
            maxsize=(SWITCH_BUFFER + RANDOM_BUFFER) * 1500 * 8,  # Convert packets to bits
            eventlist=self.eventlist,
            logger=None,
            drop_threshold=RANDOM_BUFFER * 1500 * 8
        )
        queue.setName(name)
        
        if self.logfile:
            self.logfile.write_name(queue)
            
        if self.ff:
            self.ff.add_queue(queue)
            
        return queue
        
    def _create_core_queue(self, name: str) -> RandomQueue:
        """Create a core network queue with higher speed"""
        return self._create_queue(name, CORE_TO_HOST)
        
    def get_paths(self, src: int, dest: int) -> List[Route]:
        """Get paths using default direction"""
        return self.get_bidir_paths(src, dest, False)
        
    def get_bidir_paths(self, src: int, dest: int, reverse: bool) -> List[Route]:
        """
        Get bidirectional paths between hosts in VL2
        
        Matches C++ VL2Topology::get_paths implementation
        """
        if reverse:
            src, dest = dest, src
            
        paths = []
        
        # Special case: same ToR switch
        if self.HOST_TOR(src) == self.HOST_TOR(dest):
            # Create PQueue (feeder buffer) as in C++
            from ..queues.base_queue import Queue
            pqueue = Queue(
                service_rate=CORE_TO_HOST * HOST_NIC * 1000000,  # Convert to bps
                max_size=FEEDER_BUFFER * 1500 * 8,
                eventlist=self.eventlist,
                logger=None
            )
            pqueue.setName(f"PQueue_{src}_{dest}")
            
            route = Route()
            route.push_back(pqueue)
            
            # Server to ToR
            route.push_back(self.queues_ns_nt[self.HOST_TOR_ID(src)][self.HOST_TOR(src)])
            route.push_back(self.pipes_ns_nt[self.HOST_TOR_ID(src)][self.HOST_TOR(src)])
            
            # ToR to server
            route.push_back(self.queues_nt_ns[self.HOST_TOR(dest)][self.HOST_TOR_ID(dest)])
            route.push_back(self.pipes_nt_ns[self.HOST_TOR(dest)][self.HOST_TOR_ID(dest)])
            
            paths.append(route)
            return paths
            
        # General case: different ToR switches
        # C++ creates 4*NI paths
        for i in range(4 * self.NI):
            # Create PQueue (feeder buffer) as in C++
            from ..queues.base_queue import Queue
            pqueue = Queue(
                service_rate=CORE_TO_HOST * HOST_NIC * 1000000,  # Convert to bps
                max_size=FEEDER_BUFFER * 1500 * 8,
                eventlist=self.eventlist,
                logger=None
            )
            pqueue.setName(f"PQueue_{src}_{dest}")
            
            route = Route()
            route.push_back(pqueue)
            
            # Server to ToR switch
            route.push_back(self.queues_ns_nt[self.HOST_TOR_ID(src)][self.HOST_TOR(src)])
            route.push_back(self.pipes_ns_nt[self.HOST_TOR_ID(src)][self.HOST_TOR(src)])
            
            # Choose aggregation switch for source
            if i < 2 * self.NI:
                agg_switch = self.TOR_AGG1(self.HOST_TOR(src))
            else:
                agg_switch = self.TOR_AGG2(self.HOST_TOR(src))
                
            # ToR to aggregation
            route.push_back(self.queues_nt_na[self.HOST_TOR(src)][agg_switch])
            route.push_back(self.pipes_nt_na[self.HOST_TOR(src)][agg_switch])
            
            # Aggregation to intermediate (i//4 selects the intermediate switch)
            route.push_back(self.queues_na_ni[agg_switch][i // 4])
            route.push_back(self.pipes_na_ni[agg_switch][i // 4])
            
            # Choose aggregation switch for destination
            if i % NT2A == 0:
                agg_switch_2 = self.TOR_AGG1(self.HOST_TOR(dest))
            else:
                agg_switch_2 = self.TOR_AGG2(self.HOST_TOR(dest))
                
            # Intermediate to aggregation
            route.push_back(self.queues_ni_na[i // 4][agg_switch_2])
            route.push_back(self.pipes_ni_na[i // 4][agg_switch_2])
            
            # Aggregation to ToR
            route.push_back(self.queues_na_nt[agg_switch_2][self.HOST_TOR(dest)])
            route.push_back(self.pipes_na_nt[agg_switch_2][self.HOST_TOR(dest)])
            
            # ToR to server
            route.push_back(self.queues_nt_ns[self.HOST_TOR(dest)][self.HOST_TOR_ID(dest)])
            route.push_back(self.pipes_nt_ns[self.HOST_TOR(dest)][self.HOST_TOR_ID(dest)])
            
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
        
    def no_of_nodes(self) -> int:
        """Get number of nodes in topology"""
        return self._no_of_nodes
        
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
        
    def _tor_connects_to_agg(self, tor: int, agg: int) -> bool:
        """Check if a ToR connects to an aggregation switch"""
        return agg == self.TOR_AGG1(tor) or agg == self.TOR_AGG2(tor)
        
    def _get_agg_switches_for_tor(self, tor: int) -> List[int]:
        """Get aggregation switches connected to a ToR"""
        return [self.TOR_AGG1(tor), self.TOR_AGG2(tor)]
        
    def get_host(self, host_id: int) -> Optional[Host]:
        """Get a host by ID"""
        if 0 <= host_id < self._no_of_nodes:
            return self.hosts[host_id]
        return None