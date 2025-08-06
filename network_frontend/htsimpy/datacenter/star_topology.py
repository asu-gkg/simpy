"""
Star topology for data center networks

Corresponds to star_topology.h/cpp in HTSim C++ implementation
Simple topology where all hosts connect to a central switch.
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
from .constants import FEEDER_BUFFER, SWITCH_BUFFER, RANDOM_BUFFER


class StarTopology(Topology):
    """
    Star topology implementation
    
    All hosts connect to a single central switch.
    This is the simplest possible datacenter topology,
    useful for testing and small deployments.
    """
    
    def __init__(self, 
                 logfile: Logfile,
                 eventlist: EventList,
                 firstfit: Optional[FirstFit] = None,
                 rtt: int = 1000000,  # 1ms default RTT
                 n_hosts: int = 576,   # Default number of hosts
                 link_speed: int = 10000000000):  # 10Gbps default
        """
        Initialize star topology
        
        Args:
            logfile: Logfile for logging
            eventlist: Event list
            firstfit: Optional FirstFit allocator
            rtt: Round-trip time in picoseconds
            n_hosts: Number of hosts
            link_speed: Link speed in bits per second
        """
        super().__init__()
        self.logfile = logfile
        self.eventlist = eventlist
        self.ff = firstfit
        self._rtt = rtt
        self._no_of_nodes = n_hosts
        self._link_speed = link_speed
        
        # Network components
        self.hosts: List[Host] = []
        self.pipes_out: List[Pipe] = []
        self.queues_out: List[RandomQueue] = []
        self.pipes_in: List[Pipe] = []
        self.queues_in: List[RandomQueue] = []
        
        # Link usage tracking
        self._link_usage: Dict[BaseQueue, int] = {}
        
        # Initialize the network
        self.init_network()
        
    def init_network(self):
        """Initialize the star network topology"""
        
        # Create hosts
        for i in range(self._no_of_nodes):
            host = Host(f"host_{i}")
            host.set_host_id(i)
            self.hosts.append(host)
            
        # Create pipes and queues for each host
        for i in range(self._no_of_nodes):
            # Outgoing (host to switch)
            pipe_out = Pipe(self._rtt, self.eventlist)  # C++ uses full RTT
            pipe_out.setName(f"Pipe-out-{i}")
            self.pipes_out.append(pipe_out)
            
            queue_out = RandomQueue(
                bitrate=self._link_speed,
                maxsize=(SWITCH_BUFFER + RANDOM_BUFFER) * 1500 * 8,  # Convert packets to bits
                eventlist=self.eventlist,
                logger=None,
                drop_threshold=(RANDOM_BUFFER) * 1500 * 8  # Match C++ memFromPkt(RANDOM_BUFFER)
            )
            queue_out.setName(f"OUT_{i}")  # Match C++ naming
            self.queues_out.append(queue_out)
            
            # Set host's output queue
            self.hosts[i].set_queue(queue_out)
            
            # Incoming (switch to host)
            pipe_in = Pipe(self._rtt, self.eventlist)  # C++ uses full RTT
            pipe_in.setName(f"Pipe-in-{i}")
            self.pipes_in.append(pipe_in)
            
            queue_in = RandomQueue(
                bitrate=self._link_speed,
                maxsize=(SWITCH_BUFFER + RANDOM_BUFFER) * 1500 * 8,  # Convert packets to bits
                eventlist=self.eventlist,
                logger=None,
                drop_threshold=(RANDOM_BUFFER) * 1500 * 8  # Match C++ memFromPkt(RANDOM_BUFFER)
            )
            queue_in.setName(f"IN_{i}")  # Match C++ naming
            self.queues_in.append(queue_in)
            
            # Register with logfile if needed
            if self.logfile:
                self.logfile.write_name(queue_out)
                self.logfile.write_name(queue_in)
                
            # Add queues to FirstFit if available
            if self.ff:
                self.ff.add_queue(queue_out)
                self.ff.add_queue(queue_in)
                
    def get_bidir_paths(self, src: int, dest: int, reverse: bool) -> List[Route]:
        """
        Get bidirectional paths between nodes
        
        In star topology, there's only one path between any two hosts:
        src -> queue_out -> pipe_out -> queue_in -> pipe_in -> dest
        
        Args:
            src: Source host ID
            dest: Destination host ID
            reverse: If True, get path from dest to src
            
        Returns:
            List containing the single available route
        """
        if reverse:
            src, dest = dest, src
            
        if src >= self._no_of_nodes or dest >= self._no_of_nodes:
            return []
            
        if src == dest:
            return []
            
        # Create route matching C++ implementation
        route = Route()
        
        # C++ creates a PQueue (feeder buffer) first
        from ..queues.base_queue import Queue
        pqueue = Queue(
            service_rate=self._link_speed,
            max_size=FEEDER_BUFFER * 1500 * 8,  # Convert packets to bits
            eventlist=self.eventlist,
            logger=None
        )
        pqueue.setName(f"PQueue_{src}_{dest}")
        
        # Build route: PQueue -> out_queue -> out_pipe -> in_queue -> in_pipe
        route.push_back(pqueue)
        route.push_back(self.queues_out[src])
        route.push_back(self.pipes_out[src])
        route.push_back(self.queues_in[dest])
        route.push_back(self.pipes_in[dest])
        
        return [route]
        
    def get_neighbours(self, src: int) -> List[int]:
        """
        Get neighboring nodes
        
        In star topology, all nodes are neighbors (connected via central switch)
        
        Args:
            src: Source node ID
            
        Returns:
            List of all other node IDs
        """
        if src >= self._no_of_nodes:
            return []
            
        # All other nodes are neighbors
        neighbors = []
        for i in range(self._no_of_nodes):
            if i != src:
                neighbors.append(i)
                
        return neighbors
        
    def count_queue(self, queue: RandomQueue):
        """
        Count queue usage
        
        Args:
            queue: Queue to count
        """
        if queue not in self._link_usage:
            self._link_usage[queue] = 0
        self._link_usage[queue] += 1
        
    def get_host(self, host_id: int) -> Optional[Host]:
        """
        Get a host by ID
        
        Args:
            host_id: Host ID
            
        Returns:
            The host or None if not found
        """
        if 0 <= host_id < self._no_of_nodes:
            return self.hosts[host_id]
        return None
        
    def get_link_usage(self) -> Dict[BaseQueue, int]:
        """
        Get link usage statistics
        
        Returns:
            Dictionary of queue to usage count
        """
        return self._link_usage.copy()
        
    def no_of_nodes(self) -> int:
        """
        Get number of nodes in topology
        
        Returns:
            Number of nodes (hosts)
        """
        return self._no_of_nodes