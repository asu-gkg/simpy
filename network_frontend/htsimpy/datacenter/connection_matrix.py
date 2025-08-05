"""
Connection matrix for managing traffic patterns in data center networks

Corresponds to connection_matrix.h/cpp in HTSim C++ implementation
"""

import random
import pickle
from typing import List, Dict, Optional, Tuple, Set, IO
from dataclasses import dataclass
from enum import Enum
from ..core.eventlist import EventList
from .topology import Topology
# from ..core.trigger import Trigger  # TODO: implement trigger support


# Constants
NO_START = 0xffffffffffffffff  # Indicates connection not started yet


class TriggerType(Enum):
    """Types of triggers for connection scheduling"""
    UNSPECIFIED = 0
    SINGLE_SHOT = 1
    MULTI_SHOT = 2
    BARRIER = 3


@dataclass
class Connection:
    """Represents a connection between two hosts"""
    src: int
    dst: int
    size: int
    flowid: int
    send_done_trigger: Optional[int] = None
    recv_done_trigger: Optional[int] = None
    trigger: Optional[int] = None
    start: int = NO_START
    priority: int = 0


@dataclass
class TriggerInfo:
    """Information about a trigger"""
    id: int
    type: TriggerType
    count: int = 0  # Used for barriers
    flows: List[int] = None  # Flows to be triggered
    trigger: Optional[object] = None  # The actual trigger object (TODO: implement Trigger class)
    
    def __post_init__(self):
        if self.flows is None:
            self.flows = []


@dataclass
class Failure:
    """Describes a link failure"""
    switch_type: str  # e.g., "TOR", "AGG", "CORE"
    switch_id: int
    link_id: int


