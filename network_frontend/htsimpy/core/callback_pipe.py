"""Callback Pipe implementation for HTSimPy."""

from .pipe import Pipe
from .eventlist import EventList
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .network import Packet


class CallbackPipe(Pipe):
    """
    A pipe that calls back to its parent when packet arrives.
    
    Matches C++ CallbackPipe class.
    """
    
    def __init__(self, delay: int, eventlist: EventList, parent=None):
        """
        Initialize callback pipe.
        
        Args:
            delay: Propagation delay in picoseconds
            eventlist: Event list instance
            parent: Parent object to callback (usually a switch)
        """
        super().__init__(delay, eventlist)
        self._parent = parent
        
    def receivePacket(self, pkt: 'Packet', virtual_queue=None) -> None:
        """
        Receive packet and callback to parent after delay.
        
        Override parent class receivePacket to handle callbacks.
        """
        # Store the packet with delay (uses parent Pipe implementation)
        super().receivePacket(pkt, virtual_queue)
        
    def do_next_event(self) -> None:
        """
        Process next event - deliver packet to parent.
        
        Override to callback to parent instead of normal forwarding.
        """
        if self._count == 0:
            return
        
        # Get packet from parent class
        pkt = self._inflight_v[self._next_pop].pkt
        self._next_pop = (self._next_pop + 1) % self._size
        self._count -= 1
        
        # Log traffic
        if hasattr(pkt, 'flow') and pkt.flow() and pkt.flow().log_me():
            from ..core.logger.traffic import TrafficLogger
            pkt.flow().logTraffic(pkt, self, TrafficLogger.TrafficEvent.PKT_DEPART)
        
        # Callback to parent if set
        if self._parent and hasattr(self._parent, 'receive_packet'):
            self._parent.receive_packet(pkt)
        else:
            # Normal pipe behavior - send on the packet
            pkt.sendOn()
            
        # Schedule next event if needed
        if self._count > 0:
            next_event_time = self._inflight_v[self._next_pop].time
            self._eventlist.source_is_pending(self, next_event_time)
                
    def set_parent(self, parent) -> None:
        """Set parent for callback."""
        self._parent = parent