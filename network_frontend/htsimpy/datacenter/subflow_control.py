"""
Subflow control for Multipath TCP in data center networks

Corresponds to subflow_control.h/cpp in HTSim C++ implementation
Dynamically manages MPTCP subflows based on network conditions.
"""

import random
from typing import Dict, List, Optional, Set, TYPE_CHECKING
from ..core.eventlist import EventSource, EventList
from ..core.route import Route
from ..core.logger.logfile import Logfile

if TYPE_CHECKING:
    from ..protocols.multipath_tcp import MultipathTcpSrc
    from ..protocols.tcp import TcpSrc, TcpSink


class MultipathFlowEntry:
    """
    Tracks information about a multipath flow
    """
    
    def __init__(self, byte_counter: int, src: int, dest: int):
        """
        Initialize flow entry
        
        Args:
            byte_counter: Initial byte count
            src: Source node ID
            dest: Destination node ID
        """
        self.byte_counter = byte_counter
        self.src = src
        self.dest = dest
        self.subflows: List[int] = []  # Path indices used by subflows
        self.structure: List[int] = []  # Structure indices (for fat-tree)
        self.active_subflows: List['TcpSrc'] = []  # Active TCP subflows
        
        
class SubflowControl(EventSource):
    """
    Dynamic subflow controller for MPTCP
    
    Monitors MPTCP flows and dynamically adds/removes subflows based on:
    - Throughput measurements
    - Available paths
    - Maximum subflow limits
    
    Key features:
    - Periodic monitoring of flow throughput
    - Adds subflows when throughput is below threshold
    - Ensures path diversity (no duplicate paths)
    - Supports fat-tree specific path selection
    """
    
    def __init__(self,
                 scan_period: int,
                 logfile: Optional[Logfile],
                 eventlist: EventList,
                 net_paths: Dict[int, Dict[int, List[Route]]],
                 max_subflows: int = 8,
                 link_speed_mbps: int = 10000,
                 tcp_generator: Optional[callable] = None):
        """
        Initialize subflow controller
        
        Args:
            scan_period: Period between scans in picoseconds
            logfile: Optional logfile
            eventlist: Event list
            net_paths: Network paths indexed by [src][dst]
            max_subflows: Maximum subflows per connection
            link_speed_mbps: Link speed in Mbps (for threshold calculation)
            tcp_generator: Function to create TCP sources/sinks
        """
        super().__init__(eventlist, "SubflowControl")
        
        self._scan_period = scan_period
        self._logfile = logfile
        self._net_paths = net_paths
        self._max_subflows = max_subflows
        self._tcp_generator = tcp_generator
        
        # Flow tracking
        self._flow_counters: Dict['MultipathTcpSrc', MultipathFlowEntry] = {}
        
        # Calculate throughput threshold
        # If flow achieves less than this in scan period, add subflow
        scan_period_sec = scan_period / 1e12
        self._threshold = int(scan_period_sec * link_speed_mbps * 100 * 8)
        
        print(f"SubflowControl: threshold = {self._threshold} bytes, "
              f"scan period = {scan_period_sec * 1000:.1f} ms")
              
        # Statistics
        self._total_subflows_added = 0
        self._total_scans = 0
        
        # Schedule first scan
        self.eventlist.sourceIsPendingRel(self, self._scan_period)
        
    def doNextEvent(self):
        """Handle next event - run periodic scan"""
        self.run()
        self.eventlist.sourceIsPendingRel(self, self._scan_period)
        
    def add_flow(self, src: int, dest: int, flow: 'MultipathTcpSrc'):
        """
        Register an MPTCP flow for monitoring
        
        Args:
            src: Source node ID
            dest: Destination node ID
            flow: MPTCP source to monitor
        """
        self._flow_counters[flow] = MultipathFlowEntry(0, src, dest)
        
    def add_subflow(self, flow: 'MultipathTcpSrc', choice: int, 
                   structure: int = -1):
        """
        Record that a subflow was added
        
        Args:
            flow: MPTCP source
            choice: Path index chosen
            structure: Structure index (for fat-tree, -1 otherwise)
        """
        if flow not in self._flow_counters:
            return
            
        entry = self._flow_counters[flow]
        entry.subflows.append(choice)
        
        if structure != -1:
            entry.structure.append(structure)
            
    def run(self):
        """Run periodic scan of all flows"""
        self._total_scans += 1
        
        for mtcp, entry in self._flow_counters.items():
            # Get current byte count
            current_counter = mtcp.compute_total_bytes()
            delta = current_counter - entry.byte_counter
            
            # Check if this is not the first measurement
            counts = entry.byte_counter != 0
            
            # Update counter
            entry.byte_counter = current_counter
            
            # Check if we should add a subflow
            if (counts and 
                delta < self._threshold and
                len(entry.subflows) < self._max_subflows and
                len(entry.subflows) < len(self._net_paths.get(entry.src, {}).get(entry.dest, []))):
                
                self._add_new_subflow(mtcp, entry)
                
    def _add_new_subflow(self, mtcp: 'MultipathTcpSrc', 
                        entry: MultipathFlowEntry):
        """Add a new subflow to the MPTCP connection"""
        
        if not self._tcp_generator:
            return
            
        # Get available paths
        paths = self._net_paths.get(entry.src, {}).get(entry.dest, [])
        if not paths:
            return
            
        # Find an unused path
        choice = self._find_unused_path(entry, len(paths))
        if choice is None:
            return
            
        # Create new TCP subflow
        tcp_src, tcp_snk = self._tcp_generator(
            entry.src, entry.dest,
            f"mtcp_{entry.src}_{len(entry.subflows)}_{entry.dest}"
        )
        
        if not tcp_src or not tcp_snk:
            return
            
        # Record the choice
        entry.subflows.append(choice)
        entry.active_subflows.append(tcp_src)
        
        # Create routes
        route_out = Route()
        for element in paths[choice]._elements:
            route_out.push_back(element)
        route_out.push_back(tcp_snk)
        
        route_in = Route()
        route_in.push_back(tcp_src)
        
        # Add random start delay
        extra_start_time = self.eventlist.now() + self._scan_period + \
                          int(random.random() * self._scan_period / 1000)
        
        # Join multipath connection
        mtcp.add_subflow(tcp_src)
        tcp_src.connect(route_out, route_in, tcp_snk, extra_start_time)
        
        self._total_subflows_added += 1
        
        print(f"Added subflow {len(entry.subflows)} between "
              f"{entry.src} and {entry.dest} at "
              f"{self.eventlist.now() / 1e9:.3f} ms")
              
    def _find_unused_path(self, entry: MultipathFlowEntry, 
                         num_paths: int) -> Optional[int]:
        """
        Find an unused path index
        
        Args:
            entry: Flow entry
            num_paths: Total number of available paths
            
        Returns:
            Path index or None if all paths used
        """
        # Special handling for fat-tree topology
        # K^2/4 paths means fat-tree with K pods
        if num_paths == 16 and len(entry.subflows) < 4:  # K=8 fat-tree
            # For fat-tree, ensure we use different upper pod switches
            k = 8  # Assuming K=8
            
            # Find unused structure
            for i in range(k // 2):
                if i not in entry.structure:
                    entry.structure.append(i)
                    # Convert structure to actual path
                    return i * k // 2 + random.randint(0, 1)
                    
        # General case - random selection
        used_paths = set(entry.subflows)
        available = [i for i in range(num_paths) if i not in used_paths]
        
        if not available:
            return None
            
        return random.choice(available)
        
    def print_stats(self):
        """Print statistics about subflow control"""
        print("\n=== Subflow Control Statistics ===")
        print(f"Total scans: {self._total_scans}")
        print(f"Total subflows added: {self._total_subflows_added}")
        
        for mtcp, entry in self._flow_counters.items():
            print(f"\nFlow {entry.src} -> {entry.dest}:")
            print(f"  Subflows: {len(entry.subflows)}")
            print(f"  Paths used: {entry.subflows}")
            print(f"  Total bytes: {entry.byte_counter}")
            
    def get_stats(self) -> Dict[str, int]:
        """Get statistics dictionary"""
        return {
            'total_scans': self._total_scans,
            'total_subflows_added': self._total_subflows_added,
            'monitored_flows': len(self._flow_counters),
            'total_active_subflows': sum(len(e.subflows) for e in 
                                       self._flow_counters.values())
        }
        
    def set_threshold(self, threshold: int):
        """Update throughput threshold"""
        self._threshold = threshold
        
    def get_threshold(self) -> int:
        """Get current threshold"""
        return self._threshold