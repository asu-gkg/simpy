# Logical topology base class - corresponds to topology/LogicalTopology.hh/cc in SimAI

from typing import List, Dict, Tuple, Optional, Any, TYPE_CHECKING
from abc import ABC, abstractmethod
from enum import Enum
from ..common import Tick, ComType

if TYPE_CHECKING:
    from .basic_logical_topology import BasicLogicalTopology


class LogicalTopology(ABC):
    """Base class for logical topologies in the simulation
    
    Corresponds to topology/LogicalTopology.hh/cc in SimAI
    This is an abstract base class that defines the interface for all topology types.
    """
    
    class Complexity(Enum):
        """Topology complexity levels"""
        Basic = "Basic"
        Complex = "Complex"
    
    def __init__(self):
        """Initialize logical topology"""
        self.complexity: LogicalTopology.Complexity = LogicalTopology.Complexity.Basic
    
    def get_topology(self) -> 'LogicalTopology':
        """Get topology instance
        
        Returns:
            Reference to this topology instance
        """
        return self
    
    @staticmethod
    def get_reminder(number: int, divisible: int) -> int:
        """Get modulo result handling negative numbers correctly
        
        Args:
            number: Number to divide
            divisible: Divisor
            
        Returns:
            Modulo result
        """
        if number >= 0:
            return number % divisible
        else:
            return (number + divisible) % divisible
    
    @abstractmethod
    def get_num_of_dimensions(self) -> int:
        """Get number of dimensions in the topology
        
        Returns:
            Number of dimensions
        """
        pass
    
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