#!/usr/bin/env python3
"""
entry.py - corresponds to entry.h in SimAI NS3

Contains data structures, global hash maps, and helper functions for NS3 integration
"""

from __future__ import annotations
import threading
from typing import Dict, Tuple, Optional, Callable, Any, List
from dataclasses import dataclass
from queue import Queue
from common import ns, NS3_AVAILABLE
from system.AstraNetworkAPI import NcclFlowTag, SimRequest

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

def is_receiving_finished(src: int, dst: int, flowTag: NcclFlowTag) -> bool:
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
    
    with _hash_map_lock:
        key = (tag_id, (src, dst))
        if key in waiting_to_notify_receiver:
            waiting_to_notify_receiver[key] -= 1
            if waiting_to_notify_receiver[key] == 0:
                del waiting_to_notify_receiver[key]
                return True
    return False

def SendFlow(src: int, dst: int, count: int, 
            msg_handler: Callable[[Any], None], 
            fun_arg: Any, tag: int, 
            request: SimRequest) -> None:
    """
    Send flow function (corresponds to C++ SendFlow)
    
    Args:
        src: Source node ID
        dst: Destination node ID
        count: Data count
        msg_handler: Message handler callback
        fun_arg: Function arguments
        tag: Message tag
        request: Simulation request
    """
    # This will be implemented with actual NS3 calls
    if NS3_AVAILABLE:
        # TODO: Implement actual NS3 flow sending
        pass
    else:
        # Mock implementation for development
        if msg_handler:
            msg_handler(fun_arg)

def RecvFlow(src: int, dst: int, count: int,
            msg_handler: Callable[[Any], None],
            fun_arg: Any, tag: int,
            request: SimRequest) -> None:
    """
    Receive flow function (corresponds to C++ RecvFlow)
    
    Args:
        src: Source node ID
        dst: Destination node ID
        count: Data count
        msg_handler: Message handler callback
        fun_arg: Function arguments
        tag: Message tag
        request: Simulation request
    """
    # This will be implemented with actual NS3 calls
    if NS3_AVAILABLE:
        # TODO: Implement actual NS3 flow receiving
        pass
    else:
        # Mock implementation for development
        if msg_handler:
            msg_handler(fun_arg)

def main1(network_topo: str, network_conf: str) -> None:
    """
    Main initialization function (corresponds to C++ main1)
    
    Args:
        network_topo: Network topology file path
        network_conf: Network configuration file path
    """
    # This will contain NS3 topology and configuration setup
    if NS3_AVAILABLE:
        # TODO: Implement actual NS3 topology setup
        pass
    else:
        # Mock implementation
        print(f"Mock: Setting up topology from {network_topo}")
        print(f"Mock: Setting up configuration from {network_conf}")

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