# Basic logical topology class - corresponds to topology/BasicLogicalTopology.hh/cc in SimAI

from typing import TYPE_CHECKING
from abc import abstractmethod
from enum import Enum
from .logical_topology import LogicalTopology
from ..common import ComType

if TYPE_CHECKING:
    pass


class BasicLogicalTopology(LogicalTopology):
    """Basic logical topology class
    
    Corresponds to topology/BasicLogicalTopology.hh/cc in SimAI
    This is an abstract base class for basic topologies (single dimension).
    """
    
    class BasicTopology(Enum):
        """Basic topology types"""
        Ring = "Ring"
        BinaryTree = "BinaryTree"
    
    def __init__(self, basic_topology: 'BasicLogicalTopology.BasicTopology'):
        """Initialize basic logical topology
        
        Args:
            basic_topology: Type of basic topology
        """
        super().__init__()
        self.basic_topology = basic_topology
        self.complexity = LogicalTopology.Complexity.Basic
    
    def get_num_of_dimensions(self) -> int:
        """Get number of dimensions
        
        Basic topologies always have 1 dimension.
        
        Returns:
            Always returns 1
        """
        return 1
    
    @abstractmethod
    def get_num_of_nodes_in_dimension(self, dimension: int) -> int:
        """Get number of nodes in a specific dimension
        
        Args:
            dimension: Dimension index (should be 0 for basic topologies)
            
        Returns:
            Number of nodes in the dimension
        """
        pass
    
    def get_basic_topology_at_dimension(
        self, 
        dimension: int, 
        com_type: ComType
    ) -> 'BasicLogicalTopology':
        """Get basic topology at specific dimension
        
        For basic topologies, returns self since there's only one dimension.
        
        Args:
            dimension: Dimension index (should be 0)
            com_type: Communication type
            
        Returns:
            Self reference
        """
        return self 