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
from ..core.trigger import (
    Trigger, SingleShotTrigger, MultiShotTrigger, 
    BarrierTrigger, TriggerTarget, TRIGGER_START
)


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
    trigger: Optional[Trigger] = None  # The actual trigger object
    
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
            
        Raises:
            ValueError: If n_hosts is not positive
        """
        if n_hosts <= 0:
            raise ValueError(f"Number of hosts must be positive, got {n_hosts}")
            
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
            
        Raises:
            ValueError: If src or dest is out of range or size is negative
        """
        if not 0 <= src < self.N:
            raise ValueError(f"Source host {src} out of range [0, {self.N})")
        if not 0 <= dest < self.N:
            raise ValueError(f"Destination host {dest} out of range [0, {self.N})")
        if size < 0:
            raise ValueError(f"Flow size cannot be negative, got {size}")
            
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
        
    def set_permutation(self, n_conns: Optional[int] = None) -> None:
        """
        Set up a permutation traffic pattern
        
        Each host sends to exactly one other host.
        
        Args:
            n_conns: Number of connections (default: all hosts)
            
        Raises:
            ValueError: If n_conns is invalid
        """
        if n_conns is None:
            n_conns = self.N
            
        if n_conns <= 0 or n_conns > self.N:
            raise ValueError(f"n_conns must be in range (0, {self.N}], got {n_conns}")
            
        # Create a random permutation
        destinations = list(range(n_conns))
        random.shuffle(destinations)
        
        # Ensure no self-connections
        for i in range(n_conns):
            if destinations[i] == i:
                # Swap with next position
                j = (i + 1) % n_conns
                destinations[i], destinations[j] = destinations[j], destinations[i]
                
        # Batch add connections for performance
        connections = [(src, destinations[src], 0) for src in range(n_conns)]
        self.add_connections_batch(connections)
                
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
        
    def add_connections_batch(self, connections: List[Tuple[int, int, int]]) -> List[Connection]:
        """
        Add multiple connections in batch for performance.
        
        Args:
            connections: List of (src, dest, size) tuples
            
        Returns:
            List of created connections
        """
        created_conns = []
        
        # Pre-validate all connections
        for src, dest, size in connections:
            if not 0 <= src < self.N:
                raise ValueError(f"Source host {src} out of range [0, {self.N})")
            if not 0 <= dest < self.N:
                raise ValueError(f"Destination host {dest} out of range [0, {self.N})")
            if size < 0:
                raise ValueError(f"Flow size cannot be negative, got {size}")
                
        # Batch create connections
        for src, dest, size in connections:
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
            created_conns.append(conn)
            
        return created_conns
        
    def add_trigger(self, trigger_id: int, trigger_type: TriggerType, 
                    count: int = 0) -> TriggerInfo:
        """
        Add a trigger definition.
        
        Args:
            trigger_id: Unique trigger ID
            trigger_type: Type of trigger
            count: Count for barrier triggers
            
        Returns:
            The created TriggerInfo
        """
        trigger_info = TriggerInfo(
            id=trigger_id,
            type=trigger_type,
            count=count
        )
        self.triggers[trigger_id] = trigger_info
        return trigger_info
        
    def add_flow_to_trigger(self, trigger_id: int, flow_id: int):
        """
        Add a flow to be triggered.
        
        Args:
            trigger_id: Trigger ID
            flow_id: Flow ID to trigger
        """
        if trigger_id in self.triggers:
            self.triggers[trigger_id].flows.append(flow_id)
            
    def get_trigger(self, trigger_id: int, eventlist: EventList) -> Optional[Trigger]:
        """
        Get or create a trigger
        
        Args:
            trigger_id: Trigger ID
            eventlist: Event list for trigger creation
            
        Returns:
            The trigger object or None
        """
        if trigger_id not in self.triggers:
            # Log warning for missing trigger
            import sys
            print(f"Warning: Trigger ID {trigger_id} not found in connection matrix. "
                  f"Available triggers: {list(self.triggers.keys())}", file=sys.stderr)
            return None
            
        trigger_info = self.triggers[trigger_id]
        
        if trigger_info.trigger is None:
            # Create the actual trigger based on type
            if trigger_info.type == TriggerType.SINGLE_SHOT:
                trigger_info.trigger = SingleShotTrigger(eventlist, trigger_id)
            elif trigger_info.type == TriggerType.MULTI_SHOT:
                trigger_info.trigger = MultiShotTrigger(eventlist, trigger_id)
            elif trigger_info.type == TriggerType.BARRIER:
                trigger_info.trigger = BarrierTrigger(
                    eventlist, trigger_id, trigger_info.count
                )
            else:
                print(f"Unknown trigger type: {trigger_info.type}")
                return None
            
        return trigger_info.trigger
        
    def bind_triggers(self, conn: Connection, eventlist: EventList, 
                      flow_starter=None) -> Optional[TriggerTarget]:
        """
        Bind triggers to a connection and create trigger targets.
        
        Args:
            conn: The connection
            eventlist: Event list for trigger creation
            flow_starter: Function to start the flow (for trigger activation)
            
        Returns:
            TriggerTarget if connection should be triggered, None otherwise
        """
        trigger_target = None
        
        # Check if this connection needs to be triggered
        if conn.trigger is not None:
            trigger = self.get_trigger(conn.trigger, eventlist)
            if trigger and flow_starter:
                # Create a trigger target for this flow
                from ..core.trigger import FlowTriggerTarget
                trigger_target = FlowTriggerTarget(flow_starter)
                trigger.add_target(trigger_target)
                
        # Set up send completion trigger
        if conn.send_done_trigger is not None:
            trigger = self.get_trigger(conn.send_done_trigger, eventlist)
            # The flow will need to activate this trigger when done
            
        # Set up receive completion trigger  
        if conn.recv_done_trigger is not None:
            trigger = self.get_trigger(conn.recv_done_trigger, eventlist)
            # The sink will need to activate this trigger when done
            
        return trigger_target
        
    def add_triggered_connection(self, src: int, dest: int, size: int,
                                trigger_id: int) -> Connection:
        """
        Add a connection that starts via trigger.
        
        Args:
            src: Source host ID
            dest: Destination host ID
            size: Flow size in bytes
            trigger_id: ID of trigger that starts this flow
            
        Returns:
            The created connection
        """
        conn = self.add_connection(src, dest, size)
        conn.trigger = trigger_id
        conn.start = TRIGGER_START
        return conn
        
    def add_connection_with_completion_trigger(self, src: int, dest: int, 
                                             size: int, 
                                             send_done_trigger: Optional[int] = None,
                                             recv_done_trigger: Optional[int] = None) -> Connection:
        """
        Add a connection that triggers other flows on completion.
        
        Args:
            src: Source host ID
            dest: Destination host ID
            size: Flow size in bytes
            send_done_trigger: Trigger ID to activate on send completion
            recv_done_trigger: Trigger ID to activate on receive completion
            
        Returns:
            The created connection
        """
        conn = self.add_connection(src, dest, size)
        conn.send_done_trigger = send_done_trigger
        conn.recv_done_trigger = recv_done_trigger
        return conn
        
    def create_sequential_flows(self, flows: List[Tuple[int, int, int]]) -> List[Connection]:
        """
        Create a sequence of flows where each triggers the next.
        
        Args:
            flows: List of (src, dest, size) tuples
            
        Returns:
            List of created connections
        """
        conns = []
        
        for i, (src, dest, size) in enumerate(flows):
            if i == 0:
                # First flow starts immediately
                conn = self.add_connection(src, dest, size)
            else:
                # Create trigger for this flow
                trigger_id = 1000 + i  # Arbitrary trigger ID
                self.add_trigger(trigger_id, TriggerType.SINGLE_SHOT)
                
                # Previous flow triggers this one
                conns[-1].send_done_trigger = trigger_id
                
                # This flow starts via trigger
                conn = self.add_triggered_connection(src, dest, size, trigger_id)
                
            conns.append(conn)
            
        return conns
        
    def create_barrier_synchronized_flows(self, flows: List[Tuple[int, int, int]],
                                        barrier_trigger_id: int) -> List[Connection]:
        """
        Create flows that all start after a barrier is reached.
        
        Args:
            flows: List of (src, dest, size) tuples
            barrier_trigger_id: ID for the barrier trigger
            
        Returns:
            List of created connections
        """
        # Create barrier trigger that needs all flows to complete
        self.add_trigger(barrier_trigger_id, TriggerType.BARRIER, count=len(flows))
        
        conns = []
        for i, (src, dest, size) in enumerate(flows):
            # Each flow starts via the barrier
            conn = self.add_triggered_connection(src, dest, size, barrier_trigger_id)
            conns.append(conn)
            
        return conns
        
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