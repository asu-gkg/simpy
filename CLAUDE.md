# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

SimPy is a Python implementation of SimAI, a comprehensive large-scale AI training simulation toolkit. It provides network simulation capabilities for distributed AI training workloads with three main backends:
- **Analytical**: Fast analytical simulation using bus bandwidth abstractions
- **NS3**: High-fidelity network simulation using NS-3 Python bindings
- **HTSimPy**: Pure Python implementation of the htsim network simulator

## Common Development Commands

### Environment Setup
```bash
# Create virtual environment with uv (recommended)
uv venv --python 3.11
source .venv/bin/activate

# Install dependencies
uv pip install -e .                    # Basic installation
uv pip install -e ".[ns3]"            # With NS3 support
uv pip install -e ".[dev,ns3]"        # Development environment
```

### Running Simulations
```bash
# Run with analytical backend (default)
uv run python main.py -w examples/workload_analytical.txt -n examples/busbw.yaml

# Run with NS3 backend
uv run python main.py --backend ns3 -w examples/workload_analytical.txt -c examples/network.conf

# Run with specific network topology
uv run python main.py -w examples/microAllReduce.txt -n examples/topo_8gpu.txt -g 8
```

### Testing
```bash
# Run all tests
uv run pytest

# Run specific test file
uv run python -m pytest network_frontend/htsimpy/tests/test_eventlist.py -v

# Run tests without NS3 requirement
uv run pytest -m "not ns3"

# Run with coverage
uv run pytest --cov-report=html
```

### Code Quality
```bash
# Format code
uv run black simpy/ system/ workload/ network_frontend/
uv run isort simpy/ system/ workload/ network_frontend/

# Type checking
uv run mypy simpy/ system/ workload/ network_frontend/
```

## Code Architecture

### Directory Structure
- `main.py`: Main entry point that dispatches to different backends
- `network_frontend/`: Network simulation backends
  - `analytical/`: Fast analytical simulation implementation
  - `ns3/`: NS-3 Python binding wrapper (AstraSimNetwork)
  - `htsimpy/`: Pure Python implementation of htsim
- `system/`: Core simulation system components
  - `sys.py`: Main system class managing NPUs and simulation
  - `collective/`: Collective communication algorithms (Ring, AllToAll, etc.)
  - `topology/`: Network topology implementations
- `workload/`: Workload parsing and layer management
- `SimAI/`: Reference C++ implementation (read-only)

### Key Components

1. **EventList (htsimpy)**: Core event-driven simulation engine
   - Singleton pattern for global time management
   - Handle-based event scheduling
   - Support for cancellation and rescheduling

2. **Network Backends**:
   - Analytical: Uses bus bandwidth calculations from busbw.yaml
   - NS3: Integrates with NS-3 for packet-level simulation
   - HTSimPy: Pure Python TCP/network simulation

3. **System Architecture**:
   - NPU abstraction with queues for compute/memory/network
   - Stream-based scheduling with dependencies
   - MockNccl for NCCL-compatible collective operations

4. **Workload Processing**:
   - Parses AICB-generated workload files
   - Supports various parallelism strategies (TP/EP/PP/DP)
   - Layer-based execution with communication patterns

### Important Implementation Notes

- The project is a Python port of the C++ SimAI/AstraSim codebase
- Maintains compatibility with C++ interfaces and behavior
- Uses threading locks (RLock) for thread-safe operations
- NS3 backend requires either pip wheel or source compilation
- Event timestamps use integer microseconds (SimTime = int)