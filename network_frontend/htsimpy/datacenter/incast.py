"""
Incast traffic pattern for data center networks

Corresponds to incast.h/cpp in HTSim C++ implementation
Implements the incast pattern where multiple senders simultaneously
send to a single receiver (many-to-one communication).
"""

from typing import List, Optional, TYPE_CHECKING
from ..core.eventlist import EventSource, EventList

if TYPE_CHECKING:
    from ..protocols.tcp import TcpSrc


class TcpSrcTransfer:
    """
    TCP source for transfer-based flows
    
    This represents a TCP source that sends a fixed amount of data
    and can be reset to send again. Used for incast patterns.
    """
    
    def __init__(self, tcp_src: 'TcpSrc', bytes_to_send: int, 
                 flow_stopped_callback: Optional[EventSource] = None):
        """
        Initialize TCP source transfer
        
        Args:
            tcp_src: The underlying TCP source
            bytes_to_send: Number of bytes to send
            flow_stopped_callback: Optional callback when flow completes
        """
        self._tcp_src = tcp_src
        self._bytes_to_send = bytes_to_send
        self._flow_stopped = flow_stopped_callback
        self._is_active = False
        self._original_callback = None
        
    def start(self):
        """Start the transfer"""
        if not self._is_active:
            self._is_active = True
            # Set up completion callback
            if self._flow_stopped:
                self._original_callback = self._tcp_src._flow_stopped
                self._tcp_src._flow_stopped = self._flow_stopped
            # Configure TCP source with bytes to send
            self._tcp_src.set_flowsize(self._bytes_to_send)
            self._tcp_src.startflow()
            
    def reset(self, bytes: int, restart: bool = True):
        """
        Reset the transfer with new byte count
        
        Args:
            bytes: New number of bytes to send
            restart: Whether to immediately restart the flow
        """
        self._bytes_to_send = bytes
        self._is_active = False
        
        # Reset the TCP source
        self._tcp_src.reset()
        
        if restart:
            self.start()
            
    def is_active(self) -> bool:
        """Check if transfer is active"""
        return self._is_active
        
    def mark_finished(self):
        """Mark transfer as finished"""
        self._is_active = False
        # Restore original callback
        if self._original_callback is not None:
            self._tcp_src._flow_stopped = self._original_callback
            self._original_callback = None


class Incast(EventSource):
    """
    Incast traffic pattern coordinator
    
    Manages multiple TCP flows that send to a single destination,
    creating the incast pattern common in data centers (e.g., 
    distributed file systems, MapReduce).
    
    Key features:
    - Coordinates multiple simultaneous flows
    - Restarts all flows when they complete (barrier synchronization)
    - Tracks completion of individual flows
    """
    
    def __init__(self, bytes: int, eventlist: EventList):
        """
        Initialize incast coordinator
        
        Args:
            bytes: Number of bytes each flow should send
            eventlist: Event list
        """
        super().__init__(eventlist, "Incast")
        self._bytes = bytes
        self._flows: List[TcpSrcTransfer] = []
        self._finished = 0
        self._active = False
        
    def add_flow(self, src: TcpSrcTransfer):
        """
        Add a flow to the incast
        
        Args:
            src: TCP source transfer to add
        """
        self._flows.append(src)
        # Set ourselves as the completion callback
        src._flow_stopped = self
        
    def start_incast(self):
        """Start all flows in the incast"""
        if not self._flows:
            return
            
        self._active = True
        self._finished = 0
        
        # Start all flows
        for flow in self._flows:
            flow.reset(self._bytes, restart=True)
            
        print(f"Incast started with {len(self._flows)} flows, "
              f"each sending {self._bytes} bytes")
              
    def doNextEvent(self):
        """
        Handle flow completion event
        
        Called when a flow finishes. When all flows are done,
        restart them all (barrier synchronization).
        """
        if not self._flows or not self._active:
            return
            
        self._finished += 1
        
        if self._finished >= len(self._flows):
            # All flows finished - restart them
            print(f"Transfer finished at {self.eventlist.now() / 1e9:.3f} ms")
            
            # Reset all flows and restart
            self._finished = 0
            for flow in self._flows:
                flow.reset(self._bytes, restart=True)
                
    def stop_incast(self):
        """Stop the incast pattern"""
        self._active = False
        
    def set_bytes(self, bytes: int):
        """
        Update the number of bytes to send
        
        Args:
            bytes: New byte count
        """
        self._bytes = bytes
        
    def get_flow_count(self) -> int:
        """Get number of flows in the incast"""
        return len(self._flows)
        
    def get_finished_count(self) -> int:
        """Get number of flows that have finished in current round"""
        return self._finished
        
    def is_active(self) -> bool:
        """Check if incast is active"""
        return self._active


class IncastPattern:
    """
    Helper class to set up incast traffic patterns
    
    Provides convenience methods for creating common incast scenarios.
    """
    
    @staticmethod
    def create_n_to_1(n: int, bytes: int, eventlist: EventList,
                     sources: List['TcpSrc'], 
                     create_transfer: callable) -> Incast:
        """
        Create N-to-1 incast pattern
        
        Args:
            n: Number of senders
            bytes: Bytes each sender transmits
            eventlist: Event list
            sources: List of TCP sources (must have at least n elements)
            create_transfer: Function to create TcpSrcTransfer from TcpSrc
            
        Returns:
            Configured Incast object
        """
        if len(sources) < n:
            raise ValueError(f"Need at least {n} sources, got {len(sources)}")
            
        incast = Incast(bytes, eventlist)
        
        # Add first n sources to the incast
        for i in range(n):
            transfer = create_transfer(sources[i], bytes)
            incast.add_flow(transfer)
            
        return incast
        
    @staticmethod 
    def create_partition_aggregate(partitions: int, 
                                 nodes_per_partition: int,
                                 bytes: int,
                                 eventlist: EventList,
                                 sources: List['TcpSrc'],
                                 create_transfer: callable) -> List[Incast]:
        """
        Create partition/aggregate pattern (multiple incasts)
        
        Common in distributed systems where data is partitioned and
        each partition is aggregated separately.
        
        Args:
            partitions: Number of partitions
            nodes_per_partition: Nodes in each partition  
            bytes: Bytes each node sends
            eventlist: Event list
            sources: List of TCP sources
            create_transfer: Function to create TcpSrcTransfer
            
        Returns:
            List of Incast objects, one per partition
        """
        incasts = []
        
        total_nodes = partitions * nodes_per_partition
        if len(sources) < total_nodes:
            raise ValueError(f"Need at least {total_nodes} sources")
            
        for p in range(partitions):
            incast = Incast(bytes, eventlist)
            
            # Add nodes from this partition
            start_idx = p * nodes_per_partition
            for i in range(nodes_per_partition):
                transfer = create_transfer(sources[start_idx + i], bytes)
                incast.add_flow(transfer)
                
            incasts.append(incast)
            
        return incasts