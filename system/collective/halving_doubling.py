# HalvingDoubling collective algorithm - corresponds to collective/HalvingDoubling.hh/cc in SimAI

from typing import List, Optional, TYPE_CHECKING
import math
import sys
from .algorithm import Algorithm
from ..common import ComType, EventType, InjectionPolicy, StreamState, PacketRouting
from ..callable import CallData

if TYPE_CHECKING:
    from ..topology.ring_topology import RingTopology
    from ..my_packet import MyPacket
    from ..callable import Callable


class HalvingDoubling(Algorithm):
    """HalvingDoubling collective communication algorithm
    
    Corresponds to collective/HalvingDoubling.hh/cc in SimAI
    """
    
    def __init__(self,
                 com_type: ComType,
                 id: int,
                 layer_num: int,
                 ring_topology: 'RingTopology',
                 data_size: int,
                 boost_mode: bool):
        """Initialize HalvingDoubling algorithm
        
        Args:
            com_type: Communication type
            id: Node ID
            layer_num: Layer number
            ring_topology: Ring topology
            data_size: Data size
            boost_mode: Whether boost mode is enabled
        """
        super().__init__(layer_num)
        
        # Basic properties
        self.comType = com_type
        self.id = id
        self.logicalTopology = ring_topology
        self.data_size = data_size
        self.nodes_in_ring = ring_topology.get_nodes_in_ring()
        self.parallel_reduce = 1
        
        # Packet tracking
        self.total_packets_sent = 0
        self.total_packets_received = 0
        self.free_packets = 0
        self.zero_latency_packets = 0
        self.non_zero_latency_packets = 0
        self.toggle = False
        
        # Algorithm properties
        self.name = Algorithm.Name.HalvingDoubling
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
            self.stream_count = 2 * int(math.log2(self.nodes_in_ring))
        else:
            self.stream_count = int(math.log2(self.nodes_in_ring))
        
        # Set max count
        if com_type == ComType.All_Gather:
            self.max_count = 0
        else:
            self.max_count = int(math.log2(self.nodes_in_ring))
        
        # Initialize packet counters
        self.remained_packets_per_message = 1
        self.remained_packets_per_max_count = 1
        
        # Set message size and rank offset based on communication type
        if com_type == ComType.All_Reduce:
            self.final_data_size = data_size
            self.msg_size = data_size // 2
            self.rank_offset = 1
            self.offset_multiplier = 2
        elif com_type == ComType.All_Gather:
            self.final_data_size = data_size * self.nodes_in_ring
            self.msg_size = data_size
            self.rank_offset = self.nodes_in_ring // 2
            self.offset_multiplier = 0.5
        elif com_type == ComType.Reduce_Scatter:
            self.final_data_size = data_size // self.nodes_in_ring
            self.msg_size = data_size // 2
            self.rank_offset = 1
            self.offset_multiplier = 2
        else:
            print("######### Exiting because of unknown communication type for HalvingDoubling collective algorithm #########")
            sys.exit(1)
        
        # Initialize current receiver and sender
        direction = self.specify_direction()
        self.current_receiver = id
        for i in range(self.rank_offset):
            self.current_receiver = ring_topology.get_receiver_node(
                self.current_receiver, direction)
            self.current_sender = self.current_receiver
        
        # Packet lists
        self.packets: List['MyPacket'] = []
        self.locked_packets: List['MyPacket'] = []
        
        # State flags
        self.processed = False
        self.send_back = False
        self.NPU_to_MA = False
    
    def get_non_zero_latency_packets(self) -> int:
        """Get number of non-zero latency packets
        
        Returns:
            Number of non-zero latency packets
        """
        return int(math.log2(self.nodes_in_ring)) - 1 * self.parallel_reduce
    
    def specify_direction(self) -> 'RingTopology.Direction':
        """Specify direction for the algorithm
        
        Returns:
            Direction to use
        """
        if self.rank_offset == 0:
            return self.logicalTopology.Direction.Clockwise
        
        # Get index in ring from topology
        index_in_ring = getattr(self.logicalTopology, 'index_in_ring', 0)
        reminder = (index_in_ring // self.rank_offset) % 2
        
        if reminder == 0:
            return self.logicalTopology.Direction.Clockwise
        else:
            return self.logicalTopology.Direction.Anticlockwise
    
    def run(self, event: EventType, data: CallData) -> None:
        """Run the HalvingDoubling algorithm
        
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
            if hasattr(packet, 'set_notifier'):
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
            
            # Update rank offset and message size
            self.rank_offset = int(self.rank_offset * self.offset_multiplier)
            self.msg_size = int(self.msg_size / self.offset_multiplier)
            
            if (self.rank_offset == self.nodes_in_ring and 
                self.comType == ComType.All_Reduce):
                self.offset_multiplier = 0.5
                self.rank_offset = int(self.rank_offset * self.offset_multiplier)
                self.msg_size = int(self.msg_size / self.offset_multiplier)
            
            # Update current receiver and sender
            self.current_receiver = self.id
            direction = self.specify_direction()
            for i in range(self.rank_offset):
                self.current_receiver = self.logicalTopology.get_receiver_node(
                    self.current_receiver, direction)
                self.current_sender = self.current_receiver
    
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
            # Create MyPacket equivalent
            packet = {
                'msg_size': self.msg_size,
                'queue_id': self.stream.current_queue_id if self.stream else 0,
                'sender_id': self.current_sender,
                'receiver_id': self.current_receiver,
                'sender': sender
            }
            self.packets.append(packet)
            self.locked_packets.append(packet)
            self.processed = False
            self.send_back = False
            self.NPU_to_MA = True
            self.process_max_count()
            self.zero_latency_packets -= 1
        elif self.non_zero_latency_packets > 0:
            # Create MyPacket equivalent
            packet = {
                'msg_size': self.msg_size,
                'queue_id': self.stream.current_queue_id if self.stream else 0,
                'sender_id': self.current_sender,
                'receiver_id': self.current_receiver,
                'sender': sender
            }
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