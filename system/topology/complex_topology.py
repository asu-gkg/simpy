# Complex logical topology class - corresponds to topology/ComplexLogicalTopology.hh/cc in SimAI

from typing import TYPE_CHECKING
from abc import abstractmethod
from .logical_topology import LogicalTopology
from ..common import ComType

if TYPE_CHECKING:
    from .basic_logical_topology import BasicLogicalTopology


class ComplexLogicalTopology(LogicalTopology):
    """Complex logical topology class
    
    Corresponds to topology/ComplexLogicalTopology.hh/cc in SimAI
    This is an abstract base class for complex topologies (multi-dimensional).
    """
    
    def __init__(self):
        """Initialize complex logical topology"""
        super().__init__()
        self.complexity = LogicalTopology.Complexity.Complex
    
    @abstractmethod
    def get_num_of_nodes_in_dimension(self, dimension: int) -> int:
        """Get number of nodes in a specific dimension
        
        Args:
            dimension: Dimension index
            
        Returns:
            Number of nodes in the dimension
        """
        pass
    
    @abstractmethod
    def get_num_of_dimensions(self) -> int:
        """Get number of dimensions in the topology
        
        Returns:
            Number of dimensions
        """
        pass
    
    @abstractmethod
    def get_basic_topology_at_dimension(
        self, 
        dimension: int, 
        com_type: ComType
    ) -> 'BasicLogicalTopology':
        """Get basic topology at specific dimension
        
        Args:
            dimension: Dimension index
            com_type: Communication type
            
        Returns:
            Basic topology instance for the dimension
        """
        pass 