#!/usr/bin/env python3
"""
SimAI Physical Network Main - corresponds to SimAiMain.cc in SimAI
"""

import argparse
import sys
from pathlib import Path

from system.sys import Sys
from workload.workload import Workload
from system.param_parser import ParamParser
from network_frontend.phynet.sim_ai_phy_network import SimAiPhyNetwork


def parse_arguments():
    """Parse command line arguments for phynet backend"""
    parser = argparse.ArgumentParser(description="SimAI Physical Network Backend")
    
    # Core parameters (following SimAI phynet format)
    parser.add_argument("-w", "--workload", type=str, required=True,
                       help="Workload file path")
    parser.add_argument("-g", "--gpus", type=int, default=1,
                       help="Number of GPUs, default 1")
    parser.add_argument("-s", "--comm_scale", type=float, default=1.0,
                       help="Communication scale default 1")
    parser.add_argument("-i", "--gid_index", type=int, default=0,
                       help="RDMA GID index default 0")
    parser.add_argument("-t", "--thread", type=int, default=1,
                       help="Number of threads")
    
    # Other options
    parser.add_argument("--verbose", action="store_true",
                       help="Enable verbose output")
    
    return parser.parse_args()


def main(args=None):
    """Main function for phynet backend - corresponds to main() in SimAiMain.cc"""
    if args is None:
        args = parse_arguments()
    
    # Initialize parameter parser
    param_parser = ParamParser()
    
    # Parse parameters into config
    config = param_parser.parse_args(args)
    config.mode = "PHYNET"  # Set mode to phynet
    
    # Load workload
    workload = Workload()
    workload.load_from_file(args.workload)
    
    # Initialize physical network
    phy_network = SimAiPhyNetwork(0)  # local_rank = 0
    
    # Initialize system with physical network
    system = Sys(config, network=phy_network,
                comm_scale=args.comm_scale,
                gid_index=args.gid_index)
    
    # Create output directory
    workload_name = Path(args.workload).stem
    output_dir = Path(f"results/phynet/{workload_name}")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    if args.verbose:
        print(f"Starting Physical Network Backend")
        print(f"Workload: {args.workload}")
        print(f"GPUs: {args.gpus}")
        print(f"Comm scale: {args.comm_scale}")
        print(f"GID index: {args.gid_index}")
    
    # Run simulation
    results = system.run_simulation(workload)
    system.save_results(results, output_dir)
    
    print("Physical network simulation completed")


if __name__ == "__main__":
    main() 