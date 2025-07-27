#!/usr/bin/env python3
"""
AstraSimNetwork.py - corresponds to AstraSimNetwork.cc in SimAI NS3

Main network API implementation class for NS3 backend
"""

from __future__ import annotations
import sys
import threading
from typing import Optional, Callable, Any, List
from dataclasses import dataclass
from queue import Queue

from system.AstraNetworkAPI import AstraNetworkAPI, TimeSpec, SimComm, SimRequest, BackendType
from .common import ns, NS3_AVAILABLE, RESULT_PATH
from .entry import (
    task1, SendFlow, RecvFlow, receiver_pending_queue, sender_src_port_map,
    expeRecvHash, recvHash, sentHash, nodeHash, safe_hash_get, safe_hash_set, safe_hash_del
)

# sim_event structure (same as C++ struct sim_event)
@dataclass
class sim_event:
    """Corresponds to C++ struct sim_event"""
    buffer: Any = None  # void* in C++
    count: int = 0  # uint64_t in C++
    type: int = 0
    dst: int = 0
    tag: int = 0
    fnType: str = ""

class ASTRASimNetwork(AstraNetworkAPI):
    """
    Main NS3 network implementation class
    Corresponds to C++ class ASTRASimNetwork : public AstraSim::AstraNetworkAPI
    """
    
    def __init__(self, rank: int, npu_offset: int = 0):
        """
        Initialize ASTRASimNetwork
        
        Args:
            rank: Network rank (same as C++)
            npu_offset: NPU offset (same as C++)
        """
        super().__init__(rank)
        self.npu_offset = npu_offset
        self.sim_event_queue: Queue[sim_event] = Queue()  # corresponds to queue<sim_event>
        
    def __del__(self):
        """Destructor (corresponds to C++ ~ASTRASimNetwork())"""
        # Cleanup if needed
        pass
    
    def get_backend_type(self) -> BackendType:
        """Get backend type - NS3"""
        return BackendType.NS3
    
    def sim_comm_size(self, comm: SimComm, size: List[int]) -> int:
        """
        Get communication size (corresponds to C++ sim_comm_size)
        
        Args:
            comm: Communication object
            size: Output list to store size
            
        Returns:
            0 for success
        """
        # TODO: Implement actual communication size logic
        return 0
    
    def sim_finish(self) -> int:
        """
        Finish simulation (corresponds to C++ sim_finish)
        
        Returns:
            0 for success
        """
        import os
        import threading
        
        # Print statistics like C++ version
        for key, value in nodeHash.items():
            pair_key = key  # (int, int)
            if pair_key[1] == 0:
                print(f"sim_finish on sent, Thread id: {threading.get_ident()}")
                print(f"All data sent from node {pair_key[0]} is {value}")
            else:
                print(f"sim_finish on received, Thread id: {threading.get_ident()}")
                print(f"All data received by node {pair_key[0]} is {value}")
        
        # Exit like C++ version
        os._exit(0)
        return 0
    
    def sim_time_resolution(self) -> float:
        """
        Get time resolution (corresponds to C++ sim_time_resolution)
        
        Returns:
            Time resolution (0 in C++ version)
        """
        return 0.0
    
    def sim_init(self, MEM: Any) -> int:
        """
        Initialize simulation (corresponds to C++ sim_init)
        
        Args:
            MEM: Memory API object
            
        Returns:
            0 for success
        """
        # TODO: Implement initialization logic
        return 0
    
    def sim_get_time(self) -> TimeSpec:
        """
        Get current simulation time (corresponds to C++ sim_get_time)
        
        Returns:
            Current simulation time
        """
        timeSpec = TimeSpec()
        
        if NS3_AVAILABLE:
            # Use NS3 Simulator time like C++ version
            timeSpec.time_val = float(ns.Simulator.Now().GetNanoSeconds())
        else:
            # Mock implementation
            timeSpec.time_val = 0.0
            
        return timeSpec
    
    def sim_schedule(self, delta: TimeSpec, 
                    fun_ptr: Callable[[Any], None], 
                    fun_arg: Any) -> None:
        """
        Schedule task (corresponds to C++ sim_schedule)
        
        Args:
            delta: Time delay
            fun_ptr: Function to execute
            fun_arg: Function arguments
        """
        t = task1()
        t.type = 2
        t.fun_arg = fun_arg
        t.msg_handler = fun_ptr
        t.schTime = delta.time_val
        
        if NS3_AVAILABLE:
            # Use NS3 Simulator.Schedule like C++ version
            ns.Simulator.Schedule(ns.NanoSeconds(t.schTime), t.msg_handler, t.fun_arg)
        else:
            # Mock implementation - execute immediately for testing
            if t.msg_handler:
                t.msg_handler(t.fun_arg)
    
    def sim_send(self, buffer: Any, count: int, type_: int, 
                dst: int, tag: int, request: SimRequest,
                msg_handler: Callable[[Any], None], 
                fun_arg: Any) -> int:
        """
        Send data (corresponds to C++ sim_send)
        
        Args:
            buffer: Send buffer
            count: Data count
            type_: Data type
            dst: Destination rank
            tag: Message tag
            request: Simulation request
            msg_handler: Message handler
            fun_arg: Function arguments
            
        Returns:
            0 for success
        """
        dst += self.npu_offset
        
        t = task1()
        t.src = self.rank
        t.dest = dst
        t.count = count
        t.type = 0
        t.fun_arg = fun_arg
        t.msg_handler = msg_handler
        
        # Store in sentHash like C++ version
        key = (tag, (t.src, t.dest))
        safe_hash_set(sentHash, key, t)
        
        # Call SendFlow like C++ version
        SendFlow(self.rank, dst, count, msg_handler, fun_arg, tag, request)
        
        return 0
    
    def sim_recv(self, buffer: Any, count: int, type_: int,
                src: int, tag: int, request: SimRequest,
                msg_handler: Callable[[Any], None],
                fun_arg: Any) -> int:
        """
        Receive data (corresponds to C++ sim_recv)
        
        Args:
            buffer: Receive buffer
            count: Data count
            type_: Data type
            src: Source rank
            tag: Message tag
            request: Simulation request
            msg_handler: Message handler
            fun_arg: Function arguments
            
        Returns:
            0 for success
        """
        # TODO: Add MockNcclLog integration like C++ version
        flowTag = request.flowTag
        src += self.npu_offset
        
        t = task1()
        t.src = src
        t.dest = self.rank
        t.count = count
        t.type = 1
        t.fun_arg = fun_arg
        t.msg_handler = msg_handler
        
        # Handle receive logic like C++ version
        # This includes complex hash map operations that match C++ logic
        key = (tag, (t.src, t.dest))
        
        existing_count = safe_hash_get(recvHash, key, 0)
        if existing_count > 0:
            if existing_count == t.count:
                # Complete match - remove and execute
                safe_hash_del(recvHash, key)
                # TODO: Handle flowTag logic like C++
                if t.msg_handler:
                    t.msg_handler(t.fun_arg)
            elif existing_count > t.count:
                # Partial match - update and execute
                safe_hash_set(recvHash, key, existing_count - t.count)
                # TODO: Handle flowTag logic like C++
                if t.msg_handler:
                    t.msg_handler(t.fun_arg)
            else:
                # Need more data - store expectation
                safe_hash_del(recvHash, key)
                t.count -= existing_count
                safe_hash_set(expeRecvHash, key, t)
        else:
            # No existing data - store expectation
            existing_task = safe_hash_get(expeRecvHash, key)
            if existing_task is None:
                safe_hash_set(expeRecvHash, key, t)
            else:
                # Update existing expectation
                existing_task.count += t.count
                safe_hash_set(expeRecvHash, key, existing_task)
        
        return 0
    
    def handleEvent(self, dst: int, cnt: int) -> None:
        """
        Handle event (corresponds to C++ handleEvent)
        
        Args:
            dst: Destination
            cnt: Count
        """
        # TODO: Implement event handling logic
        pass


