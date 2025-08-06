"""
FirstFit path allocation algorithm for data center networks

Corresponds to firstfit.h/cpp in HTSim C++ implementation
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from ..core.eventlist import EventList, EventSource
from ..core.route import Route
from ..queues.base_queue import BaseQueue
from ..protocols.tcp import TcpSrc


@dataclass
class FlowEntry:
    """Information about a flow for FirstFit allocation"""
    byte_counter: int
    allocated: int
    src: int
    dest: int
    route: Optional[Route]
    

class FirstFit(EventSource):
    """
    FirstFit path allocation algorithm
    
    This algorithm periodically scans flows and reallocates paths
    to balance load across the network. It's a simple greedy
    algorithm that fits flows into the least loaded paths.
    """
    
    def __init__(self, 
                 scan_period: int,
                 eventlist: EventList,
                 net_paths: Optional[List[List[List[Route]]]] = None):
        """
        Initialize FirstFit allocator
        
        Args:
            scan_period: Period between scans in picoseconds
            eventlist: The event list
            net_paths: 3D array of paths [src][dest][path_index]
        """
        super().__init__(eventlist, "FirstFit")
        self._scan_period = scan_period
        self._eventlist = eventlist
        self.net_paths = net_paths
        
        # Flow tracking
        self.flow_counters: Dict[TcpSrc, FlowEntry] = {}
        
        # Queue allocations tracking
        self.path_allocations: Dict[BaseQueue, int] = {}
        
        # Threshold for reallocation (bytes)
        # C++ uses: threshold = (int)(timeAsSec(_scanPeriod) * HOST_NIC * 100)
        # Convert scan_period from ps to seconds, multiply by HOST_NIC bps * 100
        from .constants import HOST_NIC
        self.threshold = int((scan_period / 1e12) * HOST_NIC * 100)
        
        # Start the periodic scanning
        if scan_period > 0:
            self._eventlist.source_queue().insert_at_time(self, scan_period)
            
    def do_next_event(self):
        """
        Handle the next event - perform path reallocation scan
        """
        self.run()
        
        # Schedule next scan
        if self._scan_period > 0:
            self._eventlist.source_queue().insert_at_time(
                self, 
                self._eventlist.now() + self._scan_period
            )
            
    def run(self):
        """
        Run the FirstFit allocation algorithm
        
        This scans all flows and reallocates paths if needed
        based on current traffic patterns.
        
        Matches C++ FirstFit::run() logic.
        """
        # First pass: remove flows that are below threshold
        for tcp_src, flow_entry in self.flow_counters.items():
            # Get current byte count - C++ uses _last_acked
            if hasattr(tcp_src, '_last_acked'):
                current_counter = tcp_src._last_acked
            elif hasattr(tcp_src, 'get_last_acked'):
                current_counter = tcp_src.get_last_acked()
            else:
                current_counter = 0
                
            delta = current_counter - flow_entry.byte_counter
            
            # Remove allocation if flow is allocated and delta is below threshold
            if flow_entry.allocated and delta < self.threshold:
                # Remove from path allocations
                flow_entry.allocated = 0
                
                if flow_entry.route:
                    # C++ iterates route elements at positions 1,3,5... (queues)
                    for i in range(1, len(flow_entry.route._sinklist), 2):
                        element = flow_entry.route._sinklist[i]
                        if isinstance(element, BaseQueue) and element in self.path_allocations:
                            self.path_allocations[element] -= 1
                            
        # Second pass: allocate flows that are above threshold
        for tcp_src, flow_entry in self.flow_counters.items():
            # Get current byte count
            if hasattr(tcp_src, '_last_acked'):
                current_counter = tcp_src._last_acked
            elif hasattr(tcp_src, 'get_last_acked'):
                current_counter = tcp_src.get_last_acked()
            else:
                current_counter = 0
                
            delta = current_counter - flow_entry.byte_counter
            flow_entry.byte_counter = current_counter
            
            # Speed up detection for negative deltas (C++ logic)
            if delta < 0:
                flow_entry.byte_counter = 0
                delta = current_counter
                
            # Allocate if not allocated and delta is above threshold
            if not flow_entry.allocated and delta > self.threshold:
                best_route_idx = -1
                best_cost = 10000000  # Match C++ initial value
                
                if (self.net_paths and 
                    flow_entry.src < len(self.net_paths) and
                    flow_entry.dest < len(self.net_paths[flow_entry.src])):
                    
                    paths = self.net_paths[flow_entry.src][flow_entry.dest]
                    
                    # Find path with minimum maximum queue allocation
                    for p, route in enumerate(paths):
                        current_cost = 0
                        
                        # Check queue allocations along the path
                        # C++ checks positions 1,3,5... (queues)
                        for i in range(1, len(route._sinklist), 2):
                            element = route._sinklist[i]
                            if isinstance(element, BaseQueue):
                                queue_alloc = self.path_allocations.get(element, 0)
                                if queue_alloc > current_cost:
                                    current_cost = queue_alloc
                                    
                        if current_cost < best_cost:
                            best_cost = current_cost
                            best_route_idx = p
                            
                    if best_route_idx >= 0:
                        # Set allocated flag
                        flow_entry.allocated = 1
                        
                        # Create new route (C++ copies and adds sink)
                        new_route = paths[best_route_idx]
                        
                        # Update TCP source route
                        if hasattr(tcp_src, 'replace_route'):
                            tcp_src.replace_route(new_route)
                        elif hasattr(tcp_src, 'update_route'):
                            tcp_src.update_route(new_route)
                            
                        flow_entry.route = new_route
                        
                        # Update path allocations
                        for i in range(1, len(new_route._sinklist), 2):
                            element = new_route._sinklist[i]
                            if isinstance(element, BaseQueue):
                                if element not in self.path_allocations:
                                    self.path_allocations[element] = 0
                                self.path_allocations[element] += 1
                            
    def add_flow(self, src: int, dest: int, flow: TcpSrc):
        """
        Add a flow to be managed by FirstFit
        
        Args:
            src: Source host ID
            dest: Destination host ID
            flow: The TCP source flow
        """
        # C++ asserts that flow has a route
        if hasattr(flow, '_route'):
            route = flow._route
        elif hasattr(flow, 'get_route'):
            route = flow.get_route()
        else:
            route = None
            
        # Create flow entry matching C++ constructor
        flow_entry = FlowEntry(
            byte_counter=0,
            allocated=0,
            src=src,
            dest=dest,
            route=route
        )
        
        self.flow_counters[flow] = flow_entry
        
    def add_queue(self, queue: BaseQueue):
        """
        Add a queue to track allocations
        
        Args:
            queue: Queue to track
        """
        if queue not in self.path_allocations:
            self.path_allocations[queue] = 0
            
    def get_path_allocations(self) -> Dict[BaseQueue, int]:
        """
        Get current path allocations
        
        Returns:
            Dictionary of queue to allocated bytes
        """
        return self.path_allocations.copy()
        
    def set_threshold(self, threshold: int):
        """
        Set the threshold for flow reallocation
        
        Args:
            threshold: Threshold in bytes
        """
        self.threshold = threshold