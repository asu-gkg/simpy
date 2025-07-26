# AllToAll collective algorithm - corresponds to collective/AllToAll.hh/cc in SimAI

from typing import TYPE_CHECKING
from .ring import Ring
from .algorithm import Algorithm
from ..common import ComType, EventType, InjectionPolicy
from ..callable import CallData

if TYPE_CHECKING:
    from ..topology.ring_topology import RingTopology


class AllToAll(Ring):
    """AllToAll collective communication algorithm
    
    Corresponds to collective/AllToAll.hh/cc in SimAI
    Inherits from Ring algorithm
    """
    
    def __init__(self,
                 com_type: ComType,
                 window: int,
                 id: int,
                 layer_num: int,
                 allToAllTopology: 'RingTopology',
                 data_size: int,
                 direction: 'RingTopology.Direction',
                 injection_policy: InjectionPolicy,
                 boost_mode: bool):
        """Initialize AllToAll algorithm
        
        Args:
            com_type: Communication type
            window: Window size (-1 for unlimited)
            id: Node ID
            layer_num: Layer number
            allToAllTopology: Ring topology for AllToAll
            data_size: Data size
            direction: Ring direction
            injection_policy: Injection policy
            boost_mode: Whether boost mode is enabled
        """
        # Call parent Ring constructor
        super().__init__(
            com_type,
            id,
            layer_num,
            allToAllTopology,
            data_size,
            direction,
            injection_policy,
            boost_mode
        )
        
        # Override algorithm name
        self.name = Algorithm.Name.AllToAll
        self.enabled = True
        self.middle_point = self.nodes_in_ring - 1
        
        if boost_mode:
            self.enabled = allToAllTopology.is_enabled()
        
        # Set parallel reduce based on window size
        if window == -1:
            self.parallel_reduce = self.nodes_in_ring - 1
        else:
            self.parallel_reduce = min(window, self.nodes_in_ring - 1)
        
        # Override stream count for AllToAll
        if com_type == ComType.All_to_All:
            self.stream_count = self.nodes_in_ring - 1
    
    def get_non_zero_latency_packets(self) -> int:
        """Get number of non-zero latency packets
        
        Returns:
            Number of non-zero latency packets
        """
        # Check if topology has dimension attribute and access it properly
        if hasattr(self.logicalTopology, 'dimension'):
            if self.logicalTopology.dimension != self.logicalTopology.Dimension.Local:
                return self.parallel_reduce * 1
            else:
                return (self.nodes_in_ring - 1) * self.parallel_reduce * 1
        else:
            # Default behavior if dimension is not available
            return (self.nodes_in_ring - 1) * self.parallel_reduce * 1
    
    def process_max_count(self) -> None:
        """Process max count - overridden from Ring"""
        if self.remained_packets_per_max_count > 0:
            self.remained_packets_per_max_count -= 1
        
        if self.remained_packets_per_max_count == 0:
            self.max_count -= 1
            self.release_packets()
            self.remained_packets_per_max_count = 1
            
            # Update current receiver and sender for AllToAll
            self.current_receiver = self.logicalTopology.get_receiver_node(
                self.current_receiver, self.direction)
            if self.current_receiver == self.id:
                self.current_receiver = self.logicalTopology.get_receiver_node(
                    self.current_receiver, self.direction)
            
            self.current_sender = self.logicalTopology.get_sender_node(
                self.current_sender, self.direction)
            if self.current_sender == self.id:
                self.current_sender = self.logicalTopology.get_sender_node(
                    self.current_sender, self.direction)
    
    def run(self, event: EventType, data: CallData) -> None:
        """Run the AllToAll algorithm
        
        Args:
            event: Event type
            data: Call data
        """
        if event == EventType.General:
            self.free_packets += 1
            
            if (self.comType == ComType.All_Reduce and 
                self.stream_count <= self.middle_point):
                if self.total_packets_received < self.middle_point:
                    return
                for i in range(self.parallel_reduce):
                    self.ready()
                self.iteratable()
            else:
                self.ready()
                self.iteratable()
                
        elif event == EventType.PacketReceived:
            self.total_packets_received += 1
            self.insert_packet(None)
        elif event == EventType.StreamInit:
            for i in range(self.parallel_reduce):
                self.insert_packet(None) 