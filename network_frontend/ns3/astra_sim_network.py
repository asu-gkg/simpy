#!/usr/bin/env python3
"""
AstraSim Network for NS3 - corresponds to AstraSimNetwork.cc in SimAI
"""

import argparse
import sys
from pathlib import Path

from system.sys import Sys
from workload.workload import Workload
from system.param_parser import ParamParser
from network_frontend.ns3.astra_sim_network import ASTRASimNetwork


def parse_arguments():
    """Parse command line arguments for NS3 backend"""
    parser = argparse.ArgumentParser(description="SimAI NS3 Network Backend")
    
    # Core parameters (following SimAI NS3 format)
    parser.add_argument("-w", "--workload", type=str, required=True,
                       help="Workload file path")
    parser.add_argument("-t", "--thread", type=int, default=1,
                       help="Number of threads")
    parser.add_argument("-n", "--network_topo", type=str, required=True,
                       help="Network topology file")
    parser.add_argument("-c", "--network_conf", type=str, required=True,
                       help="Network configuration file")
    
    # Other options
    parser.add_argument("--verbose", action="store_true",
                       help="Enable verbose output")
    
    return parser.parse_args()


def main(args=None):
    """Main function for NS3 backend - corresponds to main() in AstraSimNetwork.cc"""
    if args is None:
        args = parse_arguments()
    
    # Initialize parameter parser
    param_parser = ParamParser()
    
    # Parse parameters into config
    config = param_parser.parse_args(args)
    config.mode = "NS3"  # Set mode to NS3
    
    # Load workload
    workload = Workload()
    workload.load_from_file(args.workload)
    
    # Initialize NS3 network
    ns3_network = ASTRASimNetwork(0, 0)
    
    # Initialize system with NS3 network
    system = Sys(config, network=ns3_network,
                network_topo=args.network_topo,
                network_conf=args.network_conf)
    
    # Create output directory
    workload_name = Path(args.workload).stem
    output_dir = Path(f"results/ns3/{workload_name}")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    if args.verbose:
        print(f"Starting NS3 Network Backend")
        print(f"Workload: {args.workload}")
        print(f"Network topology: {args.network_topo}")
        print(f"Network config: {args.network_conf}")
    
    # Run simulation
    results = system.run_simulation(workload)
    system.save_results(results, output_dir)
    
    print("NS3 simulation completed")


if __name__ == "__main__":
    main()