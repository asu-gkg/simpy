# GeneralComplexTopology class - corresponds to GeneralComplexTopology.hh/cc in SimAI

from typing import List, Optional
from .complex_logical_topology import ComplexLogicalTopology
from .logical_topology import LogicalTopology
from .basic_logical_topology import BasicLogicalTopology
from ..common import ComType, CollectiveImplementation


class GeneralComplexTopology(ComplexLogicalTopology):
    """General complex topology - corresponds to GeneralComplexTopology in SimAI"""

    def __init__(self, id: int, dimension_size: List[int], 
                 collective_implementation: List[CollectiveImplementation]):
        """Constructor - corresponds to GeneralComplexTopology::GeneralComplexTopology"""
        super().__init__()
        self.id = id
        self.dimension_size = dimension_size
        self.collective_implementation = collective_implementation
        self.dimension_topology: List[LogicalTopology] = []
        
        # Initialize dimension topologies
        for i, size in enumerate(dimension_size):
            if i < len(collective_implementation):
                impl = collective_implementation[i]
            else:
                # Use the last implementation if not enough provided
                impl = collective_implementation[-1] if collective_implementation else None
                
            # Create appropriate topology based on dimension size
            from .ring_topology import RingTopology
            from .binary_tree import BinaryTree
            
            if size <= 1:
                # Single node dimension
                topology = None
            elif size == 2:
                # Binary topology
                topology = BinaryTree(id, size)
            else:
                # Ring topology for larger dimensions
                topology = RingTopology(id, size)
                
            self.dimension_topology.append(topology)

    def __del__(self):
        """Destructor - corresponds to GeneralComplexTopology::~GeneralComplexTopology"""
        # Cleanup dimension topologies
        for topology in self.dimension_topology:
            if topology:
                del topology

    def get_num_of_nodes_in_dimension(self, dimension: int) -> int:
        """Get number of nodes in dimension - corresponds to GeneralComplexTopology::get_num_of_nodes_in_dimension"""
        if 0 <= dimension < len(self.dimension_size):
            return self.dimension_size[dimension]
        return 1

    def get_basic_topology_at_dimension(self, dimension: int, type: ComType) -> Optional[BasicLogicalTopology]:
        """Get basic topology at dimension - corresponds to GeneralComplexTopology::get_basic_topology_at_dimension"""
        if 0 <= dimension < len(self.dimension_topology):
            topology = self.dimension_topology[dimension]
            if isinstance(topology, BasicLogicalTopology):
                return topology
        return None

    def get_num_of_dimensions(self) -> int:
        """Get number of dimensions - corresponds to GeneralComplexTopology::get_num_of_dimensions"""
        return len(self.dimension_size) 