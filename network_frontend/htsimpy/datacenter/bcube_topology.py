"""
BCube topology for data center networks

Corresponds to bcube_topology.h/cpp in HTSim C++ implementation
Implements the BCube architecture - a server-centric network topology.
"""

import math
import random
from typing import List, Optional, Dict, Tuple
from ..core.route import Route
from ..core.pipe import Pipe
from ..core.eventlist import EventList
from ..core.logger.logfile import Logfile
from ..queues.random_queue import RandomQueue
from ..queues.base_queue import BaseQueue, Queue
from .topology import Topology
from .firstfit import FirstFit
from .host import Host
from .constants import PACKET_SIZE, DEFAULT_BUFFER_SIZE


class BCubeTopology(Topology):
    """
    BCube topology implementation
    
    BCube is a server-centric network topology where:
    - Servers have multiple NICs (K+1 NICs for a K-level BCube)
    - Each level uses switches to connect servers
    - Provides multiple disjoint paths between any pair of servers
    
    Key parameters:
    - K: Number of levels (0 to K)
    - n: Number of ports per switch
    - Total servers = n^(K+1)
    """
    
    def __init__(self,
                 logfile: Logfile,
                 eventlist: EventList,
                 firstfit: Optional[FirstFit] = None,
                 no_of_nodes: int = 16,
                 ports_per_switch: int = 4,
                 no_of_levels: int = 1,
                 rtt: int = 1000000,  # 1us default
                 link_speed: int = 10000000000):  # 10Gbps default
        """
        Initialize BCube topology
        
        Args:
            logfile: Logfile for logging
            eventlist: Event list
            firstfit: Optional FirstFit allocator
            no_of_nodes: Total number of servers
            ports_per_switch: Number of ports per switch (n)
            no_of_levels: Number of levels (K)
            rtt: Round-trip time in picoseconds
            link_speed: Link speed in bps
        """
        super().__init__()
        self.logfile = logfile
        self.eventlist = eventlist
        self.ff = firstfit
        self._rtt = rtt
        self._link_speed = link_speed
        
        # Set BCube parameters
        self._set_params(no_of_nodes, ports_per_switch, no_of_levels)
        
        # Network components - using 3D structure like C++
        # Indexed as [server][switch][level]
        self.pipes_srv_switch: List[List[List[Optional[Pipe]]]] = []
        self.pipes_switch_srv: List[List[List[Optional[Pipe]]]] = []
        self.queues_srv_switch: List[List[List[Optional[BaseQueue]]]] = []
        self.queues_switch_srv: List[List[List[Optional[BaseQueue]]]] = []
        
        # Priority queues for servers (one per NIC/level)
        self.prio_queues_srv: List[List[Optional[BaseQueue]]] = []
        
        # Server addresses - each server has an address at each level
        self.addresses: List[List[int]] = []
        
        # Hosts
        self.hosts: List[Host] = []
        
        # Link usage tracking
        self._link_usage: Dict[BaseQueue, int] = {}
        
        # Initialize the network
        self.init_network()
        
    def _set_params(self, no_of_nodes: int, ports_per_switch: int, no_of_levels: int):
        """Set BCube parameters and validate"""
        if no_of_nodes != ports_per_switch ** (no_of_levels + 1):
            raise ValueError(f"Incorrect BCube parameters: nodes={no_of_nodes}, "
                           f"expected {ports_per_switch}^{no_of_levels + 1}")
            
        self._K = no_of_levels
        self._NUM_PORTS = ports_per_switch
        self._NUM_SRV = no_of_nodes
        self._NUM_SW = (self._K + 1) * self._NUM_SRV // self._NUM_PORTS
        
    def init_network(self):
        """Initialize the BCube network topology"""
        
        # Create hosts
        for i in range(self._NUM_SRV):
            host = Host(f"host_{i}")
            host.set_host_id(i)
            self.hosts.append(host)
            
        # Initialize 3D arrays
        for i in range(self._NUM_SRV):
            srv_switches = []
            srv_prio = []
            srv_addr = []
            
            for j in range(self._NUM_SW):
                level_list_q = []
                level_list_p = []
                for k in range(self._K + 1):
                    level_list_q.append(None)
                    level_list_p.append(None)
                srv_switches.append(level_list_q)
                
            for k in range(self._K + 1):
                srv_prio.append(None)
                srv_addr.append(0)
                
            self.queues_srv_switch.append([level_list[:] for level_list in srv_switches])
            self.pipes_srv_switch.append([level_list[:] for level_list in srv_switches])
            self.prio_queues_srv.append(srv_prio)
            self.addresses.append(srv_addr)
            
        # Initialize switch arrays
        self.queues_switch_srv = []
        self.pipes_switch_srv = []
        for j in range(self._NUM_SW):
            switch_srvs_q = []
            switch_srvs_p = []
            for i in range(self._NUM_SRV):
                srv_levels_q = []
                srv_levels_p = []
                for k in range(self._K + 1):
                    srv_levels_q.append(None)
                    srv_levels_p.append(None)
                switch_srvs_q.append(srv_levels_q)
                switch_srvs_p.append(srv_levels_p)
            self.queues_switch_srv.append(switch_srvs_q)
            self.pipes_switch_srv.append(switch_srvs_p)
            
        # Compute addresses for each server
        for i in range(self._NUM_SRV):
            self._address_from_srv(i)
            
            # Create priority queues for each NIC/level
            for k in range(self._K + 1):
                queue = self._alloc_src_queue(f"PRIO_SRV_{i}({k})")
                self.prio_queues_srv[i][k] = queue
                
        # Create links for each level
        for k in range(self._K + 1):
            for i in range(self._NUM_SRV):
                # Get switch ID for this server at this level
                j = self._switch_from_srv(i, k)
                
                # Server to switch
                queue_ss = self._alloc_queue(f"SRV_{i}(level_{k})_SW_{j}")
                self.queues_srv_switch[i][j][k] = queue_ss
                
                pipe_ss = Pipe(self._rtt, self.eventlist)
                pipe_ss.setName(f"Pipe-SRV_{i}(level_{k})-SW_{j}")
                self.pipes_srv_switch[i][j][k] = pipe_ss
                
                if self.logfile:
                    self.logfile.write_name(queue_ss)
                    self.logfile.write_name(pipe_ss)
                    
                # Switch to server
                queue_sw = self._alloc_queue(f"SW_{j}(level_{k})-SRV_{i}")
                self.queues_switch_srv[j][i][k] = queue_sw
                
                pipe_sw = Pipe(self._rtt, self.eventlist)
                pipe_sw.setName(f"Pipe-SW_{j}(level_{k})-SRV_{i}")
                self.pipes_switch_srv[j][i][k] = pipe_sw
                
                if self.logfile:
                    self.logfile.write_name(queue_sw)
                    self.logfile.write_name(pipe_sw)
                    
    def _alloc_src_queue(self, name: str) -> BaseQueue:
        """Allocate a source queue (priority queue for server NICs)"""
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
        """Allocate a standard queue"""
        queue = RandomQueue(
            bitrate=self._link_speed,
            maxsize=DEFAULT_BUFFER_SIZE * PACKET_SIZE,
            eventlist=self.eventlist,
            logger=None
        )
        queue.setName(name)
        
        if self.ff:
            self.ff.add_queue(queue)
            
        return queue
        
    def _address_from_srv(self, srv: int):
        """Compute BCube address components for a server"""
        addr = srv
        crt_n = self._NUM_PORTS ** self._K
        
        for i in range(self._K, -1, -1):
            self.addresses[srv][i] = addr // crt_n
            addr = addr % crt_n
            crt_n //= self._NUM_PORTS
            
    def _srv_from_address(self, address: List[int]) -> int:
        """Get server ID from BCube address"""
        addr = 0
        crt_n = self._NUM_PORTS ** self._K
        
        for i in range(self._K, -1, -1):
            addr += crt_n * address[i]
            crt_n //= self._NUM_PORTS
            
        return addr
        
    def _switch_from_srv(self, srv: int, level: int) -> int:
        """Get switch ID for a server at a specific level"""
        switch_addr = 0
        crt_n = self._NUM_PORTS ** (self._K - 1)
        
        for i in range(self._K, -1, -1):
            if i == level:
                continue
            switch_addr += crt_n * self.addresses[srv][i]
            crt_n //= self._NUM_PORTS
            
        return switch_addr
        
    def get_neighbour(self, src: int, level: int) -> int:
        """Get a random neighbor at a specific level"""
        addr = self.addresses[src][:]
        
        # Find a different address at the specified level
        while True:
            new_val = random.randint(0, self._NUM_PORTS - 1)
            if new_val != self.addresses[src][level]:
                addr[level] = new_val
                break
                
        return self._srv_from_address(addr)
        
    def get_neighbours(self, src: int) -> List[int]:
        """Get all neighboring nodes"""
        if src >= self._NUM_SRV:
            return []
            
        neighbors = []
        
        # For each level, find all neighbors (differ in one dimension)
        for level in range(self._K + 1):
            addr = self.addresses[src][:]
            
            for port in range(self._NUM_PORTS):
                if port == self.addresses[src][level]:
                    continue
                    
                addr[level] = port
                neighbors.append(self._srv_from_address(addr))
                
        return neighbors
        
    def _bcube_routing(self, src: int, dest: int, permutation: List[int]) -> Tuple[Optional[Route], Optional[int]]:
        """
        BCube routing algorithm
        
        Returns:
            Tuple of (route, first_nic_used)
        """
        route = Route()
        crt_addr = self.addresses[src][:]
        crt = src
        first_nic = None
        
        # Process dimensions in permutation order
        for i in range(self._K, -1, -1):
            level = permutation[i]
            
            if self.addresses[src][level] != self.addresses[dest][level]:
                if first_nic is None:
                    first_nic = level
                    
                # Add hop from current server to switch at this level
                sw_id = self._switch_from_srv(crt, level)
                
                queue_out = self.queues_srv_switch[crt][sw_id][level]
                pipe_out = self.pipes_srv_switch[crt][sw_id][level]
                
                if queue_out is None or pipe_out is None:
                    return None, None
                    
                route.push_back(queue_out)
                route.push_back(pipe_out)
                
                # Correct the address digit at this level
                crt_addr[level] = self.addresses[dest][level]
                crt = self._srv_from_address(crt_addr)
                
                # Add hop from switch to next server
                queue_in = self.queues_switch_srv[sw_id][crt][level]
                pipe_in = self.pipes_switch_srv[sw_id][crt][level]
                
                if queue_in is None or pipe_in is None:
                    return None, None
                    
                route.push_back(queue_in)
                route.push_back(pipe_in)
                
        return route, first_nic
        
    def _dc_routing(self, src: int, dest: int, i: int) -> Optional[Route]:
        """Disjoint path routing - permutation based on level i"""
        permutation = [0] * (self._K + 1)
        m = self._K
        
        # Create permutation
        for j in range(i, i - self._K - 1, -1):
            permutation[m] = (j + self._K + 1) % (self._K + 1)
            m -= 1
            
        route, nic = self._bcube_routing(src, dest, permutation)
        if route is None or nic is None:
            return None
            
        # Add source priority queue
        full_route = Route()
        full_route.push_back(self.hosts[src])
        full_route.push_back(self.prio_queues_srv[src][nic])
        
        # Add the bcube route
        for element in route._elements:
            full_route.push_back(element)
            
        full_route.push_back(self.hosts[dest])
        
        return full_route
        
    def _alt_dc_routing(self, src: int, dest: int, i: int, intermediate: int) -> Optional[Route]:
        """Alternative routing through an intermediate node"""
        # First path: src to intermediate (standard permutation)
        permutation1 = list(range(self._K + 1))
        route1, nic = self._bcube_routing(src, intermediate, permutation1)
        
        if route1 is None or nic is None:
            return None
            
        # Second path: intermediate to dest (shifted permutation)
        permutation2 = [0] * (self._K + 1)
        m = self._K
        
        for j in range(i - 1, i - 1 - self._K - 1, -1):
            permutation2[m] = (j + self._K + 1) % (self._K + 1)
            m -= 1
            
        route2, _ = self._bcube_routing(intermediate, dest, permutation2)
        
        if route2 is None:
            return None
            
        # Combine paths
        full_route = Route()
        full_route.push_back(self.hosts[src])
        full_route.push_back(self.prio_queues_srv[src][nic])
        
        # Add first route
        for element in route1._elements:
            full_route.push_back(element)
            
        # Add second route
        for element in route2._elements:
            full_route.push_back(element)
            
        full_route.push_back(self.hosts[dest])
        
        return full_route
        
    def get_bidir_paths(self, src: int, dest: int, reverse: bool) -> List[Route]:
        """Get bidirectional paths between nodes"""
        if reverse:
            src, dest = dest, src
            
        if src >= self._NUM_SRV or dest >= self._NUM_SRV:
            return []
            
        if src == dest:
            return []
            
        paths = []
        
        # For each level, generate a path
        for i in range(self._K, -1, -1):
            level = i
            
            if self.addresses[src][level] != self.addresses[dest][level]:
                # Direct path possible at this level
                path = self._dc_routing(src, dest, level)
                if path:
                    paths.append(path)
            else:
                # Need to route through intermediate node
                intermediate = self.get_neighbour(src, level)
                path = self._alt_dc_routing(src, dest, level, intermediate)
                if path:
                    paths.append(path)
                    
        return paths
        
    def no_of_nodes(self) -> int:
        """Get number of hosts"""
        return self._NUM_SRV
        
    def get_host(self, host_id: int) -> Optional[Host]:
        """Get a host by ID"""
        if 0 <= host_id < self._NUM_SRV:
            return self.hosts[host_id]
        return None
        
    def count_queue(self, queue: BaseQueue):
        """Count queue usage"""
        if queue not in self._link_usage:
            self._link_usage[queue] = 0
        self._link_usage[queue] += 1