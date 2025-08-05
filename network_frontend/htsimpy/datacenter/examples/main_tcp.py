"""
Complete TCP simulation example for data center networks

This example demonstrates:
- Fat-tree topology setup
- TCP flow creation with various traffic patterns
- Logging and monitoring
- Performance metrics collection

Corresponds to main_tcp.cpp in HTSim C++ implementation
"""

import sys
import random
import argparse
from typing import List, Dict, Optional

# Add parent directory to path
sys.path.append('../../../')

from htsimpy.core.eventlist import EventList
from htsimpy.core.logger.logfile import Logfile
from htsimpy.core.logger.loggers import TcpLoggerSimple
from htsimpy.core.logger.queuelogger import QueueLoggerSampling
from htsimpy.core.route import Route
from htsimpy.protocols.tcp import TcpSrc, TcpSink, TcpRtxTimerScanner
from htsimpy.datacenter import (
    FatTreeTopology, ConnectionMatrix, FirstFit,
    QueueType, PACKET_SIZE, DEFAULT_BUFFER_SIZE
)


def speedFromMbps(mbps: int) -> int:
    """Convert Mbps to bps"""
    return mbps * 1000000


def timeFromMs(ms: float) -> int:
    """Convert milliseconds to picoseconds"""
    return int(ms * 1e9)


def timeFromUs(us: float) -> int:
    """Convert microseconds to picoseconds"""
    return int(us * 1e6)


def timeFromSec(sec: float) -> int:
    """Convert seconds to picoseconds"""
    return int(sec * 1e12)


class TcpFlowGenerator:
    """Helper class to generate TCP flows"""
    
    def __init__(self, eventlist: EventList, logfile: Logfile,
                 tcp_rtx_scanner: TcpRtxTimerScanner):
        self.eventlist = eventlist
        self.logfile = logfile
        self.tcp_rtx_scanner = tcp_rtx_scanner
        self.flow_counter = 0
        
    def create_flow(self, src: int, dst: int, 
                   flowsize: int = 0) -> tuple[TcpSrc, TcpSink]:
        """Create a TCP flow"""
        tcp_src = TcpSrc(
            logger=None,
            traffic_logger=None,
            eventlist=self.eventlist
        )
        tcp_sink = TcpSink()
        
        # Set names
        tcp_src.setName(f"tcp_{src}_to_{dst}_{self.flow_counter}")
        tcp_sink.setName(f"tcp_sink_{src}_to_{dst}_{self.flow_counter}")
        
        # Log names
        self.logfile.write_name(tcp_src)
        self.logfile.write_name(tcp_sink)
        
        # Register with RTX scanner
        self.tcp_rtx_scanner.registerTcp(tcp_src)
        
        # Set flow size if specified
        if flowsize > 0:
            tcp_src.set_flowsize(flowsize)
            
        self.flow_counter += 1
        
        return tcp_src, tcp_sink


