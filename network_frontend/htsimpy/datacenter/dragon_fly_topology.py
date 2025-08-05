"""
DragonFly topology for data center networks

Corresponds to dragon_fly_topology.h/cpp in HTSim C++ implementation
Implements the DragonFly architecture - a high-radix network topology.
"""

import math
from typing import List, Optional, Dict, Tuple
from ..core.route import Route
from ..core.pipe import Pipe
from ..core.eventlist import EventList
from ..core.logger.logfile import Logfile
from ..queues.random_queue import RandomQueue
from ..queues.base_queue import BaseQueue, Queue
from ..core.switch import Switch
from .topology import Topology
from .firstfit import FirstFit
from .host import Host
from .constants import PACKET_SIZE, DEFAULT_BUFFER_SIZE, QueueType


class DragonFlyTopology(Topology):
    """
    DragonFly topology implementation
    
    DragonFly parameters:
    - p: Number of hosts per router
    - a: Number of routers per group  
    - h: Number of links used to connect to other groups
    - k: Router radix
    - g: Number of groups
    
    To balance channel load on load-balanced traffic:
    - a = 2p = 2h
    - p = h
    - k = p + h + a - 1 = 4h - 1
    - N = ap(ah+1) = 2h²(2h²+1) = 4h⁴ + 2h²
    - g <= ah + 1 = 2h² + 1
    """
    
    def __init__(self,
                 logfile: Logfile,
                 eventlist: EventList,
                 firstfit: Optional[FirstFit] = None,
                 p: Optional[int] = None,
                 a: Optional[int] = None,
                 h: Optional[int] = None,
                 no_of_nodes: Optional[int] = None,
                 queuesize: int = DEFAULT_BUFFER_SIZE * PACKET_SIZE,
                 queue_type: QueueType = QueueType.RANDOM,
                 rtt: int = 1000000,  # 1us default
                 link_speed: int = 10000000000):  # 10Gbps default
        """
        Initialize DragonFly topology
        
        Either provide (p, a, h) or no_of_nodes.
        If no_of_nodes is provided, optimal parameters will be calculated.
        
        Args:
            logfile: Logfile for logging
            eventlist: Event list
            firstfit: Optional FirstFit allocator
            p: Hosts per router (if specifying manually)
            a: Routers per group (if specifying manually)
            h: Inter-group links per router (if specifying manually)
            no_of_nodes: Total number of nodes (if auto-calculating)
            queuesize: Queue size in bytes
            queue_type: Type of queue to use
            rtt: Round-trip time in picoseconds
            link_speed: Link speed in bps
        """
        super().__init__()
        self.logfile = logfile
        self.eventlist = eventlist
        self.ff = firstfit
        self._queuesize = queuesize
        self._queue_type = queue_type
        self._rtt = rtt
        self._link_speed = link_speed
        
        # Set parameters
        if no_of_nodes is not None:
            self._set_params_from_nodes(no_of_nodes)
        elif p is not None and a is not None and h is not None:
            self._p = p
            self._a = a
            self._h = h
            self._no_of_nodes = a * p * (a * h + 1)
        else:
            raise ValueError("Must provide either no_of_nodes or (p, a, h)")
            
        self._set_params()
        
        # Network components
        self.switches: List[Optional[Switch]] = []
        
        # 2D arrays for connections
        self.pipes_host_switch: List[List[Optional[Pipe]]] = []
        self.pipes_switch_host: List[List[Optional[Pipe]]] = []
        self.queues_host_switch: List[List[Optional[BaseQueue]]] = []
        self.queues_switch_host: List[List[Optional[BaseQueue]]] = []
        
        self.pipes_switch_switch: List[List[Optional[Pipe]]] = []
        self.queues_switch_switch: List[List[Optional[BaseQueue]]] = []
        
        # Hosts
        self.hosts: List[Host] = []
        
        # Initialize the network
        self.init_network()
        
    def _set_params_from_nodes(self, no_of_nodes: int):
        """Calculate DragonFly parameters from number of nodes"""
        self._no_of_nodes = 0
        self._h = 0
        
        # Find minimum h such that the topology can accommodate no_of_nodes
        while self._no_of_nodes < no_of_nodes:
            self._h += 1
            self._p = self._h
            self._a = 2 * self._h
            self._no_of_nodes = self._a * self._p * (self._a * self._h + 1)
            
        if self._no_of_nodes > no_of_nodes:
            raise ValueError(f"Can't have a DragonFly with exactly {no_of_nodes} nodes. "
                           f"Closest is {self._no_of_nodes} nodes")
                           
    def _set_params(self):
        """Set derived parameters"""
        self._no_of_groups = self._a * self._h + 1
        self._no_of_switches = self._no_of_groups * self._a
        
        print(f"DragonFly topology with {self._p} hosts per router, "
              f"{self._a} routers per group and {self._no_of_groups} groups, "
              f"total nodes {self._no_of_nodes}")
              
    def init_network(self):
        """Initialize the DragonFly network topology"""
        
        # Create hosts
        for i in range(self._no_of_nodes):
            host = Host(f"host_{i}")
            host.set_host_id(i)
            self.hosts.append(host)
            
        # Initialize switches
        self.switches = [None] * self._no_of_switches
        if self._queue_type == QueueType.LOSSLESS:
            for j in range(self._no_of_switches):
                self.switches[j] = Switch(f"Switch_{j}", self.eventlist)
                
        # Initialize 2D arrays
        self.pipes_host_switch = [[None] * self._no_of_switches 
                                  for _ in range(self._no_of_nodes)]
        self.queues_host_switch = [[None] * self._no_of_switches 
                                   for _ in range(self._no_of_nodes)]
        
        self.pipes_switch_host = [[None] * self._no_of_nodes 
                                  for _ in range(self._no_of_switches)]
        self.queues_switch_host = [[None] * self._no_of_nodes 
                                   for _ in range(self._no_of_switches)]
        
        self.pipes_switch_switch = [[None] * self._no_of_switches 
                                    for _ in range(self._no_of_switches)]
        self.queues_switch_switch = [[None] * self._no_of_switches 
                                     for _ in range(self._no_of_switches)]
        
        # Create host-switch links
        for j in range(self._no_of_switches):
            for l in range(self._p):
                k = j * self._p + l
                if k >= self._no_of_nodes:
                    break
                    
                # Downlink (switch to host)
                queue_sh = self._alloc_queue(f"SW{j}->DST{k}", tor=True)
                self.queues_switch_host[j][k] = queue_sh
                
                pipe_sh = Pipe(self._rtt, self.eventlist)
                pipe_sh.setName(f"Pipe-SW{j}->DST{k}")
                self.pipes_switch_host[j][k] = pipe_sh
                
                if self.logfile:
                    self.logfile.write_name(queue_sh)
                    self.logfile.write_name(pipe_sh)
                    
                # Uplink (host to switch)
                queue_hs = self._alloc_src_queue(f"SRC{k}->SW{j}")
                self.queues_host_switch[k][j] = queue_hs
                
                pipe_hs = Pipe(self._rtt, self.eventlist)
                pipe_hs.setName(f"Pipe-SRC{k}->SW{j}")
                self.pipes_host_switch[k][j] = pipe_hs
                
                if self.logfile:
                    self.logfile.write_name(queue_hs)
                    self.logfile.write_name(pipe_hs)
                    
        # Create switch-switch links
        for j in range(self._no_of_switches):
            groupid = j // self._a
            
            # Intra-group links (full mesh within group)
            for k in range(j + 1, (groupid + 1) * self._a):
                if k >= self._no_of_switches:
                    break
                    
                # j -> k direction
                queue_jk = self._alloc_queue(f"SW{j}-I->SW{k}", tor=True)
                self.queues_switch_switch[j][k] = queue_jk
                
                pipe_jk = Pipe(self._rtt, self.eventlist)
                pipe_jk.setName(f"Pipe-SW{j}-I->SW{k}")
                self.pipes_switch_switch[j][k] = pipe_jk
                
                # k -> j direction
                queue_kj = self._alloc_queue(f"SW{k}-I->SW{j}", tor=False)
                self.queues_switch_switch[k][j] = queue_kj
                
                pipe_kj = Pipe(self._rtt, self.eventlist)
                pipe_kj.setName(f"Pipe-SW{k}-I->SW{j}")
                self.pipes_switch_switch[k][j] = pipe_kj
                
                if self.logfile:
                    self.logfile.write_name(queue_jk)
                    self.logfile.write_name(pipe_jk)
                    self.logfile.write_name(queue_kj)
                    self.logfile.write_name(pipe_kj)
                    
            # Inter-group links (global links)
            for l in range(self._h):
                targetgroupid = (j % self._a) * self._h + l
                
                # Only create links to groups with ID larger than ours
                if targetgroupid >= groupid:
                    targetgroupid += 1
                else:
                    continue
                    
                if targetgroupid >= self._no_of_groups:
                    continue
                    
                k = targetgroupid * self._a + groupid // self._h
                if k >= self._no_of_switches:
                    continue
                    
                # j -> k direction
                queue_jk = self._alloc_queue(f"SW{j}-G->SW{k}", tor=True)
                self.queues_switch_switch[j][k] = queue_jk
                
                pipe_jk = Pipe(self._rtt, self.eventlist)
                pipe_jk.setName(f"Pipe-SW{j}-G->SW{k}")
                self.pipes_switch_switch[j][k] = pipe_jk
                
                # k -> j direction  
                queue_kj = self._alloc_queue(f"SW{k}-G->SW{j}", tor=False)
                self.queues_switch_switch[k][j] = queue_kj
                
                pipe_kj = Pipe(self._rtt, self.eventlist)
                pipe_kj.setName(f"Pipe-SW{k}-G->SW{j}")
                self.pipes_switch_switch[k][j] = pipe_kj
                
                if self.logfile:
                    self.logfile.write_name(queue_jk)
                    self.logfile.write_name(pipe_jk)
                    self.logfile.write_name(queue_kj)
                    self.logfile.write_name(pipe_kj)
                    
    def _alloc_src_queue(self, name: str) -> BaseQueue:
        """Allocate a source queue"""
        # Using standard Queue for now - can be replaced with PriorityQueue
        queue = Queue(
            bitrate=self._link_speed,
            maxsize=100 * PACKET_SIZE,
            eventlist=self.eventlist,
            logger=None
        )
        queue.setName(name)
        
        if self.ff:
            self.ff.add_queue(queue)
            
        return queue
        
    def _alloc_queue(self, name: str, tor: bool = False) -> BaseQueue:
        """Allocate a queue based on queue type"""
        if self._queue_type == QueueType.RANDOM:
            queue = RandomQueue(
                bitrate=self._link_speed,
                maxsize=self._queuesize,
                eventlist=self.eventlist,
                logger=None
            )
        else:
            # Default to basic queue for other types
            queue = Queue(
                bitrate=self._link_speed,
                maxsize=self._queuesize,
                eventlist=self.eventlist,
                logger=None
            )
            
        queue.setName(name)
        
        if self.ff:
            self.ff.add_queue(queue)
            
        return queue
        
    def _host_tor(self, host: int) -> int:
        """Get ToR switch ID for a host"""
        return host // self._p
        
    def _host_group(self, host: int) -> int:
        """Get group ID for a host"""
        return host // (self._a * self._p)
        
    def get_bidir_paths(self, src: int, dest: int, reverse: bool) -> List[Route]:
        """Get bidirectional paths between nodes"""
        if reverse:
            src, dest = dest, src
            
        if src >= self._no_of_nodes or dest >= self._no_of_nodes:
            return []
            
        if src == dest:
            return []
            
        paths = []
        
        src_tor = self._host_tor(src)
        dest_tor = self._host_tor(dest)
        
        if src_tor == dest_tor:
            # Same ToR - direct path
            route = self._build_intra_tor_route(src, dest, src_tor)
            if route:
                paths.append(route)
                
        elif self._host_group(src) == self._host_group(dest):
            # Same group - use intra-group link
            route = self._build_intra_group_route(src, dest, src_tor, dest_tor)
            if route:
                paths.append(route)
                
        else:
            # Different groups - need global links
            
            # Add direct path if exists
            direct_route = self._build_inter_group_route(src, dest, src_tor, dest_tor)
            if direct_route:
                paths.append(direct_route)
                
            # Add indirect paths through other groups (Valiant routing)
            for p in range(self._no_of_groups):
                src_group = self._host_group(src)
                dest_group = self._host_group(dest)
                
                if p == src_group or p == dest_group:
                    continue
                    
                indirect_route = self._build_indirect_route(src, dest, src_tor, 
                                                           dest_tor, p)
                if indirect_route:
                    paths.append(indirect_route)
                    
        return paths
        
    def _build_intra_tor_route(self, src: int, dest: int, tor: int) -> Optional[Route]:
        """Build route for hosts on same ToR"""
        route = Route()
        
        # Source host to ToR
        route.push_back(self.hosts[src])
        
        queue_hs = self.queues_host_switch[src][tor]
        pipe_hs = self.pipes_host_switch[src][tor]
        
        if not queue_hs or not pipe_hs:
            return None
            
        route.push_back(queue_hs)
        route.push_back(pipe_hs)
        
        # ToR to destination host
        queue_sh = self.queues_switch_host[tor][dest]
        pipe_sh = self.pipes_switch_host[tor][dest]
        
        if not queue_sh or not pipe_sh:
            return None
            
        route.push_back(queue_sh)
        route.push_back(pipe_sh)
        
        route.push_back(self.hosts[dest])
        
        return route
        
    def _build_intra_group_route(self, src: int, dest: int, 
                                src_tor: int, dest_tor: int) -> Optional[Route]:
        """Build route for hosts in same group"""
        route = Route()
        
        # Source host to source ToR
        route.push_back(self.hosts[src])
        
        queue_hs = self.queues_host_switch[src][src_tor]
        pipe_hs = self.pipes_host_switch[src][src_tor]
        
        if not queue_hs or not pipe_hs:
            return None
            
        route.push_back(queue_hs)
        route.push_back(pipe_hs)
        
        # Source ToR to dest ToR
        queue_ss = self.queues_switch_switch[src_tor][dest_tor]
        pipe_ss = self.pipes_switch_switch[src_tor][dest_tor]
        
        if not queue_ss or not pipe_ss:
            return None
            
        route.push_back(queue_ss)
        route.push_back(pipe_ss)
        
        # Dest ToR to destination host
        queue_sh = self.queues_switch_host[dest_tor][dest]
        pipe_sh = self.pipes_switch_host[dest_tor][dest]
        
        if not queue_sh or not pipe_sh:
            return None
            
        route.push_back(queue_sh)
        route.push_back(pipe_sh)
        
        route.push_back(self.hosts[dest])
        
        return route
        
    def _build_inter_group_route(self, src: int, dest: int,
                                src_tor: int, dest_tor: int) -> Optional[Route]:
        """Build direct route between groups"""
        src_group = self._host_group(src)
        dest_group = self._host_group(dest)
        
        # Find switches with direct link between groups
        if src_group < dest_group:
            src_switch = src_group * self._a + (dest_group - 1) // self._h
            dest_switch = dest_group * self._a + src_group // self._h
        else:
            src_switch = src_group * self._a + dest_group // self._h
            dest_switch = dest_group * self._a + (src_group - 1) // self._h
            
        route = Route()
        route.push_back(self.hosts[src])
        
        # Source host to source ToR
        queue = self.queues_host_switch[src][src_tor]
        pipe = self.pipes_host_switch[src][src_tor]
        
        if not queue or not pipe:
            return None
            
        route.push_back(queue)
        route.push_back(pipe)
        
        # If source ToR is not the global switch, route to it
        if src_tor != src_switch:
            queue = self.queues_switch_switch[src_tor][src_switch]
            pipe = self.pipes_switch_switch[src_tor][src_switch]
            
            if not queue or not pipe:
                return None
                
            route.push_back(queue)
            route.push_back(pipe)
            
        # Global link between groups
        queue = self.queues_switch_switch[src_switch][dest_switch]
        pipe = self.pipes_switch_switch[src_switch][dest_switch]
        
        if not queue or not pipe:
            return None
            
        route.push_back(queue)
        route.push_back(pipe)
        
        # If dest switch is not the dest ToR, route to it
        if dest_switch != dest_tor:
            queue = self.queues_switch_switch[dest_switch][dest_tor]
            pipe = self.pipes_switch_switch[dest_switch][dest_tor]
            
            if not queue or not pipe:
                return None
                
            route.push_back(queue)
            route.push_back(pipe)
            
        # Dest ToR to destination host
        queue = self.queues_switch_host[dest_tor][dest]
        pipe = self.pipes_switch_host[dest_tor][dest]
        
        if not queue or not pipe:
            return None
            
        route.push_back(queue)
        route.push_back(pipe)
        
        route.push_back(self.hosts[dest])
        
        return route
        
    def _build_indirect_route(self, src: int, dest: int,
                            src_tor: int, dest_tor: int,
                            intermediate_group: int) -> Optional[Route]:
        """Build indirect route through an intermediate group (Valiant routing)"""
        # For simplicity, not implementing full indirect routing
        # This would require routing src->intermediate->dest
        return None
        
    def get_neighbours(self, src: int) -> Optional[List[int]]:
        """DragonFly doesn't use direct neighbor concept"""
        return None
        
    def no_of_nodes(self) -> int:
        """Get number of hosts"""
        return self._no_of_nodes
        
    def get_host(self, host_id: int) -> Optional[Host]:
        """Get a host by ID"""
        if 0 <= host_id < self._no_of_nodes:
            return self.hosts[host_id]
        return None