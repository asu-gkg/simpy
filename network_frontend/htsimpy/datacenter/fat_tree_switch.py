"""Fat Tree Switch implementation for HTSimPy."""

from typing import Dict, List, Optional, Set, Tuple, Callable
from enum import IntEnum
from ..core import Packet, Route, EventList, Pipe
from ..queues.base_queue import BaseQueue
from ..core.switch import Switch
from ..packets.tcp_packet import TcpPacket
from .routetable import RouteTable, FibEntry, HostFibEntry, PacketDirection
import random


class SwitchType(IntEnum):
    """Fat tree switch types."""
    NONE = 0
    TOR = 1  # Top of Rack (edge/leaf)
    AGG = 2  # Aggregation
    CORE = 3


class RoutingStrategy(IntEnum):
    """Routing strategies for fat tree switches."""
    NIX = 0
    ECMP = 1
    ADAPTIVE_ROUTING = 2
    ECMP_ADAPTIVE = 3
    RR = 4  # Round-robin
    RR_ECMP = 5


class StickyChoices(IntEnum):
    """Sticky routing choices."""
    PER_PACKET = 0
    PER_FLOWLET = 1


class FlowletInfo:
    """Information about a flowlet for sticky routing."""
    
    def __init__(self, egress: int, last_time: int):
        self.egress = egress
        self.last = last_time