def main():
    """Main simulation function"""
    
    # Parse arguments
    parser = argparse.ArgumentParser(description='TCP Data Center Network Simulation')
    parser.add_argument('-o', '--output', default='logout.dat',
                       help='Output log file')
    parser.add_argument('-t', '--time', type=float, default=1.0,
                       help='Simulation time in seconds')
    parser.add_argument('-n', '--nodes', type=int, default=16,
                       help='Number of nodes (will be adjusted to fit topology)')
    parser.add_argument('-c', '--conns', type=int, default=0,
                       help='Number of connections (0 for all-to-all)')
    parser.add_argument('-k', '--k', type=int, default=4,
                       help='Fat-tree parameter K (must be even)')
    parser.add_argument('-q', '--queue', type=str, default='random',
                       choices=['random', 'composite'],
                       help='Queue type')
    parser.add_argument('--linkspeed', type=int, default=10000,
                       help='Link speed in Mbps')
    parser.add_argument('--queuesize', type=int, default=100,
                       help='Queue size in packets')
    parser.add_argument('--flowsize', type=int, default=0,
                       help='Flow size in bytes (0 for infinite)')
    parser.add_argument('--pattern', type=str, default='permutation',
                       choices=['permutation', 'random', 'incast', 'all-to-all'],
                       help='Traffic pattern')
    
    args = parser.parse_args()
    
    # Create event list
    eventlist = EventList()
    eventlist.setEndtime(timeFromSec(args.time))
    
    # Create logfile
    print(f"Logging to {args.output}")
    logfile = Logfile(args.output, eventlist)
    logfile.setStartTime(timeFromSec(0))
    
    # Add TCP logger
    tcp_logger = TcpLoggerSimple()
    logfile.addLogger(tcp_logger)
    
    # Create RTX timer scanner
    tcp_rtx_scanner = TcpRtxTimerScanner(timeFromMs(10), eventlist)
    
    # Queue type
    queue_type = QueueType.RANDOM if args.queue == 'random' else QueueType.COMPOSITE
    
    # Create topology
    print(f"Creating Fat-tree topology with K={args.k}")
    linkspeed = speedFromMbps(args.linkspeed)
    queuesize = args.queuesize * PACKET_SIZE
    
    # Create FirstFit if needed
    ff = FirstFit(eventlist) if args.conns > 16 else None
    
    # Create topology
    topology = FatTreeTopology(
        logfile=logfile,
        eventlist=eventlist,
        firstfit=ff,
        k=args.k,
        queuesize=queuesize,
        queue_type=queue_type,
        link_speed=linkspeed
    )
    
    # Get actual number of nodes
    no_of_nodes = topology.no_of_nodes()
    print(f"Topology has {no_of_nodes} nodes")
    
    # Create network paths cache
    net_paths: Dict[int, Dict[int, List[Route]]] = {}
    for i in range(no_of_nodes):
        net_paths[i] = {}
        
    # Create connection matrix
    conns = ConnectionMatrix(no_of_nodes)
    
    # Set traffic pattern
    if args.pattern == 'permutation':
        if args.conns == 0:
            args.conns = no_of_nodes
        print(f"Running permutation with {args.conns} connections")
        conns.setPermutation(args.conns)
    elif args.pattern == 'random':
        if args.conns == 0:
            args.conns = no_of_nodes
        print(f"Running random with {args.conns} connections")
        conns.setRandom(args.conns)
    elif args.pattern == 'incast':
        # Simple incast: all nodes send to node 0
        print(f"Running incast to node 0")
        for i in range(1, no_of_nodes):
            conns.add_connection(i, 0)
    elif args.pattern == 'all-to-all':
        print(f"Running all-to-all")
        for i in range(no_of_nodes):
            for j in range(no_of_nodes):
                if i != j:
                    conns.add_connection(i, j)
                    
    # Create flow generator
    flow_gen = TcpFlowGenerator(eventlist, logfile, tcp_rtx_scanner)
    
    # Create flows
    flow_count = 0
    for src, destinations in conns.connections.items():
        for dst in destinations:
            # Get paths if not cached
            if dst not in net_paths[src]:
                paths = topology.get_bidir_paths(src, dst, False)
                net_paths[src][dst] = paths
                
            if not net_paths[src][dst]:
                print(f"Warning: No path found from {src} to {dst}")
                continue
                
            # Create TCP flow
            tcp_src, tcp_sink = flow_gen.create_flow(src, dst, args.flowsize)
            
            # Choose random path
            path_choice = random.randint(0, len(net_paths[src][dst]) - 1)
            chosen_path = net_paths[src][dst][path_choice]
            
            # Create routes
            route_out = Route()
            route_in = Route()
            
            # Build outgoing route
            for element in chosen_path._elements:
                route_out.push_back(element)
                
            # Build return route
            route_in.push_back(tcp_src)
            
            # Add random start time (0-10ms)
            starttime = random.randint(0, timeFromMs(10))
            
            # Connect
            tcp_src.connect(route_out, route_in, tcp_sink, starttime)
            
            flow_count += 1
            
    print(f"Created {flow_count} flows")
    
    # Add queue samplers
    print("Setting up queue monitoring...")
    for queue_list in [topology.queues_nup_nlp, topology.queues_nlp_nup,
                      topology.queues_nup_nc, topology.queues_nc_nup,
                      topology.queues_nlp_ns, topology.queues_ns_nlp]:
        for row in queue_list:
            for queue in row:
                if queue is not None:
                    sampler = QueueLoggerSampling(timeFromUs(1000), eventlist)
                    sampler.startLogging(queue)
                    logfile.addLogger(sampler)
    
    # Run simulation
    print(f"Starting simulation for {args.time} seconds...")
    while eventlist.doNextEvent():
        pass
        
    print("Simulation complete!")
    
    # Print statistics
    print("\n=== Simulation Statistics ===")
    print(f"Total flows: {flow_count}")
    print(f"Simulation time: {eventlist.now() / 1e12:.3f} seconds")
    
    # Get TCP statistics
    total_sent = 0
    total_acked = 0
    total_retransmits = 0
    
    for src, destinations in conns.connections.items():
        for dst in destinations:
            # This would need to track TCP sources to get accurate stats
            pass
            
    print(f"\nCheck {args.output} for detailed logs")


if __name__ == "__main__":
    main()