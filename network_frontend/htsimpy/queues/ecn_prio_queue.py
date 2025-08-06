"""
ECN Priority Queue - Implementation for HTSimPy

Corresponds to ECNPrioQueue in ecnprioqueue.h/cpp
A two-level priority queue supporting ECN (Explicit Congestion Notification)
"""

from .base_queue import Queue
from ..core.eventlist import EventList
from ..core.logger import QueueLogger, TrafficLogger
from ..core.network import Packet, PacketPriority
from ..core.circular_buffer import CircularBuffer
from typing import Optional, List
from enum import IntEnum
import random


class QueuePriority(IntEnum):
    """Queue priority levels - matches C++ enum"""
    Q_LO = 0
    Q_HI = 1
    Q_NONE = 2


# ECN flags from ecn.h
ECN_CE = 2  # Congestion Experienced


class ECNPrioQueue(Queue):
    """
    ECN priority queue - 2-level priority queue with ECN marking
    
    Corresponds to ECNPrioQueue in ecnprioqueue.h/cpp
    Marks packets with ECN_CE when queue exceeds threshold
    """
    
    def __init__(self, bitrate: int, maxsize_hi: int, maxsize_lo: int,
                 ecn_thresh_hi: int, ecn_thresh_lo: int,
                 eventlist: EventList, logger: Optional[QueueLogger] = None):
        """
        Initialize ECN priority queue
        
        Corresponds to ECNPrioQueue constructor
        
        Args:
            bitrate: Link speed in bps
            maxsize_hi: Maximum size for high priority queue in bytes
            maxsize_lo: Maximum size for low priority queue in bytes
            ecn_thresh_hi: ECN marking threshold for high priority in bytes
            ecn_thresh_lo: ECN marking threshold for low priority in bytes
            eventlist: Event scheduler
            logger: Optional queue logger
        """
        # Total maxsize is sum of both queues
        super().__init__(bitrate, maxsize_hi + maxsize_lo, eventlist, logger)
        
        # Counters
        self._num_packets = 0
        self._num_drops = 0  # Already in base Queue
        
        # ECN state
        self._ecn = False  # Set ECN_CE when service is complete
        
        # Queue sizes and thresholds (using arrays like C++)
        self._queuesize = [0, 0]  # mem_b _queuesize[Q_NONE]
        self._maxsize = [maxsize_lo, maxsize_hi]  # mem_b _maxsize[Q_NONE]
        self._ecn_thresh = [ecn_thresh_lo, ecn_thresh_hi]  # mem_b _ecn_thresh[Q_NONE]
        
        # Currently serving
        self._serv = QueuePriority.Q_NONE
        
        # Queues using CircularBuffer like C++
        self._enqueued = [CircularBuffer[Packet](), CircularBuffer[Packet]()]  # CircularBuffer<Packet*> _enqueued[Q_NONE]
        
        # Set node name
        self._nodename = f"ecnprioqueue({bitrate//1000000}Mb/s,{maxsize_lo}bytes_L,{maxsize_hi}bytes_H)"
    
    def queuesize(self) -> int:
        """
        Get total queue size
        
        Corresponds to ECNPrioQueue::queuesize
        """
        return self._queuesize[QueuePriority.Q_LO] + self._queuesize[QueuePriority.Q_HI]
    
    def lo_queuesize(self) -> int:
        """Get low priority queue size"""
        return self._queuesize[QueuePriority.Q_LO]
    
    def hi_queuesize(self) -> int:
        """Get high priority queue size"""
        return self._queuesize[QueuePriority.Q_HI]
    
    def num_packets(self) -> int:
        """Get number of packets served"""
        return self._num_packets
    
    def getPriority(self, pkt: Packet) -> QueuePriority:
        """
        Get queue priority for packet
        
        Corresponds to ECNPrioQueue::getPriority
        """
        pktprio = pkt.priority()
        
        if pktprio == PacketPriority.PRIO_LO:
            return QueuePriority.Q_LO
        elif pktprio == PacketPriority.PRIO_MID:
            # This queue supports two priorities only
            raise RuntimeError("ECNPrioQueue does not support MID priority")
        elif pktprio == PacketPriority.PRIO_HI:
            return QueuePriority.Q_HI
        else:  # PRIO_NONE
            # This packet didn't expect to see a priority queue
            raise RuntimeError("Packet has PRIO_NONE in priority queue")
    
    def receivePacket(self, pkt: Packet, previousHop=None) -> None:
        """
        Receive packet into queue
        
        Corresponds to ECNPrioQueue::receivePacket
        """
        pkt.flow().logTraffic(pkt, self, TrafficLogger.TrafficEvent.PKT_ARRIVE)
        
        prio = self.getPriority(pkt)
        
        # Check for queue full - with randomization on last slot
        if (self._queuesize[prio] + pkt.size() > self._maxsize[prio] or
            (self._queuesize[prio] + 2 * pkt.size() > self._maxsize[prio] and (random.randint(0, 1) & 0x01))):
            # Drop packet - droptail with random drop on last slot to reduce phase effects
            if self._logger:
                self._logger.logQueue(self, QueueLogger.QueueEvent.PKT_DROP, pkt)
            
            pkt.flow().logTraffic(pkt, self, TrafficLogger.TrafficEvent.PKT_DROP)
            print(f"B[ {self._enqueued[QueuePriority.Q_LO].size()} {self._enqueued[QueuePriority.Q_HI].size()} ] DROP {pkt.flow_id()}")
            pkt.free()
            self._num_drops += 1
            return
        else:
            # Enqueue packet
            self._enqueued[prio].push(pkt)
            self._queuesize[prio] += pkt.size()
        
        # Start service if needed
        if self._serv == QueuePriority.Q_NONE:
            self.beginService()
    
    def beginService(self) -> None:
        """
        Begin servicing packets - high priority first
        
        Corresponds to ECNPrioQueue::beginService
        Sets ECN flag based on queue occupancy at start of service
        """
        self._ecn = False
        
        if not self._enqueued[QueuePriority.Q_HI].empty():
            self._serv = QueuePriority.Q_HI
            # Set ECN bit on start of dequeue
            if self._queuesize[QueuePriority.Q_HI] > self._ecn_thresh[QueuePriority.Q_HI]:
                self._ecn = True
            # Service from back (oldest packet)
            self.eventlist.sourceIsPendingRel(self, self.drainTime(self._enqueued[QueuePriority.Q_HI].back()))
        elif not self._enqueued[QueuePriority.Q_LO].empty():
            self._serv = QueuePriority.Q_LO
            # Set ECN bit on start of dequeue
            if self._queuesize[QueuePriority.Q_LO] > self._ecn_thresh[QueuePriority.Q_LO]:
                self._ecn = True
            self.eventlist.sourceIsPendingRel(self, self.drainTime(self._enqueued[QueuePriority.Q_LO].back()))
        else:
            assert False, "beginService called with empty queues"
            self._serv = QueuePriority.Q_NONE
    
    def completeService(self) -> None:
        """
        Complete servicing current packet
        
        Corresponds to ECNPrioQueue::completeService
        """
        assert self._serv != QueuePriority.Q_NONE
        
        # Dequeue packet from appropriate queue
        pkt = self._enqueued[self._serv].pop()
        self._queuesize[self._serv] -= pkt.size()
        self._num_packets += 1
        
        pkt.flow().logTraffic(pkt, self, TrafficLogger.TrafficEvent.PKT_DEPART)
        if self._logger:
            self._logger.logQueue(self, QueueLogger.QueueEvent.PKT_SERVICE, pkt)
        
        # Set ECN bit if needed
        if self._ecn:
            pkt.set_flags(pkt.flags() | ECN_CE)
        
        pkt.sendOn()
        
        self._serv = QueuePriority.Q_NONE
        
        # Continue service if more packets
        if not self._enqueued[QueuePriority.Q_HI].empty() or not self._enqueued[QueuePriority.Q_LO].empty():
            self.beginService()
    
    def doNextEvent(self) -> None:
        """
        Process next event
        
        Corresponds to ECNPrioQueue::doNextEvent
        """
        self.completeService()