"""
Fair Priority Queue - Full implementation for HTSimPy

Corresponds to FairPriorityQueue in queue.h/queue.cpp
Uses FairPullQueue for round-robin fairness between flows at each priority level.
"""

from .base_queue import BaseQueue, Queue
from ..core.eventlist import EventList
from ..core.logger import QueueLogger, TrafficLogger
from ..core.circular_buffer import CircularBuffer
from ..core.network import Packet, PacketType, PacketPriority, PacketSink
from typing import Optional, Dict, List
from enum import IntEnum


class QueuePriority(IntEnum):
    """Queue priority levels - matches C++ enum"""
    Q_LO = 0
    Q_MID = 1
    Q_HI = 2
    Q_NONE = 3


class LosslessQueueState(IntEnum):
    """Lossless queue states - matches C++ enum"""
    PAUSED = 0
    READY = 1
    PAUSE_RECEIVED = 2


class FairPullQueue:
    """
    Fair pull queue for packets - provides round-robin fairness between flows
    Corresponds to FairPullQueue<Packet> in fairpullqueue.h/cpp
    """
    
    def __init__(self):
        """Initialize fair pull queue"""
        self._queue_map: Dict[int, CircularBuffer[Packet]] = {}  # flow_id -> queue
        self._current_queue_key: Optional[int] = None  # Current flow_id being served
        self._flow_keys: List[int] = []  # List of flow IDs for round-robin
        self._current_index: int = 0  # Index in flow_keys
        self._pull_count: int = 0
        self._preferred_flow: int = -1  # int64_t in C++, -1 means no preference
    
    def enqueue(self, pkt: Packet, priority: int = 0) -> None:
        """
        Add packet to the appropriate per-flow queue
        Corresponds to FairPullQueue<PullPkt>::enqueue
        """
        flow_id = pkt.flow_id()
        
        # Find or create queue for this flow
        if flow_id not in self._queue_map:
            self._queue_map[flow_id] = CircularBuffer[Packet]()
            self._flow_keys.append(flow_id)
        
        # Add packet to the flow's queue
        self._queue_map[flow_id].push(pkt)
        self._pull_count += 1
    
    def dequeue(self) -> Optional[Packet]:
        """
        Dequeue packet using round-robin between flows
        Corresponds to FairPullQueue<PullPkt>::dequeue
        """
        if self._pull_count == 0:
            return None
        
        # Round-robin through flows
        start_index = self._current_index
        while True:
            if not self._flow_keys:
                return None
                
            # Get current flow's queue
            flow_id = self._flow_keys[self._current_index]
            if flow_id in self._queue_map:
                queue = self._queue_map[flow_id]
                if not queue.empty():
                    # Found a non-empty queue
                    packet = queue.pop()
                    self._pull_count -= 1
                    
                    # Move to next flow for fairness
                    self._current_index = (self._current_index + 1) % len(self._flow_keys)
                    
                    # Clean up empty queues
                    if queue.empty():
                        del self._queue_map[flow_id]
                        self._flow_keys.remove(flow_id)
                        if self._current_index >= len(self._flow_keys) and self._flow_keys:
                            self._current_index = 0
                    
                    return packet
            
            # Move to next flow
            self._current_index = (self._current_index + 1) % len(self._flow_keys)
            
            # Avoid infinite loop
            if self._current_index == start_index:
                # We've checked all flows
                return None
    
    def empty(self) -> bool:
        """Check if queue is empty"""
        return self._pull_count == 0
    
    def size(self) -> int:
        """Get number of packets in queue"""
        return self._pull_count
    
    def set_preferred_flow(self, flow_id: int) -> None:
        """Set preferred flow for priority handling"""
        self._preferred_flow = flow_id


