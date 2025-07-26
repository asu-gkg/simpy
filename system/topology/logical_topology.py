# Logical topology base class - corresponds to topology/LogicalTopology.hh/cc in SimAI

from typing import List, Dict, Tuple, Optional, Any
from abc import ABC, abstractmethod
from ..common import Tick


class LogicalTopology(ABC):
    """Base class for logical topologies in the simulation
    
    Corresponds to topology/LogicalTopology.hh/cc in SimAI
    """
    
    def __init__(self, topology_name: str):
        """Initialize logical topology
        
        Args:
            topology_name: Name of the topology
        """
        self.topology_name = topology_name
        self.num_nodes = 0
        self.node_list: List[int] = []
        
        # Routing tables and connectivity
        self.routing_table: Dict[Tuple[int, int], List[int]] = {}
        self.adjacency_list: Dict[int, List[int]] = {}
        self.distance_matrix: Dict[Tuple[int, int], int] = {}
        
        # Performance characteristics
        self.latency_matrix: Dict[Tuple[int, int], Tick] = {}
        self.bandwidth_matrix: Dict[Tuple[int, int], float] = {}
        
        # Topology properties
        self.is_directed = False
        self.is_symmetric = True
        self.max_hops = 0
    
    @abstractmethod
    def initialize_topology(self, nodes: List[int]) -> None:
        """Initialize the topology with given nodes
        
        Args:
            nodes: List of node IDs to include in the topology
        """
        pass
    
    @abstractmethod
    def get_route(self, src: int, dest: int) -> List[int]:
        """Get routing path from source to destination
        
        Args:
            src: Source node ID
            dest: Destination node ID
            
        Returns:
            List of node IDs in the routing path
        """
        pass
    
    @abstractmethod
    def get_neighbors(self, node_id: int) -> List[int]:
        """Get neighbors of a node
        
        Args:
            node_id: Node ID to get neighbors for
            
        Returns:
            List of neighboring node IDs
        """
        pass
    
    def add_node(self, node_id: int) -> None:
        """Add a node to the topology
        
        Args:
            node_id: Node ID to add
        """
        if node_id not in self.node_list:
            self.node_list.append(node_id)
            self.adjacency_list[node_id] = []
            self.num_nodes = len(self.node_list)
    
    def add_edge(self, src: int, dest: int, latency: Tick = 0, 
                 bandwidth: float = 1.0, bidirectional: bool = True) -> None:
        """Add an edge between two nodes
        
        Args:
            src: Source node ID
            dest: Destination node ID
            latency: Communication latency
            bandwidth: Link bandwidth
            bidirectional: Whether the link is bidirectional
        """
        # Add nodes if they don't exist
        self.add_node(src)
        self.add_node(dest)
        
        # Add edge to adjacency list
        if dest not in self.adjacency_list[src]:
            self.adjacency_list[src].append(dest)
        
        # Set latency and bandwidth
        self.latency_matrix[(src, dest)] = latency
        self.bandwidth_matrix[(src, dest)] = bandwidth
        
        # Add reverse edge if bidirectional
        if bidirectional:
            if src not in self.adjacency_list[dest]:
                self.adjacency_list[dest].append(src)
            self.latency_matrix[(dest, src)] = latency
            self.bandwidth_matrix[(dest, src)] = bandwidth
    
    def remove_edge(self, src: int, dest: int, bidirectional: bool = True) -> None:
        """Remove an edge between two nodes
        
        Args:
            src: Source node ID
            dest: Destination node ID
            bidirectional: Whether to remove both directions
        """
        if src in self.adjacency_list and dest in self.adjacency_list[src]:
            self.adjacency_list[src].remove(dest)
            
        # Remove from matrices
        if (src, dest) in self.latency_matrix:
            del self.latency_matrix[(src, dest)]
        if (src, dest) in self.bandwidth_matrix:
            del self.bandwidth_matrix[(src, dest)]
        
        # Remove reverse edge if bidirectional
        if bidirectional:
            if dest in self.adjacency_list and src in self.adjacency_list[dest]:
                self.adjacency_list[dest].remove(src)
            if (dest, src) in self.latency_matrix:
                del self.latency_matrix[(dest, src)]
            if (dest, src) in self.bandwidth_matrix:
                del self.bandwidth_matrix[(dest, src)]
    
    def get_distance(self, src: int, dest: int) -> int:
        """Get distance (number of hops) between two nodes
        
        Args:
            src: Source node ID
            dest: Destination node ID
            
        Returns:
            Number of hops between the nodes
        """
        if (src, dest) in self.distance_matrix:
            return self.distance_matrix[(src, dest)]
        
        # Use BFS to find shortest path
        return self._calculate_distance(src, dest)
    
    def get_latency(self, src: int, dest: int) -> Tick:
        """Get communication latency between two nodes
        
        Args:
            src: Source node ID
            dest: Destination node ID
            
        Returns:
            Communication latency
        """
        return self.latency_matrix.get((src, dest), 0)
    
    def get_bandwidth(self, src: int, dest: int) -> float:
        """Get bandwidth between two nodes
        
        Args:
            src: Source node ID
            dest: Destination node ID
            
        Returns:
            Link bandwidth
        """
        return self.bandwidth_matrix.get((src, dest), 0.0)
    
    def _calculate_distance(self, src: int, dest: int) -> int:
        """Calculate shortest distance using BFS
        
        Args:
            src: Source node ID
            dest: Destination node ID
            
        Returns:
            Shortest distance in hops
        """
        if src == dest:
            return 0
        
        if src not in self.adjacency_list or dest not in self.adjacency_list:
            return -1  # Invalid nodes
        
        # BFS to find shortest path
        visited = set()
        queue = [(src, 0)]
        
        while queue:
            current, distance = queue.pop(0)
            
            if current == dest:
                self.distance_matrix[(src, dest)] = distance
                return distance
            
            if current in visited:
                continue
                
            visited.add(current)
            
            for neighbor in self.adjacency_list[current]:
                if neighbor not in visited:
                    queue.append((neighbor, distance + 1))
        
        return -1  # No path found
    
    def is_connected(self, src: int, dest: int) -> bool:
        """Check if two nodes are connected
        
        Args:
            src: Source node ID
            dest: Destination node ID
            
        Returns:
            True if nodes are connected
        """
        return self.get_distance(src, dest) >= 0
    
    def get_topology_info(self) -> Dict[str, Any]:
        """Get topology information
        
        Returns:
            Dictionary containing topology statistics
        """
        return {
            'name': self.topology_name,
            'num_nodes': self.num_nodes,
            'num_edges': sum(len(neighbors) for neighbors in self.adjacency_list.values()),
            'is_directed': self.is_directed,
            'is_symmetric': self.is_symmetric,
            'max_hops': self.max_hops
        } 