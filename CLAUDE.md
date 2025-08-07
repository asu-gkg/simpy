# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

SimPy is a Python implementation of SimAI, a comprehensive large-scale AI training simulation toolkit. It provides network simulation capabilities for distributed AI training workloads with three main backends:
- **Analytical**: Fast analytical simulation using bus bandwidth abstractions
- **NS3**: High-fidelity network simulation using NS-3 Python bindings  
- **HTSimPy**: Pure Python implementation of the htsim network simulator
- **PhyNet**: Physical network backend (experimental)

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

# Run with HTSimPy backend
uv run python main.py --backend htsimpy -w examples/microAllReduce.txt -n examples/topo_8gpu.txt -g 8

# Run HTSimPy examples directly
uv run python network_frontend/htsimpy/examples/04_tcp_example/main.py
timeout 10 uv run python network_frontend/htsimpy/examples/05_mptcp_example/main.py

# Run with specific arguments
uv run python main.py -g 8 --gpus-per-server 4 --gpu_type A100 -s 1.0 -i 0 --verbose
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
uv run pytest --cov-report=html --cov-report=term-missing

# Run HTSimPy test comparisons with C++
make -f Makefile  # Build C++ comparison tests
./test_cpp_comparison
uv run python test_python_datacenter.py
```

### Code Quality
```bash
# Format code
uv run black simpy/ system/ workload/ network_frontend/
uv run isort simpy/ system/ workload/ network_frontend/

# Type checking
uv run mypy simpy/ system/ workload/ network_frontend/

# Pre-commit hooks (if installed)
uv run pre-commit install
uv run pre-commit run --all-files
```

## Code Architecture

### Core Design Patterns

1. **Event-Driven Simulation**: 
   - Central `EventList` singleton manages discrete event scheduling
   - All components inherit from `EventSource` to participate in simulation
   - Events are scheduled with microsecond precision timestamps

2. **C++ Compatibility**:
   - Python implementations precisely mirror C++ SimAI/AstraSim interfaces
   - Maintains same class hierarchies and method signatures
   - Uses integer timestamps (SimTime = int) for microsecond precision

3. **Network Abstraction**:
   - Common `AstraNetworkAPI` interface for all backends
   - Backends handle packet-level or analytical simulation
   - Support for different queue types (FIFO, Priority, Lossless, ECN)

### Key Implementation Details

**HTSimPy Backend Architecture**:
- `EventList`: Global event scheduler using handle-based cancellation
- `Packet` hierarchy: TCP, NDP packets with proper header/payload separation  
- `Queue` types: FIFO, CompositePrioQueue, LosslessInput/Output queues
- `Topology` classes: FatTree, VL2, BCube, DragonFly implementations
- Logging system: Structured logging matching C++ output format

**System Layer**:
- `Sys` class: Main simulation controller managing NPUs
- Stream-based execution with dependency tracking
- MockNccl: NCCL-compatible collective implementation
- Queue levels: Compute, Memory, Network, Collective queues

**Workload Processing**:
- Parses AICB workload format
- Supports TP/EP/PP/DP/SP parallelism strategies
- Layer-based execution with communication patterns

### Important Implementation Notes

- Thread safety via `threading.RLock` for concurrent operations
- NS3 backend requires NS3 Python bindings (pip or source)
- HTSimPy uses pure Python without external dependencies
- Circular buffer implementation for packet reordering
- Queue enum values must match C++ (e.g., LOSSLESS_INPUT = 3)
- Fat tree routing uses deterministic inter-pod paths for consistency