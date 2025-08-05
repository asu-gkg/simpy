"""
Oversubscribed Fat Tree topology for data center networks

Corresponds to oversubscribed_fat_tree_topology.h/cpp in HTSim C++ implementation
Implements a fat-tree topology with oversubscription (more servers than bisection bandwidth).
"""

from typing import List, Optional, Dict
from ..core.route import Route
from ..core.pipe import Pipe
from ..core.eventlist import EventList
from ..core.logger.logfile import Logfile
from ..queues.random_queue import RandomQueue
from ..queues.base_queue import BaseQueue, Queue
from .topology import Topology
from .firstfit import FirstFit
from .host import Host
from .constants import PACKET_SIZE, DEFAULT_BUFFER_SIZE, QueueType


class OversubscribedFatTreeTopology(Topology):
    """
    Oversubscribed Fat Tree topology implementation
    
    Similar to regular fat tree but with oversubscription:
    - More servers connected to each ToR switch
    - Same number of uplinks, creating oversubscription
    
    Structure:
    - Core switches at the top
    - Upper pod switches (aggregation) 
    - Lower pod switches (ToR)
    - Servers at the bottom
    
    Key difference from regular fat tree:
    - Each ToR connects to 2*K servers instead of K
    - This creates 2:1 oversubscription ratio
    """
    
    def __init__(self,
                 logfile: Logfile,
                 eventlist: EventList,
                 firstfit: Optional[FirstFit] = None,
                 k: int = 8,
                 n: int = 1,  # Oversubscription factor
                 queuesize: int = DEFAULT_BUFFER_SIZE * PACKET_SIZE,
                 queue_type: QueueType = QueueType.RANDOM,
                 rtt: int = 1000000,  # 1us default
                 link_speed: int = 10000000000):  # 10Gbps default
        """
        Initialize oversubscribed fat tree topology
        
        Args:
            logfile: Logfile for logging
            eventlist: Event list
            firstfit: Optional FirstFit allocator
            k: Number of ports per switch (must be even)
            n: Oversubscription factor (servers = 2*K per ToR)
            queuesize: Queue size in bytes
            queue_type: Type of queue to use
            rtt: Round-trip time in picoseconds
            link_speed: Link speed in bps
        """
        super().__init__()
        self.logfile = logfile
        self.eventlist = eventlist
        self.ff = firstfit
        self._k = k
        self._n = n
        self._queuesize = queuesize
        self._queue_type = queue_type
        self._rtt = rtt
        self._link_speed = link_speed
        
        # Calculate topology dimensions
        self._nk = k * k // 2  # Number of upper/lower pod switches
        self._nc = k * k // 4  # Number of core switches
        self._nsrv = k * k * k  # Total servers (oversubscribed)
        self._no_of_nodes = self._nsrv
        
        # Network components - 2D arrays
        # Core to upper pod
        self.pipes_nc_nup: List[List[Optional[Pipe]]] = []
        self.queues_nc_nup: List[List[Optional[BaseQueue]]] = []
        self.pipes_nup_nc: List[List[Optional[Pipe]]] = []
        self.queues_nup_nc: List[List[Optional[BaseQueue]]] = []
        
        # Upper pod to lower pod
        self.pipes_nup_nlp: List[List[Optional[Pipe]]] = []
        self.queues_nup_nlp: List[List[Optional[BaseQueue]]] = []
        self.pipes_nlp_nup: List[List[Optional[Pipe]]] = []
        self.queues_nlp_nup: List[List[Optional[BaseQueue]]] = []
        
        # Lower pod to servers
        self.pipes_nlp_ns: List[List[Optional[Pipe]]] = []
        self.queues_nlp_ns: List[List[Optional[BaseQueue]]] = []
        self.pipes_ns_nlp: List[List[Optional[Pipe]]] = []
        self.queues_ns_nlp: List[List[Optional[BaseQueue]]] = []
        
        # Hosts
        self.hosts: List[Host] = []
        
        # Link usage tracking
        self._link_usage: Dict[BaseQueue, int] = {}
        
        # Initialize the network
        self.init_network()
        
    def init_network(self):
        """Initialize the oversubscribed fat tree network topology"""
        
        # Create hosts
        for i in range(self._nsrv):
            host = Host(f"host_{i}")
            host.set_host_id(i)
            self.hosts.append(host)
            
        # Initialize 2D arrays
        # Core to upper pod
        self.pipes_nc_nup = [[None] * self._nk for _ in range(self._nc)]
        self.queues_nc_nup = [[None] * self._nk for _ in range(self._nc)]
        self.pipes_nup_nc = [[None] * self._nc for _ in range(self._nk)]
        self.queues_nup_nc = [[None] * self._nc for _ in range(self._nk)]
        
        # Upper pod to lower pod
        self.pipes_nup_nlp = [[None] * self._nk for _ in range(self._nk)]
        self.queues_nup_nlp = [[None] * self._nk for _ in range(self._nk)]
        self.pipes_nlp_nup = [[None] * self._nk for _ in range(self._nk)]
        self.queues_nlp_nup = [[None] * self._nk for _ in range(self._nk)]
        
        # Lower pod to servers
        self.pipes_nlp_ns = [[None] * self._nsrv for _ in range(self._nk)]
        self.queues_nlp_ns = [[None] * self._nsrv for _ in range(self._nk)]
        self.pipes_ns_nlp = [[None] * self._nk for _ in range(self._nsrv)]
        self.queues_ns_nlp = [[None] * self._nk for _ in range(self._nsrv)]
        
        # Create lower pod switch to server connections
        for j in range(self._nk):
            # Each lower pod switch connects to 2*K servers (oversubscription)
            for l in range(2 * self._k):
                k = j * 2 * self._k + l
                if k >= self._nsrv:
                    continue
                    
                # Downlink
                queue_down = self._alloc_queue(f"LS_{j}-DST_{k}")
                self.queues_nlp_ns[j][k] = queue_down
                
                pipe_down = Pipe(self._rtt, self.eventlist)
                pipe_down.setName(f"Pipe-nt-ns-{j}-{k}")
                self.pipes_nlp_ns[j][k] = pipe_down
                
                # Uplink
                queue_up = self._alloc_src_queue(f"SRC_{k}-LS_{j}")
                self.queues_ns_nlp[k][j] = queue_up
                
                pipe_up = Pipe(self._rtt, self.eventlist)
                pipe_up.setName(f"Pipe-ns-nt-{k}-{j}")
                self.pipes_ns_nlp[k][j] = pipe_up
                
                if self.logfile:
                    self.logfile.write_name(queue_down)
                    self.logfile.write_name(pipe_down)
                    self.logfile.write_name(queue_up)
                    self.logfile.write_name(pipe_up)
                    
        # Create lower pod to upper pod connections
        for j in range(self._nk):
            podid = 2 * j // self._k
            
            # Connect to upper pod switches in same pod
            for k in range(self._min_pod_id(podid), self._max_pod_id(podid) + 1):
                if k >= self._nk:
                    continue
                    
                # Downlink
                queue_down = self._alloc_queue(f"US_{k}-LS_{j}")
                self.queues_nup_nlp[k][j] = queue_down
                
                pipe_down = Pipe(self._rtt, self.eventlist)
                pipe_down.setName(f"Pipe-na-nt-{k}-{j}")
                self.pipes_nup_nlp[k][j] = pipe_down
                
                # Uplink
                queue_up = self._alloc_queue(f"LS_{j}-US_{k}")
                self.queues_nlp_nup[j][k] = queue_up
                
                pipe_up = Pipe(self._rtt, self.eventlist)
                pipe_up.setName(f"Pipe-nt-na-{j}-{k}")
                self.pipes_nlp_nup[j][k] = pipe_up
                
                if self.logfile:
                    self.logfile.write_name(queue_down)
                    self.logfile.write_name(pipe_down)
                    self.logfile.write_name(queue_up)
                    self.logfile.write_name(pipe_up)
                    
        # Create upper pod to core connections
        for j in range(self._nk):
            podpos = j % (self._k // 2)
            
            for l in range(self._k // 2):
                k = podpos * self._k // 2 + l
                if k >= self._nc:
                    continue
                    
                # Uplink
                queue_up = self._alloc_queue(f"US_{j}-CS_{k}")
                self.queues_nup_nc[j][k] = queue_up
                
                pipe_up = Pipe(self._rtt, self.eventlist)
                pipe_up.setName(f"Pipe-nup-nc-{j}-{k}")
                self.pipes_nup_nc[j][k] = pipe_up
                
                # Downlink
                queue_down = self._alloc_queue(f"CS_{k}-US_{j}")
                self.queues_nc_nup[k][j] = queue_down
                
                pipe_down = Pipe(self._rtt, self.eventlist)
                pipe_down.setName(f"Pipe-nc-nup-{k}-{j}")
                self.pipes_nc_nup[k][j] = pipe_down
                
                if self.logfile:
                    self.logfile.write_name(queue_up)
                    self.logfile.write_name(pipe_up)
                    self.logfile.write_name(queue_down)
                    self.logfile.write_name(pipe_down)
                    
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
        
    def _alloc_queue(self, name: str) -> BaseQueue:
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
        
    def _host_pod_switch(self, src: int) -> int:
        """Get lower pod switch for a host"""
        return src // (2 * self._k)
        
    def _host_pod(self, src: int) -> int:
        """Get pod ID for a host"""
        return src // (self._k * self._k)
        
    def _min_pod_id(self, pod_id: int) -> int:
        """Get minimum upper pod switch ID for a pod"""
        return pod_id * self._k // 2
        
    def _max_pod_id(self, pod_id: int) -> int:
        """Get maximum upper pod switch ID for a pod"""
        return (pod_id + 1) * self._k // 2 - 1
        
    def get_bidir_paths(self, src: int, dest: int, reverse: bool) -> List[Route]:
        """Get bidirectional paths between nodes"""
        if reverse:
            src, dest = dest, src
            
        if src >= self._no_of_nodes or dest >= self._no_of_nodes:
            return []
            
        if src == dest:
            return []
            
        paths = []
        
        src_tor = self._host_pod_switch(src)
        dest_tor = self._host_pod_switch(dest)
        
        if src_tor == dest_tor:
            # Same ToR - direct path
            route = self._build_intra_tor_route(src, dest, src_tor)
            if route:
                paths.append(route)
                
        elif self._host_pod(src) == self._host_pod(dest):
            # Same pod - go through upper pod switches
            src_pod = self._host_pod(src)
            
            # Try all upper pod switches in the pod
            for up in range(self._min_pod_id(src_pod), self._max_pod_id(src_pod) + 1):
                route = self._build_intra_pod_route(src, dest, src_tor, dest_tor, up)
                if route:
                    paths.append(route)
                    
        else:
            # Different pods - go through core
            # Each path: src -> src_tor -> src_up -> core -> dest_up -> dest_tor -> dest
            
            src_pod = self._host_pod(src)
            dest_pod = self._host_pod(dest)
            
            # Try all combinations of upper pod switches and core switches
            for src_up in range(self._min_pod_id(src_pod), self._max_pod_id(src_pod) + 1):
                if src_up >= self._nk:
                    continue
                    
                # Each upper pod switch connects to K/2 core switches
                podpos = src_up % (self._k // 2)
                
                for l in range(self._k // 2):
                    core = podpos * self._k // 2 + l
                    if core >= self._nc:
                        continue
                        
                    # Find destination upper pod switch that connects to this core
                    for dest_up in range(self._min_pod_id(dest_pod), self._max_pod_id(dest_pod) + 1):
                        if dest_up >= self._nk:
                            continue
                            
                        dest_podpos = dest_up % (self._k // 2)
                        if core >= dest_podpos * self._k // 2 and core < (dest_podpos + 1) * self._k // 2:
                            route = self._build_inter_pod_route(src, dest, src_tor, dest_tor,
                                                              src_up, dest_up, core)
                            if route:
                                paths.append(route)
                                
        return paths
        
    def _build_intra_tor_route(self, src: int, dest: int, tor: int) -> Optional[Route]:
        """Build route for hosts on same ToR"""
        route = Route()
        
        # Source host to ToR
        route.push_back(self.hosts[src])
        
        queue_up = self.queues_ns_nlp[src][tor]
        pipe_up = self.pipes_ns_nlp[src][tor]
        
        if not queue_up or not pipe_up:
            return None
            
        route.push_back(queue_up)
        route.push_back(pipe_up)
        
        # ToR to destination host
        queue_down = self.queues_nlp_ns[tor][dest]
        pipe_down = self.pipes_nlp_ns[tor][dest]
        
        if not queue_down or not pipe_down:
            return None
            
        route.push_back(queue_down)
        route.push_back(pipe_down)
        
        route.push_back(self.hosts[dest])
        
        return route
        
    def _build_intra_pod_route(self, src: int, dest: int, src_tor: int, 
                              dest_tor: int, up: int) -> Optional[Route]:
        """Build route for hosts in same pod"""
        route = Route()
        
        # Source host to source ToR
        route.push_back(self.hosts[src])
        
        queue = self.queues_ns_nlp[src][src_tor]
        pipe = self.pipes_ns_nlp[src][src_tor]
        
        if not queue or not pipe:
            return None
            
        route.push_back(queue)
        route.push_back(pipe)
        
        # Source ToR to upper pod
        queue = self.queues_nlp_nup[src_tor][up]
        pipe = self.pipes_nlp_nup[src_tor][up]
        
        if not queue or not pipe:
            return None
            
        route.push_back(queue)
        route.push_back(pipe)
        
        # Upper pod to dest ToR
        queue = self.queues_nup_nlp[up][dest_tor]
        pipe = self.pipes_nup_nlp[up][dest_tor]
        
        if not queue or not pipe:
            return None
            
        route.push_back(queue)
        route.push_back(pipe)
        
        # Dest ToR to destination host
        queue = self.queues_nlp_ns[dest_tor][dest]
        pipe = self.pipes_nlp_ns[dest_tor][dest]
        
        if not queue or not pipe:
            return None
            
        route.push_back(queue)
        route.push_back(pipe)
        
        route.push_back(self.hosts[dest])
        
        return route
        
    def _build_inter_pod_route(self, src: int, dest: int, src_tor: int, dest_tor: int,
                              src_up: int, dest_up: int, core: int) -> Optional[Route]:
        """Build route between pods through core"""
        route = Route()
        
        # Source host to source ToR
        route.push_back(self.hosts[src])
        
        queue = self.queues_ns_nlp[src][src_tor]
        pipe = self.pipes_ns_nlp[src][src_tor]
        
        if not queue or not pipe:
            return None
            
        route.push_back(queue)
        route.push_back(pipe)
        
        # Source ToR to source upper pod
        queue = self.queues_nlp_nup[src_tor][src_up]
        pipe = self.pipes_nlp_nup[src_tor][src_up]
        
        if not queue or not pipe:
            return None
            
        route.push_back(queue)
        route.push_back(pipe)
        
        # Source upper pod to core
        queue = self.queues_nup_nc[src_up][core]
        pipe = self.pipes_nup_nc[src_up][core]
        
        if not queue or not pipe:
            return None
            
        route.push_back(queue)
        route.push_back(pipe)
        
        # Core to dest upper pod
        queue = self.queues_nc_nup[core][dest_up]
        pipe = self.pipes_nc_nup[core][dest_up]
        
        if not queue or not pipe:
            return None
            
        route.push_back(queue)
        route.push_back(pipe)
        
        # Dest upper pod to dest ToR
        queue = self.queues_nup_nlp[dest_up][dest_tor]
        pipe = self.pipes_nup_nlp[dest_up][dest_tor]
        
        if not queue or not pipe:
            return None
            
        route.push_back(queue)
        route.push_back(pipe)
        
        # Dest ToR to destination host
        queue = self.queues_nlp_ns[dest_tor][dest]
        pipe = self.pipes_nlp_ns[dest_tor][dest]
        
        if not queue or not pipe:
            return None
            
        route.push_back(queue)
        route.push_back(pipe)
        
        route.push_back(self.hosts[dest])
        
        return route
        
    def get_neighbours(self, src: int) -> Optional[List[int]]:
        """Get neighboring nodes - not used in fat tree"""
        return None
        
    def no_of_nodes(self) -> int:
        """Get number of hosts"""
        return self._no_of_nodes
        
    def get_host(self, host_id: int) -> Optional[Host]:
        """Get a host by ID"""
        if 0 <= host_id < self._no_of_nodes:
            return self.hosts[host_id]
        return None
        
    def count_queue(self, queue: BaseQueue):
        """Count queue usage"""
        if queue not in self._link_usage:
            self._link_usage[queue] = 0
        self._link_usage[queue] += 1