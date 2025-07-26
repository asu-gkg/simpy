# Simulation send caller - corresponds to SimSendCaller.hh/cc in SimAI

from typing import Any, Optional, TYPE_CHECKING
from .callable import Callable, CallData
from .common import EventType, Tick

if TYPE_CHECKING:
    from .sys import Sys


class SimSendCaller(Callable):
    """Handles simulation send operations and callbacks
    
    Corresponds to SimSendCaller.hh/cc in SimAI
    """
    
    def __init__(self, sys_ref: 'Sys', dest_node: int, tag: int, 
                 request_id: int, completion_callback: Optional[Callable] = None):
        """Initialize simulation send caller
        
        Args:
            sys_ref: Reference to the system
            dest_node: Destination node ID
            tag: Message tag
            request_id: Request identifier
            completion_callback: Callback to invoke on completion
        """
        self.sys_ref = sys_ref
        self.dest_node = dest_node
        self.tag = tag
        self.request_id = request_id
        self.completion_callback = completion_callback
        
        # Send operation state
        self.bytes_sent = 0
        self.total_bytes = 0
        self.send_start_time: Tick = 0
        self.send_end_time: Tick = 0
        self.completed = False
        
        # Network and routing information
        self.src_node = sys_ref.id if sys_ref else 0
        self.message_buffer: Optional[Any] = None
        self.packet_size = 0
    
    def call(self, event_type: EventType, data: CallData) -> None:
        """Handle events for send operation
        
        Args:
            event_type: Type of event to handle
            data: Event data
        """
        if event_type == EventType.PacketSent:
            self._handle_packet_sent(data)
        elif event_type == EventType.SendCompleted:
            self._handle_send_completed(data)
        elif event_type == EventType.General:
            self._handle_general_event(data)
    
    def initiate_send(self, buffer: Any, byte_count: int, packet_size: int) -> None:
        """Initiate a send operation
        
        Args:
            buffer: Data buffer to send
            byte_count: Total bytes to send
            packet_size: Size of each packet
        """
        self.message_buffer = buffer
        self.total_bytes = byte_count
        self.packet_size = packet_size
        self.send_start_time = self.sys_ref.get_tick() if self.sys_ref else 0
        
        # Start sending packets
        self._send_next_packet()
    
    def _send_next_packet(self) -> None:
        """Send the next packet in the message"""
        if self.bytes_sent >= self.total_bytes:
            self._complete_send()
            return
        
        # Calculate packet size for this transmission
        remaining_bytes = self.total_bytes - self.bytes_sent
        current_packet_size = min(self.packet_size, remaining_bytes)
        
        # Simulate sending the packet
        # In a real implementation, this would interface with the network simulation
        self.bytes_sent += current_packet_size
        
        # Schedule callback for packet completion
        if self.sys_ref:
            # Use a small delay to simulate packet transmission time
            delay = current_packet_size / 1000  # Simple bandwidth model
            self.sys_ref.register_event(
                self, 
                EventType.PacketSent, 
                CallData(), 
                int(delay)
            )
    
    def _handle_packet_sent(self, data: CallData) -> None:
        """Handle packet sent event
        
        Args:
            data: Event data
        """
        # Continue sending if more packets remain
        if self.bytes_sent < self.total_bytes:
            self._send_next_packet()
        else:
            self._complete_send()
    
    def _handle_send_completed(self, data: CallData) -> None:
        """Handle send completion event
        
        Args:
            data: Event data
        """
        self._complete_send()
    
    def _handle_general_event(self, data: CallData) -> None:
        """Handle general events
        
        Args:
            data: Event data
        """
        # Handle any general events related to the send operation
        pass
    
    def _complete_send(self) -> None:
        """Complete the send operation"""
        if self.completed:
            return
            
        self.completed = True
        self.send_end_time = self.sys_ref.get_tick() if self.sys_ref else 0
        
        # Invoke completion callback if provided
        if self.completion_callback:
            self.completion_callback.call(EventType.SendCompleted, CallData())
    
    def get_send_latency(self) -> Tick:
        """Get the latency of the send operation
        
        Returns:
            Send latency in simulation ticks
        """
        if self.completed:
            return self.send_end_time - self.send_start_time
        return 0
    
    def is_completed(self) -> bool:
        """Check if the send operation is completed
        
        Returns:
            True if send is completed
        """
        return self.completed
    
    def get_progress(self) -> float:
        """Get send progress as a percentage
        
        Returns:
            Progress percentage (0.0 to 1.0)
        """
        if self.total_bytes == 0:
            return 1.0
        return min(1.0, self.bytes_sent / self.total_bytes) 