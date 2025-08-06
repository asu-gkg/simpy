"""Route table implementation for HTSimPy."""

from typing import Dict, List, Optional
from enum import IntEnum
from ..core import Route


class PacketDirection(IntEnum):
    """Packet direction."""
    UPWARD = 0
    DOWNWARD = 1
    

class FibEntry:
    """FIB (Forwarding Information Base) entry.
    
    Matches C++ FibEntry class.
    """
    
    def __init__(self, outport: Route, cost: int, direction: PacketDirection):
        self._out = outport
        self._cost = cost
        self._direction = direction
        
    def get_egress_port(self) -> Route:
        """Get egress port route."""
        return self._out
        
    def get_cost(self) -> int:
        """Get cost."""
        return self._cost
        
    def get_direction(self) -> PacketDirection:
        """Get packet direction."""
        return self._direction


class HostFibEntry:
    """Host-specific FIB entry.
    
    Matches C++ HostFibEntry class.
    """
    
    def __init__(self, outport: Route, flowid: int):
        self._out = outport
        self._flowid = flowid
        
    def get_egress_port(self) -> Route:
        """Get egress port route."""
        return self._out
        
    def get_flow_id(self) -> int:
        """Get flow ID."""
        return self._flowid


class RouteTable:
    """Route table for switch FIB.
    
    Matches C++ RouteTable class.
    """
    
    def __init__(self):
        # Destination -> List of FIB entries (for multipath)
        self._fib: Dict[int, List[FibEntry]] = {}
        # Destination -> Flow ID -> Host FIB entry
        self._hostfib: Dict[int, Dict[int, HostFibEntry]] = {}
        
    def add_route(self, destination: int, port: Route, cost: int, direction: PacketDirection) -> None:
        """Add route to FIB."""
        entry = FibEntry(port, cost, direction)
        
        if destination not in self._fib:
            self._fib[destination] = []
        self._fib[destination].append(entry)
        
    def add_host_route(self, destination: int, port: Route, flowid: int) -> None:
        """Add host-specific route."""
        entry = HostFibEntry(port, flowid)
        
        if destination not in self._hostfib:
            self._hostfib[destination] = {}
        self._hostfib[destination][flowid] = entry
        
    def set_routes(self, destination: int, routes: List[FibEntry]) -> None:
        """Set all routes for a destination."""
        self._fib[destination] = routes
        
    def get_routes(self, destination: int) -> Optional[List[FibEntry]]:
        """Get all routes to destination."""
        return self._fib.get(destination)
        
    def get_host_route(self, destination: int, flowid: int) -> Optional[HostFibEntry]:
        """Get host-specific route."""
        if destination in self._hostfib:
            return self._hostfib[destination].get(flowid)
        return None