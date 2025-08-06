"""
Lossless Input Queue - Implementation for HTSimPy

Corresponds to LosslessInputQueue in queue_lossless_input.h/cpp
A FIFO queue that supports PAUSE frames and lossless operation
"""

from .base_queue import Queue
from ..core.eventlist import EventList
from ..core.network import VirtualQueue, Packet, PacketSink
from ..core.callback_pipe import CallbackPipe
from typing import Optional, TYPE_CHECKING
from enum import IntEnum

if TYPE_CHECKING:
    from ..datacenter.switch import Switch


class LosslessState(IntEnum):
    """Lossless queue states - matches C++ enum"""
    PAUSED = 0
    READY = 1  
    PAUSE_RECEIVED = 2


class LosslessInputQueue(Queue, VirtualQueue):
    """
    Lossless input queue - implements flow control with PAUSE frames
    
    Corresponds to LosslessInputQueue in queue_lossless_input.h/cpp
    Sends PAUSE frames to stop/start upstream sender based on thresholds
    """
    
    # Static thresholds - must be set before creating queues
    _low_threshold: int = 0
    _high_threshold: int = 0
    
    @classmethod
    def set_thresholds(cls, low: int, high: int) -> None:
        """Set global thresholds for all lossless input queues"""
        cls._low_threshold = low
        cls._high_threshold = high
    
    def __init__(self, eventlist: EventList, peer: Optional['Queue'] = None, 
                 sw: Optional['Switch'] = None, wire_latency: Optional[int] = None):
        """
        Initialize lossless input queue
        
        Three constructors in C++:
        1. LosslessInputQueue(EventList&) - basic constructor
        2. LosslessInputQueue(EventList&, BaseQueue*) - with peer
        3. LosslessInputQueue(EventList&, BaseQueue*, Switch*, simtime_picosec) - full
        """
        # Initialize Queue with 1Gbps speed and 2000 packet buffer
        # speedFromGbps(1) = 1000000000 bps
        # Packet::data_packet_size() * 2000
        from ..core.network import Packet
        bitrate = 1000000000  # 1 Gbps
        maxsize = Packet.data_packet_size() * 2000  # In bytes
        
        Queue.__init__(self, bitrate, maxsize, eventlist, None)
        VirtualQueue.__init__(self)
        
        # Check thresholds are set
        assert self._high_threshold > 0, "High threshold must be set before creating queue"
        assert self._high_threshold > self._low_threshold, "High threshold must be > low threshold"
        
        # State tracking
        self._state_recv = LosslessState.READY
        
        # Wire and switch references
        self._wire: Optional[CallbackPipe] = None
        self._switch: Optional['Switch'] = sw
        
        if peer is not None:
            # Set up peer relationship
            self._nodename = f"VirtualQueue({peer._name})"
            self._remoteEndpoint = peer
            peer.setRemoteEndpoint(self)
            
            if sw is not None and wire_latency is not None:
                # Full constructor with wire
                self._wire = CallbackPipe(wire_latency, eventlist, peer)
                assert self._switch is not None
    
    def receivePacket(self, pkt: Packet, previousHop=None) -> None:
        """
        Receive packet into queue
        
        Corresponds to LosslessInputQueue::receivePacket
        """
        # Normal packet, enqueue it
        self._queuesize += pkt.size()
        
        # Send PAUSE notifications if needed
        assert self._queuesize > 0
        if self._queuesize > self._high_threshold and self._state_recv != LosslessState.PAUSED:
            self._state_recv = LosslessState.PAUSED
            self.sendPause(1000)
        
        # Check for overflow (should not happen in lossless)
        if self._queuesize > self._maxsize:
            print(f" Queue {self._name} LOSSLESS not working! I should have dropped this packet {self._queuesize // Packet.data_packet_size()}")
        
        # Forward packet
        if hasattr(pkt, 'nexthop') and hasattr(pkt, 'route'):
            if pkt.nexthop() < pkt.route().size():
                # Continue on route
                pkt.sendOn2(self)
            else:
                # At destination switch
                assert self._switch is not None
                pkt.set_ingress_queue(self)
                self._switch.receivePacket(pkt)
        else:
            # No route info, send to switch
            if self._switch:
                pkt.set_ingress_queue(self)
                self._switch.receivePacket(pkt)
    
    def completedService(self, pkt: Packet) -> None:
        """
        Complete service of packet - called by virtual queue mechanism
        
        Corresponds to LosslessInputQueue::completedService
        """
        self._queuesize -= pkt.size()
        
        # Unblock if below low threshold
        assert self._queuesize >= 0
        if self._queuesize < self._low_threshold and self._state_recv == LosslessState.PAUSED:
            self._state_recv = LosslessState.READY
            self.sendPause(0)
    
    def sendPause(self, wait: int) -> None:
        """
        Send PAUSE frame to upstream sender
        
        Corresponds to LosslessInputQueue::sendPause
        wait: pause time (0 to unpause)
        """
        switchID = 0
        if self._switch:
            switchID = self._switch.getID()
        
        # Create pause packet
        try:
            from ..packets.eth_pause_packet import EthPausePacket
            pkt = EthPausePacket.newpkt(wait, switchID)
            
            if self._wire:
                self._wire.receivePacket(pkt)
            elif self.getRemoteEndpoint():
                self.getRemoteEndpoint().receivePacket(pkt)
        except ImportError:
            # EthPausePacket not implemented yet
            pass
    
    def setName(self, name: str) -> None:
        """
        Set queue name
        
        Corresponds to virtual void setName override
        """
        super().setName(name)
        self._nodename += name
    
    def nodename(self) -> str:
        """Get node name"""
        return self._nodename