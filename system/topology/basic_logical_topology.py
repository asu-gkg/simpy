# Basic logical topology implementation - corresponds to topology/BasicLogicalTopology.hh/cc in SimAI

from typing import List, Dict, Any
from .logical_topology import LogicalTopology
from ..common import Tick


class BasicLogicalTopology(LogicalTopology):
    """Basic implementation of logical topology
    
    Corresponds to topology/BasicLogicalTopology.hh/cc in SimAI
    """
    
    def __init__(self, topology_name: str = "BasicTopology"):
        """Initialize basic logical topology
        
        Args:
            topology_name: Name of the topology
        """
        super().__init__(topology_name)
        
        # Basic topology specific properties
        self.dimension = 1
        self.nodes_per_dimension: List[int] = []
        self.stride: List[int] = []
        
        # Communication patterns
        self.communication_groups: Dict[str, List[int]] = {}
        
    def initialize_topology(self, nodes: List[int]) -> None:
        """Initialize the topology with given nodes
        
        Args:
            nodes: List of node IDs to include in the topology
        """
        self.node_list = sorted(nodes)
        self.num_nodes = len(nodes)
        
        # Initialize adjacency list for all nodes
        for node in nodes:
            self.adjacency_list[node] = []
        
        # Build the basic topology structure
        self._build_topology_structure()
        
        # Calculate distance matrix
        self._compute_all_distances()
    
    def _build_topology_structure(self) -> None:
        """Build the basic topology structure"""
        # For basic topology, create a simple linear arrangement
        # More complex topologies will override this method
        
        for i, node in enumerate(self.node_list):
            # Connect to previous node
            if i > 0:
                prev_node = self.node_list[i-1]
                self.add_edge(prev_node, node, latency=1, bandwidth=1.0)
            
            # Connect to next node
            if i < len(self.node_list) - 1:
                next_node = self.node_list[i+1]
                self.add_edge(node, next_node, latency=1, bandwidth=1.0)
    
    def get_route(self, src: int, dest: int) -> List[int]:
        """Get routing path from source to destination
        
        Args:
            src: Source node ID
            dest: Destination node ID
            
        Returns:
            List of node IDs in the routing path
        """
        if src == dest:
            return [src]
        
        if src not in self.node_list or dest not in self.node_list:
            return []
        
        # Use BFS to find shortest path
        path = self._find_shortest_path(src, dest)
        return path if path else []
    
    def _find_shortest_path(self, src: int, dest: int) -> List[int]:
        """Find shortest path between two nodes using BFS
        
        Args:
            src: Source node ID
            dest: Destination node ID
            
        Returns:
            List of nodes in the shortest path
        """
        if src == dest:
            return [src]
        
        visited = set()
        queue = [(src, [src])]
        
        while queue:
            current, path = queue.pop(0)
            
            if current in visited:
                continue
                
            visited.add(current)
            
            for neighbor in self.adjacency_list.get(current, []):
                new_path = path + [neighbor]
                
                if neighbor == dest:
                    return new_path
                
                if neighbor not in visited:
                    queue.append((neighbor, new_path))
        
        return []  # No path found
    
    def get_neighbors(self, node_id: int) -> List[int]:
        """Get neighbors of a node
        
        Args:
            node_id: Node ID to get neighbors for
            
        Returns:
            List of neighboring node IDs
        """
        return self.adjacency_list.get(node_id, [])
    
    def _compute_all_distances(self) -> None:
        """Compute distance matrix for all node pairs"""
        for src in self.node_list:
            for dest in self.node_list:
                if (src, dest) not in self.distance_matrix:
                    distance = self._calculate_distance(src, dest)
                    self.distance_matrix[(src, dest)] = distance
    
    def set_dimension(self, dimension: int, nodes_per_dim: List[int]) -> None:
        """Set topology dimension and structure
        
        Args:
            dimension: Number of dimensions
            nodes_per_dim: Number of nodes per dimension
        """
        self.dimension = dimension
        self.nodes_per_dimension = nodes_per_dim.copy()
        
        # Calculate stride for each dimension
        self.stride = [1]
        for i in range(dimension - 1):
            self.stride.append(self.stride[-1] * nodes_per_dim[i])
    
    def get_node_coordinates(self, node_id: int) -> List[int]:
        """Get coordinates of a node in the topology
        
        Args:
            node_id: Node ID
            
        Returns:
            List of coordinates for each dimension
        """
        if node_id not in self.node_list:
            return []
        
        coordinates = []
        remaining = node_id
        
        for i in range(self.dimension):
            coord = remaining // self.stride[i]
            coordinates.append(coord % self.nodes_per_dimension[i])
            remaining = remaining % self.stride[i]
        
        return coordinates
    
    def get_node_from_coordinates(self, coordinates: List[int]) -> int:
        """Get node ID from coordinates
        
        Args:
            coordinates: Coordinates for each dimension
            
        Returns:
            Node ID at the given coordinates
        """
        if len(coordinates) != self.dimension:
            return -1
        
        node_id = 0
        for i, coord in enumerate(coordinates):
            node_id += coord * self.stride[i]
        
        return node_id if node_id in self.node_list else -1
    
    def create_communication_group(self, group_name: str, nodes: List[int]) -> None:
        """Create a communication group
        
        Args:
            group_name: Name of the communication group
            nodes: List of nodes in the group
        """
        valid_nodes = [node for node in nodes if node in self.node_list]
        self.communication_groups[group_name] = valid_nodes
    
    def get_communication_group(self, group_name: str) -> List[int]:
        """Get nodes in a communication group
        
        Args:
            group_name: Name of the communication group
            
        Returns:
            List of nodes in the group
        """
        return self.communication_groups.get(group_name, [])
    
    def get_topology_diameter(self) -> int:
        """Get the diameter of the topology (maximum distance between any two nodes)
        
        Returns:
            Topology diameter
        """
        max_distance = 0
        for src in self.node_list:
            for dest in self.node_list:
                distance = self.get_distance(src, dest)
                if distance > max_distance:
                    max_distance = distance
        
        self.max_hops = max_distance
        return max_distance
    
    def get_average_distance(self) -> float:
        """Get average distance between all node pairs
        
        Returns:
            Average distance in the topology
        """
        total_distance = 0
        total_pairs = 0
        
        for src in self.node_list:
            for dest in self.node_list:
                if src != dest:
                    distance = self.get_distance(src, dest)
                    if distance >= 0:
                        total_distance += distance
                        total_pairs += 1
        
        return total_distance / total_pairs if total_pairs > 0 else 0.0 