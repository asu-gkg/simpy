"""
Short flows traffic pattern example for data center networks

This example demonstrates:
- Short flows with Poisson arrivals
- Mixed workload (mice and elephants)
- Flow size distributions (web search, data mining, etc.)

Corresponds to shortflows examples in HTSim C++ implementation
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
    FatTreeTopology, ConnectionMatrix, QueueType,
    ShortFlows, FlowSizeGenerators
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


def tcp_generator(src: int, dst: int, flow_size: int):
    """Generate TCP source and sink for short flows"""
    tcp_src = TcpSrc(None, None, eventlist)
    tcp_sink = TcpSink()
    
    # Set flow size
    tcp_src.set_flowsize(flow_size)
    
    return tcp_src, tcp_sink


def main():
    """Main simulation function"""
    global eventlist  # For tcp_generator
    
    # Parse arguments
    parser = argparse.ArgumentParser(description='Short Flows Simulation')
    parser.add_argument('-o', '--output', default='logout_shortflows.dat',
                       help='Output log file')
    parser.add_argument('-t', '--time', type=float, default=1.0,
                       help='Simulation time in seconds')
    parser.add_argument('-k', '--k', type=int, default=4,
                       help='Fat-tree parameter K')
    parser.add_argument('-l', '--lambda', type=float, default=100.0,
                       dest='lambda_rate',
                       help='Flow arrival rate (flows/sec)')
    parser.add_argument('--workload', type=str, default='websearch',
                       choices=['fixed', 'websearch', 'datamining', 'cache'],
                       help='Workload type')
    parser.add_argument('--fixedsize', type=int, default=70000,
                       help='Fixed flow size in bytes (for fixed workload)')
    parser.add_argument('--linkspeed', type=int, default=10000,
                       help='Link speed in Mbps')
    parser.add_argument('--pattern', type=str, default='random',
                       choices=['random', 'permutation', 'stride'],
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
    
    # Create topology
    print(f"Creating Fat-tree topology with K={args.k}")
    linkspeed = speedFromMbps(args.linkspeed)
    
    topology = FatTreeTopology(
        logfile=logfile,
        eventlist=eventlist,
        firstfit=None,
        k=args.k,
        queue_type=QueueType.RANDOM,
        link_speed=linkspeed
    )
    
    no_of_nodes = topology.no_of_nodes()
    print(f"Topology has {no_of_nodes} nodes")
    
    # Create connection matrix based on pattern
    conn_matrix = ConnectionMatrix(no_of_nodes)
    
    if args.pattern == 'random':
        # Random all-to-all pattern
        for i in range(no_of_nodes):
            for j in range(no_of_nodes):
                if i != j:
                    conn_matrix.add_connection(i, j)
    elif args.pattern == 'permutation':
        conn_matrix.setPermutation(no_of_nodes)
    elif args.pattern == 'stride':
        # Stride pattern
        stride = no_of_nodes // 2
        for i in range(no_of_nodes):
            j = (i + stride) % no_of_nodes
            conn_matrix.add_connection(i, j)
            
    # Select flow size generator
    if args.workload == 'fixed':
        flow_size_gen = FlowSizeGenerators.fixed_size(args.fixedsize)
        print(f"Using fixed flow size: {args.fixedsize} bytes")
    elif args.workload == 'websearch':
        flow_size_gen = FlowSizeGenerators.web_search()
        print("Using web search workload distribution")
    elif args.workload == 'datamining':
        flow_size_gen = FlowSizeGenerators.data_mining()
        print("Using data mining workload distribution")
    elif args.workload == 'cache':
        flow_size_gen = FlowSizeGenerators.cache_follower()
        print("Using cache follower workload distribution")
        
    # Pre-compute paths for all pairs
    print("Pre-computing network paths...")
    net_paths = {}
    for i in range(no_of_nodes):
        net_paths[i] = {}
        for j in range(no_of_nodes):
            if i != j:
                paths = topology.get_bidir_paths(i, j, False)
                if paths:
                    net_paths[i][j] = paths
                    
    # TCP generator function that captures necessary variables
    def tcp_gen_closure(src: int, dst: int, flow_size: int):
        tcp_src = TcpSrc(None, None, eventlist)
        tcp_sink = TcpSink()
        
        # Set flow size
        tcp_src.set_flowsize(flow_size)
        
        # Register with scanner
        tcp_rtx_scanner.registerTcp(tcp_src)
        
        return tcp_src, tcp_sink
    
    # Create short flows generator
    print(f"Creating short flows generator with λ={args.lambda_rate} flows/sec")
    short_flows = ShortFlows(
        lambda_rate=args.lambda_rate,
        eventlist=eventlist,
        net_paths=net_paths,
        connection_matrix=conn_matrix,
        logfile=logfile,
        tcp_generator=tcp_gen_closure,
        flow_size_generator=flow_size_gen
    )
    
    # Run simulation
    print(f"Running simulation for {args.time} seconds...")
    
    last_print_time = 0
    print_interval = timeFromSec(0.1)  # Print every 100ms
    
    while eventlist.doNextEvent():
        current_time = eventlist.now()
        
        # Periodic status update
        if current_time - last_print_time > print_interval:
            stats = short_flows.get_stats()
            print(f"Time: {current_time/1e12:.3f}s - "
                  f"Created: {stats['total_created']} flows, "
                  f"Started: {stats['total_started']} flows")
            last_print_time = current_time
            
    print("\nSimulation complete!")
    
    # Print final statistics
    stats = short_flows.get_stats()
    print("\n=== Short Flows Statistics ===")
    print(f"Total flows created: {stats['total_created']}")
    print(f"Total flows started: {stats['total_started']}")
    print(f"Connection pairs: {stats['connection_pairs']}")
    print(f"Simulation time: {eventlist.now() / 1e12:.3f} seconds")
    print(f"Effective arrival rate: {stats['total_started'] / (eventlist.now() / 1e12):.2f} flows/sec")
    
    # Print workload statistics
    if args.workload != 'fixed':
        print(f"\nWorkload: {args.workload}")
        print("Flow size distribution will vary based on workload type")
        
    print(f"\nCheck {args.output} for detailed logs")


if __name__ == "__main__":
    main()