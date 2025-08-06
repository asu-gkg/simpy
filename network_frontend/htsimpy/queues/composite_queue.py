"""Composite queue implementation for HTSimPy."""

from typing import Optional, Dict, List
from ..core import Packet, EventList, EventSource
from ..core.logger import Logger
from .base_queue import BaseQueue
from .fifo_queue import FIFOQueue


class CompositeQueue(BaseQueue):
    """
    Composite queue that maintains per-flow sub-queues.
    
    Each flow gets its own FIFO queue, and flows are served
    in round-robin fashion to ensure fairness.
    """
    
    def __init__(
        self,
        service_rate: float,
        max_size: int,
        eventlist: EventList,
        logger: Optional[Logger] = None
    ):
        """
        Initialize composite queue.
        
        Args:
            service_rate: Service rate in bits per second
            max_size: Maximum queue size in bits
            eventlist: Event list for scheduling
            logger: Optional logger for queue events
        """
        super().__init__(service_rate, eventlist, logger)
        self._service_rate = service_rate
        self._maxsize = max_size
        self._queuesize = 0  # Current size in bits
        self._flow_queues: Dict[int, List[Packet]] = {}  # flow_id -> packet list
        self._flow_sizes: Dict[int, int] = {}  # flow_id -> total size in bits
        self._active_flows: List[int] = []  # List of flows with packets
        self._current_flow_idx = 0  # For round-robin
        self._total_packets = 0
        
    def _get_flow_id(self, pkt: Packet) -> int:
        """Extract flow ID from packet."""
        if hasattr(pkt, 'flow_id'):
            return pkt.flow_id()
        elif hasattr(pkt, 'get_flow_id'):
            return pkt.get_flow_id()
        elif hasattr(pkt, 'src') and hasattr(pkt, 'dst'):
            # Use src-dst pair as flow ID
            return hash((pkt.src(), pkt.dst()))
        else:
            # Default to single flow
            return 0
            
    def enqueue(self, pkt: Packet) -> bool:
        """
        Add packet to appropriate flow queue.
        
        Args:
            pkt: Packet to enqueue
            
        Returns:
            True if packet was enqueued, False if dropped
        """
        # Check if queue has space
        pkt_size = pkt.size() * 8  # Convert to bits
        if self._queuesize + pkt_size > self._maxsize:
            # Drop packet
            if self._logger:
                self._logger.log_packet_drop(pkt)
            return False
            
        # Get flow ID
        flow_id = self._get_flow_id(pkt)
        
        # Create flow queue if needed
        if flow_id not in self._flow_queues:
            self._flow_queues[flow_id] = []
            self._flow_sizes[flow_id] = 0
            self._active_flows.append(flow_id)
            
        # Add packet to flow queue
        self._flow_queues[flow_id].append(pkt)
        self._flow_sizes[flow_id] += pkt_size
        
        # Update global state
        self._queuesize += pkt_size
        self._total_packets += 1
        
        # Log enqueue
        if self._logger:
            self._logger.log_packet_enqueue(pkt, self._queuesize)
            
        # Schedule service if this is the only packet
        if self._total_packets == 1:
            self._schedule_dequeue()
            
        return True
        
    def dequeue(self) -> Optional[Packet]:
        """
        Remove packet from next flow in round-robin order.
        
        Returns:
            Packet if available, None otherwise
        """
        if self._total_packets == 0 or not self._active_flows:
            return None
            
        # Find next non-empty flow
        attempts = 0
        while attempts < len(self._active_flows):
            flow_id = self._active_flows[self._current_flow_idx]
            
            if flow_id in self._flow_queues and self._flow_queues[flow_id]:
                # Get packet from this flow
                pkt = self._flow_queues[flow_id].pop(0)
                pkt_size = pkt.size() * 8
                
                # Update flow state
                self._flow_sizes[flow_id] -= pkt_size
                if not self._flow_queues[flow_id]:
                    # Remove empty flow
                    del self._flow_queues[flow_id]
                    del self._flow_sizes[flow_id]
                    self._active_flows.remove(flow_id)
                    # Adjust index if needed
                    if self._current_flow_idx >= len(self._active_flows):
                        self._current_flow_idx = 0
                else:
                    # Move to next flow for fairness
                    self._current_flow_idx = (self._current_flow_idx + 1) % len(self._active_flows)
                    
                # Update global state
                self._queuesize -= pkt_size
                self._total_packets -= 1
                
                # Log dequeue
                if self._logger:
                    self._logger.log_packet_dequeue(pkt, self._queuesize)
                    
                return pkt
                
            # Try next flow
            self._current_flow_idx = (self._current_flow_idx + 1) % len(self._active_flows)
            attempts += 1
            
        return None
        
    def num_packets(self) -> int:
        """Get total number of packets in queue."""
        return self._total_packets
        
    def num_flows(self) -> int:
        """Get number of active flows."""
        return len(self._active_flows)
        
    def get_flow_stats(self) -> Dict[int, int]:
        """Get packet count per flow."""
        stats = {}
        for flow_id, packets in self._flow_queues.items():
            stats[flow_id] = len(packets)
        return stats
        
    def queuesize(self) -> int:
        """Get current queue size in bits."""
        return self._queuesize
        
    def maxsize(self) -> int:
        """Get maximum queue size in bits."""
        return self._maxsize
        
    def receivePacket(self, pkt: Packet) -> None:
        """
        Receive packet from network.
        
        This is called when a packet arrives at the queue.
        """
        if not self.enqueue(pkt):
            # Packet was dropped
            pkt.free()
            
    def do_next_event(self) -> None:
        """
        Process next event (service a packet).
        
        This is called by the event scheduler when it's time
        to dequeue and send the next packet.
        """
        pkt = self.dequeue()
        if pkt and self._next_sink:
            # Send packet to next hop
            self._next_sink.receivePacket(pkt)
            
        # Schedule next dequeue if queue is not empty
        if self._total_packets > 0:
            self._schedule_dequeue()
            
    def _schedule_dequeue(self) -> None:
        """Schedule the next packet dequeue event."""
        if self._total_packets > 0 and self._active_flows:
            # Get next packet to estimate service time
            flow_id = self._active_flows[self._current_flow_idx]
            if flow_id in self._flow_queues and self._flow_queues[flow_id]:
                pkt = self._flow_queues[flow_id][0]  # Peek at next packet
                service_time = (pkt.size() * 8 * 10**12) // self._service_rate
                
                # Schedule dequeue event
                self._eventlist.sourceIsPending(self, service_time)