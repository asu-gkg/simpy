# Simulation receive caller - corresponds to SimRecvCaller.hh/cc in SimAI

from typing import Any, Optional, TYPE_CHECKING
from .callable import Callable, CallData
from .common import EventType, Tick

if TYPE_CHECKING:
    from .sys import Sys


class SimRecvCaller(Callable):
    """Handles simulation receive operations and callbacks
    
    Corresponds to SimRecvCaller.hh/cc in SimAI
    """
    
    def __init__(self, sys_ref: 'Sys', src_node: int, tag: int, 
                 request_id: int, completion_callback: Optional[Callable] = None):
        """Initialize simulation receive caller
        
        Args:
            sys_ref: Reference to the system
            src_node: Source node ID
            tag: Message tag
            request_id: Request identifier
            completion_callback: Callback to invoke on completion
        """
        self.sys_ref = sys_ref
        self.src_node = src_node
        self.tag = tag
        self.request_id = request_id
        self.completion_callback = completion_callback
        
        # Receive operation state
        self.bytes_received = 0
        self.expected_bytes = 0
        self.recv_start_time: Tick = 0
        self.recv_end_time: Tick = 0
        self.completed = False
        self.started = False
        
        # Network and routing information
        self.dest_node = sys_ref.id if sys_ref else 0
        self.receive_buffer: Optional[Any] = None
        self.packets_received = 0
        self.out_of_order_packets = {}  # For handling out-of-order delivery
    
    def call(self, event_type: EventType, data: CallData) -> None:
        """Handle events for receive operation
        
        Args:
            event_type: Type of event to handle
            data: Event data
        """
        if event_type == EventType.PacketReceived:
            self._handle_packet_received(data)
        elif event_type == EventType.ReceiveCompleted:
            self._handle_receive_completed(data)
        elif event_type == EventType.General:
            self._handle_general_event(data)
    
    def initiate_receive(self, buffer: Any, expected_byte_count: int) -> None:
        """Initiate a receive operation
        
        Args:
            buffer: Buffer to store received data
            expected_byte_count: Expected number of bytes to receive
        """
        self.receive_buffer = buffer
        self.expected_bytes = expected_byte_count
        self.recv_start_time = self.sys_ref.get_tick() if self.sys_ref else 0
        self.started = True
        
        # The receive operation is now waiting for incoming packets
        # Packets will arrive through packet_received events
    
    def packet_arrived(self, packet_data: Any, packet_size: int, 
                      packet_sequence: int = 0) -> None:
        """Handle arrival of a packet
        
        Args:
            packet_data: Data contained in the packet
            packet_size: Size of the packet
            packet_sequence: Sequence number of the packet
        """
        if not self.started or self.completed:
            return
        
        # Store packet data (handle out-of-order if needed)
        if packet_sequence in self.out_of_order_packets:
            return  # Duplicate packet
        
        self.out_of_order_packets[packet_sequence] = {
            'data': packet_data,
            'size': packet_size
        }
        
        self.packets_received += 1
        self.bytes_received += packet_size
        
        # Check if we have received enough data
        if self.bytes_received >= self.expected_bytes:
            self._complete_receive()
        
        # Schedule packet received event
        if self.sys_ref:
            self.sys_ref.register_event(
                self,
                EventType.PacketReceived,
                CallData(),
                0  # Immediate processing
            )
    
    def _handle_packet_received(self, data: CallData) -> None:
        """Handle packet received event
        
        Args:
            data: Event data
        """
        # Process the received packet
        # Check if this completes the receive operation
        if self.bytes_received >= self.expected_bytes:
            self._complete_receive()
    
    def _handle_receive_completed(self, data: CallData) -> None:
        """Handle receive completion event
        
        Args:
            data: Event data
        """
        self._complete_receive()
    
    def _handle_general_event(self, data: CallData) -> None:
        """Handle general events
        
        Args:
            data: Event data
        """
        # Handle any general events related to the receive operation
        pass
    
    def _complete_receive(self) -> None:
        """Complete the receive operation"""
        if self.completed:
            return
            
        self.completed = True
        self.recv_end_time = self.sys_ref.get_tick() if self.sys_ref else 0
        
        # Assemble the received data from out-of-order packets
        self._assemble_received_data()
        
        # Invoke completion callback if provided
        if self.completion_callback:
            self.completion_callback.call(EventType.ReceiveCompleted, CallData())
    
    def _assemble_received_data(self) -> None:
        """Assemble received data from packets in correct order"""
        # Sort packets by sequence number and assemble data
        sorted_packets = sorted(self.out_of_order_packets.items())
        
        # In a real implementation, this would copy data to the receive buffer
        # For now, we just mark the operation as complete
        pass
    
    def get_receive_latency(self) -> Tick:
        """Get the latency of the receive operation
        
        Returns:
            Receive latency in simulation ticks
        """
        if self.completed:
            return self.recv_end_time - self.recv_start_time
        return 0
    
    def is_completed(self) -> bool:
        """Check if the receive operation is completed
        
        Returns:
            True if receive is completed
        """
        return self.completed
    
    def get_progress(self) -> float:
        """Get receive progress as a percentage
        
        Returns:
            Progress percentage (0.0 to 1.0)
        """
        if self.expected_bytes == 0:
            return 1.0
        return min(1.0, self.bytes_received / self.expected_bytes)
    
    def is_waiting(self) -> bool:
        """Check if the receive operation is waiting for data
        
        Returns:
            True if waiting for more data
        """
        return self.started and not self.completed and self.bytes_received < self.expected_bytes 