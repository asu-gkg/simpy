# ComplexLogicalTopology class - corresponds to ComplexLogicalTopology.hh in SimAI

from abc import ABC, abstractmethod
from typing import Optional
from .logical_topology import LogicalTopology
from .basic_logical_topology import BasicLogicalTopology
from ..common import ComType


class ComplexLogicalTopology(LogicalTopology):
    """Complex logical topology base class - corresponds to ComplexLogicalTopology in SimAI"""

    def __init__(self):
        """Constructor - corresponds to ComplexLogicalTopology::ComplexLogicalTopology"""
        super().__init__()

    @abstractmethod
    def get_num_of_nodes_in_dimension(self, dimension: int) -> int:
        """Get number of nodes in dimension - pure virtual method"""
        pass

    @abstractmethod
    def get_basic_topology_at_dimension(self, dimension: int, type: ComType) -> Optional[BasicLogicalTopology]:
        """Get basic topology at dimension - pure virtual method"""
        pass

    @abstractmethod
    def get_num_of_dimensions(self) -> int:
        """Get number of dimensions - pure virtual method"""
        pass 