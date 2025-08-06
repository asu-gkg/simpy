"""
Composite Priority Queue - Implementation for HTSimPy

Corresponds to CompositePrioQueue in compositeprioqueue.h/cpp
A composite queue that transforms packets into headers when there is no space 
and services headers with priority.
"""

from .base_queue import Queue
from ..core.eventlist import EventList
from ..core.logger import QueueLogger, TrafficLogger
from ..core.network import Packet, PacketType
from typing import Optional, List
from enum import IntEnum
import random


class QueueType(IntEnum):
    """Queue type constants - matches C++ defines"""
    QUEUE_INVALID = 0
    QUEUE_LOW = 1
    QUEUE_HIGH = 2


MAX_PATH_LEN = 20  # Maximum path length constant


class CompositePrioQueue(Queue):
    """
    Composite priority queue - transforms packets to headers when full
    
    Corresponds to CompositePrioQueue in compositeprioqueue.h/cpp
    Services high priority (headers) and low priority (data) with configurable ratio
    """
    
    def __init__(self, bitrate: int, maxsize: int, eventlist: EventList,
                 logger: Optional[QueueLogger] = None):
        """
        Initialize composite priority queue
        
        Corresponds to CompositePrioQueue constructor in compositeprioqueue.cpp
        """
        super().__init__(bitrate, maxsize, eventlist, logger)
        
        # Service ratios
        self._ratio_high = 10  # High priority service ratio
        self._ratio_low = 1    # Low priority service ratio
        self._crt = 0          # Current position in ratio cycle
        
        # Counters
        self._num_headers = 0  # Data packets stripped to headers
        self._num_packets = 0  # Total packets served
        self._num_acks = 0     # ACK packets served
        self._num_nacks = 0    # NACK packets served
        self._num_pulls = 0    # PULL packets served
        self._num_drops = 0    # Already defined in base Queue
        self._stripped = 0     # Packets stripped to headers
        self._dropped = 0      # Headers dropped
        
        # Path length tracking
        self._enqueued_path_lens = [0] * (MAX_PATH_LEN + 1)
        self._max_path_len_queued = 0
        self._max_path_len_seen = 0
        
        # Queue sizes
        self._queuesize_high = 0
        self._queuesize_low = 0
        
        # Currently serving
        self._serv = QueueType.QUEUE_INVALID
        
        # Queues
        self._enqueued_low: List[Packet] = []   # Low priority queue
        self._enqueued_high: List[Packet] = []  # High priority queue
        
        # Set node name
        self._nodename = f"compqueue({bitrate//1000000}Mb/s,{maxsize}bytes)"
    
    def queuesize(self) -> int:
        """
        Get total queue size
        
        Corresponds to CompositePrioQueue::queuesize
        """
        return self._queuesize_low + self._queuesize_high
    
    def num_headers(self) -> int:
        """Get number of headers (stripped data packets)"""
        return self._num_headers
    
    def num_packets(self) -> int:
        """Get number of packets served"""
        return self._num_packets
    
    def num_stripped(self) -> int:
        """Get number of packets stripped to headers"""
        return self._stripped
    
    def num_acks(self) -> int:
        """Get number of ACKs served"""
        return self._num_acks
    
    def num_nacks(self) -> int:
        """Get number of NACKs served"""
        return self._num_nacks
    
    def num_pulls(self) -> int:
        """Get number of PULLs served"""
        return self._num_pulls
    
    def receivePacket(self, pkt: Packet, previousHop=None) -> None:
        """
        Receive packet into queue
        
        Corresponds to CompositePrioQueue::receivePacket
        """
        pkt.flow().logTraffic(pkt, self, TrafficLogger.TrafficEvent.PKT_ARRIVE)
        
        if not pkt.header_only():
            # Regular data packet
            if (self._queuesize_low + pkt.size() <= self._maxsize or
                (self._enqueued_low and pkt.path_len() == self._enqueued_low[0].path_len() and random.random() < 0.5) or
                (pkt.path_len() < self._max_path_len_queued)):
                
                # We can accept the packet because either:
                # 1. Queue isn't full, or
                # 2. Arriving packet has same path length as front packet and coin flip says keep it, or
                # 3. Arriving packet has shorter path than some queued packet
                
                if self._queuesize_low + pkt.size() > self._maxsize:
                    # Need to trim a packet from low priority queue
                    assert self._enqueued_low
                    
                    if pkt.path_len() < self._max_path_len_queued:
                        print(f"Trim1 {pkt.path_len()} max {self._max_path_len_queued}")
                        self._trim_low_priority_packet(pkt.path_len())
                    else:
                        # Same path length, coin flip said to drop queued packet
                        print(f"Trim2 {pkt.path_len()} max {self._max_path_len_queued}")
                        self._trim_low_priority_packet(pkt.path_len() - 1)
                
                assert self._queuesize_low + pkt.size() <= self._maxsize
                
                self._enqueue_packet(pkt)
                if self._logger:
                    self._logger.logQueue(self, QueueLogger.QueueEvent.PKT_ENQUEUE, pkt)
                
                if self._serv == QueueType.QUEUE_INVALID:
                    self.beginService()
                
                return
            else:
                # Strip packet - low priority queue is full
                print(f"B [ {len(self._enqueued_low)} {len(self._enqueued_high)} ] STRIP")
                pkt.strip_payload()
                self._stripped += 1
                pkt.flow().logTraffic(pkt, self, TrafficLogger.TrafficEvent.PKT_TRIM)
                if self._logger:
                    self._logger.logQueue(self, QueueLogger.QueueEvent.PKT_TRIM, pkt)
        
        # Handle header packet
        assert pkt.header_only()
        
        if self._queuesize_high + pkt.size() > self._maxsize:
            # Drop header - high priority queue is full
            if self._logger:
                self._logger.logQueue(self, QueueLogger.QueueEvent.PKT_DROP, pkt)
            pkt.flow().logTraffic(pkt, self, TrafficLogger.TrafficEvent.PKT_DROP)
            print(f"D[ {len(self._enqueued_low)} {len(self._enqueued_high)} ] DROP {pkt.flow_id()}")
            pkt.free()
            self._num_drops += 1
            return
        
        # Enqueue header in high priority queue
        self._enqueued_high.insert(0, pkt)  # push_front
        self._queuesize_high += pkt.size()
        
        if self._serv == QueueType.QUEUE_INVALID:
            self.beginService()
    
    def beginService(self) -> None:
        """
        Begin servicing packets
        
        Corresponds to CompositePrioQueue::beginService
        """
        if self._enqueued_high and self._enqueued_low:
            # Both queues have packets - use ratio
            self._crt += 1
            
            if self._crt >= (self._ratio_high + self._ratio_low):
                self._crt = 0
            
            if self._crt < self._ratio_high:
                self._serv = QueueType.QUEUE_HIGH
                # Service from back (oldest packet)
                self.eventlist.sourceIsPendingRel(self, self.drainTime(self._enqueued_high[-1]))
            else:
                assert self._crt < self._ratio_high + self._ratio_low
                self._serv = QueueType.QUEUE_LOW
                self.eventlist.sourceIsPendingRel(self, self.drainTime(self._enqueued_low[-1]))
            return
        
        if self._enqueued_high:
            self._serv = QueueType.QUEUE_HIGH
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
        
        Corresponds to CompositePrioQueue::completeService
        """
        if self._serv == QueueType.QUEUE_LOW:
            pkt = self._dequeue_low_packet()
        elif self._serv == QueueType.QUEUE_HIGH:
            pkt = self._dequeue_high_packet()
        else:
            assert False, f"Invalid service type: {self._serv}"
            return
        
        pkt.flow().logTraffic(pkt, self, TrafficLogger.TrafficEvent.PKT_DEPART)
        if self._logger:
            self._logger.logQueue(self, QueueLogger.QueueEvent.PKT_SERVICE, pkt)
        pkt.sendOn()
        
        self._serv = QueueType.QUEUE_INVALID
        
        if self._enqueued_high or self._enqueued_low:
            self.beginService()
    
    def doNextEvent(self) -> None:
        """
        Process next event
        
        Corresponds to CompositePrioQueue::doNextEvent
        """
        self.completeService()
    
    def _enqueue_packet(self, pkt: Packet) -> None:
        """
        Add packet to low priority queue and update bookkeeping
        
        Corresponds to CompositePrioQueue::enqueue_packet
        """
        self._enqueued_low.insert(0, pkt)  # push_front
        self._queuesize_low += pkt.size()
        
        if self._max_path_len_queued < pkt.path_len():
            self._max_path_len_queued = pkt.path_len()
            if self._max_path_len_seen < self._max_path_len_queued:
                self._max_path_len_seen = self._max_path_len_queued
        
        self._enqueued_path_lens[pkt.path_len()] += 1
        self._check_queued()
    
    def _dequeue_low_packet(self) -> Packet:
        """
        Dequeue packet from low priority queue
        
        Corresponds to CompositePrioQueue::dequeue_low_packet
        """
        assert self._enqueued_low
        pkt = self._enqueued_low.pop()  # Remove from back
        self._queuesize_low -= pkt.size()
        self._num_packets += 1
        
        # Update priority housekeeping
        path_len = pkt.path_len()
        assert self._enqueued_path_lens[path_len] > 0
        self._enqueued_path_lens[path_len] -= 1
        
        if path_len == self._max_path_len_queued and self._enqueued_path_lens[path_len] == 0:
            # We just dequeued the last packet with the longest path len
            self._find_max_path_len_queued()
        
        self._check_queued()
        return pkt
    
    def _dequeue_high_packet(self) -> Packet:
        """
        Dequeue packet from high priority queue
        
        Corresponds to CompositePrioQueue::dequeue_high_packet
        """
        assert self._enqueued_high
        pkt = self._enqueued_high.pop()  # Remove from back
        self._queuesize_high -= pkt.size()
        
        if pkt.type() == PacketType.NDPACK:
            self._num_acks += 1
        elif pkt.type() == PacketType.NDPNACK:
            self._num_nacks += 1
        elif pkt.type() == PacketType.NDPPULL:
            self._num_pulls += 1
        else:
            print(f"Hdr: type={pkt.type()}")
            self._num_headers += 1
        
        self._check_queued()
        return pkt
    
    def _find_max_path_len_queued(self) -> None:
        """
        Recalculate maximum path length in queue
        
        Corresponds to CompositePrioQueue::find_max_path_len_queued
        """
        self._max_path_len_queued = 0
        if not self._enqueued_low:
            return
        
        for i in range(self._max_path_len_seen, -1, -1):
            if self._enqueued_path_lens[i] > 0:
                self._max_path_len_queued = i
                return
        
        self._check_queued()
    
    def _check_queued(self) -> None:
        """
        Verify queue consistency
        
        Corresponds to CompositePrioQueue::check_queued
        """
        maxpath = 0
        total_queued = 0
        
        for i in range(MAX_PATH_LEN):
            if self._enqueued_path_lens[i] > 0:
                maxpath = i
                total_queued += self._enqueued_path_lens[i]
        
        assert maxpath == self._max_path_len_queued
        assert total_queued <= 8
    
    def _trim_low_priority_packet(self, prio: int) -> None:
        """
        Trim a low priority packet with path length > prio
        
        Corresponds to CompositePrioQueue::trim_low_priority_packet
        """
        assert prio < self._max_path_len_queued
        
        # Working from tail of queue, find first packet with path_len > prio
        c = -1
        for i, pkt in enumerate(self._enqueued_low):
            c += 1
            if pkt.path_len() > prio:
                # Found packet to trim
                booted_pkt = self._enqueued_low.pop(i)
                self._queuesize_low -= booted_pkt.size()
                
                # Update priority housekeeping
                path_len = booted_pkt.path_len()
                assert self._enqueued_path_lens[path_len] > 0
                self._enqueued_path_lens[path_len] -= 1
                
                if path_len == self._max_path_len_queued and self._enqueued_path_lens[path_len] == 0:
                    # We just removed the last packet with the longest path len
                    self._find_max_path_len_queued()
                
                self._check_queued()
                
                print(f"C [ {len(self._enqueued_low)} {len(self._enqueued_high)} ] STRIP")
                print(f"Arriving: {prio} booted: {booted_pkt.path_len()} posn: {c}")
                
                booted_pkt.strip_payload()
                
                if self._queuesize_high + booted_pkt.size() > self._maxsize:
                    # No space in header queue either
                    self._dropped += 1
                    booted_pkt.flow().logTraffic(booted_pkt, self, TrafficLogger.TrafficEvent.PKT_DROP)
                    booted_pkt.free()
                    if self._logger:
                        self._logger.logQueue(self, QueueLogger.QueueEvent.PKT_DROP, booted_pkt)
                else:
                    self._stripped += 1
                    booted_pkt.flow().logTraffic(booted_pkt, self, TrafficLogger.TrafficEvent.PKT_TRIM)
                    self._enqueued_high.insert(0, booted_pkt)  # push_front
                    self._queuesize_high += booted_pkt.size()
                    if self._logger:
                        self._logger.logQueue(self, QueueLogger.QueueEvent.PKT_TRIM, booted_pkt)
                
                self._check_queued()
                return
        
        # Should not reach here
        print(f"FAIL!, can't find packet with less than {prio}")
        for pkt in self._enqueued_low:
            print(f"pathlen: {pkt.path_len()}")
        for c in range(self._max_path_len_seen + 1):
            print(f"len: {c} count: {self._enqueued_path_lens[c]}")
        assert False, "Failed to find packet to trim"