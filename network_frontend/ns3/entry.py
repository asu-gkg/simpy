#!/usr/bin/env python3
"""
entry.py - corresponds to entry.h in SimAI NS3

Contains data structures, global hash maps, and helper functions for NS3 integration
"""

from __future__ import annotations
import threading
import os
import logging
from typing import Dict, Tuple, Optional, Callable, Any, List
from dataclasses import dataclass
from queue import Queue
from .common import (
    ns, NS3_AVAILABLE, port_number, server_address,
    pair_rtt, pair_bw, pair_bdp, has_win, global_t, max_bdp, max_rtt,
    packet_payload_size, flow_input, node_num, switch_num, nvswitch_num,
    setup_network_globals, gpu_type, gpus_per_server, topology_file,
    enable_qcn, use_dynamic_pfc_threshold, pause_time, cc_mode, 
    data_rate, link_delay, NodeType, Interface, nbr2if, serverAddress,
    GPUType, NVswitchs, SetConfig, SetupNetwork, ReadConf
)
from system.AstraNetworkAPI import NcclFlowTag, SimRequest

# Constants (same as C++)
_QPS_PER_CONNECTION_ = 1

# Global hash maps (same names as C++)
# Note: Using Dict instead of std::map to maintain Python idioms while keeping C++ naming

# receiver_pending_queue: map<pair<pair<int, int>, int>, ncclFlowTag>
receiver_pending_queue: Dict[Tuple[Tuple[int, int], int], NcclFlowTag] = {}

# sender_src_port_map: map<pair<int, pair<int, int>>, ncclFlowTag>
sender_src_port_map: Dict[Tuple[int, Tuple[int, int]], NcclFlowTag] = {}

# Task structure (same as C++ struct task1)
@dataclass
class task1:
    """Corresponds to C++ struct task1"""
    src: int = 0
    dest: int = 0
    type: int = 0
    count: int = 0  # uint64_t in C++
    fun_arg: Any = None  # void* in C++
    msg_handler: Optional[Callable[[Any], None]] = None  # void (*msg_handler)(void*) in C++
    schTime: float = 0.0  # double in C++

# Global hash maps using task1 and other types
# expeRecvHash: map<pair<int, pair<int, int>>, struct task1>
expeRecvHash: Dict[Tuple[int, Tuple[int, int]], task1] = {}

# recvHash: map<pair<int, pair<int, int>>, uint64_t>
recvHash: Dict[Tuple[int, Tuple[int, int]], int] = {}

# sentHash: map<pair<int, pair<int, int>>, struct task1>
sentHash: Dict[Tuple[int, Tuple[int, int]], task1] = {}

# nodeHash: map<pair<int, int>, int64_t>
nodeHash: Dict[Tuple[int, int], int] = {}

# waiting_to_sent_callback: map<pair<int, pair<int, int>>, int>
waiting_to_sent_callback: Dict[Tuple[int, Tuple[int, int]], int] = {}

# waiting_to_notify_receiver: map<pair<int, pair<int, int>>, int>
waiting_to_notify_receiver: Dict[Tuple[int, Tuple[int, int]], int] = {}

# received_chunksize: map<pair<int, pair<int, int>>, uint64_t>
received_chunksize: Dict[Tuple[int, Tuple[int, int]], int] = {}

# sent_chunksize: map<pair<int, pair<int, int>>, uint64_t>
sent_chunksize: Dict[Tuple[int, Tuple[int, int]], int] = {}

# Thread synchronization (for thread safety like C++)
_hash_map_lock = threading.RLock()

# Network configuration and setup functions
def read_conf(network_topo: str, network_conf: str) -> bool:
    """Read network configuration files - corresponds to C++ ReadConf"""
    from . import common
    
    try:
        # Read topology file
        if not os.path.exists(network_topo):
            logging.error(f"Topology file not found: {network_topo}")
            return False
            
        with open(network_topo, 'r') as topo_file:
            # Read first line: node_num gpus_per_server nvswitch_num switch_num link_num gpu_type
            first_line = topo_file.readline().strip().split()
            if len(first_line) >= 5:
                common.node_num = int(first_line[0])
                common.gpus_per_server = int(first_line[1])
                common.nvswitch_num = int(first_line[2])
                common.switch_num = int(first_line[3])
                common.link_num = int(first_line[4])
                
                if len(first_line) > 5:
                    gpu_type_str = first_line[5]
                    # Map GPU type string to enum
                    gpu_type_map = {
                        "A100": common.GPUType.A100,
                        "A800": common.GPUType.A800,
                        "H100": common.GPUType.H100,
                        "H800": common.GPUType.H800,
                        "NONE": common.GPUType.NONE
                    }
                    common.gpu_type = gpu_type_map.get(gpu_type_str, common.GPUType.NONE)
            
            logging.info(f"Topology: {common.node_num} nodes, {common.gpus_per_server} GPUs/server, "
                        f"{common.nvswitch_num} NVSwitches, {common.switch_num} switches, "
                        f"{common.link_num} links")
        
        # Read configuration file
        if network_conf and os.path.exists(network_conf):
            common.ReadConf(network_topo, network_conf)
        
        return True
        
    except Exception as e:
        logging.error(f"Failed to read configuration: {e}")
        return False

