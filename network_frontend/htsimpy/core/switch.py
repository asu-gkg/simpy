"""
Basic switch implementation for HTSimPy
"""

from typing import Optional, Dict, List, TYPE_CHECKING
from .network import PacketSink, Packet
from .eventlist import EventList
from .logger.core import Logged

if TYPE_CHECKING:
    from .logger.switch import SwitchLogger


class FibEntry:
    """
    Forwarding Information Base (FIB) entry.
    
    Represents a routing entry in a switch's forwarding table.
    """
    
    def __init__(self):
        """Initialize FIB entry."""
        self.address: int = 0  # Destination address
        self.flowid: int = 0  # Flow identifier
        self.egress: Optional[PacketSink] = None  # Egress port/queue


class Switch(PacketSink, Logged):
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
        PacketSink.__init__(self)
        Logged.__init__(self, name)
        self._name = name
        self._eventlist = eventlist
        self._forwarding_table: Dict[int, PacketSink] = {}
        self._port_count = 0
        self._packets_forwarded = 0
        self._packets_dropped = 0
        self._switch_logger: Optional['SwitchLogger'] = None
        
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
        # Log packet arrival
        if self._switch_logger:
            from .logger.switch import SwitchLogger
            self._switch_logger.log_switch(self, SwitchLogger.SwitchEvent.PKT_ARRIVE, pkt)
            
        self._packets_forwarded += 1
        
        # Log packet forward
        if self._switch_logger:
            from .logger.switch import SwitchLogger
            self._switch_logger.log_switch(self, SwitchLogger.SwitchEvent.PKT_FORWARD, pkt)
            
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
    
    def nodename(self) -> str:
        """Get node name - required by PacketSink interface"""
        return self._name
        
    def get_packets_forwarded(self) -> int:
        """Get number of packets forwarded"""
        return self._packets_forwarded
        
    def add_logger(self, logfile, sample_period: int):
        """
        Add a logger to this switch
        
        Args:
            logfile: Logfile instance
            sample_period: Sampling period in picoseconds
        """
        from .logger.switch import SwitchLoggerFactory
        
        # Create a sampling logger for the switch
        factory = SwitchLoggerFactory(
            logfile,
            SwitchLoggerFactory.SwitchLoggerType.LOGGER_SAMPLING,
            self._eventlist
        )
        factory.set_sample_period(sample_period)
        self._switch_logger = factory.create_switch_logger(self)
        
    def drop_packet(self, pkt: Packet):
        """
        Drop a packet
        
        Args:
            pkt: Packet to drop
        """
        self._packets_dropped += 1
        
        # Log packet drop
        if self._switch_logger:
            from .logger.switch import SwitchLogger
            self._switch_logger.log_switch(self, SwitchLogger.SwitchEvent.PKT_DROP, pkt)
            
        # Free the packet
        if hasattr(pkt, 'free'):
            pkt.free()
        
    def __str__(self) -> str:
        return f"Switch({self._name})"