# AstraSimDataAPI.py - corresponds to AstraSimDataAPI.hh in SimAI

from dataclasses import dataclass, field
from typing import List, Dict, Tuple


@dataclass
class LayerData:
    """层数据类，对应C++中的LayerData类"""
    layer_name: str = ""
    total_forward_pass_compute: float = 0.0
    total_weight_grad_compute: float = 0.0
    total_input_grad_compute: float = 0.0
    total_waiting_for_fwd_comm: float = 0.0
    total_waiting_for_wg_comm: float = 0.0
    total_waiting_for_ig_comm: float = 0.0
    total_fwd_comm: float = 0.0
    total_weight_grad_comm: float = 0.0
    total_input_grad_comm: float = 0.0
    avg_queuing_delay: List[Tuple[int, float]] = field(default_factory=list)
    avg_network_message_delay: List[Tuple[int, float]] = field(default_factory=list)


@dataclass
class AstraSimDataAPI:
    """AstraSim数据API类，对应C++中的AstraSimDataAPI类"""
    run_name: str = ""
    layers_stats: List[LayerData] = field(default_factory=list)
    avg_chunk_latency_per_logical_dimension: List[float] = field(default_factory=list)
    workload_finished_time: float = 0.0
    total_compute: float = 0.0
    total_exposed_comm: float = 0.0 