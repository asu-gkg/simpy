"""
Host class for data center networks

Extracted from generic_topology.h in HTSim C++ implementation
"""

from typing import Optional
from ..core.network import PacketSink, Packet
from ..queues.base_queue import BaseQueue


class Host(PacketSink):
    """
    Represents a host (server) in the data center network
    
    A host is an endpoint that can send and receive packets.
    It has an associated queue for outgoing traffic.
    """
    
    def __init__(self, name: str):
        """
        Initialize a host
        
        Args:
            name: Name/identifier for the host
        """
        super().__init__()
        self._nodename = name
        self._queue: Optional[BaseQueue] = None
        self._host_id: Optional[int] = None
        
    def set_queue(self, queue: BaseQueue):
        """
        Set the output queue for this host
        
        Args:
            queue: Queue for outgoing packets
        """
        self._queue = queue
        
    def get_queue(self) -> Optional[BaseQueue]:
        """
        Get the output queue
        
        Returns:
            The output queue or None
        """
        return self._queue
        
    def set_host_id(self, host_id: int):
        """
        Set the host ID
        
        Args:
            host_id: Unique identifier for this host
        """
        self._host_id = host_id
        
    def get_host_id(self) -> Optional[int]:
        """
        Get the host ID
        
        Returns:
            The host ID or None
        """
        return self._host_id
        
    def receivePacket(self, pkt: Packet):
        """
        Receive a packet
        
        Note: Hosts shouldn't normally receive packets directly -
        the route should make the switching decision to the
        receiving protocol. This may be revisited later.
        
        Args:
            pkt: The packet to receive
            
        Raises:
            NotImplementedError: Always, as hosts shouldn't receive packets directly
        """
        raise NotImplementedError(
            "Hosts shouldn't receive packets directly - "
            "route to the receiving protocol instead"
        )
        
    def nodename(self) -> str:
        """
        Get the node name
        
        Returns:
            The name of this host
        """
        return self._nodename
    
    def __str__(self) -> str:
        """String representation"""
        return f"Host({self._nodename})"
    
    def __repr__(self) -> str:
        """Detailed representation"""
        return f"Host(name={self._nodename}, id={self._host_id})"