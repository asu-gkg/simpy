# Ring topology class - corresponds to topology/RingTopology.hh/cc in SimAI

from typing import Dict
from enum import Enum
from .basic_logical_topology import BasicLogicalTopology


class RingTopology(BasicLogicalTopology):
    """Ring topology implementation
    
    Corresponds to topology/RingTopology.hh/cc in SimAI
    """
    
    class Direction(Enum):
        """Ring traversal directions"""
        Clockwise = "Clockwise"
        Anticlockwise = "Anticlockwise"
    
    class Dimension(Enum):
        """Ring dimensions"""
        Local = "Local"
        Vertical = "Vertical"
        Horizontal = "Horizontal"
        NA = "NA"
    
    def __init__(
        self,
        dimension: 'RingTopology.Dimension',
        node_id: int,
        total_nodes_in_ring: int,
        index_in_ring: int,
        offset: int
    ):
        """Initialize ring topology
        
        Args:
            dimension: Ring dimension type
            node_id: This node's ID
            total_nodes_in_ring: Total number of nodes in the ring
            index_in_ring: Index of this node in the ring
            offset: Offset for node ID calculation
        """
        super().__init__(BasicLogicalTopology.BasicTopology.Ring)
        
        self.name = f"Ring_{dimension.value}"
        self.id = node_id
        self.next_node_id = -1
        self.previous_node_id = -1
        self.offset = offset
        self.total_nodes_in_ring = total_nodes_in_ring
        self.index_in_ring = index_in_ring
        self.dimension = dimension
        
        # Create mapping from ID to index
        self.id_to_index: Dict[int, int] = {}
        
        # Find neighbors
        self.find_neighbors()
    
    def get_num_of_nodes_in_dimension(self, dimension: int) -> int:
        """Get number of nodes in dimension
        
        Args:
            dimension: Dimension index (should be 0 for ring)
            
        Returns:
            Total nodes in the ring
        """
        return self.total_nodes_in_ring
    
    def find_neighbors(self) -> None:
        """Find neighboring nodes in the ring"""
        if self.total_nodes_in_ring <= 1:
            return
        
        # Calculate next node (clockwise)
        next_index = (self.index_in_ring + 1) % self.total_nodes_in_ring
        self.next_node_id = self.offset + next_index
        
        # Calculate previous node (anticlockwise)
        prev_index = (self.index_in_ring - 1) % self.total_nodes_in_ring
        self.previous_node_id = self.offset + prev_index
        
        # Build ID to index mapping
        for i in range(self.total_nodes_in_ring):
            node_id = self.offset + i
            self.id_to_index[node_id] = i
    
    def get_receiver_node(self, node_id: int, direction: Direction) -> int:
        """Get receiver node for a given node and direction
        
        Args:
            node_id: Source node ID
            direction: Direction to send
            
        Returns:
            Receiver node ID
        """
        if node_id not in self.id_to_index:
            return -1
        
        index = self.id_to_index[node_id]
        
        if direction == RingTopology.Direction.Clockwise:
            next_index = (index + 1) % self.total_nodes_in_ring
        else:  # Anticlockwise
            next_index = (index - 1) % self.total_nodes_in_ring
        
        return self.offset + next_index
    
    def get_sender_node(self, node_id: int, direction: Direction) -> int:
        """Get sender node for a given node and direction
        
        Args:
            node_id: Destination node ID
            direction: Direction of sending
            
        Returns:
            Sender node ID
        """
        if node_id not in self.id_to_index:
            return -1
        
        index = self.id_to_index[node_id]
        
        if direction == RingTopology.Direction.Clockwise:
            prev_index = (index - 1) % self.total_nodes_in_ring
        else:  # Anticlockwise
            prev_index = (index + 1) % self.total_nodes_in_ring
        
        return self.offset + prev_index
    
    def get_nodes_in_ring(self) -> int:
        """Get total number of nodes in the ring
        
        Returns:
            Total nodes in ring
        """
        return self.total_nodes_in_ring
    
    def is_enabled(self) -> bool:
        """Check if this ring topology is enabled
        
        Returns:
            True if enabled (more than 1 node)
        """
        return self.total_nodes_in_ring > 1 