class ConnectionMatrix:
    """
    Manages connection patterns for datacenter simulations
    
    Supports various traffic patterns including:
    - Permutation (one-to-one)
    - Random connections
    - Incast/Outcast patterns
    - Hotspot traffic
    - Custom patterns from files
    """
    
    def __init__(self, n_hosts: int):
        """
        Initialize connection matrix
        
        Args:
            n_hosts: Number of hosts in the datacenter
        """
        self.N = n_hosts
        self.connections: Dict[int, List[int]] = {}
        self.conns: List[Connection] = []
        self.triggers: Dict[int, TriggerInfo] = {}
        self.failures: List[Failure] = []
        self._next_flowid = 0
        
    def add_connection(self, src: int, dest: int, size: int = 0) -> Connection:
        """
        Add a single connection
        
        Args:
            src: Source host ID
            dest: Destination host ID
            size: Flow size in bytes (0 for infinite)
            
        Returns:
            The created connection
        """
        if src not in self.connections:
            self.connections[src] = []
        self.connections[src].append(dest)
        
        conn = Connection(
            src=src,
            dst=dest,
            size=size,
            flowid=self._next_flowid
        )
        self._next_flowid += 1
        self.conns.append(conn)
        return conn
        
    def set_permutation(self, n_conns: Optional[int] = None):
        """
        Set up a permutation traffic pattern
        
        Each host sends to exactly one other host.
        
        Args:
            n_conns: Number of connections (default: all hosts)
        """
        if n_conns is None:
            n_conns = self.N
            
        # Create a random permutation
        destinations = list(range(n_conns))
        random.shuffle(destinations)
        
        # Ensure no self-connections
        for i in range(n_conns):
            if destinations[i] == i:
                # Swap with next position
                j = (i + 1) % n_conns
                destinations[i], destinations[j] = destinations[j], destinations[i]
                
        # Add connections
        for src, dst in enumerate(destinations):
            if src < n_conns:
                self.add_connection(src, dst)
                
    def set_permutation_rack(self, n_conns: int, rack_size: int):
        """
        Set up permutation within rack constraints
        
        Args:
            n_conns: Number of connections
            rack_size: Size of each rack
        """
        # Implement rack-aware permutation
        for rack_id in range(n_conns // rack_size):
            rack_start = rack_id * rack_size
            rack_hosts = list(range(rack_start, min(rack_start + rack_size, n_conns)))
            
            if len(rack_hosts) > 1:
                destinations = rack_hosts.copy()
                random.shuffle(destinations)
                
                # Ensure no self-connections within rack
                for i, src in enumerate(rack_hosts):
                    if destinations[i] == src:
                        j = (i + 1) % len(rack_hosts)
                        destinations[i], destinations[j] = destinations[j], destinations[i]
                    
                for i, src in enumerate(rack_hosts):
                    self.add_connection(src, destinations[i])
                    
    def set_random(self, n_conns: int):
        """
        Set up random connections
        
        Args:
            n_conns: Number of random connections to create
        """
        for _ in range(n_conns):
            src = random.randint(0, self.N - 1)
            dst = random.randint(0, self.N - 1)
            
            # Avoid self-connections
            while dst == src:
                dst = random.randint(0, self.N - 1)
                
            self.add_connection(src, dst)
            
    def set_stride(self, stride: int):
        """
        Set up stride pattern
        
        Host i connects to host (i + stride) % N
        
        Args:
            stride: The stride value
        """
        for i in range(self.N):
            dst = (i + stride) % self.N
            if dst != i:
                self.add_connection(i, dst)
                
    def set_incast(self, hosts_per_incast: int, center: int):
        """
        Set up incast pattern
        
        Multiple hosts send to a single destination
        
        Args:
            hosts_per_incast: Number of senders
            center: Destination host ID
        """
        senders = list(range(self.N))
        senders.remove(center)  # Remove the center from potential senders
        
        # Select random senders
        selected_senders = random.sample(senders, min(hosts_per_incast, len(senders)))
        
        for src in selected_senders:
            self.add_connection(src, center)
            
    def set_outcast(self, src: int, hosts_per_outcast: int, start_dest: int = 0):
        """
        Set up outcast pattern
        
        Single host sends to multiple destinations
        
        Args:
            src: Source host ID
            hosts_per_outcast: Number of destinations
            start_dest: Starting destination ID
        """
        destinations = []
        for i in range(hosts_per_outcast):
            dst = (start_dest + i) % self.N
            if dst != src:
                destinations.append(dst)
                
        for dst in destinations:
            self.add_connection(src, dst)
            
    def set_many_to_many(self, n_hosts: int):
        """
        Set up many-to-many pattern
        
        First n_hosts all communicate with each other
        
        Args:
            n_hosts: Number of hosts in the all-to-all pattern
        """
        for src in range(n_hosts):
            for dst in range(n_hosts):
                if src != dst:
                    self.add_connection(src, dst)
                    
    def set_hotspot(self, hosts_per_spot: int, n_hotspots: int):
        """
        Set up hotspot pattern
        
        Creates hotspots where groups of hosts communicate heavily
        
        Args:
            hosts_per_spot: Hosts per hotspot
            n_hotspots: Number of hotspots
        """
        for spot in range(n_hotspots):
            start = spot * hosts_per_spot
            end = min(start + hosts_per_spot, self.N)
            
            # All-to-all within hotspot
            for src in range(start, end):
                for dst in range(start, end):
                    if src != dst:
                        self.add_connection(src, dst)
                        
    def set_staggered_random(self, topology: Topology, n_conns: int, local_prob: float):
        """
        Set up staggered random pattern with locality
        
        Args:
            topology: The network topology
            n_conns: Number of connections
            local_prob: Probability of local (same rack) traffic
        """
        # This would need topology-specific implementation
        # For now, just do random with some locality bias
        for _ in range(n_conns):
            src = random.randint(0, self.N - 1)
            
            if random.random() < local_prob:
                # Local traffic - pick destination in same "rack"
                # Assuming simple rack structure
                rack_size = 40  # Common datacenter rack size
                rack_id = src // rack_size
                rack_start = rack_id * rack_size
                rack_end = min(rack_start + rack_size, self.N)
                
                dst = random.randint(rack_start, rack_end - 1)
                while dst == src:
                    dst = random.randint(rack_start, rack_end - 1)
            else:
                # Remote traffic
                dst = random.randint(0, self.N - 1)
                while dst == src:
                    dst = random.randint(0, self.N - 1)
                    
            self.add_connection(src, dst)
            
    def save(self, filename: str) -> bool:
        """
        Save connection matrix to file
        
        Args:
            filename: Output filename
            
        Returns:
            True if successful
        """
        try:
            with open(filename, 'wb') as f:
                data = {
                    'N': self.N,
                    'connections': self.connections,
                    'conns': self.conns,
                    'triggers': self.triggers,
                    'failures': self.failures
                }
                pickle.dump(data, f)
            return True
        except Exception as e:
            print(f"Error saving connection matrix: {e}")
            return False
            
    def load(self, filename: str) -> bool:
        """
        Load connection matrix from file
        
        Args:
            filename: Input filename
            
        Returns:
            True if successful
        """
        try:
            with open(filename, 'rb') as f:
                data = pickle.load(f)
                self.N = data['N']
                self.connections = data['connections']
                self.conns = data['conns']
                self.triggers = data.get('triggers', {})
                self.failures = data.get('failures', [])
                
                # Update next flow ID
                if self.conns:
                    self._next_flowid = max(c.flowid for c in self.conns) + 1
                    
            return True
        except Exception as e:
            print(f"Error loading connection matrix: {e}")
            return False
            
    def get_all_connections(self) -> List[Connection]:
        """
        Get all connections
        
        Returns:
            List of all connections
        """
        return self.conns.copy()
        
    def get_trigger(self, trigger_id: int, eventlist: EventList) -> Optional[object]:
        """
        Get or create a trigger
        
        Args:
            trigger_id: Trigger ID
            eventlist: Event list for trigger creation
            
        Returns:
            The trigger object or None
        """
        if trigger_id not in self.triggers:
            return None
            
        trigger_info = self.triggers[trigger_id]
        
        if trigger_info.trigger is None:
            # TODO: Create the actual trigger when Trigger class is implemented
            # trigger_info.trigger = Trigger(eventlist, trigger_info.count)
            pass
            
        return trigger_info.trigger
        
    def bind_triggers(self, conn: Connection, eventlist: EventList):
        """
        Bind triggers to a connection
        
        Args:
            conn: The connection
            eventlist: Event list for trigger creation
        """
        # This would be implemented based on the specific trigger requirements
        pass
        
    def add_failure(self, switch_type: str, switch_id: int, link_id: int):
        """
        Add a link failure
        
        Args:
            switch_type: Type of switch (TOR, AGG, CORE)
            switch_id: Switch ID
            link_id: Link ID on the switch
        """
        self.failures.append(Failure(
            switch_type=switch_type,
            switch_id=switch_id,
            link_id=link_id
        ))