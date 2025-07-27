#!/usr/bin/env python3
"""
common.py - corresponds to common.h in SimAI NS3

Contains global configuration variables and NS3-related imports
"""

# Copyright headers same as C++
__copyright__ = """
Copyright (c) 2024, Alibaba Group;
Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

import sys
from typing import Dict, List, Optional
from enum import Enum

# Try to import NS3 - fallback gracefully if not available
try:
    from ns import ns
    NS3_AVAILABLE = True
except ImportError:
    print("Warning: NS3 Python bindings not available. Some functionality will be limited.")
    NS3_AVAILABLE = False
    # Create mock ns object for development
    class MockNS3:
        class Simulator:
            @staticmethod
            def Now():
                class MockTime:
                    def GetNanoSeconds(self):
                        return 0.0
                return MockTime()
            
            @staticmethod
            def Schedule(*args):
                pass
    ns = MockNS3()

# GPU Type enum (corresponding to C++ GPUType)
class GPUType(Enum):
    H100 = 0
    A100 = 1
    V100 = 2

# Global configuration variables (same names as C++)
cc_mode: int = 1
enable_qcn: bool = True
use_dynamic_pfc_threshold: bool = True
packet_payload_size: int = 1000
l2_chunk_size: int = 0
l2_ack_interval: int = 0
pause_time: float = 5.0
simulator_stop_time: float = 3.01

# String configurations
data_rate: str = ""
link_delay: str = ""
topology_file: str = ""
flow_file: str = ""
trace_file: str = ""
trace_output_file: str = ""
fct_output_file: str = "fct.txt"
pfc_output_file: str = "pfc.txt"
send_output_file: str = "send.txt"

# Timer and rate configurations
alpha_resume_interval: float = 55.0
rp_timer: float = 0.0
ewma_gain: float = 1.0 / 16.0
rate_decrease_interval: float = 4.0
fast_recovery_times: int = 5
rate_ai: str = ""
rate_hai: str = ""
min_rate: str = "100Mb/s"
dctcp_rate_ai: str = "1000Mb/s"

# Boolean flags
clamp_target_rate: bool = False
l2_back_to_zero: bool = False
error_rate_per_link: float = 0.0
has_win: int = 1
global_t: int = 1
mi_thresh: int = 5
var_win: bool = False
fast_react: bool = True
multi_rate: bool = True
sample_feedback: bool = False
rate_bound: bool = True

# PINT configurations  
pint_log_base: float = 1.05
pint_prob: float = 1.0
u_target: float = 0.95
int_multi: int = 1

# Network configurations
nic_total_pause_time: int = 0
ack_high_prio: int = 0
link_down_time: int = 0
link_down_A: int = 0
link_down_B: int = 0
enable_trace: int = 1
buffer_size: int = 16

# Topology variables (same names as C++)
node_num: int = 0
switch_num: int = 0
link_num: int = 0
trace_num: int = 0
nvswitch_num: int = 0
gpus_per_server: int = 0
gpu_type: GPUType = GPUType.H100
NVswitchs: List[int] = []

# Monitoring configurations
qp_mon_interval: int = 100
bw_mon_interval: int = 10000
qlen_mon_interval: int = 10000
mon_start: int = 0
mon_end: int = 2100000000
qlen_mon_file: str = ""

# Result path constant
RESULT_PATH: str = "./ncclFlowModel_"

# QPS per connection
_QPS_PER_CONNECTION_: int = 1 