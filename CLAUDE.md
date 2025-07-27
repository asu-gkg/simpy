# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This repository contains a Python port of the SimAI (Simulator for AI) project, specifically the AstraSim component. SimAI is a full-stack simulator for AI/ML training workloads that models the entire training process including framework, collective communication, and network layers.

The codebase is structured as both:
1. The original C++ SimAI implementation located in `SimAI/` directory
2. A Python/SimPy port being developed in the root directory

## Key Architecture Components

### Python Port Structure
- `system/` - Core system simulation classes (Sys, streams, collective operations)
- `network_frontend/` - Network simulation backends (analytical, ns3, phynet)
- `workload/` - Workload parsing and layer management
- `main.py` - Entry point that dispatches to different backends

### C++ Original Structure (SimAI/)
- `astra-sim-alibabacloud/` - Core AstraSim implementation
- `ns-3-alibabacloud/` - NS-3 network simulator integration
- `aicb/` - AI Communication Benchmark tool
- `SimCCL/` - Collective communication library

## Common Development Commands

### Building the C++ Version
```bash
# Build SimAI-Analytical (fast simulation)
./SimAI/scripts/build.sh -c analytical

# Build SimAI-Simulation with NS-3 (detailed simulation)
./SimAI/scripts/build.sh -c ns3

# Build SimAI-Physical (RDMA traffic generation)
./SimAI/scripts/build.sh -c phy

# Clean build artifacts
./SimAI/scripts/build.sh -l analytical
```

### Running Simulations
```bash
# Run analytical simulation
./bin/SimAI_analytical -w example/workload_analytical.txt -g 9216 -g_p_s 8 -r test- -busbw example/busbw.yaml

# Run NS-3 simulation
AS_SEND_LAT=3 AS_NVLS_ENABLE=1 ./bin/SimAI_simulator -t 16 -w ./example/microAllReduce.txt -n ./Spectrum-X_128g_8gps_100Gbps_A100 -c astra-sim-alibabacloud/inputs/config/SimAI.conf

# Generate network topology
python3 ./SimAI/astra-sim-alibabacloud/inputs/topo/gen_Topo_Template.py -topo Spectrum-X -g 128 -gt A100 -bw 100Gbps -nvbw 2400Gbps
```

### Python Port Commands
```bash
# Run Python version with analytical backend
uv run main.py --backend analytical -w examples/workload_analytical.txt -g 8
uv run main.py --backend analytical -w examples/microAllReduce.txt -g 8

# Run Python version with ns3 backend
uv run main.py --backend ns3 -w examples/microAllReduce.txt -n topo_file.txt

# Run Python version with phynet backend
uv run main.py --backend phynet -w example/microAllReduce.txt -g 2
```

## Important Implementation Notes

### Current Porting Status
The Python port is in progress. Key files that have been ported include:
- `system/sys.py` - Main system class (corresponds to Sys.cc/Sys.hh)
- `system/collective/` - Collective communication algorithms
- `network_frontend/analytical/` - Analytical network backend
- `workload/` - Workload parsing and management

### Key Differences in Python Port
1. Memory management is handled automatically by Python
2. C++ pointers are replaced with Python object references
3. Static class variables require careful handling in Python
4. Event scheduling uses SimPy's discrete event simulation framework

### Environment Variables
- `AS_LOG_LEVEL` - Set logging level (DEBUG, INFO, WARNING, ERROR)
- `AS_PXN_ENABLE` - Enable PXN (0/1)
- `AS_NVLS_ENABLE` - Enable NVLS (0/1)
- `AS_SEND_LAT` - Set packet sending latency in microseconds
- `AS_NVLSTREE_ENABLE` - Enable NVLS Tree

### Testing Approach
Since there's no explicit test framework visible, testing is done through:
1. Running example workloads and comparing outputs
2. Verifying functional parity between C++ and Python implementations
3. Checking simulation results match expected behavior

## Architecture Overview

The simulator operates in three main modes:

1. **Analytical Mode** - Fast simulation using bus bandwidth abstractions
2. **Simulation Mode** - Detailed network simulation using NS-3
3. **Physical Mode** - Real RDMA traffic generation (beta)

Key simulation flow:
1. Parse workload file defining AI model layers and communication patterns
2. Generate collective communication operations (AllReduce, AllGather, etc.)
3. Schedule and execute operations through chosen network backend
4. Collect performance metrics and generate results

The system supports various parallel strategies (TP, DP, EP, PP) and collective algorithms (Ring, Tree, Halving-Doubling, NCCL flow models).