"""
Control Priority Queue - Implementation for HTSimPy

Corresponds to CtrlPrioQueue in prioqueue.h/cpp
A simple 2-level priority queue for control traffic (high) vs data (low)
"""

from .base_queue import Queue
from ..core.eventlist import EventList
from ..core.logger import QueueLogger, TrafficLogger
from ..core.network import Packet, PacketType, PacketPriority
from typing import Optional, List
from enum import IntEnum
import random


class QueuePriority(IntEnum):
    """Queue priority levels - matches C++ enum"""
    Q_LO = 0
    Q_HI = 1
    Q_NONE = 2


class QueueType(IntEnum):
    """Queue type constants - matches C++ defines"""
    QUEUE_INVALID = 0
    QUEUE_LOW = 1
    QUEUE_HIGH = 2


class CtrlPrioQueue(Queue):
    """
    Control priority queue - 2-level priority queue for control vs data traffic
    
    Corresponds to CtrlPrioQueue in prioqueue.h/cpp
    Services high priority (control) packets before low priority (data) packets
    """
    
    def __init__(self, bitrate: int, maxsize: int, eventlist: EventList,
                 logger: Optional[QueueLogger] = None):
        """
        Initialize control priority queue
        
        Corresponds to CtrlPrioQueue constructor in prioqueue.cpp
        """
        super().__init__(bitrate, maxsize, eventlist, logger)
        
        # Counters
        self._num_packets = 0  # Data packets served
        self._num_acks = 0     # ACK packets served
        self._num_nacks = 0    # NACK packets served
        self._num_pulls = 0    # PULL packets served
        self._num_drops = 0    # Already in base Queue
        
        # Queue sizes
        self._queuesize_high = 0
        self._queuesize_low = 0
        
        # Currently serving
        self._serv = QueueType.QUEUE_INVALID
        
        # Queues - use lists like C++
        self._enqueued_low: List[Packet] = []   # list<Packet*>
        self._enqueued_high: List[Packet] = []  # list<Packet*>
        
        # Set node name (note: uses "compqueue" in C++)
        self._nodename = f"compqueue({bitrate//1000000}Mb/s,{maxsize}bytes)"
    
    def queuesize(self) -> int:
        """
        Get total queue size
        
        Corresponds to CtrlPrioQueue::queuesize
        """
        return self._queuesize_low + self._queuesize_high
    
    def num_packets(self) -> int:
        """Get number of data packets served"""
        return self._num_packets
    
    def num_acks(self) -> int:
        """Get number of ACKs served"""
        return self._num_acks
    
    def num_pulls(self) -> int:
        """Get number of PULLs served"""
        return self._num_pulls
    
    def getPriority(self, pkt: Packet) -> QueuePriority:
        """
        Get queue priority for packet
        
        Corresponds to CtrlPrioQueue::getPriority
        """
        pktprio = pkt.priority()
        
        if pktprio == PacketPriority.PRIO_LO:
            return QueuePriority.Q_LO
        elif pktprio == PacketPriority.PRIO_MID:
            # This queue supports two priorities only
            raise RuntimeError("CtrlPrioQueue does not support MID priority")
        elif pktprio == PacketPriority.PRIO_HI:
            return QueuePriority.Q_HI
        else:  # PRIO_NONE
            # This packet didn't expect to see a priority queue
            raise RuntimeError("Packet has PRIO_NONE in priority queue")
    
    def receivePacket(self, pkt: Packet, previousHop=None) -> None:
        """
        Receive packet into queue
        
        Corresponds to CtrlPrioQueue::receivePacket
        """
        pkt.flow().logTraffic(pkt, self, TrafficLogger.TrafficEvent.PKT_ARRIVE)
        
        prio = self.getPriority(pkt)
        
        # Select appropriate queue
        if prio == QueuePriority.Q_LO:
            enqueued = self._enqueued_low
            queuesize_ptr = 'low'
        elif prio == QueuePriority.Q_HI:
            enqueued = self._enqueued_high
            queuesize_ptr = 'high'
        else:
            raise RuntimeError(f"Invalid priority: {prio}")
        
        # Get current queue size
        current_queuesize = self._queuesize_low if queuesize_ptr == 'low' else self._queuesize_high
        
        # Check for overflow
        if current_queuesize + pkt.size() > self._maxsize:
            # Need to drop a packet - randomly choose arriving or queued
            if random.random() < 0.5:
                # Drop arriving packet
                dropped_pkt = pkt
                print("drop arriving!")
            else:
                # Drop oldest packet from queue
                print("drop last from queue!")
                dropped_pkt = enqueued[0]  # front()
                enqueued.pop(0)  # pop_front()
                
                # Update queue size
                if queuesize_ptr == 'low':
                    self._queuesize_low -= dropped_pkt.size()
                else:
                    self._queuesize_high -= dropped_pkt.size()
                
                # Enqueue arriving packet
                enqueued.insert(0, pkt)  # push_front
                if queuesize_ptr == 'low':
                    self._queuesize_low += pkt.size()
                else:
                    self._queuesize_high += pkt.size()
            
            # Log drop
            if self._logger:
                self._logger.logQueue(self, QueueLogger.QueueEvent.PKT_DROP, dropped_pkt)
            
            # Print drop info based on packet type
            if pkt.type() == PacketType.NDPLITERTS:
                print("RTS dropped ", end='')
            elif pkt.type() == PacketType.NDPLITE:
                print("Data dropped ", end='')
            elif pkt.type() == PacketType.NDPLITEACK:
                print("Ack dropped ", end='')
            else:
                # For other types, just continue
                pass
            
            dropped_pkt.flow().logTraffic(dropped_pkt, self, TrafficLogger.TrafficEvent.PKT_DROP)
            print(f"B[ {len(self._enqueued_low)} {len(enqueued)} ] DROP {dropped_pkt.flow_id()}")
            dropped_pkt.free()
            self._num_drops += 1
        else:
            # Enqueue packet
            enqueued.insert(0, pkt)  # push_front
            if queuesize_ptr == 'low':
                self._queuesize_low += pkt.size()
            else:
                self._queuesize_high += pkt.size()
        
        # Start service if needed
        if self._serv == QueueType.QUEUE_INVALID:
            self.beginService()
    
    def beginService(self) -> None:
        """
        Begin servicing packets - high priority first
        
        Corresponds to CtrlPrioQueue::beginService
        """
        if self._enqueued_high:
            self._serv = QueueType.QUEUE_HIGH
            # Service from back (oldest packet)
            self.eventlist.sourceIsPendingRel(self, self.drainTime(self._enqueued_high[-1]))
        elif self._enqueued_low:
            self._serv = QueueType.QUEUE_LOW
            self.eventlist.sourceIsPendingRel(self, self.drainTime(self._enqueued_low[-1]))
        else:
            assert False, "beginService called with empty queues"
            self._serv = QueueType.QUEUE_INVALID
    
    def completeService(self) -> None:
        """
        Complete servicing current packet
        
        Corresponds to CtrlPrioQueue::completeService
        """
        if self._serv == QueueType.QUEUE_LOW:
            assert self._enqueued_low
            pkt = self._enqueued_low.pop()  # pop_back
            self._queuesize_low -= pkt.size()
            self._num_packets += 1
        elif self._serv == QueueType.QUEUE_HIGH:
            assert self._enqueued_high
            pkt = self._enqueued_high.pop()  # pop_back
            self._queuesize_high -= pkt.size()
            
            # Update counters based on packet type
            if pkt.type() in [PacketType.NDPACK, PacketType.NDPLITEACK]:
                self._num_acks += 1
            elif pkt.type() == PacketType.NDPNACK:
                self._num_nacks += 1
            elif pkt.type() in [PacketType.NDPPULL, PacketType.NDPLITEPULL]:
                self._num_pulls += 1
            else:
                # C++ aborts here - we'll just count it as misc
                pass
        else:
            assert False, f"Invalid service type: {self._serv}"
            return
        
        pkt.flow().logTraffic(pkt, self, TrafficLogger.TrafficEvent.PKT_DEPART)
        if self._logger:
            self._logger.logQueue(self, QueueLogger.QueueEvent.PKT_SERVICE, pkt)
        pkt.sendOn()
        
        self._serv = QueueType.QUEUE_INVALID
        
        # Continue service if more packets
        if self._enqueued_high or self._enqueued_low:
            self.beginService()
    
    def doNextEvent(self) -> None:
        """
        Process next event
        
        Corresponds to CtrlPrioQueue::doNextEvent
        """
        self.completeService()