"""
Lossless Output Queue - Implementation for HTSimPy

Corresponds to LosslessOutputQueue in queue_lossless_output.h/cpp
A FIFO queue that supports PAUSE frames and lossless operation on output side
"""

from .base_queue import Queue
from ..core.eventlist import EventList
from ..core.logger import QueueLogger, TrafficLogger
from ..core.network import Packet, PacketType, VirtualQueue
from typing import Optional, List
from enum import IntEnum


class QueueState(IntEnum):
    """Queue states for lossless operation - matches C++ enum"""
    PAUSED = 0
    READY = 1
    PAUSE_RECEIVED = 2


# ECN flags
ECN_CE = 2  # Congestion Experienced


class LosslessOutputQueue(Queue):
    """
    Lossless output queue - handles PAUSE frames and ECN marking
    
    Corresponds to LosslessOutputQueue in queue_lossless_output.h/cpp
    Receives PAUSE frames from downstream and stops/starts sending accordingly
    """
    
    def __init__(self, bitrate: int, maxsize: int, eventlist: EventList,
                 logger: Optional[QueueLogger] = None, ECN: int = 0, K: int = 0):
        """
        Initialize lossless output queue
        
        Corresponds to LosslessOutputQueue constructor
        
        Args:
            bitrate: Link speed in bps
            maxsize: Maximum queue size in bytes
            eventlist: Event scheduler
            logger: Optional queue logger
            ECN: ECN enabled (0=disabled, 1=enabled)
            K: ECN marking threshold in bytes
        """
        super().__init__(bitrate, maxsize, eventlist, logger)
        
        # Lossless state tracking
        self._state_send = QueueState.READY
        self._sending = 0  # Flag indicating packet is being transmitted
        
        # Virtual queue tracking
        self._vq: List[VirtualQueue] = []  # list<VirtualQueue*>
        
        # ECN support
        self._ecn_enabled = ECN
        self._K = K
        
        # Statistics
        self._txbytes = 0  # Total bytes transmitted
        
        # Set node name
        self._nodename = f"queue lossless output({bitrate//1000000}Mb/s,{maxsize}bytes)"
    
    def is_paused(self) -> bool:
        """Check if queue is paused"""
        return self._state_send == QueueState.PAUSED or self._state_send == QueueState.PAUSE_RECEIVED
    
    def receivePacket(self, pkt: Packet, prev: Optional[VirtualQueue] = None) -> None:
        """
        Receive packet into queue
        
        Two overloads in C++:
        1. receivePacket(Packet&) - extracts ingress queue
        2. receivePacket(Packet&, VirtualQueue*) - with explicit VQ
        """
        # Handle first overload - extract ingress queue from packet
        if prev is None:
            if pkt.type() == PacketType.ETH_PAUSE:
                self._receivePacketWithVQ(pkt, None)
            else:
                # Get ingress queue from packet
                from .lossless_input_queue import LosslessInputQueue
                if hasattr(pkt, 'get_ingress_queue'):
                    q = pkt.get_ingress_queue()
                    pkt.clear_ingress_queue()
                    # Cast to VirtualQueue
                    if isinstance(q, VirtualQueue):
                        self._receivePacketWithVQ(pkt, q)
                    else:
                        self._receivePacketWithVQ(pkt, None)
                else:
                    self._receivePacketWithVQ(pkt, None)
        else:
            self._receivePacketWithVQ(pkt, prev)
    
    def _receivePacketWithVQ(self, pkt: Packet, prev: Optional[VirtualQueue]) -> None:
        """
        Internal method for receiving packet with virtual queue
        
        Corresponds to LosslessOutputQueue::receivePacket(Packet&, VirtualQueue*)
        """
        # Check if this is a PAUSE frame
        if pkt.type() == PacketType.ETH_PAUSE:
            try:
                from ..packets.eth_pause_packet import EthPausePacket
                pause_pkt = pkt  # Should be EthPausePacket
                
                if hasattr(pause_pkt, 'sleepTime') and pause_pkt.sleepTime() > 0:
                    # Remote end is telling us to shut up
                    if self._sending:
                        # We have a packet in flight
                        self._state_send = QueueState.PAUSE_RECEIVED
                    else:
                        self._state_send = QueueState.PAUSED
                else:
                    # We are allowed to send!
                    self._state_send = QueueState.READY
                    
                    # Start transmission if we have packets to send
                    if len(self._enqueued) > 0 and not self._sending:
                        self.beginService()
            except ImportError:
                # EthPausePacket not implemented yet
                pass
            
            pkt.free()
            return
        
        # Normal packet, enqueue it
        # Remember the virtual queue that sent us this packet
        assert prev is not None, "Virtual queue must be provided for data packets"
        
        pkt.flow().logTraffic(pkt, self, TrafficLogger.TrafficEvent.PKT_ARRIVE)
        
        queueWasEmpty = len(self._enqueued) == 0
        
        # Add to queues
        self._vq.insert(0, prev)  # push_front
        self._enqueued.append(pkt)  # Use parent's deque
        self._queuesize_bytes += pkt.size()
        
        # Check for overflow (should not happen in lossless)
        if self._queuesize_bytes > self._maxsize:
            from ..core.network import Packet
            print(f" Queue {self._name} LOSSLESS not working! I should have dropped this packet {self._queuesize_bytes // Packet.data_packet_size()}")
        
        if self._logger:
            self._logger.logQueue(self, QueueLogger.QueueEvent.PKT_ENQUEUE, pkt)
        
        # Start service if needed
        if queueWasEmpty and self._state_send == QueueState.READY:
            assert len(self._enqueued) == 1
            self.beginService()
    
    def beginService(self) -> None:
        """
        Begin servicing packets
        
        Corresponds to LosslessOutputQueue::beginService
        """
        assert self._state_send == QueueState.READY and not self._sending
        
        # Call parent beginService
        super().beginService()
        self._sending = 1
    
    def completeService(self) -> None:
        """
        Complete servicing current packet
        
        Corresponds to LosslessOutputQueue::completeService
        """
        # Dequeue the packet
        assert len(self._enqueued) > 0
        
        pkt = self._enqueued.popleft()  # FIFO from parent Queue
        q = self._vq.pop()  # pop_back
        
        # ECN marking
        if self._ecn_enabled and self._queuesize_bytes > self._K:
            pkt.set_flags(pkt.flags() | ECN_CE)
        
        # HPCC INT information (if HPCC packet)
        if pkt.type() == PacketType.HPCC:
            try:
                from ..packets.hpcc_packet import HPCCPacket
                if isinstance(pkt, HPCCPacket):
                    h = pkt
                    assert h._int_hop < 5
                    
                    h._int_info[h._int_hop]._queuesize = self._queuesize_bytes
                    h._int_info[h._int_hop]._ts = self.eventlist.now()
                    
                    if self._switch:
                        h._int_info[h._int_hop]._switchID = self._switch.getID()
                        h._int_info[h._int_hop]._type = self._switch.getType()
                    
                    h._int_info[h._int_hop]._txbytes = self._txbytes
                    h._int_info[h._int_hop]._linkrate = self._bitrate
                    
                    h._int_hop += 1
            except ImportError:
                # HPCC not implemented yet
                pass
        
        # Update queue size and stats
        self._queuesize_bytes -= pkt.size()
        self._txbytes += pkt.size()
        
        pkt.flow().logTraffic(pkt, self, TrafficLogger.TrafficEvent.PKT_DEPART)
        
        if self._logger:
            self._logger.logQueue(self, QueueLogger.QueueEvent.PKT_SERVICE, pkt)
        
        # Tell the virtual input queue this packet is done
        q.completedService(pkt)
        
        # Log packet send for bandwidth utilization tracking
        self.log_packet_send(self.drainTime(pkt))
        
        # Send packet to next hop
        pkt.sendOn()
        
        self._sending = 0
        
        # Update state if pause was received
        if self._state_send == QueueState.PAUSE_RECEIVED:
            self._state_send = QueueState.PAUSED
        
        # Continue service if more packets and not paused
        if len(self._enqueued) > 0:
            if self._state_send == QueueState.READY:
                self.beginService()