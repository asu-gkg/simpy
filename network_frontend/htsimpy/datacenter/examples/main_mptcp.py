"""
Multipath TCP (MPTCP) example for data center networks

This example demonstrates:
- MPTCP with multiple subflows
- Dynamic subflow control
- Different congestion control algorithms
- Path diversity in fat-tree topology

Corresponds to MPTCP examples in HTSim C++ implementation
"""

import sys
import random
import argparse
from typing import Dict, List

# Add parent directory to path
sys.path.append('../../../')

from htsimpy.core.eventlist import EventList
from htsimpy.core.logger.logfile import Logfile
from htsimpy.core.logger.loggers import TcpLoggerSimple
from htsimpy.protocols.tcp import TcpSrc, TcpSink, TcpRtxTimerScanner
from htsimpy.protocols.multipath_tcp import (
    MultipathTcpSrc, MultipathTcpAlgorithm
)
from htsimpy.datacenter import (
    FatTreeTopology, ConnectionMatrix, FirstFit, QueueType,
    SubflowControl
)
from htsimpy.core.route import Route


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


def create_mptcp_subflow(src: int, dst: int, subflow_id: int,
                        eventlist: EventList, 
                        tcp_rtx_scanner: TcpRtxTimerScanner,
                        logfile: Logfile):
    """Create a TCP subflow for MPTCP"""
    tcp_src = TcpSrc(None, None, eventlist)
    tcp_sink = TcpSink()
    
    # Set names
    tcp_src.setName(f"mptcp_sub_{src}_to_{dst}_{subflow_id}")
    tcp_sink.setName(f"mptcp_sink_{src}_to_{dst}_{subflow_id}")
    
    # Log names
    logfile.write_name(tcp_src)
    logfile.write_name(tcp_sink)
    
    # Register with RTX scanner
    tcp_rtx_scanner.registerTcp(tcp_src)
    
    return tcp_src, tcp_sink


