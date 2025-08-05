"""
Incast traffic pattern example for data center networks

This example demonstrates:
- Incast traffic pattern (many-to-one)
- TCP incast problem and mitigation
- Performance monitoring

Corresponds to incast examples in HTSim C++ implementation
"""

import sys
import random
import argparse

# Add parent directory to path
sys.path.append('../../../')

from htsimpy.core.eventlist import EventList
from htsimpy.core.logger.logfile import Logfile
from htsimpy.core.logger.loggers import TcpLoggerSimple
from htsimpy.protocols.tcp import TcpSrc, TcpSink, TcpRtxTimerScanner
from htsimpy.datacenter import (
    FatTreeTopology, FirstFit, QueueType,
    Incast, IncastPattern, TcpSrcTransfer
)
from htsimpy.core.route import Route


def speedFromMbps(mbps: int) -> int:
    """Convert Mbps to bps"""
    return mbps * 1000000


def timeFromMs(ms: float) -> int:
    """Convert milliseconds to picoseconds"""
    return int(ms * 1e9)


def timeFromSec(sec: float) -> int:
    """Convert seconds to picoseconds"""
    return int(sec * 1e12)


def create_tcp_transfer(tcp_src: TcpSrc, bytes_to_send: int, 
                       incast: Incast) -> TcpSrcTransfer:
    """Create a TCP transfer wrapper for incast"""
    transfer = TcpSrcTransfer(tcp_src, bytes_to_send, incast)
    return transfer


def main():
    """Main simulation function"""
    
    # Parse arguments
    parser = argparse.ArgumentParser(description='Incast TCP Simulation')
    parser.add_argument('-o', '--output', default='logout_incast.dat',
                       help='Output log file')
    parser.add_argument('-t', '--time', type=float, default=10.0,
                       help='Simulation time in seconds')
    parser.add_argument('-k', '--k', type=int, default=4,
                       help='Fat-tree parameter K')
    parser.add_argument('-n', '--senders', type=int, default=15,
                       help='Number of incast senders')
    parser.add_argument('-b', '--bytes', type=int, default=100000,
                       help='Bytes per sender (default 100KB)')
    parser.add_argument('--linkspeed', type=int, default=10000,
                       help='Link speed in Mbps')
    parser.add_argument('--queuesize', type=int, default=100,
                       help='Queue size in packets')
    parser.add_argument('--receiver', type=int, default=0,
                       help='Receiver node ID')
    
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
    
    # Create topology
    print(f"Creating Fat-tree topology with K={args.k}")
    linkspeed = speedFromMbps(args.linkspeed)
    queuesize = args.queuesize * 1500  # packet size
    
    topology = FatTreeTopology(
        logfile=logfile,
        eventlist=eventlist,
        firstfit=None,
        k=args.k,
        queuesize=queuesize,
        queue_type=QueueType.RANDOM,
        link_speed=linkspeed
    )
    
    no_of_nodes = topology.no_of_nodes()
    print(f"Topology has {no_of_nodes} nodes")
    
    if args.receiver >= no_of_nodes:
        print(f"Error: Receiver {args.receiver} >= {no_of_nodes} nodes")
        return
        
    if args.senders >= no_of_nodes:
        args.senders = no_of_nodes - 1
        print(f"Adjusted senders to {args.senders}")
    
    # Create incast coordinator
    incast = Incast(args.bytes, eventlist)
    
    # Select senders (all except receiver)
    senders = []
    for i in range(no_of_nodes):
        if i != args.receiver and len(senders) < args.senders:
            senders.append(i)
            
    print(f"Incast: {len(senders)} senders -> receiver {args.receiver}")
    print(f"Each sender will send {args.bytes} bytes")
    
    # Create flows
    for sender_id, sender in enumerate(senders):
        # Create TCP source and sink
        tcp_src = TcpSrc(None, None, eventlist)
        tcp_sink = TcpSink()
        
        # Set names
        tcp_src.setName(f"incast_src_{sender}_to_{args.receiver}")
        tcp_sink.setName(f"incast_sink_{sender}_to_{args.receiver}")
        
        # Log names
        logfile.write_name(tcp_src)
        logfile.write_name(tcp_sink)
        
        # Register with RTX scanner
        tcp_rtx_scanner.registerTcp(tcp_src)
        
        # Get paths
        paths = topology.get_bidir_paths(sender, args.receiver, False)
        if not paths:
            print(f"Warning: No path from {sender} to {args.receiver}")
            continue
            
        # Choose shortest path for incast
        shortest_path = min(paths, key=lambda p: len(p._elements))
        
        # Create routes
        route_out = Route()
        for element in shortest_path._elements:
            route_out.push_back(element)
            
        route_in = Route()
        route_in.push_back(tcp_src)
        
        # Create transfer wrapper
        transfer = create_tcp_transfer(tcp_src, args.bytes, incast)
        incast.add_flow(transfer)
        
        # Connect with staggered start times to avoid synchronization
        starttime = timeFromMs(sender_id * 0.1)  # 0.1ms apart
        tcp_src.connect(route_out, route_in, tcp_sink, starttime)
        
    # Start the incast
    print("Starting incast transfers...")
    incast.start_incast()
    
    # Monitor specific queues (ToR switch of receiver)
    receiver_tor = args.receiver // (args.k // 2)
    print(f"Monitoring queues at ToR switch {receiver_tor}")
    
    # Run simulation
    print(f"Running simulation for {args.time} seconds...")
    
    last_print_time = 0
    print_interval = timeFromSec(0.1)  # Print every 100ms
    
    while eventlist.doNextEvent():
        current_time = eventlist.now()
        
        # Periodic status update
        if current_time - last_print_time > print_interval:
            completed = incast.get_finished_count()
            total = incast.get_flow_count()
            print(f"Time: {current_time/1e12:.3f}s - "
                  f"Completed: {completed}/{total} flows")
            last_print_time = current_time
            
    print("\nSimulation complete!")
    
    # Print final statistics
    print("\n=== Incast Statistics ===")
    print(f"Total flows: {incast.get_flow_count()}")
    print(f"Simulation time: {eventlist.now() / 1e12:.3f} seconds")
    print(f"Final completed: {incast.get_finished_count()}")
    
    print(f"\nCheck {args.output} for detailed logs")


if __name__ == "__main__":
    main()