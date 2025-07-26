# GeneralComplexTopology class - corresponds to GeneralComplexTopology.hh/cc in SimAI

from typing import List, Optional
from .complex_logical_topology import ComplexLogicalTopology
from .logical_topology import LogicalTopology
from .basic_logical_topology import BasicLogicalTopology
from ..common import ComType, CollectiveImplementation, CollectiveImplementationType


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
        
        # Initialize offset to 1, exactly like C++
        offset = 1
        last_dim = len(collective_implementation) - 1
        
        # Loop through each dimension, exactly matching C++ logic
        for dim in range(len(collective_implementation)):
            impl = collective_implementation[dim]
            
            if (impl.type == CollectiveImplementationType.Ring or
                impl.type == CollectiveImplementationType.Direct or
                impl.type == CollectiveImplementationType.HalvingDoubling or
                impl.type == CollectiveImplementationType.NcclFlowModel or
                impl.type == CollectiveImplementationType.NcclTreeFlowModel):
                
                # Create RingTopology with exact C++ parameters
                from .ring_topology import RingTopology
                ring = RingTopology(
                    RingTopology.Dimension.NA,  # dimension
                    id,                         # id
                    dimension_size[dim],        # total_nodes_in_ring
                    (id % (offset * dimension_size[dim])) // offset,  # index_in_ring
                    offset                      # offset
                )
                self.dimension_topology.append(ring)
                
            elif (impl.type == CollectiveImplementationType.OneRing or
                  impl.type == CollectiveImplementationType.OneDirect or
                  impl.type == CollectiveImplementationType.OneHalvingDoubling):
                
                # Calculate total NPUs
                total_npus = 1
                for d in dimension_size:
                    total_npus *= d
                    
                # Create RingTopology for "One" variants
                from .ring_topology import RingTopology
                ring = RingTopology(
                    RingTopology.Dimension.NA,  # dimension
                    id,                         # id
                    total_npus,                 # total_nodes_in_ring
                    id % total_npus,            # index_in_ring
                    1                           # offset
                )
                self.dimension_topology.append(ring)
                return  # Early return like in C++
                
            elif impl.type == CollectiveImplementationType.DoubleBinaryTree:
                from .double_binary_tree_topology import DoubleBinaryTreeTopology
                
                if dim == last_dim:
                    dbt = DoubleBinaryTreeTopology(
                        id, dimension_size[dim], id % offset, offset
                    )
                    self.dimension_topology.append(dbt)
                else:
                    dbt = DoubleBinaryTreeTopology(
                        id,
                        dimension_size[dim],
                        (id - (id % (offset * dimension_size[dim]))) + (id % offset),
                        offset
                    )
                    self.dimension_topology.append(dbt)
            
            # Update offset exactly like C++: offset *= dimension_size[dim]
            offset *= dimension_size[dim]

    def __del__(self):
        """Destructor - corresponds to GeneralComplexTopology::~GeneralComplexTopology"""
        # In Python, cleanup is automatic, but following C++ pattern
        for topology in self.dimension_topology:
            if topology:
                del topology

    def get_num_of_nodes_in_dimension(self, dimension: int) -> int:
        """Get number of nodes in dimension - corresponds to GeneralComplexTopology::get_num_of_nodes_in_dimension"""
        if dimension >= len(self.dimension_topology):
            print(f"dim: {dimension} requested! but max dim is: {len(self.dimension_topology) - 1}")
        assert dimension < len(self.dimension_topology)
        return self.dimension_topology[dimension].get_num_of_nodes_in_dimension(0)

    def get_basic_topology_at_dimension(self, dimension: int, type: ComType) -> Optional[BasicLogicalTopology]:
        """Get basic topology at dimension - corresponds to GeneralComplexTopology::get_basic_topology_at_dimension"""
        return self.dimension_topology[dimension].get_basic_topology_at_dimension(0, type)

    def get_num_of_dimensions(self) -> int:
        """Get number of dimensions - corresponds to GeneralComplexTopology::get_num_of_dimensions"""
        return len(self.dimension_topology) 