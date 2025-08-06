"""
ECN Queue implementation for HTSimPy

Corresponds to ECN queue in C++ htsim implementation.
ECN (Explicit Congestion Notification) marking queue.
"""

from typing import Optional
from .base_queue import Queue
from ..core.eventlist import EventList
from ..core.logger import QueueLogger
from ..core import Packet


class ECNQueue(Queue):
    """
    ECN-enabled queue implementation.
    
    Marks packets with ECN when queue size exceeds threshold.
    Corresponds to C++ ECNQueue class.
    """
    
    def __init__(self, bitrate: int, maxsize: int, eventlist: EventList, 
                 logger: Optional[QueueLogger] = None, 
                 marking_threshold: int = 0):
        """
        Initialize ECN queue.
        
        Args:
            bitrate: Link speed in bps
            maxsize: Maximum queue size in bytes
            eventlist: Event list instance
            logger: Optional queue logger
            marking_threshold: Threshold for ECN marking in bytes
        """
        super().__init__(bitrate, maxsize, eventlist, logger)
        self._marking_threshold = marking_threshold if marking_threshold > 0 else maxsize // 2
        self._packets_marked = 0
        
        # Update node name to indicate ECN
        self._nodename = f"ecnqueue({bitrate//1000000}Mb/s,{maxsize}bytes,mark@{self._marking_threshold}bytes)"
        
    def receivePacket(self, pkt: Packet) -> None:
        """
        Receive packet and mark with ECN if needed.
        
        Overrides Queue.receivePacket to add ECN marking logic.
        """
        # Check if we should mark the packet before enqueueing
        if self._queuesize >= self._marking_threshold:
            # Mark packet with ECN
            if hasattr(pkt, 'set_ecn'):
                pkt.set_ecn(True)
            elif hasattr(pkt, 'set_flags') and hasattr(pkt, 'ECN'):
                # For TCP packets
                pkt.set_flags(pkt.flags() | pkt.ECN)
            self._packets_marked += 1
            
        # Call parent receivePacket
        super().receivePacket(pkt)
        
    def get_packets_marked(self) -> int:
        """Get number of packets marked with ECN."""
        return self._packets_marked
        
    def reset_marked_count(self) -> None:
        """Reset ECN marking counter."""
        self._packets_marked = 0
        
    def set_marking_threshold(self, threshold: int) -> None:
        """Update ECN marking threshold."""
        self._marking_threshold = threshold