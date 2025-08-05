"""
Topology comparison example for data center networks

This example demonstrates:
- Different datacenter topologies (Fat-tree, VL2, BCube, DragonFly)
- Topology characteristics and path diversity
- Performance comparison under same workload

Corresponds to topology comparison examples in HTSim
"""

import sys
import random
import argparse
from typing import Dict, List, Type

# Add parent directory to path
sys.path.append('../../../')

from htsimpy.core.eventlist import EventList
from htsimpy.core.logger.logfile import Logfile
from htsimpy.core.logger.loggers import TcpLoggerSimple
from htsimpy.protocols.tcp import TcpSrc, TcpSink, TcpRtxTimerScanner
from htsimpy.datacenter import (
    Topology, FatTreeTopology, VL2Topology, BCubeTopology,
    DragonFlyTopology, StarTopology, ConnectionMatrix,
    QueueType, PACKET_SIZE
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


def analyze_topology(topology: Topology, name: str):
    """Analyze and print topology characteristics"""
    print(f"\n=== {name} Topology Analysis ===")
    
    n = topology.no_of_nodes()
    print(f"Number of nodes: {n}")
    
    # Sample path diversity
    sample_pairs = min(10, n // 2)
    total_paths = 0
    min_paths = float('inf')
    max_paths = 0
    avg_path_length = 0
    path_count = 0
    
    for i in range(sample_pairs):
        src = random.randint(0, n - 1)
        dst = random.randint(0, n - 1)
        if src == dst:
            continue
            
        paths = topology.get_bidir_paths(src, dst, False)
        if paths:
            num_paths = len(paths)
            total_paths += num_paths
            min_paths = min(min_paths, num_paths)
            max_paths = max(max_paths, num_paths)
            
            # Average path length
            for path in paths:
                avg_path_length += len(path._elements)
                path_count += 1
                
    if sample_pairs > 0:
        print(f"Path diversity (sampled {sample_pairs} pairs):")
        print(f"  Min paths: {min_paths}")
        print(f"  Max paths: {max_paths}")
        print(f"  Avg paths: {total_paths / sample_pairs:.1f}")
        
    if path_count > 0:
        print(f"  Avg path length: {avg_path_length / path_count:.1f} hops")


def create_topology(topo_type: str, eventlist: EventList, 
                   logfile: Logfile, nodes: int,
                   linkspeed: int) -> Topology:
    """Create a topology based on type"""
    
    if topo_type == "fattree":
        # Find appropriate k for fat-tree
        k = 4
        while k * k * k // 4 < nodes:
            k += 2
        return FatTreeTopology(
            logfile=logfile,
            eventlist=eventlist,
            k=k,
            queue_type=QueueType.RANDOM,
            link_speed=linkspeed
        )
        
    elif topo_type == "vl2":
        # VL2 parameters (simplified)
        return VL2Topology(
            logfile=logfile,
            eventlist=eventlist,
            link_speed=linkspeed
        )
        
    elif topo_type == "bcube":
        # BCube parameters
        # Find suitable parameters
        k = 1  # levels
        n = 4  # ports per switch
        while n ** (k + 1) < nodes:
            if n < 8:
                n *= 2
            else:
                k += 1
                n = 4
        return BCubeTopology(
            logfile=logfile,
            eventlist=eventlist,
            no_of_nodes=n ** (k + 1),
            ports_per_switch=n,
            no_of_levels=k,
            link_speed=linkspeed
        )
        
    elif topo_type == "dragonfly":
        return DragonFlyTopology(
            logfile=logfile,
            eventlist=eventlist,
            no_of_nodes=nodes,
            queue_type=QueueType.RANDOM,
            link_speed=linkspeed
        )
        
    elif topo_type == "star":
        return StarTopology(
            logfile=logfile,
            eventlist=eventlist,
            n_hosts=nodes,
            link_speed=linkspeed
        )
        
    else:
        raise ValueError(f"Unknown topology type: {topo_type}")


def run_workload(topology: Topology, eventlist: EventList, 
                logfile: Logfile, tcp_rtx_scanner: TcpRtxTimerScanner,
                pattern: str, num_flows: int) -> Dict[str, float]:
    """Run a workload on the topology and collect metrics"""
    
    n = topology.no_of_nodes()
    
    # Create connection matrix
    conn_matrix = ConnectionMatrix(n)
    
    if pattern == "permutation":
        conn_matrix.setPermutation(min(num_flows, n))
    elif pattern == "random":
        conn_matrix.setRandom(num_flows)
    elif pattern == "incast":
        # Incast to node 0
        for i in range(1, min(num_flows + 1, n)):
            conn_matrix.add_connection(i, 0)
            
    # Create flows
    flow_count = 0
    tcp_sources = []
    
    for src, destinations in conn_matrix.connections.items():
        for dst in destinations:
            # Get paths
            paths = topology.get_bidir_paths(src, dst, False)
            if not paths:
                continue
                
            # Create TCP flow
            tcp_src = TcpSrc(None, None, eventlist)
            tcp_sink = TcpSink()
            
            tcp_src.setName(f"tcp_{src}_to_{dst}")
            tcp_sink.setName(f"tcp_sink_{src}_to_{dst}")
            
            logfile.write_name(tcp_src)
            logfile.write_name(tcp_sink)
            
            tcp_rtx_scanner.registerTcp(tcp_src)
            tcp_sources.append(tcp_src)
            
            # Choose shortest path
            shortest = min(paths, key=lambda p: len(p._elements))
            
            # Create routes
            route_out = Route()
            for element in shortest._elements:
                route_out.push_back(element)
                
            route_in = Route()
            route_in.push_back(tcp_src)
            
            # Connect
            tcp_src.connect(route_out, route_in, tcp_sink, 0)
            flow_count += 1
            
    # Collect initial metrics
    start_time = eventlist.now()
    
    # Run for a fixed duration
    run_duration = timeFromMs(100)  # 100ms
    end_time = start_time + run_duration
    
    while eventlist.now() < end_time and eventlist.doNextEvent():
        pass
        
    # Calculate metrics
    total_bytes = sum(src._last_acked for src in tcp_sources)
    duration = (eventlist.now() - start_time) / 1e12  # Convert to seconds
    
    metrics = {
        'flows': flow_count,
        'total_bytes': total_bytes,
        'duration': duration,
        'throughput_gbps': (total_bytes * 8 / 1e9) / duration if duration > 0 else 0
    }
    
    return metrics


def main():
    """Main simulation function"""
    
    # Parse arguments
    parser = argparse.ArgumentParser(description='Topology Comparison')
    parser.add_argument('-o', '--output', default='logout_topologies.dat',
                       help='Output log file prefix')
    parser.add_argument('-n', '--nodes', type=int, default=64,
                       help='Target number of nodes')
    parser.add_argument('--pattern', type=str, default='permutation',
                       choices=['permutation', 'random', 'incast'],
                       help='Traffic pattern')
    parser.add_argument('--flows', type=int, default=32,
                       help='Number of flows')
    parser.add_argument('--linkspeed', type=int, default=10000,
                       help='Link speed in Mbps')
    parser.add_argument('--topologies', nargs='+',
                       default=['fattree', 'star'],
                       choices=['fattree', 'vl2', 'bcube', 'dragonfly', 'star'],
                       help='Topologies to compare')
    
    args = parser.parse_args()
    
    print("=== Datacenter Topology Comparison ===")
    print(f"Target nodes: {args.nodes}")
    print(f"Traffic pattern: {args.pattern}")
    print(f"Number of flows: {args.flows}")
    print(f"Link speed: {args.linkspeed} Mbps")
    print(f"Topologies: {', '.join(args.topologies)}")
    
    linkspeed = speedFromMbps(args.linkspeed)
    results = {}
    
    # Test each topology
    for topo_name in args.topologies:
        print(f"\n{'='*50}")
        print(f"Testing {topo_name.upper()} topology")
        print(f"{'='*50}")
        
        # Create event list
        eventlist = EventList()
        eventlist.setEndtime(timeFromSec(1.0))
        
        # Create logfile
        logfile_name = f"{args.output}_{topo_name}"
        logfile = Logfile(logfile_name, eventlist)
        
        # Add logger
        tcp_logger = TcpLoggerSimple()
        logfile.addLogger(tcp_logger)
        
        # Create RTX scanner
        tcp_rtx_scanner = TcpRtxTimerScanner(timeFromMs(10), eventlist)
        
        try:
            # Create topology
            topology = create_topology(topo_name, eventlist, logfile,
                                     args.nodes, linkspeed)
            
            # Analyze topology
            analyze_topology(topology, topo_name.upper())
            
            # Run workload
            print(f"\nRunning {args.pattern} workload...")
            metrics = run_workload(topology, eventlist, logfile,
                                 tcp_rtx_scanner, args.pattern, args.flows)
            
            results[topo_name] = metrics
            
            print(f"\nResults for {topo_name}:")
            print(f"  Flows created: {metrics['flows']}")
            print(f"  Total data: {metrics['total_bytes']/1e6:.1f} MB")
            print(f"  Duration: {metrics['duration']:.3f} s")
            print(f"  Throughput: {metrics['throughput_gbps']:.2f} Gbps")
            
        except Exception as e:
            print(f"Error with {topo_name}: {e}")
            results[topo_name] = {'error': str(e)}
            
    # Summary comparison
    print(f"\n{'='*50}")
    print("SUMMARY COMPARISON")
    print(f"{'='*50}")
    
    print(f"\n{'Topology':<12} {'Flows':<8} {'Throughput (Gbps)':<18}")
    print(f"{'-'*40}")
    
    for topo, metrics in results.items():
        if 'error' in metrics:
            print(f"{topo:<12} {'ERROR':<8} {metrics['error']}")
        else:
            print(f"{topo:<12} {metrics['flows']:<8} "
                  f"{metrics['throughput_gbps']:<18.2f}")
            
    # Find best performer
    valid_results = {k: v for k, v in results.items() if 'error' not in v}
    if valid_results:
        best = max(valid_results.items(), 
                  key=lambda x: x[1]['throughput_gbps'])
        print(f"\nBest throughput: {best[0]} "
              f"({best[1]['throughput_gbps']:.2f} Gbps)")


if __name__ == "__main__":
    main()