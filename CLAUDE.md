# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This repository contains a Python port of the SimAI (Simulator for AI) project, specifically the AstraSim component. SimAI is a full-stack simulator for AI/ML training workloads that models the entire training process including framework, collective communication, and network layers.

The codebase is structured as both:
1. The original C++ SimAI implementation located in `SimAI/` directory
2. A Python/SimPy port being developed in the root directory
3. HTSim network simulator integration in `network_frontend/htsimpy/`

## Key Architecture Components

### Python Port Structure
- `system/` - Core system simulation classes (Sys, streams, collective operations)
  - `sys.py` - Main system class managing GPU simulation
  - `collective/` - Collective communication algorithms (Ring, Tree, Halving-Doubling, etc.)
  - `topology/` - Network topology abstractions
  - `memory/` - Memory subsystem simulation
- `network_frontend/` - Network simulation backends
  - `analytical/` - Fast analytical network simulation
  - `ns3/` - NS-3 network simulator integration
  - `phynet/` - Physical network emulation
  - `htsimpy/` - HTSim-based packet-level simulation
- `workload/` - Workload parsing and layer management
  - `workload.py` - Main workload class
  - `layer.py` - Individual layer representation
- `main.py` - Entry point that dispatches to different backends

### C++ Original Structure (SimAI/)
- `astra-sim-alibabacloud/` - Core AstraSim implementation
- `ns-3-alibabacloud/` - NS-3 network simulator integration
- `aicb/` - AI Communication Benchmark tool
- `SimCCL/` - Collective communication library

## Common Development Commands

### Python Environment Setup
```bash
# Install uv (fast Python package manager)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create virtual environment
uv venv --python 3.11

# Activate environment
source .venv/bin/activate

# Install dependencies
uv pip install -e .  # Basic install
uv pip install -e ".[ns3]"  # With NS3 support
uv pip install -e ".[dev,ns3]"  # Development environment
```

### Running Python Simulations
```bash
# Run with analytical backend (fastest)
uv run main.py --backend analytical -w examples/workload_analytical.txt -g 8
uv run main.py --backend analytical -w examples/microAllReduce.txt -g 8

# Run with ns3 backend (detailed network simulation)
uv run main.py --backend ns3 -w examples/microAllReduce.txt -n examples/topo_8gpu.txt -c examples/network.conf

# Run with phynet backend (physical network emulation)
uv run main.py --backend phynet -w examples/microAllReduce.txt -g 2

# Run with verbose output
uv run main.py --backend analytical -w examples/workload_analytical.txt -g 8 --verbose
```

### Development Commands
```bash
# Code formatting
uv run black system/ workload/ network_frontend/
uv run isort system/ workload/ network_frontend/

# Type checking
uv run mypy system/ workload/ network_frontend/

# Run tests
uv run pytest  # Run all tests
uv run pytest -m "not ns3"  # Skip NS3 tests
uv run pytest -m "ns3"  # Only NS3 tests
uv run pytest --cov  # With coverage

# Run specific test files
uv run pytest test_ns3.py
uv run pytest test_ns3_backend.py
```

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

### Running C++ Simulations
```bash
# Run analytical simulation
./bin/SimAI_analytical -w example/workload_analytical.txt -g 9216 -g_p_s 8 -r test- -busbw example/busbw.yaml

# Run NS-3 simulation
AS_SEND_LAT=3 AS_NVLS_ENABLE=1 ./bin/SimAI_simulator -t 16 -w ./example/microAllReduce.txt -n ./Spectrum-X_128g_8gps_100Gbps_A100 -c astra-sim-alibabacloud/inputs/config/SimAI.conf

# Generate network topology
python3 ./SimAI/astra-sim-alibabacloud/inputs/topo/gen_Topo_Template.py -topo Spectrum-X -g 128 -gt A100 -bw 100Gbps -nvbw 2400Gbps
```

## Important Implementation Notes

### Current Porting Status
The Python port is actively being developed with focus on functional parity with the C++ version. Key components ported:
- `system/sys.py` - Main system class (corresponds to Sys.cc/Sys.hh)
- `system/collective/` - All major collective algorithms
- `network_frontend/analytical/` - Analytical network backend (fully functional)
- `network_frontend/ns3/` - NS3 integration (requires NS3 installation)
- `workload/` - Complete workload parsing and management

### Key Differences in Python Port
1. Memory management is handled automatically by Python
2. C++ pointers are replaced with Python object references
3. Static class variables require careful handling in Python
4. Event scheduling uses SimPy's discrete event simulation framework
5. Thread safety implemented using Python's threading.RLock

### Environment Variables
- `AS_LOG_LEVEL` - Set logging level (DEBUG, INFO, WARNING, ERROR)
- `AS_PXN_ENABLE` - Enable PXN (0/1)
- `AS_NVLS_ENABLE` - Enable NVLS (0/1)
- `AS_SEND_LAT` - Set packet sending latency in microseconds
- `AS_NVLSTREE_ENABLE` - Enable NVLS Tree
- `OPENBLAS_NUM_THREADS` - Set to 1 to avoid conflicts with cppyy

### Testing Approach
The project uses pytest for testing with the following test categories:
- Unit tests for individual components
- Integration tests for system behavior
- NS3-specific tests (marked with `@pytest.mark.ns3`)
- Comparison tests between Python and C++ implementations

Test files are located in the root directory:
- `test_ns3.py` - Basic NS3 functionality tests
- `test_ns3_backend.py` - NS3 backend integration tests

## Architecture Overview

The simulator operates in three main modes:

1. **Analytical Mode** - Fast simulation using bus bandwidth abstractions
   - Best for quick design space exploration
   - Uses simplified network models
   - Fastest execution time

2. **Simulation Mode** - Detailed network simulation using NS-3 or HTSim
   - Packet-level simulation accuracy
   - Supports various network topologies
   - Slower but more accurate

3. **Physical Mode** - Real RDMA traffic generation (beta)
   - Actual network traffic generation
   - For validation on real hardware

### Key Simulation Flow
1. Parse workload file defining AI model layers and communication patterns
2. Generate collective communication operations (AllReduce, AllGather, etc.)
3. Schedule operations based on dependencies and resource availability
4. Execute operations through chosen network backend
5. Collect performance metrics and generate results

### Supported Features
- **Parallel Strategies**: TP (Tensor Parallel), DP (Data Parallel), EP (Expert Parallel), PP (Pipeline Parallel)
- **Collective Algorithms**: Ring, Tree, Halving-Doubling, NCCL flow models, Double Binary Tree
- **Network Topologies**: Fat-tree, Torus, Dragonfly, custom topologies via configuration
- **Workload Formats**: Compatible with existing SimAI workload files
- **Output Formats**: CSV results, detailed logs, performance metrics

### Performance Optimization Tips
1. Use analytical backend for initial exploration
2. Enable only necessary logging levels
3. Consider using `uv` for faster Python package management
4. For NS3 simulations, compile NS3 with optimization flags
5. Use appropriate parallelism settings based on workload characteristics