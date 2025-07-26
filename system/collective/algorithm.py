# Collective communication algorithm base class - corresponds to collective/Algorithm.hh/cc in SimAI

from typing import List, Dict, Any, Optional, TYPE_CHECKING
from abc import ABC, abstractmethod
from ..common import ComType, Tick, CollectiveImplementationType
from ..callable import Callable

if TYPE_CHECKING:
    from ..topology.logical_topology import LogicalTopology
    from ..collective_phase import CollectivePhase


class CollectiveImplementation:
    """Implementation details for collective operations
    
    Corresponds to collective implementation types in SimAI
    """
    
    def __init__(self, impl_type: CollectiveImplementationType, 
                 algorithm_name: str = ""):
        """Initialize collective implementation
        
        Args:
            impl_type: Type of implementation
            algorithm_name: Name of the algorithm
        """
        self.impl_type = impl_type
        self.algorithm_name = algorithm_name
        self.parameters: Dict[str, Any] = {}
    
    def set_parameter(self, key: str, value: Any) -> None:
        """Set algorithm parameter
        
        Args:
            key: Parameter name
            value: Parameter value
        """
        self.parameters[key] = value
    
    def get_parameter(self, key: str, default: Any = None) -> Any:
        """Get algorithm parameter
        
        Args:
            key: Parameter name
            default: Default value if not found
            
        Returns:
            Parameter value
        """
        return self.parameters.get(key, default)


class Algorithm(ABC):
    """Base class for collective communication algorithms
    
    Corresponds to collective/Algorithm.hh/cc in SimAI
    """
    
    def __init__(self, algorithm_name: str, collective_type: ComType):
        """Initialize algorithm
        
        Args:
            algorithm_name: Name of the algorithm
            collective_type: Type of collective operation
        """
        self.algorithm_name = algorithm_name
        self.collective_type = collective_type
        self.implementation = CollectiveImplementation(
            CollectiveImplementationType.Ring, 
            algorithm_name
        )
        
        # Algorithm properties
        self.supports_pipelining = False
        self.requires_synchronization = True
        self.optimal_chunk_size = 1024  # Default chunk size in bytes
        
        # Performance characteristics
        self.latency_model_params: Dict[str, float] = {}
        self.bandwidth_efficiency = 1.0
        
        # Node and topology information
        self.num_nodes = 0
        self.node_list: List[int] = []
        self.topology: Optional['LogicalTopology'] = None
    
    @abstractmethod
    def generate_collective_phases(self, data_size: int, num_nodes: int, 
                                 node_list: List[int]) -> List['CollectivePhase']:
        """Generate collective communication phases
        
        Args:
            data_size: Size of data to communicate
            num_nodes: Number of participating nodes
            node_list: List of participating node IDs
            
        Returns:
            List of collective phases to execute
        """
        pass
    
    @abstractmethod
    def calculate_latency(self, data_size: int, num_nodes: int) -> Tick:
        """Calculate expected latency for the collective operation
        
        Args:
            data_size: Size of data to communicate
            num_nodes: Number of participating nodes
            
        Returns:
            Expected latency in simulation ticks
        """
        pass
    
    def set_topology(self, topology: 'LogicalTopology') -> None:
        """Set the network topology for the algorithm
        
        Args:
            topology: Network topology to use
        """
        self.topology = topology
    
    def set_implementation(self, implementation: CollectiveImplementation) -> None:
        """Set the implementation details
        
        Args:
            implementation: Implementation configuration
        """
        self.implementation = implementation
    
    def get_implementation_type(self) -> CollectiveImplementationType:
        """Get the implementation type
        
        Returns:
            Implementation type
        """
        return self.implementation.impl_type
    
    def calculate_chunk_size(self, data_size: int, num_nodes: int) -> int:
        """Calculate optimal chunk size for the algorithm
        
        Args:
            data_size: Total data size
            num_nodes: Number of participating nodes
            
        Returns:
            Optimal chunk size
        """
        # Default implementation - can be overridden by specific algorithms
        if self.supports_pipelining:
            # For pipelined algorithms, use smaller chunks
            return min(self.optimal_chunk_size, data_size // (num_nodes * 2))
        else:
            # For non-pipelined algorithms, process all data at once
            return data_size
    
    def estimate_bandwidth_requirement(self, data_size: int, num_nodes: int) -> float:
        """Estimate bandwidth requirement for the collective
        
        Args:
            data_size: Size of data to communicate
            num_nodes: Number of participating nodes
            
        Returns:
            Estimated bandwidth requirement
        """
        # Base implementation - specific algorithms should override
        return data_size * self.bandwidth_efficiency
    
    def get_algorithm_info(self) -> Dict[str, Any]:
        """Get algorithm information
        
        Returns:
            Dictionary containing algorithm details
        """
        return {
            'name': self.algorithm_name,
            'collective_type': self.collective_type.name if hasattr(self.collective_type, 'name') else str(self.collective_type),
            'implementation_type': self.implementation.impl_type.name if hasattr(self.implementation.impl_type, 'name') else str(self.implementation.impl_type),
            'supports_pipelining': self.supports_pipelining,
            'requires_synchronization': self.requires_synchronization,
            'optimal_chunk_size': self.optimal_chunk_size,
            'bandwidth_efficiency': self.bandwidth_efficiency
        }
    
    def validate_parameters(self, data_size: int, num_nodes: int, 
                          node_list: List[int]) -> bool:
        """Validate algorithm parameters
        
        Args:
            data_size: Size of data to communicate
            num_nodes: Number of participating nodes
            node_list: List of participating node IDs
            
        Returns:
            True if parameters are valid
        """
        if data_size <= 0:
            return False
        
        if num_nodes <= 0 or len(node_list) != num_nodes:
            return False
        
        # Check for duplicate nodes
        if len(set(node_list)) != len(node_list):
            return False
        
        return True
    
    def set_latency_model_param(self, param_name: str, value: float) -> None:
        """Set latency model parameter
        
        Args:
            param_name: Parameter name
            value: Parameter value
        """
        self.latency_model_params[param_name] = value
    
    def get_latency_model_param(self, param_name: str, default: float = 0.0) -> float:
        """Get latency model parameter
        
        Args:
            param_name: Parameter name
            default: Default value if not found
            
        Returns:
            Parameter value
        """
        return self.latency_model_params.get(param_name, default) 