def main():
    """Main simulation function"""
    
    # Parse arguments
    parser = argparse.ArgumentParser(description='MPTCP Data Center Simulation')
    parser.add_argument('-o', '--output', default='logout_mptcp.dat',
                       help='Output log file')
    parser.add_argument('-t', '--time', type=float, default=1.0,
                       help='Simulation time in seconds')
    parser.add_argument('-k', '--k', type=int, default=8,
                       help='Fat-tree parameter K')
    parser.add_argument('-c', '--conns', type=int, default=8,
                       help='Number of connections')
    parser.add_argument('-s', '--subflows', type=int, default=4,
                       help='Initial subflows per connection')
    parser.add_argument('--algo', type=str, default='coupled_epsilon',
                       choices=['uncoupled', 'coupled_inc', 'fully_coupled',
                               'coupled_epsilon', 'coupled_tcp'],
                       help='MPTCP congestion control algorithm')
    parser.add_argument('--epsilon', type=float, default=1.0,
                       help='Epsilon for coupled_epsilon algorithm')
    parser.add_argument('--dynamic', action='store_true',
                       help='Enable dynamic subflow control')
    parser.add_argument('--max-subflows', type=int, default=8,
                       help='Maximum subflows for dynamic control')
    parser.add_argument('--linkspeed', type=int, default=10000,
                       help='Link speed in Mbps')
    
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
    
    # Map algorithm names to enum values
    algo_map = {
        'uncoupled': MultipathTcpAlgorithm.UNCOUPLED,
        'coupled_inc': MultipathTcpAlgorithm.COUPLED_INC,
        'fully_coupled': MultipathTcpAlgorithm.FULLY_COUPLED,
        'coupled_epsilon': MultipathTcpAlgorithm.COUPLED_EPSILON,
        'coupled_tcp': MultipathTcpAlgorithm.COUPLED_TCP
    }
    algo = algo_map[args.algo]
    
    # Create topology
    print(f"Creating Fat-tree topology with K={args.k}")
    linkspeed = speedFromMbps(args.linkspeed)
    
    # Use FirstFit for MPTCP
    ff = FirstFit(eventlist)
    
    topology = FatTreeTopology(
        logfile=logfile,
        eventlist=eventlist,
        firstfit=ff,
        k=args.k,
        queue_type=QueueType.RANDOM,
        link_speed=linkspeed
    )
    
    no_of_nodes = topology.no_of_nodes()
    print(f"Topology has {no_of_nodes} nodes")
    print(f"Using MPTCP algorithm: {args.algo}")
    if args.algo == 'coupled_epsilon':
        print(f"Epsilon: {args.epsilon}")
    
    # Pre-compute paths
    print("Pre-computing network paths...")
    net_paths: Dict[int, Dict[int, List[Route]]] = {}
    for i in range(no_of_nodes):
        net_paths[i] = {}
        
    # Create connection matrix
    conn_matrix = ConnectionMatrix(no_of_nodes)
    if args.conns >= no_of_nodes:
        conn_matrix.setPermutation(no_of_nodes)
    else:
        conn_matrix.setRandom(args.conns)
        
    # Create subflow controller if dynamic control enabled
    subflow_control = None
    if args.dynamic:
        print(f"Enabling dynamic subflow control (max {args.max_subflows} subflows)")
        
        # TCP generator for subflow control
        def tcp_gen(src: int, dst: int, name: str):
            return create_mptcp_subflow(src, dst, 999, eventlist, 
                                      tcp_rtx_scanner, logfile)
            
        subflow_control = SubflowControl(
            scan_period=timeFromMs(100),  # Scan every 100ms
            logfile=logfile,
            eventlist=eventlist,
            net_paths=net_paths,
            max_subflows=args.max_subflows,
            tcp_generator=tcp_gen
        )
    
    # Create MPTCP flows
    flow_count = 0
    mptcp_sources = []
    
    for src, destinations in conn_matrix.connections.items():
        for dst in destinations:
            # Get paths if not cached
            if dst not in net_paths[src]:
                paths = topology.get_bidir_paths(src, dst, False)
                net_paths[src][dst] = paths
                
            if not net_paths[src][dst]:
                print(f"Warning: No paths from {src} to {dst}")
                continue
                
            # Create MPTCP source
            if algo == MultipathTcpAlgorithm.COUPLED_EPSILON:
                mptcp_src = MultipathTcpSrc(algo, eventlist, None, args.epsilon)
            else:
                mptcp_src = MultipathTcpSrc(algo, eventlist, None)
                
            mptcp_src.setName(f"mptcp_{src}_to_{dst}")
            logfile.write_name(mptcp_src)
            mptcp_sources.append(mptcp_src)
            
            # Register with subflow control
            if subflow_control:
                subflow_control.add_flow(src, dst, mptcp_src)
            
            # Determine number of subflows
            num_subflows = min(args.subflows, len(net_paths[src][dst]))
            print(f"MPTCP flow {src}->{dst}: {num_subflows} initial subflows "
                  f"(of {len(net_paths[src][dst])} available paths)")
            
            # Select diverse paths for subflows
            selected_paths = []
            if num_subflows == len(net_paths[src][dst]):
                # Use all paths
                selected_paths = list(range(len(net_paths[src][dst])))
            else:
                # For fat-tree, try to use different upper pod switches
                # This gives better path diversity
                path_groups = {}
                for i, path in enumerate(net_paths[src][dst]):
                    # Group by intermediate switches (simplified)
                    key = len(path._elements)  # Group by path length
                    if key not in path_groups:
                        path_groups[key] = []
                    path_groups[key].append(i)
                    
                # Select from different groups
                for group in path_groups.values():
                    if len(selected_paths) < num_subflows:
                        selected_paths.append(random.choice(group))
                        
                # Fill remaining with random choices
                while len(selected_paths) < num_subflows:
                    choice = random.randint(0, len(net_paths[src][dst]) - 1)
                    if choice not in selected_paths:
                        selected_paths.append(choice)
            
            # Create subflows
            for subflow_id, path_idx in enumerate(selected_paths):
                # Create TCP subflow
                tcp_src, tcp_sink = create_mptcp_subflow(
                    src, dst, subflow_id, eventlist, tcp_rtx_scanner, logfile
                )
                
                # Get the selected path
                chosen_path = net_paths[src][dst][path_idx]
                
                # Create routes
                route_out = Route()
                for element in chosen_path._elements:
                    route_out.push_back(element)
                    
                route_in = Route()
                route_in.push_back(tcp_src)
                
                # Add subflow to MPTCP
                mptcp_src.add_subflow(tcp_src)
                
                # Record in subflow control
                if subflow_control:
                    subflow_control.add_subflow(mptcp_src, path_idx)
                
                # Connect with slight delay between subflows
                starttime = timeFromMs(subflow_id * 1)
                tcp_src.connect(route_out, route_in, tcp_sink, starttime)
                
            # Start the MPTCP flow
            mptcp_src.startflow()
            flow_count += 1
            
    print(f"\nCreated {flow_count} MPTCP flows")
    
    # Run simulation
    print(f"Running simulation for {args.time} seconds...")
    
    last_print_time = 0
    print_interval = timeFromSec(0.1)
    
    while eventlist.doNextEvent():
        current_time = eventlist.now()
        
        if current_time - last_print_time > print_interval:
            # Print status
            total_bytes = sum(src.compute_total_bytes() 
                            for src in mptcp_sources)
            print(f"Time: {current_time/1e12:.3f}s - "
                  f"Total bytes sent: {total_bytes/1e6:.1f} MB")
            
            if subflow_control:
                stats = subflow_control.get_stats()
                print(f"  Subflows added: {stats['total_subflows_added']}, "
                      f"Active: {stats['total_active_subflows']}")
                      
            last_print_time = current_time
            
    print("\nSimulation complete!")
    
    # Print final statistics
    print("\n=== MPTCP Statistics ===")
    print(f"Total MPTCP flows: {flow_count}")
    print(f"Simulation time: {eventlist.now() / 1e12:.3f} seconds")
    
    total_bytes = 0
    total_subflows = 0
    
    for src in mptcp_sources:
        bytes_sent = src.compute_total_bytes()
        num_subflows = len(src._subflows)
        total_bytes += bytes_sent
        total_subflows += num_subflows
        
    print(f"Total data sent: {total_bytes/1e9:.3f} GB")
    print(f"Average subflows per flow: {total_subflows/flow_count:.1f}")
    
    if subflow_control:
        print("\n=== Subflow Control Statistics ===")
        subflow_control.print_stats()
        
    print(f"\nCheck {args.output} for detailed logs")


if __name__ == "__main__":
    main()