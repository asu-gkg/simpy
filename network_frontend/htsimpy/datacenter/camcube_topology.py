"""CamCube topology implementation for HTSimPy."""

from typing import List, Optional, Tuple, Dict, Set
from .topology import Topology
from .host import Host
from ..core import Pipe, EventList, Route, Packet
from ..queues import PriorityQueue, RandomQueue, CompositeQueue
from ..queues.base_queue import BaseQueue as Queue
from .constants import HOST_NIC, SWITCH_BUFFER, RANDOM_BUFFER, FEEDER_BUFFER
from ..packets.tcp_packet import TcpPacket
from ..core.logger.logfile import Logfile
from ..core.logger.queue import QueueLoggerSampling
import math


class CamCubeTopology(Topology):
    """
    CamCube topology implementation.
    
    CamCube is a 3D torus direct-connect topology where each server is connected
    to 6 neighbors in a k×k×k cube arrangement.
    """
    
    def __init__(
        self,
        k: int,
        logfile: Logfile,
        eventlist: EventList,
        queue_type: str = "composite",
        rtt_ps: int = 1000,
        host_nic_mbps: int = HOST_NIC
    ):
        """
        Initialize CamCube topology.
        
        Args:
            k: Dimension of the cube (creates k^3 servers)
            logfile: Logfile instance for logging
            eventlist: EventList instance
            queue_type: Type of queue ("random", "composite", "composite_prio")
            rtt_ps: Round-trip time in picoseconds
            host_nic_mbps: Host NIC speed in Mbps
        """
        super().__init__()
        
        # Set number of nodes
        self._no_of_nodes = k * k * k  # k^3 servers
        
        # Input validation
        if k <= 0:
            raise ValueError(f"k must be positive, got {k}")
        if rtt_ps <= 0:
            raise ValueError(f"RTT must be positive, got {rtt_ps}")
        if host_nic_mbps <= 0:
            raise ValueError(f"Host NIC speed must be positive, got {host_nic_mbps}")
        if queue_type not in ["random", "composite", "composite_prio"]:
            raise ValueError(f"Invalid queue type: {queue_type}")
            
        self.k = k
        self.num_servers = k ** 3
        self.logfile = logfile
        self.eventlist = eventlist
        self.queue_type = queue_type
        self.rtt = rtt_ps
        self.host_nic_mbps = host_nic_mbps
        
        # Network components
        self.pipes: Dict[Tuple[int, int], Pipe] = {}  # (server, direction) -> Pipe
        self.queues: Dict[Tuple[int, int], Queue] = {}  # (server, direction) -> Queue
        self.prio_queues: Dict[Tuple[int, int], Queue] = {}  # Priority queues
        self.addresses: Dict[int, Tuple[int, int, int]] = {}  # server -> (x, y, z)
        
        # Initialize network
        self._init_network()
        
    def _init_network(self) -> None:
        """Initialize the network topology."""
        # Calculate addresses for all servers
        for srv in range(self.num_servers):
            self.addresses[srv] = self._address_from_srv(srv)
            
        # Create queues and pipes for each server
        for srv in range(self.num_servers):
            # Each server has 6 connections (±x, ±y, ±z)
            for direction in range(6):
                # Create priority queue
                logger = QueueLoggerSampling(1000000, self.eventlist)  # 1ms sampling
                self.logfile.addLogger(logger)
                
                prio_queue = self._alloc_src_queue(logger)
                if hasattr(prio_queue, 'setName'):
                    prio_queue.setName(f"PRIO_SRV_{srv}({direction})")
                self.prio_queues[(srv, direction)] = prio_queue
                
        # Create links along each axis
        for axis in range(3):
            for srv in range(self.num_servers):
                addr = self.addresses[srv]
                name = f"{addr[0]}{addr[1]}{addr[2]}"
                
                # Positive direction
                logger = QueueLoggerSampling(1000000, self.eventlist)
                if hasattr(self.logfile, 'addLogger'):
                    self.logfile.addLogger(logger)
                
                queue = self._alloc_queue(logger)
                if hasattr(queue, 'setName'):
                    queue.setName(f"SRV_{name}(axis_{axis})_pos")
                self.queues[(srv, axis)] = queue
                
                pipe = Pipe(self.rtt, self.eventlist)
                if hasattr(pipe, 'setName'):
                    pipe.setName(f"Pipe-SRV_{name}(axis_{axis})_pos")
                self.pipes[(srv, axis)] = pipe
                
                # Negative direction
                logger = QueueLoggerSampling(1000000, self.eventlist)
                if hasattr(self.logfile, 'addLogger'):
                    self.logfile.addLogger(logger)
                
                queue = self._alloc_queue(logger)
                if hasattr(queue, 'setName'):
                    queue.setName(f"SRV_{name}(axis_{axis})_neg")
                self.queues[(srv, axis + 3)] = queue
                
                pipe = Pipe(self.rtt, self.eventlist)
                if hasattr(pipe, 'setName'):
                    pipe.setName(f"Pipe-SRV_{name}(axis_{axis})_neg")
                self.pipes[(srv, axis + 3)] = pipe
                
    def _address_from_srv(self, srv: int) -> Tuple[int, int, int]:
        """Convert server ID to 3D address."""
        z = srv // (self.k * self.k)
        y = (srv - z * self.k * self.k) // self.k
        x = srv % self.k
        return (x, y, z)
        
    def _srv_from_address(self, address: Tuple[int, int, int]) -> int:
        """Convert 3D address to server ID."""
        return address[0] + address[1] * self.k + address[2] * self.k * self.k
        
    def _alloc_src_queue(self, logger) -> Queue:
        """Allocate source queue."""
        return PriorityQueue(
            self.host_nic_mbps * 1000000,  # Convert Mbps to bps
            FEEDER_BUFFER * 1500 * 8,  # Convert packets to bits
            self.eventlist,
            logger
        )
        
    def _alloc_queue(self, logger, speed_mbps: Optional[int] = None) -> Queue:
        """Allocate queue based on queue type."""
        if speed_mbps is None:
            speed_mbps = self.host_nic_mbps
            
        speed_bps = speed_mbps * 1000000
        
        if self.queue_type == "random":
            return RandomQueue(
                speed_bps,
                (SWITCH_BUFFER + RANDOM_BUFFER) * 1500 * 8,
                self.eventlist,
                logger,
                RANDOM_BUFFER * 1500 * 8
            )
        elif self.queue_type == "composite":
            return CompositeQueue(
                speed_bps,
                8 * 1500 * 8,  # 8 packets
                self.eventlist,
                logger
            )
        elif self.queue_type == "composite_prio":
            # Use CompositeQueue for now as CompositePrioQueue is not implemented
            return CompositeQueue(
                speed_bps,
                8 * 1500 * 8,
                self.eventlist,
                logger
            )
        else:
            raise ValueError(f"Unknown queue type: {self.queue_type}")
            
    def get_distance(self, src: int, dest: int, dimension: int) -> Tuple[int, int]:
        """Get distance between src and dest in given dimension.
        
        Returns:
            (distance, interface) where interface is the direction to go
        """
        src_coord = self.addresses[src][dimension]
        dest_coord = self.addresses[dest][dimension]
        
        # Calculate distances in both directions (torus wrap-around)
        a = (src_coord + self.k - dest_coord) % self.k
        b = (dest_coord + self.k - src_coord) % self.k
        
        if a < b:
            # Go negative direction
            iface = dimension + 3
            return (a, iface)
        else:
            # Go positive direction
            iface = dimension
            return (b, iface)
            
    def get_paths(self, src: int, dest: int) -> List[Route]:
        """Get all paths from src to dest."""
        return self.get_paths_camcube(src, dest)
        
    def get_paths_camcube(self, src: int, dest: int, first: bool = True) -> List[Route]:
        """
        Get CamCube paths using dimensional routing.
        
        Matches C++ CamCubeTopology::get_paths_camcube logic.
        """
        if src == dest:
            return []
            
        paths = []
        
        # Get distances in each dimension
        x_dist, ifx = self.get_distance(src, dest, 0)
        y_dist, ify = self.get_distance(src, dest, 1)
        z_dist, ifz = self.get_distance(src, dest, 2)
        
        # Build paths by routing in different dimension orders
        # This matches the C++ recursive approach
        current_addr = list(self.addresses[src])
        
        # Route in X dimension first
        if x_dist >= 1:
            # Move one hop in X direction
            if ifx < 3:
                current_addr[0] = (current_addr[0] + 1) % self.k
            else:
                current_addr[0] = (current_addr[0] + self.k - 1) % self.k
                
            next_srv = self._srv_from_address(current_addr)
            
            if next_srv == dest:
                # Direct path
                route = Route()
                if first and (src, ifx) in self.prio_queues:
                    route.push_back(self.prio_queues[(src, ifx)])
                route.push_back(self.queues[(src, ifx)])
                route.push_back(self.pipes[(src, ifx)])
                paths.append(route)
            else:
                # Recurse from next hop
                sub_paths = self.get_paths_camcube(next_srv, dest, False)
                for sub_route in sub_paths:
                    # Prepend current hop to sub_route (matches C++ push_front logic)
                    sub_route.push_front(self.pipes[(src, ifx)])
                    sub_route.push_front(self.queues[(src, ifx)])
                    if first and (src, ifx) in self.prio_queues:
                        sub_route.push_front(self.prio_queues[(src, ifx)])
                    paths.append(sub_route)
                    
        # Reset for Y dimension
        current_addr = list(self.addresses[src])
        
        # Route in Y dimension first  
        if y_dist >= 1:
            if ify < 3:
                current_addr[1] = (current_addr[1] + 1) % self.k
            else:
                current_addr[1] = (current_addr[1] + self.k - 1) % self.k
                
            next_srv = self._srv_from_address(current_addr)
            
            if next_srv == dest:
                route = Route()
                if first and (src, ify) in self.prio_queues:
                    route.push_back(self.prio_queues[(src, ify)])
                route.push_back(self.queues[(src, ify)])
                route.push_back(self.pipes[(src, ify)])
                paths.append(route)
            else:
                sub_paths = self.get_paths_camcube(next_srv, dest, False)
                for sub_route in sub_paths:
                    # Prepend current hop to sub_route (matches C++ push_front logic)
                    sub_route.push_front(self.pipes[(src, ify)])
                    sub_route.push_front(self.queues[(src, ify)])
                    if first and (src, ify) in self.prio_queues:
                        sub_route.push_front(self.prio_queues[(src, ify)])
                    paths.append(sub_route)
                    
        # Reset for Z dimension
        current_addr = list(self.addresses[src])
        
        # Route in Z dimension first
        if z_dist >= 1:
            if ifz < 3:
                current_addr[2] = (current_addr[2] + 1) % self.k
            else:
                current_addr[2] = (current_addr[2] + self.k - 1) % self.k
                
            next_srv = self._srv_from_address(current_addr)
            
            if next_srv == dest:
                route = Route()
                if first and (src, ifz) in self.prio_queues:
                    route.push_back(self.prio_queues[(src, ifz)])
                route.push_back(self.queues[(src, ifz)])
                route.push_back(self.pipes[(src, ifz)])
                paths.append(route)
            else:
                sub_paths = self.get_paths_camcube(next_srv, dest, False)
                for sub_route in sub_paths:
                    # Prepend current hop to sub_route (matches C++ push_front logic)
                    sub_route.push_front(self.pipes[(src, ifz)])
                    sub_route.push_front(self.queues[(src, ifz)])
                    if first and (src, ifz) in self.prio_queues:
                        sub_route.push_front(self.prio_queues[(src, ifz)])
                    paths.append(sub_route)
                    
        return paths
        
    def _get_neighbor(self, srv: int, dimension: int, positive: bool) -> int:
        """Get neighbor server in given dimension and direction."""
        addr = list(self.addresses[srv])
        if positive:
            addr[dimension] = (addr[dimension] + 1) % self.k
        else:
            addr[dimension] = (addr[dimension] - 1 + self.k) % self.k
        return self._srv_from_address(tuple(addr))
        
    def get_neighbours(self, src: int) -> List[int]:
        """Get all neighbors of a server."""
        neighbors = []
        for dim in range(3):
            # Positive direction
            neighbors.append(self._get_neighbor(src, dim, True))
            # Negative direction  
            neighbors.append(self._get_neighbor(src, dim, False))
        return neighbors
        
    def no_of_nodes(self) -> int:
        """Get number of nodes in topology.
        
        Returns:
            Number of nodes (servers)
        """
        return self._no_of_nodes
        
    def count_queue(self, queue: Queue) -> None:
        """Count queue (for statistics)."""
        # Initialize queue statistics if not exists
        if not hasattr(self, '_queue_stats'):
            self._queue_stats = {}
            
        # Count packets and bytes
        if queue not in self._queue_stats:
            self._queue_stats[queue] = {
                'count': 0,
                'total_bytes': 0,
                'max_occupancy': 0
            }
            
        self._queue_stats[queue]['count'] += 1
        
        if hasattr(queue, 'queuesize'):
            current_size = queue.queuesize()
            if current_size > self._queue_stats[queue]['max_occupancy']:
                self._queue_stats[queue]['max_occupancy'] = current_size
                
        if hasattr(queue, 'get_bytes_queued'):
            self._queue_stats[queue]['total_bytes'] += queue.get_bytes_queued()
        
    def print_path(self, file, src: int, route: Route) -> None:
        """Print path to file."""
        src_addr = self.addresses[src]
        file.write(f"Path from server {src} ({src_addr[0]},{src_addr[1]},{src_addr[2]}):\n")
        
        if route and hasattr(route, '__len__'):
            file.write(f"  Length: {len(route)} hops\n")
            for i, hop in enumerate(route):
                if hasattr(hop, 'get_name'):
                    file.write(f"  Hop {i}: {hop.get_name()}\n")
                else:
                    file.write(f"  Hop {i}: {hop}\n")
        else:
            file.write("  No route found\n")
            
        file.write("\n")
        
    def print_paths(self, file, src: int, paths: List[Route]) -> None:
        """Print all paths to file."""
        src_addr = self.addresses[src]
        file.write(f"All paths from server {src} ({src_addr[0]},{src_addr[1]},{src_addr[2]}):\n")
        file.write(f"Total paths: {len(paths)}\n\n")
        
        for i, path in enumerate(paths):
            file.write(f"Path {i}:\n")
            self.print_path(file, src, path)
            
        # Print queue statistics if available
        if hasattr(self, '_queue_stats') and self._queue_stats:
            file.write("\nQueue Statistics:\n")
            for queue, stats in self._queue_stats.items():
                queue_name = queue.get_name() if hasattr(queue, 'get_name') else str(queue)
                file.write(f"  {queue_name}:\n")
                file.write(f"    Count: {stats['count']}\n")
                file.write(f"    Max occupancy: {stats['max_occupancy']}\n")
                file.write(f"    Total bytes: {stats['total_bytes']}\n")