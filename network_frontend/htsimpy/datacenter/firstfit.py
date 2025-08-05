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
        self.threshold = 10000000  # 10MB default
        
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
        """
        # Reset path allocations
        self.path_allocations.clear()
        
        # List of flows that need reallocation
        flows_to_reallocate = []
        
        # First pass: check which flows need reallocation
        for tcp_src, flow_entry in self.flow_counters.items():
            # Get current byte count from TCP source
            current_bytes = tcp_src.get_sent_bytes() if hasattr(tcp_src, 'get_sent_bytes') else 0
            
            # Calculate bytes sent since last scan
            bytes_sent = current_bytes - flow_entry.byte_counter
            flow_entry.byte_counter = current_bytes
            
            # Check if flow is significant enough to consider
            if bytes_sent > self.threshold:
                flows_to_reallocate.append((tcp_src, flow_entry, bytes_sent))
                
        # Sort flows by bytes sent (descending) - allocate heavy flows first
        flows_to_reallocate.sort(key=lambda x: x[2], reverse=True)
        
        # Second pass: reallocate flows
        for tcp_src, flow_entry, bytes_sent in flows_to_reallocate:
            if self.net_paths and flow_entry.src < len(self.net_paths):
                if flow_entry.dest < len(self.net_paths[flow_entry.src]):
                    paths = self.net_paths[flow_entry.src][flow_entry.dest]
                    
                    if paths:
                        # Find the least loaded path
                        best_path = None
                        best_load = float('inf')
                        
                        for path in paths:
                            path_load = self._calculate_path_load(path)
                            if path_load < best_load:
                                best_load = path_load
                                best_path = path
                                
                        # Reallocate if we found a better path
                        if best_path and best_path != flow_entry.route:
                            self._reallocate_flow(tcp_src, flow_entry, best_path)
                            
    def add_flow(self, src: int, dest: int, flow: TcpSrc):
        """
        Add a flow to be managed by FirstFit
        
        Args:
            src: Source host ID
            dest: Destination host ID
            flow: The TCP source flow
        """
        # Get initial route if available
        route = None
        if (self.net_paths and 
            src < len(self.net_paths) and 
            dest < len(self.net_paths[src]) and
            self.net_paths[src][dest]):
            # Use first available path initially
            route = self.net_paths[src][dest][0]
            
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
            
    def _calculate_path_load(self, path: Route) -> int:
        """
        Calculate the load on a path
        
        Args:
            path: The route to check
            
        Returns:
            Total allocated load on the path
        """
        total_load = 0
        
        # Sum allocations for all queues in the path
        for element in path.route_elements():
            if isinstance(element, BaseQueue):
                total_load += self.path_allocations.get(element, 0)
                
        return total_load
        
    def _reallocate_flow(self, tcp_src: TcpSrc, flow_entry: FlowEntry, new_path: Route):
        """
        Reallocate a flow to a new path
        
        Args:
            tcp_src: The TCP source
            flow_entry: Flow entry information
            new_path: New path to use
        """
        # Remove allocation from old path
        if flow_entry.route:
            for element in flow_entry.route.route_elements():
                if isinstance(element, BaseQueue) and element in self.path_allocations:
                    self.path_allocations[element] -= flow_entry.allocated
                    
        # Add allocation to new path
        flow_entry.route = new_path
        for element in new_path.route_elements():
            if isinstance(element, BaseQueue):
                if element not in self.path_allocations:
                    self.path_allocations[element] = 0
                self.path_allocations[element] += flow_entry.allocated
                
        # Update the TCP source route if supported
        if hasattr(tcp_src, 'update_route'):
            tcp_src.update_route(new_path)
            
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