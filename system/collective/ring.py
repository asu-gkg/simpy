# Ring collective algorithm - corresponds to collective/Ring.hh/cc in SimAI

from typing import List, Optional, TYPE_CHECKING
import threading
from .algorithm import Algorithm
from ..common import ComType, EventType, InjectionPolicy, StreamState
from ..callable import CallData

if TYPE_CHECKING:
    from ..topology.ring_topology import RingTopology
    from ..callable import Callable


class Ring(Algorithm):
    """Ring collective communication algorithm
    
    Corresponds to collective/Ring.hh/cc in SimAI
    """
    
    # Class variable for critical section synchronization
    _g_ring_inCriticalSection = threading.Lock()
    
    def __init__(self, 
                 com_type: ComType,
                 id: int,
                 layer_num: int,
                 ring_topology: 'RingTopology',
                 data_size: int,
                 direction: 'RingTopology.Direction',
                 injection_policy: InjectionPolicy,
                 boost_mode: bool):
        """Initialize Ring algorithm
        
        Args:
            com_type: Communication type
            id: Node ID
            layer_num: Layer number
            ring_topology: Ring topology
            data_size: Data size
            direction: Ring direction
            injection_policy: Injection policy
            boost_mode: Whether boost mode is enabled
        """
        super().__init__(layer_num)
        
        # Basic properties
        self.comType = com_type
        self.id = id
        self.logicalTopology = ring_topology
        self.data_size = data_size
        self.direction = direction
        self.nodes_in_ring = ring_topology.get_nodes_in_ring()
        self.current_receiver = ring_topology.get_receiver_node(id, direction)
        self.current_sender = ring_topology.get_sender_node(id, direction)
        self.parallel_reduce = 1  # each ring has xx channels
        self.injection_policy = injection_policy
        
        # Packet tracking
        self.total_packets_sent = 0
        self.total_packets_received = 0
        self.free_packets = 0
        self.zero_latency_packets = 0
        self.non_zero_latency_packets = 0
        self.toggle = False
        
        # Algorithm properties
        self.name = Algorithm.Name.Ring
        self.enabled = True
        if boost_mode:
            self.enabled = ring_topology.is_enabled()
        
        # Set transmission type based on topology dimension
        if hasattr(ring_topology, 'dimension'):
            if ring_topology.dimension == ring_topology.Dimension.Local:
                self.transmition = "Fast"  # MemBus::Transmition::Fast
            else:
                self.transmition = "Usual"  # MemBus::Transmition::Usual
        else:
            self.transmition = "Usual"
        
        # Configure stream count based on communication type
        if com_type == ComType.All_Reduce:
            self.stream_count = 2 * (self.nodes_in_ring - 1)
        elif com_type == ComType.All_to_All:
            self.stream_count = ((self.nodes_in_ring - 1) * self.nodes_in_ring) // 2
            if injection_policy == InjectionPolicy.Aggressive:
                self.parallel_reduce = self.nodes_in_ring - 1
            elif injection_policy == InjectionPolicy.Normal:
                self.parallel_reduce = 1
            else:
                self.parallel_reduce = 1
        else:
            self.stream_count = self.nodes_in_ring - 1
        
        # Set max count
        if com_type in [ComType.All_to_All, ComType.All_Gather]:
            self.max_count = 0
        else:
            self.max_count = self.nodes_in_ring - 1
        
        # Initialize packet counters
        self.remained_packets_per_message = 1
        self.remained_packets_per_max_count = 1
        
        # Set message size based on communication type
        if com_type == ComType.All_Reduce:
            self.final_data_size = data_size
            self.msg_size = data_size // self.nodes_in_ring
        elif com_type == ComType.All_Gather:
            self.final_data_size = data_size * self.nodes_in_ring
            self.msg_size = data_size
        elif com_type == ComType.Reduce_Scatter:
            self.final_data_size = data_size // self.nodes_in_ring
            self.msg_size = data_size // self.nodes_in_ring
        elif com_type == ComType.All_to_All:
            self.final_data_size = data_size
            self.msg_size = data_size // self.nodes_in_ring
        
        # Packet lists
        self.packets: List = []
        self.locked_packets: List = []
        
        # State flags
        self.processed = False
        self.send_back = False
        self.NPU_to_MA = False
    
    def get_non_zero_latency_packets(self) -> int:
        """Get number of non-zero latency packets
        
        Returns:
            Number of non-zero latency packets
        """
        return (self.nodes_in_ring - 1) * self.parallel_reduce * 1
    
    def run(self, event: EventType, data: CallData) -> None:
        """Run the ring algorithm
        
        Args:
            event: Event type
            data: Call data
        """
        if event == EventType.General:
            self.free_packets += 1
            self.ready()
            self.iteratable()
        elif event == EventType.PacketReceived:
            self.total_packets_received += 1
            self.insert_packet(None)
        elif event == EventType.StreamInit:
            for i in range(self.parallel_reduce):
                self.insert_packet(None)
    
    def release_packets(self) -> None:
        """Release packets for transmission"""
        # Set notifier for packets
        for packet in self.locked_packets:
            packet.set_notifier(self)
        
        # Create packet bundle and send
        if hasattr(self.stream, 'owner'):
            # This would create a PacketBundle in the real implementation
            # For now, we simulate the behavior
            pass
        
        self.locked_packets.clear()
    
    def process_stream_count(self) -> None:
        """Process stream count"""
        if self.remained_packets_per_message > 0:
            self.remained_packets_per_message -= 1
        
        if (self.remained_packets_per_message == 0 and 
            self.stream_count > 0):
            self.stream_count -= 1
            if self.stream_count > 0:
                self.remained_packets_per_message = 1
        
        if (self.remained_packets_per_message == 0 and 
            self.stream_count == 0 and
            self.stream.state != StreamState.Dead):
            self.stream.changeState(StreamState.Zombie)
    
    def process_max_count(self) -> None:
        """Process max count"""
        if self.remained_packets_per_max_count > 0:
            self.remained_packets_per_max_count -= 1
        
        if self.remained_packets_per_max_count == 0:
            self.max_count -= 1
            self.release_packets()
            self.remained_packets_per_max_count = 1
    
    def reduce(self) -> None:
        """Reduce operation"""
        self.process_stream_count()
        if self.packets:
            self.packets.pop(0)
        self.free_packets -= 1
        self.total_packets_sent += 1
    
    def iteratable(self) -> bool:
        """Check if algorithm can continue iterating
        
        Returns:
            True if can continue, False otherwise
        """
        if (self.stream_count == 0 and 
            self.free_packets == (self.parallel_reduce * 1)):
            self.exit()
            return False
        return True
    
    def insert_packet(self, sender: Optional['Callable']) -> None:
        """Insert a packet for processing
        
        Args:
            sender: Packet sender (can be None)
        """
        if not self.enabled:
            return
        
        if (self.zero_latency_packets == 0 and 
            self.non_zero_latency_packets == 0):
            self.zero_latency_packets = self.parallel_reduce * 1
            self.non_zero_latency_packets = self.get_non_zero_latency_packets()
            self.toggle = not self.toggle
        
        if self.zero_latency_packets > 0:
            # Create MyPacket
            from ..my_packet import MyPacket
            packet = MyPacket.create_basic(
                self.stream.current_queue_id if self.stream else 0,
                self.current_sender,
                self.current_receiver
            )
            packet.sender = sender
            self.packets.append(packet)
            self.locked_packets.append(packet)
            self.processed = False
            self.send_back = False
            self.NPU_to_MA = True
            self.process_max_count()
            self.zero_latency_packets -= 1
        elif self.non_zero_latency_packets > 0:
            # Create MyPacket
            from ..my_packet import MyPacket
            packet = MyPacket.create_basic(
                self.stream.current_queue_id if self.stream else 0,
                self.current_sender,
                self.current_receiver
            )
            packet.sender = sender
            self.packets.append(packet)
            self.locked_packets.append(packet)
            
            if (self.comType == ComType.Reduce_Scatter or
                (self.comType == ComType.All_Reduce and self.toggle)):
                self.processed = True
            else:
                self.processed = False
            
            if self.non_zero_latency_packets <= self.parallel_reduce * 1:
                self.send_back = False
            else:
                self.send_back = True
            
            self.NPU_to_MA = False
            print(f"id: {self.id} non-zero latency packets at tick: {0}")  # Placeholder for Sys::boostedTick()
            self.process_max_count()
            self.non_zero_latency_packets -= 1
        else:
            raise RuntimeError("should not inject nothing!")
    
    def ready(self) -> bool:
        """Check if ready to send packets
        
        Returns:
            True if ready, False otherwise
        """
        if (self.stream.state in [StreamState.Created, StreamState.Ready]):
            self.stream.changeState(StreamState.Executing)
        
        if (not self.enabled or 
            len(self.packets) == 0 or 
            self.stream_count == 0 or 
            self.free_packets == 0):
            return False
        
        packet = self.packets[0]
        
        # Simulate network send/receive operations
        # In real implementation, this would call front_end_sim_send/recv
        # For now, we just simulate the behavior
        self.reduce()
        return True
    
    def exit(self) -> None:
        """Exit the algorithm"""
        if self.packets:
            self.packets.clear()
        if self.locked_packets:
            self.locked_packets.clear()
        
        # Call parent exit method
        super().exit() 