# ============================================================================
# Main function and user_param (same as C++ main() in AstraSimNetwork.cc)
# ============================================================================

import argparse
import os
from pathlib import Path
from typing import Dict, List

from system.sys import Sys
from workload.workload import Workload

# user_param structure (same as C++ struct user_param)
class user_param:
    """Corresponds to C++ struct user_param"""
    def __init__(self):
        self.thread: int = 1
        self.workload: str = ""
        self.network_topo: str = ""
        self.network_conf: str = ""

def user_param_parse(argv: List[str]) -> tuple[user_param, int]:
    """
    Parse user parameters (corresponds to C++ user_param_prase function)
    
    Args:
        argv: Command line arguments
        
    Returns:
        Tuple of (user_param object, exit_code)
    """
    parser = argparse.ArgumentParser(description="SimAI NS3 Network Backend")
    
    # Same parameters as C++ version
    parser.add_argument("-h", "--help", action="help", 
                       help="Show this help message")
    parser.add_argument("-t", "--thread", type=int, default=1,
                       help="Number of threads, default 1")
    parser.add_argument("-w", "--workload", type=str, required=True,
                       help="Workload file path")
    parser.add_argument("-n", "--network_topo", type=str, required=True,
                       help="Network topology file")
    parser.add_argument("-c", "--network_conf", type=str, required=True,
                       help="Network configuration file")
    
    try:
        args = parser.parse_args(argv[1:])  # Skip script name
        
        params = user_param()
        params.thread = args.thread
        params.workload = args.workload
        params.network_topo = args.network_topo
        params.network_conf = args.network_conf
        
        return params, 0
    except SystemExit as e:
        return user_param(), e.code if e.code else 0

