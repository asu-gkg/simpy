"""
Basic switch implementation for HTSimPy
"""

from typing import Optional, Dict, List
from .network import PacketSink, Packet
from .eventlist import EventList


class Switch(PacketSink):
    """
    Basic switch implementation
    
    A switch forwards packets based on routing decisions.
    This is a simplified implementation - more sophisticated
    switches can be built by extending this class.
    """
    
    def __init__(self, name: str, eventlist: EventList):
        """
        Initialize switch
        
        Args:
            name: Switch name/identifier
            eventlist: Event list
        """
        super().__init__()
        self._name = name
        self._eventlist = eventlist
        self._forwarding_table: Dict[int, PacketSink] = {}
        self._port_count = 0
        self._packets_forwarded = 0
        
    def receivePacket(self, pkt: Packet):
        """
        Receive and forward a packet
        
        In a real switch, this would:
        1. Look up destination in forwarding table
        2. Apply any switching policies
        3. Forward to appropriate output port
        
        This simplified version just counts packets.
        
        Args:
            pkt: The packet to process
        """
        self._packets_forwarded += 1
        # In a real implementation, would forward based on destination
        
    def add_port(self) -> int:
        """
        Add a port to the switch
        
        Returns:
            Port number
        """
        port = self._port_count
        self._port_count += 1
        return port
        
    def set_forwarding_entry(self, dest: int, next_hop: PacketSink):
        """
        Set a forwarding table entry
        
        Args:
            dest: Destination ID
            next_hop: Next hop sink
        """
        self._forwarding_table[dest] = next_hop
        
    def get_name(self) -> str:
        """Get switch name"""
        return self._name
        
    def get_packets_forwarded(self) -> int:
        """Get number of packets forwarded"""
        return self._packets_forwarded
        
    def __str__(self) -> str:
        return f"Switch({self._name})"