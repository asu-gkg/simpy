#!/usr/bin/env python3
"""
SimAI astrasim Python implementation - Main entry point
Supports different network backends: analytical, ns3, phynet
"""

import argparse
import sys


def parse_arguments():
    """Parse command line arguments using argparse"""
    parser = argparse.ArgumentParser(description="SimAI astrasim Python implementation")
    
    # 后端选择
    parser.add_argument("--backend", "-b", type=str, default="analytical",
                        choices=["analytical", "ns3", "phynet"],
                        help="Network backend: analytical, ns3, or phynet")
    
    # 其他参数
    parser.add_argument("-w", "--workload", type=str, help="Workload file")
    parser.add_argument("-g", "--gpus", type=int, default=1, help="Number of GPUs")
    parser.add_argument("-r", "--result", type=str, default="None", help="Result file")
    parser.add_argument("--gpus-per-server", "-g_p_s", type=int, default=1, help="GPUs per server")
    parser.add_argument("--gpu_type", "-g_type", type=str, default="A100", help="GPU type")
    parser.add_argument("-s", "--comm_scale", type=float, default=1.0, help="Communication scale")
    parser.add_argument("-i", "--gid_index", type=int, default=0, help="GPU ID index")
    parser.add_argument("-n", "--network_topo", type=str, default="", help="Network topology")
    parser.add_argument("-c", "--network_conf", type=str, default="", help="Network configuration")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")
    
    return parser.parse_args()


def run_backend(args):
    """Run the specified backend"""
    if args.backend == "analytical":
        from network_frontend.analytical.analytical_astra import main as backend_main
    elif args.backend == "ns3":
        from network_frontend.ns3.AstraSimNetwork import main as backend_main
    elif args.backend == "phynet":
        from network_frontend.phynet.sim_ai_main import main as backend_main
    else:
        print(f"Unknown backend: {args.backend}")
        sys.exit(1)
    
    backend_main(args)


def main():
    """Main function - dispatches to appropriate backend"""
    args = parse_arguments()
    run_backend(args)


if __name__ == "__main__":
    main() 