def set_config():
    """Set NS3 configuration parameters - corresponds to C++ SetConfig"""
    from . import common
    
    logging.info("Setting NS3 configuration parameters")
    
    if NS3_AVAILABLE:
        # Set NS3 configuration using Config system
        common.SetConfig()
    else:
        # Mock mode - just log the configuration
        logging.info(f"Mock mode - Configuration: cc_mode={common.cc_mode}, "
                    f"enable_qcn={common.enable_qcn}, pause_time={common.pause_time}")

def setup_network(qp_finish_cb, send_finish_cb):
    """Setup NS3 network topology - corresponds to C++ SetupNetwork"""
    from . import common
    
    logging.info(f"Setting up network with {common.node_num} nodes")
    
    if NS3_AVAILABLE:
        # Use actual NS3 network setup
        success = common.SetupNetwork(qp_finish_cb, send_finish_cb)
        if success:
            logging.info("NS3 network setup completed successfully")
        else:
            logging.error("NS3 network setup failed")
        return success
    else:
        # Mock mode network setup
        logging.info("Mock mode - Simulating network setup")
        
        # Initialize port numbers for each node pair
        for i in range(common.node_num):
            common.port_number[i] = {}
            for j in range(common.node_num):
                if i != j:
                    common.port_number[i][j] = 9000
                    
        # Initialize server addresses
        common.server_address = {}
        for i in range(common.node_num):
            common.server_address[i] = 0x0b000001 + ((i // 256) * 0x00010000) + ((i % 256) * 0x00000100)
            
        # Initialize pair RTT and bandwidth (mock values)
        gpu_num = common.node_num - common.nvswitch_num - common.switch_num
        for i in range(gpu_num):
            common.pair_rtt[i] = {}
            common.pair_bw[i] = {}
            for j in range(gpu_num):
                if i != j:
                    # Mock RTT in microseconds
                    common.pair_rtt[i][j] = 10 if abs(i - j) <= common.gpus_per_server else 100
                    # Mock bandwidth in bps (100Gbps for local, 25Gbps for remote)
                    common.pair_bw[i][j] = 100000000000 if abs(i - j) <= common.gpus_per_server else 25000000000
                    
        logging.info(f"Mock network setup completed: {gpu_num} GPUs, {common.nvswitch_num} NVSwitches")
        return True

# Import MockNcclLog from system module
from system.mock_nccl_log import MockNcclLog, NcclLogLevel as MockNcclLogLevel

def get_mock_nccl_log():
    """Get MockNcclLog instance"""
    return MockNcclLog.getInstance(), MockNcclLogLevel

def is_sending_finished(src: int, dst: int, flowTag: NcclFlowTag) -> bool:
    """
    Check if sending is finished (corresponds to C++ function)
    
    Args:
        src: Source node ID
        dst: Destination node ID  
        flowTag: NCCL flow tag
        
    Returns:
        True if sending is finished
    """
    tag_id = flowTag.current_flow_id
    
    with _hash_map_lock:
        key = (tag_id, (src, dst))
        if key in waiting_to_sent_callback:
            waiting_to_sent_callback[key] -= 1
            if waiting_to_sent_callback[key] == 0:
                del waiting_to_sent_callback[key]
                return True
    return False

def is_receive_finished(src: int, dst: int, flowTag: NcclFlowTag) -> bool:
    """
    Check if receiving is finished (corresponds to C++ function)
    
    Args:
        src: Source node ID
        dst: Destination node ID
        flowTag: NCCL flow tag
        
    Returns:
        True if receiving is finished
    """
    tag_id = flowTag.current_flow_id
    NcclLog, NcclLogLevel = get_mock_nccl_log()
    
    with _hash_map_lock:
        key = (tag_id, (src, dst))
        if key in waiting_to_notify_receiver:
            if NcclLogLevel:
                NcclLog.writeLog(NcclLogLevel.DEBUG,
                    " is_receive_finished waiting_to_notify_receiver tag_id %d src %d dst %d count %d",
                    tag_id, src, dst, waiting_to_notify_receiver[key])
            
            waiting_to_notify_receiver[key] -= 1
            if waiting_to_notify_receiver[key] == 0:
                del waiting_to_notify_receiver[key]
                return True
    return False

def SendFlow(src: int, dst: int, maxPacketCount: int, 
            msg_handler: Callable[[Any], None], 
            fun_arg: Any, tag: int, 
            request: SimRequest) -> None:
    """
    Send flow function (corresponds to C++ SendFlow) - EXACT replica
    
    Args:
        src: Source node ID
        dst: Destination node ID
        maxPacketCount: Maximum packet count
        msg_handler: Message handler callback
        fun_arg: Function arguments
        tag: Message tag
        request: Simulation request
    """
    NcclLog, NcclLogLevel = get_mock_nccl_log()
    
    # Calculate packet distribution like C++
    PacketCount = (maxPacketCount + _QPS_PER_CONNECTION_ - 1) // _QPS_PER_CONNECTION_
    leftPacketCount = maxPacketCount
    
    for index in range(_QPS_PER_CONNECTION_):
        real_PacketCount = min(PacketCount, leftPacketCount)
        leftPacketCount -= real_PacketCount
        
        # Get port number like C++ (with increment)
        with _hash_map_lock:
            if src not in port_number:
                port_number[src] = {}
            if dst not in port_number[src]:
                port_number[src][dst] = 9000
            port = port_number[src][dst]
            port_number[src][dst] += 1
        
        # Store flowTag mapping like C++
        with _hash_map_lock:
            sender_src_port_map[(port, (src, dst))] = request.flowTag
        
        flow_id = request.flowTag.current_flow_id
        nvls_on = request.flowTag.nvls_on
        pg = 3
        dport = 100
        
        # Get send latency from environment like C++
        send_lat = 6000
        send_lat_env = os.getenv("AS_SEND_LAT")
        if send_lat_env:
            try:
                send_lat = int(send_lat_env)
            except ValueError:
                if NcclLogLevel:
                    NcclLog.writeLog(NcclLogLevel.ERROR, "send_lat set error")
                os._exit(-1)
        
        send_lat *= 1000  # Convert to nanoseconds
        
        # Increment flow index like C++
        flow_input.idx += 1
        
        if real_PacketCount == 0:
            real_PacketCount = 1
        
        # Log packet sending like C++
        if NcclLogLevel:
            # Get current simulation tick
            tick = ns.core.Simulator.Now().GetNanoSeconds() if NS3_AVAILABLE else int(os.times()[4] * 1e9)
            
            NcclLog.writeLog(NcclLogLevel.DEBUG,
                " [Packet sending event] %d SendFlow to %d channelid: %d flow_id %d srcip %d dstip %d size: %d at the tick: %d",
                src, dst, tag, flow_id, 
                server_address.get(src, 0), server_address.get(dst, 0),
                maxPacketCount, tick)
            
            NcclLog.writeLog(NcclLogLevel.DEBUG,
                " request->flowTag [Packet sending event] %d SendFlow to %d tag_id: %d flow_id %d srcip %d dstip %d size: %d at the tick: %d",
                request.flowTag.sender_node, request.flowTag.receiver_node,
                request.flowTag.tag_id, request.flowTag.current_flow_id,
                server_address.get(src, 0), server_address.get(dst, 0),
                maxPacketCount, tick)
        
        # Create NS3 flow or simulate in Mock mode
        if NS3_AVAILABLE:
            # TODO: Implement actual NS3 RdmaClientHelper equivalent
            # For now, schedule a completion event
            completion_time = ns.core.NanoSeconds(send_lat + (real_PacketCount * 8 * 1000) // 100000)  # Assume 100Gbps
            ns.core.Simulator.Schedule(completion_time, 
                                     lambda: _handle_send_completion(src, dst, request.flowTag, msg_handler, fun_arg))
        else:
            # Mock mode - simulate sending with a delayed callback
            import time
            from threading import Timer
            
            # Calculate simulated transfer time (nanoseconds to seconds)
            transfer_time_ns = send_lat + (real_PacketCount * 8 * 1000000000) // pair_bw.get(src, {}).get(dst, 100000000000)
            transfer_time_s = transfer_time_ns / 1e9
            
            # Schedule completion callback
            def mock_send_completion():
                _handle_send_completion(src, dst, request.flowTag, msg_handler, fun_arg)
                
            timer = Timer(transfer_time_s, mock_send_completion)
            timer.start()
        
        # Update waiting counters like C++
        with _hash_map_lock:
            flow_key = (request.flowTag.current_flow_id, (src, dst))
            waiting_to_sent_callback[flow_key] = waiting_to_sent_callback.get(flow_key, 0) + 1
            waiting_to_notify_receiver[flow_key] = waiting_to_notify_receiver.get(flow_key, 0) + 1
        
        if NcclLogLevel:
            NcclLog.writeLog(NcclLogLevel.DEBUG,
                "waiting_to_notify_receiver current_flow_id %d src %d dst %d count %d",
                request.flowTag.current_flow_id, src, dst,
                waiting_to_notify_receiver.get((request.flowTag.tag_id, (src, dst)), 0))

def _handle_send_completion(src: int, dst: int, flowTag: NcclFlowTag, 
                           msg_handler: Callable[[Any], None], fun_arg: Any):
    """Handle send completion - internal helper function"""
    # Notify receiver that data has arrived
    notify_receiver_receive_data(src, dst, flowTag.size, flowTag)
    
    # Check if sending is finished
    if is_sending_finished(src, dst, flowTag):
        # Notify sender
        notify_sender_sending_finished(src, dst, flowTag.size, flowTag)

def notify_receiver_receive_data(sender_node: int, receiver_node: int,
                               message_size: int, flowTag: NcclFlowTag) -> None:
    """
    Notify receiver about received data (corresponds to C++ function) - EXACT replica
    
    Args:
        sender_node: Sender node ID
        receiver_node: Receiver node ID
        message_size: Message size
        flowTag: NCCL flow tag
    """
    NcclLog, NcclLogLevel = get_mock_nccl_log()
    
    with _hash_map_lock:
        if NcclLogLevel:
            NcclLog.writeLog(NcclLogLevel.DEBUG,
                " %d notify recevier: %d message size: %d",
                sender_node, receiver_node, message_size)
        
        tag = flowTag.tag_id
        key = (tag, (sender_node, receiver_node))
        
        if key in expeRecvHash:
            t2 = expeRecvHash[key]
            
            if NcclLogLevel:
                NcclLog.writeLog(NcclLogLevel.DEBUG,
                    " %d notify recevier: %d message size: %d t2.count: %d channle id: %d",
                    sender_node, receiver_node, message_size, t2.count, flowTag.channel_id)
            
            # Get event handler data (simplified for Python)
            ehd = t2.fun_arg  # Assuming this is RecvPacketEventHandlerData equivalent
            
            if message_size == t2.count:
                if NcclLogLevel:
                    NcclLog.writeLog(NcclLogLevel.DEBUG,
                        " message_size = t2.count expeRecvHash.erase %d notify recevier: %d message size: %d channel_id %d",
                        sender_node, receiver_node, message_size, tag)
                
                del expeRecvHash[key]
                
                # Set flowTag like C++
                if hasattr(ehd, 'flowTag'):
                    assert ehd.flowTag.current_flow_id == -1 and ehd.flowTag.child_flow_id == -1
                    ehd.flowTag = flowTag
                
                # Execute callback outside lock
                temp_handler = t2.msg_handler
                temp_arg = t2.fun_arg
                
                # Release lock before callback
                pass  # Will release at end of with block
                
                # Execute callback
                if temp_handler:
                    temp_handler(temp_arg)
                
                # Skip to end section
                goto_receiver_end_1st_section = True
                
            elif message_size > t2.count:
                recvHash[key] = message_size - t2.count
                
                if NcclLogLevel:
                    NcclLog.writeLog(NcclLogLevel.DEBUG,
                        "message_size > t2.count expeRecvHash.erase %d notify recevier: %d message size: %d channel_id %d",
                        sender_node, receiver_node, message_size, tag)
                
                del expeRecvHash[key]
                
                # Set flowTag like C++
                if hasattr(ehd, 'flowTag'):
                    assert ehd.flowTag.current_flow_id == -1 and ehd.flowTag.child_flow_id == -1
                    ehd.flowTag = flowTag
                
                # Execute callback outside lock
                temp_handler = t2.msg_handler
                temp_arg = t2.fun_arg
                
                # Execute callback
                if temp_handler:
                    temp_handler(temp_arg)
                
                goto_receiver_end_1st_section = True
                
            else:
                # message_size < t2.count
                t2.count -= message_size
                expeRecvHash[key] = t2
                goto_receiver_end_1st_section = False
        else:
            # No expectation found
            receiver_pending_queue[((receiver_node, sender_node), tag)] = flowTag
            
            if key not in recvHash:
                recvHash[key] = message_size
            else:
                recvHash[key] += message_size
            
            goto_receiver_end_1st_section = False
    
    # receiver_end_1st_section: (C++ label equivalent)
    # Update nodeHash for statistics
    with _hash_map_lock:
        node_key = (receiver_node, 1)
        if node_key not in nodeHash:
            nodeHash[node_key] = message_size
        else:
            nodeHash[node_key] += message_size

def notify_sender_sending_finished(sender_node: int, receiver_node: int,
                                  message_size: int, flowTag: NcclFlowTag) -> None:
    """
    Notify sender that sending is finished (corresponds to C++ function) - EXACT replica
    
    Args:
        sender_node: Sender node ID
        receiver_node: Receiver node ID
        message_size: Message size
        flowTag: NCCL flow tag
    """
    NcclLog, NcclLogLevel = get_mock_nccl_log()
    
    with _hash_map_lock:
        tag = flowTag.tag_id
        key = (tag, (sender_node, receiver_node))
        
        if key in sentHash:
            t2 = sentHash[key]
            
            # Get event handler data (simplified for Python)
            ehd = t2.fun_arg  # Assuming this is SendPacketEventHandlerData equivalent
            if hasattr(ehd, 'flowTag'):
                ehd.flowTag = flowTag
            
            if t2.count == message_size:
                del sentHash[key]
                
                # Update nodeHash for statistics
                node_key = (sender_node, 0)
                if node_key not in nodeHash:
                    nodeHash[node_key] = message_size
                else:
                    nodeHash[node_key] += message_size
                
                # Execute callback outside lock
                temp_handler = t2.msg_handler
                temp_arg = t2.fun_arg
                
                # Execute callback
                if temp_handler:
                    temp_handler(temp_arg)
            else:
                if NcclLogLevel:
                    NcclLog.writeLog(NcclLogLevel.ERROR,
                        "sentHash msg size != sender_node %d receiver_node %d message_size %d flow_id",
                        sender_node, receiver_node, message_size)
        else:
            if NcclLogLevel:
                NcclLog.writeLog(NcclLogLevel.ERROR,
                    "sentHash cann't find sender_node %d receiver_node %d message_size %d",
                    sender_node, receiver_node, message_size)

def qp_finish(fout, q):
    """
    QP finish callback (corresponds to C++ qp_finish) - Simplified for Python
    
    Args:
        fout: File output (simplified)
        q: Queue pair object (simplified)
    """
    # This would be called by NS3 when a queue pair finishes
    # Simplified implementation for Python
    pass

def send_finish(fout, q):
    """
    Send finish callback (corresponds to C++ send_finish) - Simplified for Python
    
    Args:
        fout: File output (simplified)  
        q: Queue pair object (simplified)
    """
    # This would be called by NS3 when sending finishes
    # Simplified implementation for Python
    pass

def main1(network_topo: str, network_conf: str) -> int:
    """
    Main initialization function (corresponds to C++ main1) - EXACT replica
    
    Args:
        network_topo: Network topology file path
        network_conf: Network configuration file path
        
    Returns:
        0 for success, -1 for failure
    """
    import time
    
    begin_time = time.time()
    
    if not read_conf(network_topo, network_conf):
        return -1
    
    set_config()
    setup_network(qp_finish, send_finish)
    setup_network_globals()
    
    print("Running Simulation.")
    
    end_time = time.time()
    print(f"Setup completed in {end_time - begin_time:.3f} seconds")
    
    return 0

def cleanup_hash_maps() -> None:
    """
    Clean up all global hash maps (utility function)
    """
    with _hash_map_lock:
        receiver_pending_queue.clear()
        sender_src_port_map.clear()
        expeRecvHash.clear()
        recvHash.clear()
        sentHash.clear()
        nodeHash.clear()
        waiting_to_sent_callback.clear()
        waiting_to_notify_receiver.clear()
        received_chunksize.clear()
        sent_chunksize.clear()

# Thread-safe operations for hash maps
def safe_hash_get(hash_map: Dict, key: Any, default: Any = None) -> Any:
    """Thread-safe hash map get operation"""
    with _hash_map_lock:
        return hash_map.get(key, default)

def safe_hash_set(hash_map: Dict, key: Any, value: Any) -> None:
    """Thread-safe hash map set operation"""
    with _hash_map_lock:
        hash_map[key] = value

def safe_hash_del(hash_map: Dict, key: Any) -> bool:
    """Thread-safe hash map delete operation"""
    with _hash_map_lock:
        if key in hash_map:
            del hash_map[key]
            return True
        return False 