def main(argv=None):
    """
    Main function for NS3 backend (corresponds to main() in AstraSimNetwork.cc)
    
    Args:
        argv: Command line arguments (defaults to sys.argv)
    """
    if argv is None:
        argv = sys.argv
    
    # Parse user parameters like C++ version
    user_params, exit_code = user_param_parse(argv)
    if exit_code != 0:
        return exit_code
    
    # TODO: Add MockNcclLog initialization like C++ version
    # MockNcclLog::set_log_name("SimAI.log");
    # MockNcclLog* NcclLog = MockNcclLog::getInstance();
    print("Initializing SimAI NS3 backend...")
    
    # TODO: Add multi-threading support like C++ version
    # #ifdef NS3_MTP
    # MtpInterface::Enable(user_params.thread);
    # #endif
    
    # Initialize NS3 topology and configuration
    from .entry import main1, cleanup_hash_maps
    from . import common
    
    main1(user_params.network_topo, user_params.network_conf)
    
    # Get topology information (these will be set by main1)
    nodes_num = common.node_num - common.switch_num
    gpu_num = common.node_num - common.nvswitch_num - common.switch_num
    
    # Create node to nvswitch mapping like C++ version
    node2nvswitch: Dict[int, int] = {}
    for i in range(gpu_num):
        node2nvswitch[i] = gpu_num + i // common.gpus_per_server
    
    for i in range(gpu_num, gpu_num + common.nvswitch_num):
        node2nvswitch[i] = i
        common.NVswitchs.append(i)
    
    # TODO: Enable NS3 logging like C++ version
    if common.NS3_AVAILABLE:
        # LogComponentEnable("OnOffApplication", LOG_LEVEL_INFO);
        # LogComponentEnable("PacketSink", LOG_LEVEL_INFO);
        # LogComponentEnable("GENERIC_SIMULATION", LOG_LEVEL_INFO);
        pass
    
    # Create networks and systems (same structure as C++)
    networks: List[ASTRASimNetwork] = []
    systems: List[Sys] = []
    
    for j in range(nodes_num):
        # Create network like C++ version
        network = ASTRASimNetwork(j, 0)
        networks.append(network)
        
        # Create system like C++ version
        # TODO: Match exact C++ Sys constructor parameters
        system = Sys(
            network=network,
            memory=None,  # nullptr in C++
            id=j,
            num_passes=0,
            comm_group_size=1,
            num_queues_per_dim=[nodes_num],
            num_dims=[1],
            allocation_policy="",
            workload_file=user_params.workload,
            comm_scale=1,
            compute_scale=1,
            injection_scale=1,
            total_stat_rows=1,
            stat_row=0,
            path=common.RESULT_PATH,
            run_name="test1",
            true_protocolon=True,
            seprate_log=False,
            _gpu_type=common.gpu_type,
            num_gpus=[gpu_num],
            NVswitchs=common.NVswitchs,
            gpus_per_server=common.gpus_per_server
        )
        
        # Set nvswitch_id like C++ version
        system.nvswitch_id = node2nvswitch[j]
        system.num_gpus = nodes_num - common.nvswitch_num
        
        systems.append(system)
    
    # Fire workloads like C++ version
    for i in range(nodes_num):
        systems[i].workload.fire()
    
    print("Starting NS3 simulator...")
    
    if common.NS3_AVAILABLE:
        # Run NS3 simulator like C++ version
        common.ns.Simulator.Run()
        common.ns.Simulator.Stop(common.ns.Seconds(2000000000))
        common.ns.Simulator.Destroy()
    else:
        print("NS3 not available - running mock simulation")
        # Mock simulation for development
        import time
        time.sleep(1)  # Simulate some work
        print("Mock simulation completed")
    
    # TODO: Cleanup like C++ version
    # #ifdef NS3_MPI
    # MpiInterface::Disable();
    # #endif
    
    cleanup_hash_maps()
    return 0

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code) 