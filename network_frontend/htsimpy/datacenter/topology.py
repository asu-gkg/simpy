"""
Base topology class for data center networks

Corresponds to topology.h in HTSim C++ implementation
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Tuple
from ..core.route import Route
from ..core.logger.logfile import Logfile


class Topology(ABC):
    """
    Abstract base class for network topologies
    
    This class defines the interface that all topology implementations must follow.
    """
    
    def __init__(self):
        self._no_of_nodes = 0
        
    def get_paths(self, src: int, dest: int) -> List[Route]:
        """
        Get paths from source to destination
        
        Args:
            src: Source node ID
            dest: Destination node ID
            
        Returns:
            List of possible routes
        """
        return self.get_bidir_paths(src, dest, True)
    
    @abstractmethod
    def get_bidir_paths(self, src: int, dest: int, reverse: bool) -> List[Route]:
        """
        Get bidirectional paths between nodes
        
        Args:
            src: Source node ID
            dest: Destination node ID
            reverse: Whether to get reverse path (dest to src)
            
        Returns:
            List of possible routes
        """
        pass
    
    @abstractmethod
    def get_neighbours(self, src: int) -> Optional[List[int]]:
        """
        Get neighboring nodes of a given node
        
        Args:
            src: Node ID
            
        Returns:
            List of neighbor node IDs, or None if not applicable
        """
        pass
    
    def no_of_nodes(self) -> int:
        """
        Get total number of nodes in the topology
        
        Returns:
            Number of nodes
        """
        # In C++, the default implementation calls abort()
        # In Python, we raise NotImplementedError
        raise NotImplementedError("no_of_nodes() must be implemented by subclass")
    
    def add_switch_loggers(self, logfile: Logfile, sample_period: int):
        """
        Add loggers to record total queue size at switches
        
        Args:
            logfile: Logfile instance
            sample_period: Sampling period in picoseconds
        """
        # In C++, the default implementation calls abort()
        # In Python, we raise NotImplementedError
        raise NotImplementedError("add_switch_loggers() must be implemented by subclass")