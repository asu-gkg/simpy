"""Priority queue implementation for HTSimPy."""

from typing import Optional, List
from ..core import Packet, EventList
from ..core.logger import Logger
from .base_queue import BaseQueue


class PriorityQueue(BaseQueue):
    """
    Priority queue that serves packets based on priority.
    
    Higher priority packets are served first. Within same priority,
    packets are served in FIFO order.
    """
    
    def __init__(
        self,
        service_rate: float,
        max_size: int,
        eventlist: EventList,
        logger: Optional[Logger] = None
    ):
        """
        Initialize priority queue.
        
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
        self._packets_by_priority: dict[int, List[Packet]] = {}
        self._num_packets = 0
        
    def enqueue(self, pkt: Packet) -> bool:
        """
        Add packet to queue based on priority.
        
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
            
        # Get packet priority (default to 0)
        priority = 0
        if hasattr(pkt, 'priority'):
            priority = pkt.priority()
        elif hasattr(pkt, 'get_priority'):
            priority = pkt.get_priority()
            
        # Add to appropriate priority list
        if priority not in self._packets_by_priority:
            self._packets_by_priority[priority] = []
        self._packets_by_priority[priority].append(pkt)
        
        # Update state
        self._queuesize += pkt_size
        self._num_packets += 1
        
        # Log enqueue
        if self._logger:
            self._logger.log_packet_enqueue(pkt, self._queuesize)
            
        # Schedule service if this is the only packet
        if self._num_packets == 1:
            self._schedule_dequeue()
            
        return True
        
    def dequeue(self) -> Optional[Packet]:
        """
        Remove highest priority packet from queue.
        
        Returns:
            Packet if available, None otherwise
        """
        if self._num_packets == 0:
            return None
            
        # Find highest priority with packets
        highest_priority = max(self._packets_by_priority.keys())
        
        # Get packet from highest priority queue
        pkt = self._packets_by_priority[highest_priority].pop(0)
        if not self._packets_by_priority[highest_priority]:
            del self._packets_by_priority[highest_priority]
            
        # Update state
        pkt_size = pkt.size() * 8
        self._queuesize -= pkt_size
        self._num_packets -= 1
        
        # Log dequeue
        if self._logger:
            self._logger.log_packet_dequeue(pkt, self._queuesize)
            
        return pkt
        
    def num_packets(self) -> int:
        """Get number of packets in queue."""
        return self._num_packets
        
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
        if self._num_packets > 0:
            self._schedule_dequeue()
            
    def _schedule_dequeue(self) -> None:
        """Schedule the next packet dequeue event."""
        if self._num_packets > 0 and self._packets_by_priority:
            # Get highest priority
            highest_priority = max(self._packets_by_priority.keys())
            if self._packets_by_priority[highest_priority]:
                # Peek at next packet
                pkt = self._packets_by_priority[highest_priority][0]
                service_time = (pkt.size() * 8 * 10**12) // self._service_rate
                
                # Schedule dequeue event
                self._eventlist.sourceIsPending(self, service_time)