class FatTreeSwitch(Switch):
    """
    Fat Tree switch with various routing strategies.
    
    Supports ECMP, adaptive routing, round-robin, and flowlet switching.
    """
    
    # Class variables for global configuration
    _strategy: RoutingStrategy = RoutingStrategy.NIX
    _ar_fraction: int = 1  # Adaptive routing fraction
    _ar_sticky: int = StickyChoices.PER_PACKET
    _sticky_delta: int = 50000  # 50us flowlet timeout
    _ecn_threshold_fraction: float = 0.75
    _speculative_threshold_fraction: float = 0.25
    _port_flow_counts: Dict[BaseQueue, int] = {}
    
    # Function pointer for adaptive routing comparison (matches C++ fn)
    fn: Callable = None  # Will be set to one of the compare functions
    
    @classmethod
    def init_class_defaults(cls):
        """Initialize class defaults to match C++."""
        if cls.fn is None:
            cls.fn = cls.compare_queuesize
    
    def __init__(
        self,
        eventlist: EventList,
        name: str,
        switch_type: SwitchType,
        switch_id: int,
        switch_delay: int,
        fat_tree_topology: Optional['FatTreeTopology'] = None
    ):
        """
        Initialize Fat Tree switch.
        
        Args:
            eventlist: Event list instance
            name: Switch name
            switch_type: Type of switch (TOR, AGG, CORE)
            switch_id: Switch ID
            switch_delay: Processing delay in picoseconds
            fat_tree_topology: Reference to fat tree topology
        """
        super().__init__(name, eventlist)  # Switch expects (name, eventlist)
        self._type = switch_type
        self._id = switch_id
        self._switch_delay = switch_delay
        self._ft = fat_tree_topology
        self._name = name  # Explicitly set name in case parent doesn't
        
        # Initialize class defaults if not already done
        self.__class__.init_class_defaults()
        
        # Initialize routing structures
        self._uproutes: Optional[List[FibEntry]] = None
        self._flowlet_maps: Dict[int, FlowletInfo] = {}
        self._crt_route = 0  # Current round-robin route
        self._hash_salt = random.randint(0, 0xFFFFFFFF)
        self._last_choice = 0
        self._packets: Set[Packet] = set()
        self._fib = RouteTable()  # FIB for routing
        self._ports: List[BaseQueue] = []  # Switch ports
        
        # Create internal pipe for switch delay with callback
        from ..core.callback_pipe import CallbackPipe
        self._pipe = CallbackPipe(switch_delay, eventlist, self)
        if hasattr(self._pipe, 'set_name'):
            self._pipe.set_name(f"{name}_internal_pipe")
        
    def receive_packet(self, pkt: Packet) -> None:
        """Process incoming packet.
        
        Matches C++ FatTreeSwitch::receivePacket two-phase processing.
        """
        # Handle ETH_PAUSE packets specially
        if hasattr(pkt, 'type') and pkt.type() == 'ETH_PAUSE':
            # Find the egress queue that should process this
            for port in self._ports:
                if hasattr(port, 'get_remote_endpoint'):
                    remote = port.get_remote_endpoint()
                    if hasattr(remote, 'get_id') and remote.get_id() == pkt.sender_id():
                        port.receive_packet(pkt)
                        break
            return
            
        # Two-phase processing using _packets set
        if pkt not in self._packets:
            # Ingress pipeline processing
            self._packets.add(pkt)
            
            # Get next hop
            nh = self.get_next_hop(pkt, None)
            if nh:
                # Set next hop route
                pkt.set_route(nh)
                # Emulate switching latency
                self._pipe.receive_packet(pkt)
            else:
                # No route found
                self._packets.discard(pkt)
                pkt.free()
        else:
            # Egress queue processing
            self._packets.discard(pkt)
            # Forward packet on its route
            pkt.send_on()
            
    def get_next_hop(self, pkt: Packet, ingress_port: Optional[BaseQueue]) -> Optional[Route]:
        """
        Determine next hop for packet based on routing strategy.
        
        Matches C++ FatTreeSwitch::getNextHop logic.
        """
        # Get destination
        dest = None
        if hasattr(pkt, 'dst'):
            dest = pkt.dst()
        elif hasattr(pkt, 'get_dst'):
            dest = pkt.get_dst()
        else:
            return None
            
        # Look up available routes in FIB
        available_hops = None
        if hasattr(self, '_fib') and hasattr(self._fib, 'get_routes'):
            available_hops = self._fib.get_routes(dest)
        elif hasattr(self, '_fib') and isinstance(self._fib, dict) and dest in self._fib:
            # Support dictionary-style FIB
            available_hops = [self._fib[dest]]
        
        if not available_hops:
            return None
            
        ecmp_choice = 0
        
        if len(available_hops) > 1:
            # Multiple paths available - use routing strategy
            if self._strategy == RoutingStrategy.NIX:
                # Should not happen
                assert False, "NIX strategy with multiple paths"
                
            elif self._strategy == RoutingStrategy.ECMP:
                # Hash-based ECMP
                flow_id = pkt.flow_id() if hasattr(pkt, 'flow_id') else 0
                pathid = pkt.pathid() if hasattr(pkt, 'pathid') else 0
                ecmp_choice = self._freebsd_hash(flow_id, pathid, self._hash_salt) % len(available_hops)
                
            elif self._strategy == RoutingStrategy.ADAPTIVE_ROUTING:
                if self._ar_sticky == StickyChoices.PER_PACKET:
                    # Per-packet adaptive routing
                    ecmp_choice = self.adaptive_route(available_hops, self.fn)
                    
                elif self._ar_sticky == StickyChoices.PER_FLOWLET:
                    # Flowlet-based sticky routing
                    flow_id = pkt.flow_id() if hasattr(pkt, 'flow_id') else 0
                    now = self._eventlist.now()
                    
                    if flow_id in self._flowlet_maps:
                        # Existing flowlet
                        f = self._flowlet_maps[flow_id]
                        
                        # Check if we should reroute
                        if (now - f.last > self._sticky_delta and random.randint(0, 1) == 0):
                            # Time to potentially reroute
                            new_route = self.adaptive_route(available_hops, self.fn)
                            
                            # Check if new route is better
                            if self.fn(available_hops[f.egress], available_hops[new_route]) < 0:
                                f.egress = new_route
                                self._last_choice = now
                                
                        ecmp_choice = f.egress
                        f.last = now
                    else:
                        # New flowlet
                        ecmp_choice = self.adaptive_route(available_hops, self.fn)
                        self._last_choice = now
                        self._flowlet_maps[flow_id] = FlowletInfo(ecmp_choice, now)
                        
            elif self._strategy == RoutingStrategy.ECMP_ADAPTIVE:
                # ECMP with occasional adaptive
                flow_id = pkt.flow_id() if hasattr(pkt, 'flow_id') else 0
                pathid = pkt.pathid() if hasattr(pkt, 'pathid') else 0
                ecmp_choice = self._freebsd_hash(flow_id, pathid, self._hash_salt) % len(available_hops)
                
                # C++ uses: if (random()%100 < 50)
                if random.randint(0, 99) < 50:  # 50% probability
                    # Replace with adaptive choice
                    ecmp_choice = self.replace_worst_choice(available_hops, self.fn, ecmp_choice)
                    
            elif self._strategy == RoutingStrategy.RR:
                # Round-robin with permutation like C++
                if self._crt_route >= 5 * len(available_hops):
                    self._crt_route = 0
                    self.permute_paths(available_hops)
                ecmp_choice = self._crt_route % len(available_hops)
                self._crt_route += 1
                
            elif self._strategy == RoutingStrategy.RR_ECMP:
                # Round-robin for TOR switches, ECMP for others (matches C++)
                if self._type == SwitchType.TOR:
                    if self._crt_route >= 5 * len(available_hops):
                        self._crt_route = 0
                        self.permute_paths(available_hops)
                    ecmp_choice = self._crt_route % len(available_hops)
                    self._crt_route += 1
                else:
                    # Use ECMP for non-TOR switches
                    flow_id = pkt.flow_id() if hasattr(pkt, 'flow_id') else 0
                    pathid = pkt.pathid() if hasattr(pkt, 'pathid') else 0
                    ecmp_choice = self._freebsd_hash(flow_id, pathid, self._hash_salt) % len(available_hops)
        
        # Get the selected FIB entry and return its egress port
        # C++ code assumes FibEntry has getEgressPort() method
        return available_hops[ecmp_choice].get_egress_port()
        
    def _select_route(self, pkt: Packet, routes: List[FibEntry]) -> int:
        """Select route index based on routing strategy."""
        if not routes:
            return -1
            
        # Get flow hash for packet
        flow_hash = self._get_flow_hash(pkt)
        
        if self._strategy == RoutingStrategy.ECMP:
            # Simple ECMP - hash-based selection
            return flow_hash % len(routes)
            
        elif self._strategy == RoutingStrategy.RR:
            # Round-robin
            self._crt_route = (self._crt_route + 1) % len(routes)
            return self._crt_route
            
        elif self._strategy == RoutingStrategy.ADAPTIVE_ROUTING:
            # Adaptive routing - choose best path
            return self.adaptive_route(routes, self.compare_queuesize)
            
        elif self._strategy == RoutingStrategy.ECMP_ADAPTIVE:
            # ECMP with adaptive fallback
            if random.randint(1, self._ar_fraction) == 1:
                # Use adaptive routing
                return self.adaptive_route_p2c(routes, self.compare_pqb)
            else:
                # Use ECMP
                return flow_hash % len(routes)
                
        elif self._strategy == RoutingStrategy.RR_ECMP:
            # Round-robin with ECMP tie-breaking
            if random.randint(1, self._ar_fraction) == 1:
                self._crt_route = (self._crt_route + 1) % len(routes)
                return self._crt_route
            else:
                return flow_hash % len(routes)
                
        else:
            # Default to first route
            return 0
            
    def _get_flow_hash(self, pkt: Packet) -> int:
        """Get flow hash for packet."""
        if isinstance(pkt, TcpPacket):
            # Use 5-tuple hash for TCP
            src = pkt.src()
            dst = pkt.dst()
            sport = pkt.sport() if hasattr(pkt, 'sport') else 0
            dport = pkt.dport() if hasattr(pkt, 'dport') else 0
            return self._freebsd_hash(src, dst, (sport << 16) | dport)
        else:
            # Use source/destination for non-TCP
            src = 0
            dst = 0
            if hasattr(pkt, 'src'):
                src = pkt.src()
            if hasattr(pkt, 'dst'):
                dst = pkt.dst()
            return self._freebsd_hash(src, dst, self._hash_salt)
        
    def add_host_port(self, addr: int, flowid: int, transport) -> None:
        """Add host port to FIB.
        
        Matches C++ FatTreeSwitch::addHostPort.
        """
        route = Route()
        # Get queues and pipes from fat tree topology
        pod_switch = self._ft.HOST_POD_SWITCH(addr) if hasattr(self._ft, 'HOST_POD_SWITCH') else 0
        
        # Add queue, pipe, and transport to route
        if hasattr(self._ft, 'queues_nlp_ns') and pod_switch < len(self._ft.queues_nlp_ns) and addr < len(self._ft.queues_nlp_ns[pod_switch]):
            route.push_back(self._ft.queues_nlp_ns[pod_switch][addr][0])  # Use first bundle link [0]
        if hasattr(self._ft, 'pipes_nlp_ns') and pod_switch < len(self._ft.pipes_nlp_ns) and addr < len(self._ft.pipes_nlp_ns[pod_switch]):
            route.push_back(self._ft.pipes_nlp_ns[pod_switch][addr][0])   # Use first bundle link [0]
        route.push_back(transport)
        
        # Add to FIB
        self._fib.add_host_route(addr, route, flowid)
        
    def permute_paths(self, uproutes: List[FibEntry]) -> None:
        """Randomly permute paths for load balancing."""
        random.shuffle(uproutes)
        
    def add_upward_routes(self, uproutes: List[FibEntry]) -> None:
        """Add upward routes for this switch."""
        self._uproutes = uproutes
        # Permute for load balancing
        if uproutes:
            self.permute_paths(uproutes)
        
    @classmethod
    def set_strategy(cls, strategy: RoutingStrategy) -> None:
        """Set global routing strategy."""
        assert cls._strategy == RoutingStrategy.NIX, "Strategy already set"
        cls._strategy = strategy
        
    @classmethod
    def set_ar_fraction(cls, fraction: int) -> None:
        """Set adaptive routing fraction."""
        assert fraction >= 1
        cls._ar_fraction = fraction
        
    def adaptive_route(
        self,
        ecmp_set: List[FibEntry],
        compare_fn: Callable[[FibEntry, FibEntry], int]
    ) -> int:
        """
        Select route using adaptive routing.
        
        Args:
            ecmp_set: Set of equal-cost paths
            compare_fn: Comparison function for paths
            
        Returns:
            Index of selected path
        """
        if not ecmp_set:
            return 0
            
        # Simple implementation: choose path with best metric
        best_idx = 0
        for i in range(1, len(ecmp_set)):
            if compare_fn(ecmp_set[i], ecmp_set[best_idx]) < 0:
                best_idx = i
                
        return best_idx
        
    def adaptive_route_p2c(
        self,
        ecmp_set: List[FibEntry],
        compare_fn: Callable[[FibEntry, FibEntry], int]
    ) -> int:
        """
        Power of two choices adaptive routing.
        
        Randomly select two paths and choose the better one.
        """
        if len(ecmp_set) <= 1:
            return 0
            
        # Pick two random choices
        idx1 = random.randint(0, len(ecmp_set) - 1)
        idx2 = random.randint(0, len(ecmp_set) - 1)
        
        # Choose better one
        if compare_fn(ecmp_set[idx1], ecmp_set[idx2]) <= 0:
            return idx1
        return idx2
        
    def replace_worst_choice(self, ecmp_set: List[FibEntry], cmp: Callable, my_choice: int) -> int:
        """Replace worst choice with better alternative if my_choice is the worst.
        
        Matches C++ replace_worst_choice logic.
        """
        if len(ecmp_set) == 0:
            return 0
            
        # Find best and worst choices
        best_choice = 0
        worst_choice = 0
        min_entry = ecmp_set[0]
        max_entry = ecmp_set[0]
        best_choices = [0]  # Initialize with first choice like C++
        best_choices_count = 1
        
        for i in range(1, len(ecmp_set)):  # Start from 1 like C++
            c = cmp(min_entry, ecmp_set[i])  # C++ order: cmp(min, (*ecmp_set)[i])
            
            if c < 0:
                best_choice = i
                min_entry = ecmp_set[best_choice]
                best_choices_count = 0
                best_choices = [best_choice]
                best_choices_count = 1
            elif c == 0:
                assert best_choices_count < 256  # Match C++ assert
                best_choices.append(i)
                best_choices_count += 1
                    
            if cmp(max_entry, ecmp_set[i]) > 0:
                worst_choice = i
                max_entry = ecmp_set[worst_choice]
                
        # Check if my_choice is the worst
        r = cmp(ecmp_set[my_choice], ecmp_set[worst_choice])
        assert r >= 0
        
        if r == 0:
            # My choice is among the worst - pick from best choices
            assert best_choices_count >= 1
            return best_choices[random.randint(0, best_choices_count - 1)]
        else:
            return my_choice
        
    @staticmethod
    def compare_flow_count(left: FibEntry, right: FibEntry) -> int:
        """Compare paths by flow count.
        
        Returns:
            1 if left has fewer flows (better)
            -1 if right has fewer flows (better)
            0 if equal
        """
        # Get queues from egress routes
        l_route = left.get_egress_port() if hasattr(left, 'get_egress_port') else None
        r_route = right.get_egress_port() if hasattr(right, 'get_egress_port') else None
        
        if l_route and len(l_route) > 0:
            l_queue = l_route[0]  # First element is the queue
            if l_queue not in FatTreeSwitch._port_flow_counts:
                FatTreeSwitch._port_flow_counts[l_queue] = 0
            l_count = FatTreeSwitch._port_flow_counts[l_queue]
        else:
            l_count = 0
            
        if r_route and len(r_route) > 0:
            r_queue = r_route[0]
            if r_queue not in FatTreeSwitch._port_flow_counts:
                FatTreeSwitch._port_flow_counts[r_queue] = 0
            r_count = FatTreeSwitch._port_flow_counts[r_queue]
        else:
            r_count = 0
            
        # Match C++ logic: return 1 if left is better (fewer flows)
        if l_count < r_count:
            return 1
        elif l_count > r_count:
            return -1
        else:
            return 0
        
    @staticmethod
    def compare_pause(left: FibEntry, right: FibEntry) -> int:
        """Compare paths by pause status.
        
        Returns:
            1 if left is not paused and right is paused
            -1 if left is paused and right is not paused
            0 if both have same pause status
        """
        # Get queues from egress routes (match C++ logic)
        l_route = left.get_egress_port() if hasattr(left, 'get_egress_port') else None
        r_route = right.get_egress_port() if hasattr(right, 'get_egress_port') else None
        
        l_paused = False
        r_paused = False
        
        if l_route and len(l_route) > 0:
            l_queue = l_route[0]
            # Check for LosslessOutputQueue-style is_paused method
            if hasattr(l_queue, 'is_paused') and callable(l_queue.is_paused):
                l_paused = l_queue.is_paused()
                
        if r_route and len(r_route) > 0:
            r_queue = r_route[0]
            if hasattr(r_queue, 'is_paused') and callable(r_queue.is_paused):
                r_paused = r_queue.is_paused()
                
        # Match C++ logic exactly
        if not l_paused and r_paused:
            return 1
        elif l_paused and not r_paused:
            return -1
        else:
            return 0
        
    @staticmethod
    def compare_bandwidth(left: FibEntry, right: FibEntry) -> int:
        """Compare paths by bandwidth utilization.
        
        Returns:
            1 if left has lower utilization (better)
            -1 if right has lower utilization (better) 
            0 if equal
        """
        # Get queues from egress routes
        l_route = left.get_egress_port() if hasattr(left, 'get_egress_port') else None
        r_route = right.get_egress_port() if hasattr(right, 'get_egress_port') else None
        
        l_util = 0
        r_util = 0
        
        if l_route and len(l_route) > 0:
            l_queue = l_route[0]
            if hasattr(l_queue, 'quantized_utilization'):
                l_util = l_queue.quantized_utilization()
                
        if r_route and len(r_route) > 0:
            r_queue = r_route[0]
            if hasattr(r_queue, 'quantized_utilization'):
                r_util = r_queue.quantized_utilization()
                
        # Match C++ logic: lower utilization is better
        if l_util < r_util:
            return 1
        elif l_util > r_util:
            return -1
        else:
            return 0
        
    @staticmethod
    def compare_queuesize(left: FibEntry, right: FibEntry) -> int:
        """Compare paths by queue size.
        
        Returns:
            1 if left has smaller queue (better)
            -1 if right has smaller queue (better)
            0 if equal
        """
        # Get queues from egress routes
        l_route = left.get_egress_port() if hasattr(left, 'get_egress_port') else None
        r_route = right.get_egress_port() if hasattr(right, 'get_egress_port') else None
        
        l_size = 0
        r_size = 0
        
        if l_route and len(l_route) > 0:
            l_queue = l_route[0]
            if hasattr(l_queue, 'quantized_queuesize'):
                l_size = l_queue.quantized_queuesize()
            elif hasattr(l_queue, 'queuesize'):
                l_size = l_queue.queuesize()
                
        if r_route and len(r_route) > 0:
            r_queue = r_route[0]
            if hasattr(r_queue, 'quantized_queuesize'):
                r_size = r_queue.quantized_queuesize()
            elif hasattr(r_queue, 'queuesize'):
                r_size = r_queue.queuesize()
                
        # Match C++ logic: smaller queue is better
        if l_size < r_size:
            return 1
        elif l_size > r_size:
            return -1
        else:
            return 0
        
    @staticmethod
    def compare_pqb(left: FibEntry, right: FibEntry) -> int:
        """Compare by pause, queue, bandwidth."""
        # First compare pause
        p = FatTreeSwitch.compare_pause(left, right)
        if p != 0:
            return p
            
        # Then queue size
        p = FatTreeSwitch.compare_queuesize(left, right)
        if p != 0:
            return p
            
        # Finally bandwidth
        return FatTreeSwitch.compare_bandwidth(left, right)
        
    @staticmethod
    def compare_pq(left: FibEntry, right: FibEntry) -> int:
        """Compare by pause, then queue size."""
        p = FatTreeSwitch.compare_pause(left, right)
        if p != 0:
            return p
        return FatTreeSwitch.compare_queuesize(left, right)
        
    @staticmethod
    def compare_pb(left: FibEntry, right: FibEntry) -> int:
        """Compare by pause, then bandwidth."""
        p = FatTreeSwitch.compare_pause(left, right)
        if p != 0:
            return p
        return FatTreeSwitch.compare_bandwidth(left, right)
        
    @staticmethod
    def compare_qb(left: FibEntry, right: FibEntry) -> int:
        """Compare by queue size, then bandwidth."""
        p = FatTreeSwitch.compare_queuesize(left, right)
        if p != 0:
            return p
        return FatTreeSwitch.compare_bandwidth(left, right)
        
    def get_type(self) -> int:
        """Get switch type."""
        return self._type
        
    def nodename(self) -> str:
        """Get node name."""
        return self._name
        
    def _freebsd_hash(self, target1: int, target2: int = 0, target3: int = 0) -> int:
        """FreeBSD hash function for ECMP."""
        a = 0x9e3779b9
        b = 0x9e3779b9
        c = 0
        
        b += target3
        c += target2
        a += target1
        
        # MIX macro expanded
        a -= b; a -= c; a ^= (c >> 13)
        b -= c; b -= a; b ^= (a << 8)
        c -= a; c -= b; c ^= (b >> 13)
        a -= b; a -= c; a ^= (c >> 12)
        b -= c; b -= a; b ^= (a << 16)
        c -= a; c -= b; c ^= (b >> 5)
        a -= b; a -= c; a ^= (c >> 3)
        b -= c; b -= a; b ^= (a << 10)
        c -= a; c -= b; c ^= (b >> 15)
        
        return c & 0xFFFFFFFF
        
    def add_port(self, port: BaseQueue) -> int:
        """Add port to switch.
        
        Returns:
            Port index
        """
        self._ports.append(port)
        if hasattr(port, 'set_remote_endpoint'):
            port.set_remote_endpoint(self)
        elif hasattr(port, 'setSwitch'):
            port.setSwitch(self)
        return len(self._ports) - 1
            
    def set_id(self, switch_id: int) -> None:
        """Set switch ID."""
        self._id = switch_id
        
    def get_id(self) -> int:
        """Get switch ID."""
        return self._id
        
    def receivePacket(self, pkt: Packet) -> None:
        """Alias for receive_packet to match C++ naming."""
        self.receive_packet(pkt)
        
    def addPort(self, port: BaseQueue) -> int:
        """Alias for add_port to match C++ naming."""
        return self.add_port(port)
        
    def add_logger(self, logfile, sample_period: int) -> None:
        """Add logger to switch ports.
        
        Matches C++ Switch::add_logger.
        """
        # Add logger for each port/queue
        for port in self._ports:
            if hasattr(port, 'add_logger'):
                port.add_logger(logfile, sample_period)