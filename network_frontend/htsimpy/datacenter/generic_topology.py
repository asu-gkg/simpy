"""
Generic topology loader for data center networks

Corresponds to generic_topology.h/cpp in HTSim C++ implementation
Loads arbitrary topologies from configuration files.
"""

import re
from typing import List, Optional, Dict, TextIO
from ..core.route import Route
from ..core.pipe import Pipe
from ..core.eventlist import EventList
from ..core.logger.logfile import Logfile
from ..queues.random_queue import RandomQueue
from ..queues.base_queue import BaseQueue, Queue
from ..core.switch import Switch
from .topology import Topology
from .host import Host
from .constants import QueueType, PACKET_SIZE


class GenericTopology(Topology):
    """
    Generic topology that can be loaded from configuration files
    
    Supports loading arbitrary network topologies defined in text files.
    Format supports hosts, switches, queues, and pipes with flexible connectivity.
    """
    
    def __init__(self, logfile: Logfile, eventlist: EventList):
        """
        Initialize generic topology
        
        Args:
            logfile: Logfile for logging
            eventlist: Event list
        """
        super().__init__()
        self._logfile = logfile
        self._eventlist = eventlist
        
        # Network components
        self._hosts: List[Host] = []
        self._switches: List[Switch] = []
        self._pipes: List[Pipe] = []
        self._queues: List[BaseQueue] = []
        
        # Lookup dictionaries by name
        self._host_map: Dict[str, Host] = {}
        self._switch_map: Dict[str, Switch] = {}
        self._pipe_map: Dict[str, Pipe] = {}
        self._queue_map: Dict[str, BaseQueue] = {}
        
        # Topology information
        self._no_of_hosts = 0
        self._no_of_switches = 0
        self._no_of_links = 0
        
        # Routing information
        self._routes: Dict[tuple, List[Route]] = {}  # (src, dest) -> [routes]
        
    def load(self, filename: str) -> bool:
        """
        Load topology from configuration file
        
        Args:
            filename: Path to topology file
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Two-pass loading like C++ implementation
            # Pass 1: Create all objects
            with open(filename, 'r') as f:
                if not self._load_pass(f, 1):
                    return False
                    
            # Pass 2: Connect objects
            with open(filename, 'r') as f:
                if not self._load_pass(f, 2):
                    return False
                    
            return True
        except Exception as e:
            print(f"Error loading topology: {e}")
            return False
            
    def _load_pass(self, f: TextIO, pass_num: int) -> bool:
        """
        Load topology in a specific pass
        
        Pass 1: Create objects
        Pass 2: Connect objects
        """
        line_num = 0
        
        for line in f:
            line_num += 1
            line = line.strip()
            
            # Skip comments and empty lines
            if not line or line.startswith('#'):
                continue
                
            # Tokenize line
            tokens = line.split()
            if not tokens:
                continue
                
            keyword = tokens[0].lower()
            
            try:
                if keyword == 'host':
                    self._parse_host(tokens, pass_num)
                elif keyword == 'switch':
                    self._parse_switch(tokens, pass_num)
                elif keyword == 'queue':
                    self._parse_queue(tokens, pass_num)
                elif keyword == 'pipe':
                    self._parse_pipe(tokens, pass_num)
                elif keyword == 'route':
                    if pass_num == 2:
                        self._parse_route(tokens)
                else:
                    print(f"Unknown keyword '{keyword}' at line {line_num}")
                    
            except Exception as e:
                print(f"Error parsing line {line_num}: {e}")
                return False
                
        return True
        
    def _parse_host(self, tokens: List[str], pass_num: int):
        """Parse host definition"""
        if pass_num != 1:
            return
            
        if len(tokens) < 2:
            raise ValueError("Host requires name")
            
        name = tokens[1]
        
        # Create host
        host = Host(name)
        host.set_host_id(self._no_of_hosts)
        
        self._hosts.append(host)
        self._host_map[name] = host
        self._no_of_hosts += 1
        
        if self._logfile:
            self._logfile.write_name(host)
            
    def _parse_switch(self, tokens: List[str], pass_num: int):
        """Parse switch definition"""
        if pass_num != 1:
            return
            
        if len(tokens) < 2:
            raise ValueError("Switch requires name")
            
        name = tokens[1]
        
        # Create switch
        switch = Switch(name, self._eventlist)
        
        self._switches.append(switch)
        self._switch_map[name] = switch
        self._no_of_switches += 1
        
        if self._logfile:
            self._logfile.write_name(switch)
            
    def _parse_queue(self, tokens: List[str], pass_num: int):
        """
        Parse queue definition
        Format: queue <name> <bitrate> <size> [type]
        """
        if pass_num != 1:
            return
            
        if len(tokens) < 4:
            raise ValueError("Queue requires name, bitrate, and size")
            
        name = tokens[1]
        bitrate = self._parse_bitrate(tokens[2])
        size = self._parse_size(tokens[3])
        
        # Optional queue type
        qtype = tokens[4] if len(tokens) > 4 else "random"
        
        # Create queue based on type
        if qtype.lower() == "random":
            queue = RandomQueue(
                bitrate=bitrate,
                maxsize=size,
                eventlist=self._eventlist,
                logger=None
            )
        else:
            # Default to basic queue
            queue = Queue(
                bitrate=bitrate,
                maxsize=size,
                eventlist=self._eventlist,
                logger=None
            )
            
        queue.setName(name)
        
        self._queues.append(queue)
        self._queue_map[name] = queue
        
        if self._logfile:
            self._logfile.write_name(queue)
            
    def _parse_pipe(self, tokens: List[str], pass_num: int):
        """
        Parse pipe definition
        Format: pipe <name> <delay>
        """
        if pass_num != 1:
            return
            
        if len(tokens) < 3:
            raise ValueError("Pipe requires name and delay")
            
        name = tokens[1]
        delay = self._parse_time(tokens[2])
        
        # Create pipe
        pipe = Pipe(delay, self._eventlist)
        pipe.setName(name)
        
        self._pipes.append(pipe)
        self._pipe_map[name] = pipe
        
        if self._logfile:
            self._logfile.write_name(pipe)
            
    def _parse_route(self, tokens: List[str]):
        """
        Parse route definition
        Format: route <src_host> <dst_host> <element1> <element2> ...
        """
        if len(tokens) < 4:
            raise ValueError("Route requires source, destination, and path elements")
            
        src_name = tokens[1]
        dst_name = tokens[2]
        
        # Find source and destination hosts
        src_host = self._find_host(src_name)
        dst_host = self._find_host(dst_name)
        
        if not src_host or not dst_host:
            raise ValueError(f"Invalid hosts in route: {src_name}, {dst_name}")
            
        # Build route
        route = Route()
        route.push_back(src_host)
        
        # Add path elements
        for i in range(3, len(tokens)):
            element_name = tokens[i]
            
            # Try to find element in queues, pipes, switches
            element = (self._find_queue(element_name) or
                      self._find_pipe(element_name) or
                      self._find_switch(element_name))
                      
            if not element:
                raise ValueError(f"Unknown element in route: {element_name}")
                
            route.push_back(element)
            
        route.push_back(dst_host)
        
        # Store route
        key = (src_host.get_host_id(), dst_host.get_host_id())
        if key not in self._routes:
            self._routes[key] = []
        self._routes[key].append(route)
        
    def _find_host(self, name: str) -> Optional[Host]:
        """Find host by name"""
        return self._host_map.get(name)
        
    def _find_switch(self, name: str) -> Optional[Switch]:
        """Find switch by name"""
        return self._switch_map.get(name)
        
    def _find_queue(self, name: str) -> Optional[BaseQueue]:
        """Find queue by name"""
        return self._queue_map.get(name)
        
    def _find_pipe(self, name: str) -> Optional[Pipe]:
        """Find pipe by name"""
        return self._pipe_map.get(name)
        
    def _parse_bitrate(self, s: str) -> int:
        """Parse bitrate string (e.g., '10Gbps', '100Mbps')"""
        match = re.match(r'(\d+(?:\.\d+)?)\s*([KMGkmg]?)bps', s)
        if match:
            value = float(match.group(1))
            unit = match.group(2).upper()
            
            multiplier = {
                '': 1,
                'K': 1000,
                'M': 1000000,
                'G': 1000000000
            }
            
            return int(value * multiplier.get(unit, 1))
        else:
            # Try parsing as raw number
            return int(s)
            
    def _parse_size(self, s: str) -> int:
        """Parse size string (e.g., '100KB', '1MB', '1000')"""
        match = re.match(r'(\d+(?:\.\d+)?)\s*([KMGkmg]?)B?', s)
        if match:
            value = float(match.group(1))
            unit = match.group(2).upper()
            
            multiplier = {
                '': 1,
                'K': 1024,
                'M': 1024 * 1024,
                'G': 1024 * 1024 * 1024
            }
            
            return int(value * multiplier.get(unit, 1))
        else:
            # Try parsing as raw number (assume packets)
            return int(s) * PACKET_SIZE
            
    def _parse_time(self, s: str) -> int:
        """Parse time string (e.g., '1ms', '100us', '10ns')"""
        match = re.match(r'(\d+(?:\.\d+)?)\s*([munp]?)s', s)
        if match:
            value = float(match.group(1))
            unit = match.group(2)
            
            multiplier = {
                '': 1e12,      # seconds to picoseconds
                'm': 1e9,      # milliseconds to picoseconds
                'u': 1e6,      # microseconds to picoseconds
                'n': 1e3,      # nanoseconds to picoseconds
                'p': 1         # picoseconds
            }
            
            return int(value * multiplier.get(unit, 1e12))
        else:
            # Try parsing as raw number (assume picoseconds)
            return int(s)
            
    def get_bidir_paths(self, src: int, dest: int, reverse: bool) -> List[Route]:
        """Get bidirectional paths between nodes"""
        if reverse:
            src, dest = dest, src
            
        key = (src, dest)
        return self._routes.get(key, [])
        
    def get_neighbours(self, src: int) -> Optional[List[int]]:
        """Get neighboring nodes - not used in generic topology"""
        return None
        
    def no_of_nodes(self) -> int:
        """Get number of hosts"""
        return self._no_of_hosts
        
    def get_host(self, host_id: int) -> Optional[Host]:
        """Get host by ID"""
        if 0 <= host_id < self._no_of_hosts:
            return self._hosts[host_id]
        return None
        
    def get_host_by_name(self, name: str) -> Optional[Host]:
        """Get host by name"""
        return self._host_map.get(name)