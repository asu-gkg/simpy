# Collective communication algorithm base class - corresponds to collective/Algorithm.hh/cc in SimAI

from typing import Optional, TYPE_CHECKING
from abc import ABC, abstractmethod
from enum import Enum
from ..common import ComType, EventType
from ..callable import Callable, CallData

if TYPE_CHECKING:
    from ..base_stream import BaseStream
    from ..topology.logical_topology import LogicalTopology


class Algorithm(Callable, ABC):
    """Base class for collective communication algorithms
    
    Corresponds to collective/Algorithm.hh/cc in SimAI
    """
    
    class Name(Enum):
        """Algorithm names - corresponds to Algorithm::Name in SimAI"""
        Ring = "Ring"
        DoubleBinaryTree = "DoubleBinaryTree"
        AllToAll = "AllToAll"
        HalvingDoubling = "HalvingDoubling"
    
    def __init__(self, layer_num: int = 0):
        """Initialize algorithm
        
        Args:
            layer_num: Layer number for this algorithm
        """
        super().__init__()
        
        # Core properties - matching C++ implementation
        self.name: Optional[Algorithm.Name] = None
        self.id: int = 0
        self.stream: Optional['BaseStream'] = None
        self.logicalTopology: Optional['LogicalTopology'] = None
        self.data_size: int = 0
        self.final_data_size: int = 0
        self.comType: ComType = ComType.None_
        self.enabled: bool = True
        self.layer_num: int = layer_num
    
    @abstractmethod
    def run(self, event: EventType, data: CallData) -> None:
        """Run the algorithm - pure virtual method
        
        Args:
            event: Event type
            data: Call data
        """
        pass
    
    def init(self, stream: 'BaseStream') -> None:
        """Initialize the algorithm with a stream
        
        Args:
            stream: BaseStream instance to associate with this algorithm
        """
        self.stream = stream
    
    def call(self, event_type: EventType, data: CallData) -> None:
        """Handle an event call - from Callable interface
        
        Args:
            event_type: Type of event
            data: Associated call data
        """
        # Default implementation - can be overridden by subclasses
        pass
    
    def exit(self) -> None:
        """Exit the algorithm and proceed to next vnet baseline"""
        if self.stream and hasattr(self.stream, 'owner'):
            # Proceed to next vnet baseline - matching C++ implementation
            self.stream.owner.proceed_to_next_vnet_baseline(self.stream) 