class HostQueue(Queue):
    """
    Host queue base class - corresponds to HostQueue in queue.h
    
    Adds sender tracking for lossless operation
    """
    
    def __init__(self, bitrate: int, maxsize: int, eventlist: EventList,
                 logger: Optional[QueueLogger] = None):
        """Initialize host queue"""
        super().__init__(bitrate, maxsize, eventlist, logger)
        self._senders: List[PacketSink] = []  # vector<PacketSink*> _senders
    
    def addHostSender(self, snk: PacketSink) -> None:
        """Add a host sender - corresponds to addHostSender"""
        self._senders.append(snk)
    
    def serviceTime(self, pkt: Packet) -> int:
        """Service time for packet - must be implemented by subclass"""
        raise NotImplementedError("serviceTime must be implemented by subclass")


class FairPriorityQueue(HostQueue):
    """
    Fair priority queue - implements 3-level priority with per-flow fairness
    
    Corresponds to FairPriorityQueue in queue.h/queue.cpp
    Uses FairPullQueue at each priority level for fairness between flows
    """
    
    def __init__(self, bitrate: int, maxsize: int, eventlist: EventList, 
                 logger: Optional[QueueLogger] = None):
        """
        Initialize fair priority queue
        
        Corresponds to FairPriorityQueue constructor in queue.cpp
        """
        super().__init__(bitrate, maxsize, eventlist, logger)
        
        # Priority queues using FairPullQueue for fairness
        self._queue = [FairPullQueue() for _ in range(QueuePriority.Q_NONE)]
        
        # Queue sizes per priority
        self._queuesize = [0 for _ in range(QueuePriority.Q_NONE)]
        
        # Currently servicing priority
        self._servicing = QueuePriority.Q_NONE
        
        # Packet currently being sent
        self._sending: Optional[Packet] = None
        
        # Lossless operation state
        self._state_send = LosslessQueueState.READY
    
    def getPriority(self, pkt: Packet) -> QueuePriority:
        """
        Get queue priority for packet
        
        Corresponds to FairPriorityQueue::getPriority
        """
        prio = pkt.priority()
        if prio == PacketPriority.PRIO_LO:
            return QueuePriority.Q_LO
        elif prio == PacketPriority.PRIO_MID:
            return QueuePriority.Q_MID
        elif prio == PacketPriority.PRIO_HI:
            return QueuePriority.Q_HI
        else:  # PRIO_NONE
            # The packet didn't expect to see a priority queue
            raise RuntimeError("Packet has PRIO_NONE in priority queue")
    
    def serviceTime(self, pkt: Optional[Packet] = None) -> int:
        """
        Calculate service time for packet
        
        Corresponds to FairPriorityQueue::serviceTime
        Note: This is inaccurate as noted in C++ comments
        """
        if pkt is None:
            # Use total queue size if no packet specified
            total_size = sum(self._queuesize)
            return total_size * self._ps_per_byte
        
        prio = self.getPriority(pkt)
        if prio == QueuePriority.Q_LO:
            # Low priority waits for all packets
            return sum(self._queuesize) * self._ps_per_byte
        elif prio == QueuePriority.Q_MID:
            # Mid priority waits for high and mid packets
            return (self._queuesize[QueuePriority.Q_HI] + 
                   self._queuesize[QueuePriority.Q_MID]) * self._ps_per_byte
        elif prio == QueuePriority.Q_HI:
            # High priority only waits for other high priority
            return self._queuesize[QueuePriority.Q_HI] * self._ps_per_byte
        else:
            raise RuntimeError("Invalid priority")
    
    def receivePacket(self, pkt: Packet, previousHop=None) -> None:
        """
        Receive packet into queue
        
        Corresponds to FairPriorityQueue::receivePacket
        Handles both data packets and PAUSE frames
        """
        # Check if this is a PAUSE packet
        if pkt.type() == PacketType.ETH_PAUSE:
            # Handle pause frame
            try:
                from ..packets.eth_pause_packet import EthPausePacket
                pause_pkt = pkt  # Should be EthPausePacket
                
                if hasattr(pause_pkt, 'sleepTime') and pause_pkt.sleepTime() > 0:
                    # Remote end is telling us to shut up
                    if self.queuesize() > 0:
                        # We have a packet in flight
                        self._state_send = LosslessQueueState.PAUSE_RECEIVED
                    else:
                        self._state_send = LosslessQueueState.PAUSED
                else:
                    # We are allowed to send!
                    self._state_send = LosslessQueueState.READY
                    
                    # Start transmission if we have packets to send
                    if self.queuesize() > 0:
                        self.beginService()
                
                # Must send the pause packets to all sources on the same host
                if hasattr(self, '_senders'):
                    for sender in self._senders:
                        # Create new pause packet for each sender
                        e = EthPausePacket.newpkt(pause_pkt.sleepTime(), pause_pkt.senderID())
                        sender.receivePacket(e)
            except ImportError:
                # EthPausePacket not implemented yet, just free the packet
                pass
            
            pkt.free()
            return
        
        # Regular packet handling
        prio = self.getPriority(pkt)
        pkt.flow().logTraffic(pkt, self, TrafficLogger.TrafficEvent.PKT_ARRIVE)
        
        # Check if queue was empty before enqueue
        queueWasEmpty = self.queuesize() == 0
        
        # Check for queue overflow (debugging, not dropping)
        if self.queuesize() > self._maxsize and self.queuesize() // 1000000 != (self.queuesize() + pkt.size()) // 1000000:
            print(f"Host Queue size {self.queuesize()}")
        
        # Enqueue the packet
        self._queuesize[prio] += pkt.size()
        self._queue[prio].enqueue(pkt)
        
        if self._logger:
            self._logger.logQueue(self, QueueLogger.QueueEvent.PKT_ENQUEUE, pkt)
        
        # Start service if queue was empty and we're ready to send
        if queueWasEmpty and self._state_send == LosslessQueueState.READY:
            self.beginService()
    
    def beginService(self) -> None:
        """
        Begin servicing packets
        
        Corresponds to FairPriorityQueue::beginService
        """
        assert self._state_send == LosslessQueueState.READY
        
        # Schedule the next dequeue event - check priorities from high to low
        for prio in range(QueuePriority.Q_HI, QueuePriority.Q_LO - 1, -1):
            if self._queuesize[prio] > 0:
                # Dequeue packet from this priority
                self._sending = self._queue[prio].dequeue()
                
                if self._sending is None:
                    continue
                
                assert self._sending is not None
                self.eventlist.sourceIsPendingRel(self, self.drainTime(self._sending))
                self._servicing = QueuePriority(prio)
                return
    
    def completeService(self) -> None:
        """
        Complete servicing current packet
        
        Corresponds to FairPriorityQueue::completeService
        """
        if self._state_send == LosslessQueueState.PAUSED:
            return
        
        if self._servicing == QueuePriority.Q_NONE or self._sending is None:
            print(f"{self._name} trying to deque {self._servicing}, qsize {self.queuesize()}")
        else:
            # Dequeue the packet
            pkt = self._sending
            self._queuesize[self._servicing] -= pkt.size()
            
            self._sending = None
            
            pkt.flow().logTraffic(pkt, self, TrafficLogger.TrafficEvent.PKT_DEPART)
            if self._logger:
                self._logger.logQueue(self, QueueLogger.QueueEvent.PKT_SERVICE, pkt)
            
            # Tell the packet to move on to the next pipe
            pkt.sendOn()
        
        # Update state if pause was received
        if self._state_send == LosslessQueueState.PAUSE_RECEIVED:
            self._state_send = LosslessQueueState.PAUSED
        
        # Schedule next packet if we have more and are allowed to send
        if self.queuesize() > 0 and self._state_send == LosslessQueueState.READY:
            self.beginService()
        else:
            self._servicing = QueuePriority.Q_NONE
    
    def queuesize(self) -> int:
        """
        Get total queue size across all priorities
        
        Corresponds to FairPriorityQueue::queuesize
        """
        return sum(self._queuesize)
    
    def doNextEvent(self) -> None:
        """
        Process next event (dequeue completion)
        
        Inherited from Queue but needs to call our completeService
        """
        self.completeService()