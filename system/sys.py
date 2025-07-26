# System class - corresponds to Sys.cc/Sys.hh in SimAI
# This is the main system simulation class that manages the entire simulation

from typing import List, Dict, Tuple, Optional, Any, Callable as CallableType
from abc import ABC, abstractmethod
import time
from enum import Enum
import threading
from .callable import Callable, CallData
from .common import (
    EventType, ComType, CollectiveImplementationType, CollectiveOptimization,
    SchedulingPolicy, IntraDimensionScheduling, InterDimensionScheduling,
    InjectionPolicy, StreamState, Tick, GPUType, ParallelStrategy
)
from .api import AstraNetworkAPI, AstraMemoryAPI
from .collective_phase import CollectivePhase
from .usage_tracker import UsageTracker
from .send_packet_event_handler_data import SendPacketEventHandlerData
from .mem_bus import MemBus
from .base_stream import BaseStream
from .stream_baseline import StreamBaseline
from .dataset import DataSet
from .sim_send_caller import SimSendCaller
from .sim_recv_caller import SimRecvCaller
from .queue_levels import QueueLevels
from .topology.logical_topology import LogicalTopology
from .topology.basic_logical_topology import BasicLogicalTopology
from .scheduling.offline_greedy import OfflineGreedy
from .collective.algorithm import CollectiveImplementation
from .mock_nccl_comm import MockNcclComm, SingleFlow, ncclInfo, sim_request, timespec_t
from .AstraNetworkAPI import SimRequest as sim_request, TimeSpec as timespec_t
from .mock_nccl_group import MockNcclGroup

from ..workload.workload import Workload

class Sys(Callable):
    """Main system simulation class - corresponds to Sys.hh in SimAI"""

    class SchedulerUnit:
        """Inner class for scheduler unit - corresponds to Sys::SchedulerUnit in SimAI"""

        def __init__(self, sys: 'Sys', queues: List[int], max_running_streams: int,
                     ready_list_threshold: int, queue_threshold: int):
            self.sys = sys
            self.ready_list_threshold = ready_list_threshold
            self.queue_threshold = queue_threshold
            self.max_running_streams = max_running_streams
            self.running_streams: Dict[int, int] = {}
            self.stream_pointer: Dict[int, Any] = {}  # iterator type
            self.latency_per_dimension: List[Tick] = []
            self.total_chunks_per_dimension: List[float] = []
            self.total_active_chunks_per_dimension: List[int] = []
            self.queue_id_to_dimension: Dict[int, int] = {}
            self.usage: List[UsageTracker] = []

        def notify_stream_removed(self, vnet: int, running_time: Tick) -> None:
            pass

        def notify_stream_added(self, vnet: int) -> None:
            pass

        def notify_stream_added_into_ready_list(self) -> None:
            pass

        def get_average_latency_per_dimension(self) -> List[float]:
            """Get average latency per dimension"""
            return [0.0] * len(self.usage)  # 返回默认值

    class sysCriticalSection:
        """Critical section class for thread safety - corresponds to Sys::sysCriticalSection in SimAI"""

        def __init__(self):
            # Simulate atomic exchange operation
            pass

        def ExitSection(self) -> None:
            pass

        def __del__(self):
            pass

    # Static class variables
    g_sys_inCriticalSection: bool = False
    offset: Tick = 0
    dummy_data: bytes = b'\x00\x00'
    all_generators: List['Sys'] = []

    def __init__(self, NI: AstraNetworkAPI, MEM: AstraMemoryAPI, id: int, npu_offset: int,
                num_passes: int, physical_dims: List[int], queues_per_dim: List[int],
                my_sys: str, my_workload: str, comm_scale: float, compute_scale: float,
                injection_scale: float, total_stat_rows: int, stat_row: int, path: str,
                run_name: str, seprate_log: bool, rendezvous_enabled: bool,
                gpu_type: GPUType, all_gpus: List[int], NVSwitchs: List[int],
                ngpus_per_node: int):
        """Constructor - corresponds to Sys::Sys in SimAI"""
        # Initialize member variables
        self.scheduler_unit: Optional[self.SchedulerUnit] = None
        self.NI = NI
        self.MEM = MEM
        self.finished_workloads = 0
        self.id = id
        self.npu_offset = npu_offset
        self.nvswitch_id = 0
        self.num_gpus = 0
        self.NVSwitchs = NVSwitchs
        self.ngpus_per_node = ngpus_per_node
        self.gpu_type = gpu_type

        # Collective implementation vectors
        self.all_reduce_implementation_per_dimension: List[CollectiveImplementation] = []
        self.reduce_scatter_implementation_per_dimension: List[CollectiveImplementation] = []
        self.all_gather_implementation_per_dimension: List[CollectiveImplementation] = []
        self.all_to_all_implementation_per_dimension: List[CollectiveImplementation] = []
        self.collectiveOptimization: CollectiveOptimization = CollectiveOptimization.Baseline

        # Timing
        self.start_sim_time = time.time()
        self.end_sim_time = 0.0
        self.freq = 1.0  # 频率，用于时间转换

        # Event handling
        self.registered_for_finished_stream_event: List[Callable] = []

        # Physical and logical dimensions
        self.physical_dims = physical_dims
        self.all_gpus = all_gpus
        self.queues_per_dim = queues_per_dim
        self.max_running = 0
        self.concurrent_streams = 0
        self.active_first_phase = 0
        self.dim_to_break = 0
        self.logical_broken_dims: List[int] = []

        # Scheduling and execution
        self.priority_counter = 0
        self.boost_mode = False
        self.rendezvous_enabled = rendezvous_enabled
        self.initialized = False

        # Latencies and delays
        self.processing_latency = 0
        self.communication_delay = 0
        self.preferred_dataset_splits = 0
        self.num_channels = 0
        self.compute_scale = compute_scale
        self.comm_scale = comm_scale
        self.injection_scale = injection_scale
        self.local_reduction_delay = 0
        self.pending_events = 0
        self.method = ""

        # Core components
        self.workload: Optional[Workload] = None
        self.memBus: Optional[MemBus] = None
        self.all_queues = 0
        self.ready_list: List[BaseStream] = []
        self.running_list: List[StreamBaseline] = []  # PHY_MTP
        self.scheduling_policy: SchedulingPolicy = SchedulingPolicy.FIFO
        self.first_phase_streams = 0
        self.total_running_streams = 0
        self.active_Streams: Dict[int, List[BaseStream]] = {}
        self.stream_priorities: Dict[int, List[int]] = {}

        # Data for analysis
        self.nic_ratio_data: List[List[str]] = []
        self.nvlink_ratio_data: List[List[str]] = []
        self.ata_ratio_data: List[List[str]] = []

        # Topology and levels
        self.vLevels: Optional[QueueLevels] = None
        self.logical_topologies: Dict[str, LogicalTopology] = {}
        self.event_queue: Dict[Tick, List[Tuple[Callable, EventType, CallData]]] = {}
        self.total_nodes = 0

        # Stream tracking
        self.streams_injected = 0
        self.streams_finished = 0
        self.stream_counter = 0
        self.enabled = False

        # Configuration strings
        self.inp_scheduling_policy = ""
        self.inp_all_reduce_implementation = ""
        self.inp_reduce_scatter_implementation = ""
        self.inp_all_gather_implementation = ""
        self.inp_all_to_all_implementation = ""
        self.inp_collective_optimization = ""

        # LogGP parameters
        self.inp_L = 0.0
        self.inp_o = 0.0
        self.inp_g = 0.0
        self.inp_G = 0.0
        self.inp_model_shared_bus = 0
        self.active_chunks_per_dimension = 0
        self.model_shared_bus = False
        self.inp_boost_mode = 0

        # Scheduling policies
        self.intra_dimension_scheduling: IntraDimensionScheduling = IntraDimensionScheduling.FIFO
        self.inter_dimension_scheduling: InterDimensionScheduling = InterDimensionScheduling.Ascending
        self.round_robin_inter_dimension_scheduler = 0
        self.offline_greedy: Optional[OfflineGreedy] = None
        self.last_scheduled_collective: Tick = 0

        # Communication tracking
        self.pending_sends: Dict[Tuple[int, int], List[SimSendCaller]] = {}
        self.is_there_pending_sends: Dict[Tuple[int, int], bool] = {}

        # Separate log flag
        self.seprate_log = seprate_log

        # Mock NCCL components
        self.mock_nccl_comms: Dict[ParallelStrategy, MockNcclComm] = {}

    def __del__(self):
        """Destructor - corresponds to Sys::~Sys in SimAI"""
        self.end_sim_time = time.time()
        duration_minutes = (self.end_sim_time - self.start_sim_time) / 60.0
        if self.id == 0:
            print("*****")
            print(f"Time to exit: {time.ctime()}")
            print(f"all-reduce Collective implementation: {self.inp_all_reduce_implementation}")
            print(f"reduce-scatter Collective implementation: {self.inp_reduce_scatter_implementation}")
            print(f"all-gather Collective implementation: {self.inp_all_gather_implementation}")
            print(f"all-to-all Collective implementation: {self.inp_all_to_all_implementation}")
            print("*****")

    # Event handling methods
    def register_for_finished_stream(self, callable_obj: Callable) -> None:
        """Register for finished stream event - corresponds to Sys::register_for_finished_stream"""
        pass

    def increase_finished_streams(self, amount: int) -> None:
        """Increase finished streams count - corresponds to Sys::increase_finished_streams"""
        pass

    def zero_latecy_register_event(self, callable_obj: Callable, event: EventType,
                                   callData: CallData, cycles: int) -> None:
        """Register zero latency event - corresponds to Sys::zero_latecy_register_event"""
        pass

    def register_event(self, callable_obj: Callable, event: EventType,
                       callData: CallData, cycles: int) -> None:
        """Register event - corresponds to Sys::register_event"""
        pass

    def insert_into_ready_list(self, stream: BaseStream) -> None:
        """Insert stream into ready list - corresponds to Sys::insert_into_ready_list"""
        pass

    def insert_into_running_list(self, stream: StreamBaseline) -> None:
        """Insert stream into running list - corresponds to Sys::insert_into_running_list (PHY_MTP)"""
        pass

    def schedule(self, num: int) -> None:
        """Schedule streams - corresponds to Sys::schedule"""
        pass

    def register_phases(self, stream: BaseStream, phases_to_go: List[CollectivePhase]) -> None:
        """Register phases for stream - corresponds to Sys::register_phases"""
        pass

    def call(self, event_type: EventType, data: CallData) -> None:
        """Handle events - implementation of Callable interface - corresponds to Sys::call"""
        pass

    def try_register_event(self, callable_obj: Callable, event: EventType,
                           callData: CallData, cycles: Tick) -> None:
        """Try to register event - corresponds to Sys::try_register_event"""
        pass

    def call_events(self) -> None:
        """Call events - corresponds to Sys::call_events"""
        pass

    def workload_finished(self) -> None:
        """Mark workload as finished - corresponds to Sys::workload_finished"""
        self.finished_workloads += 1

    # Static methods
    @staticmethod
    def boostedTick() -> Tick:
        """Get boosted tick - corresponds to Sys::boostedTick"""
        from .common import CLOCK_PERIOD
        
        ts = None
        if len(Sys.all_generators) > 0 and Sys.all_generators[0] is not None:
            ts = Sys.all_generators[0]
        else:
            # Look for first non-null generator
            for i in range(1, len(Sys.all_generators)):
                if Sys.all_generators[i] is not None:
                    ts = Sys.all_generators[i]
                    break
        
        if ts is None:
            return Sys.offset
        
        # Get simulation time from network interface
        tmp = ts.NI.sim_get_time()
        tick = tmp.time_val // CLOCK_PERIOD
        return tick + Sys.offset

    def get_tick(self) -> Tick:
        """Get current tick - corresponds to Sys::get_tick"""
        return self.boostedTick()

    @staticmethod
    def exiting() -> None:
        """Handle exiting - corresponds to Sys::exiting"""
        pass

    def nextPowerOf2(self, n: int) -> int:
        """Get next power of 2 - corresponds to Sys::nextPowerOf2"""
        pass

    @staticmethod
    def sys_panic(msg: str) -> None:
        """System panic - corresponds to Sys::sys_panic"""
        print(msg)
        exit(1)

    def exitSimLoop(self, msg: str) -> None:
        """Exit simulation loop - corresponds to Sys::exitSimLoop"""
        pass

    # Main simulation methods
    def iterate(self) -> None:
        """Main iteration method - corresponds to Sys::iterate"""
        self.call_events()

    def initialize_sys(self, name: str) -> bool:
        """Initialize system from file - corresponds to Sys::initialize_sys"""
        pass

    def trim(self, string: str, whitespace: str) -> str:
        """Trim string - corresponds to Sys::trim"""
        pass

    def parse_var(self, var: str, value: str) -> bool:
        """Parse variable - corresponds to Sys::parse_var"""
        pass

    def post_process_inputs(self) -> bool:
        """Post process inputs - corresponds to Sys::post_process_inputs"""
        pass

    def generate_collective_implementation_from_input(self, input_str: str) -> List[CollectiveImplementation]:
        """Generate collective implementation from input - corresponds to Sys::generate_collective_implementation_from_input"""
        pass

    def break_dimension(self, model_parallel_npu_group: int) -> int:
        """Break dimension - corresponds to Sys::break_dimension"""
        pass

    # Communication methods
    def front_end_sim_send(self, delay: Tick, buffer: Any, count: int, msg_type: int,
                           dst: int, tag: int, request: sim_request,
                           msg_handler: CallableType, fun_arg: Any) -> int:
        """Frontend simulation send - corresponds to Sys::front_end_sim_send"""
        pass

    def front_end_sim_recv(self, delay: Tick, buffer: Any, count: int, msg_type: int,
                           src: int, tag: int, request: sim_request,
                           msg_handler: CallableType, fun_arg: Any) -> int:
        """Frontend simulation receive - corresponds to Sys::front_end_sim_recv"""
        pass

    def sim_send(self, delay: Tick, buffer: Any, count: int, msg_type: int,
                 dst: int, tag: int, request: sim_request,
                 msg_handler: CallableType, fun_arg: Any) -> int:
        """Simulation send - corresponds to Sys::sim_send"""
        pass

    def sim_recv(self, delay: Tick, buffer: Any, count: int, msg_type: int,
                 src: int, tag: int, request: sim_request,
                 msg_handler: CallableType, fun_arg: Any) -> int:
        """Simulation receive - corresponds to Sys::sim_recv"""
        pass

    def rendezvous_sim_send(self, delay: Tick, buffer: Any, count: int, msg_type: int,
                            dst: int, tag: int, request: sim_request,
                            msg_handler: CallableType, fun_arg: Any) -> int:
        """Rendezvous simulation send - corresponds to Sys::rendezvous_sim_send"""
        pass

    def rendezvous_sim_recv(self, delay: Tick, buffer: Any, count: int, msg_type: int,
                            src: int, tag: int, request: sim_request,
                            msg_handler: CallableType, fun_arg: Any) -> int:
        """Rendezvous simulation receive - corresponds to Sys::rendezvous_sim_recv"""
        pass

    # Memory operations
    def mem_read(self, bytes_count: int) -> Tick:
        """Memory read operation - corresponds to Sys::mem_read"""
        pass

    def mem_write(self, bytes_count: int) -> Tick:
        """Memory write operation - corresponds to Sys::mem_write"""
        pass

    # Utility methods
    @staticmethod
    def get_layer_numbers(workload_input: str) -> int:
        """Get layer numbers from workload - corresponds to Sys::get_layer_numbers"""
        pass

    def split_string(self, string: str, sep: str) -> List[str]:
        """Split string - corresponds to Sys::split_string"""
        pass

    # Collective generation methods
    def generate_all_reduce(self, size: int, involved_dimensions: List[bool],
                            pref_scheduling: SchedulingPolicy, layer: int,
                            event: EventType = EventType.NONE,
                            layer_ptr: Optional[Callable] = None) -> DataSet:
        """Generate all-reduce collective - corresponds to Sys::generate_all_reduce"""
        pass

    def generate_all_to_all(self, size: int, involved_dimensions: List[bool],
                            pref_scheduling: SchedulingPolicy, layer: int,
                            event: EventType = EventType.NONE,
                            layer_ptr: Optional[Callable] = None) -> DataSet:
        """Generate all-to-all collective - corresponds to Sys::generate_all_to_all"""
        pass

    def generate_all_gather(self, size: int, involved_dimensions: List[bool],
                            pref_scheduling: SchedulingPolicy, layer: int,
                            event: EventType = EventType.NONE,
                            layer_ptr: Optional[Callable] = None) -> DataSet:
        """Generate all-gather collective - corresponds to Sys::generate_all_gather"""
        pass

    def generate_reduce_scatter(self, size: int, involved_dimensions: List[bool],
                                pref_scheduling: SchedulingPolicy, layer: int,
                                event: EventType = EventType.NONE,
                                layer_ptr: Optional[Callable] = None) -> DataSet:
        """Generate reduce-scatter collective - corresponds to Sys::generate_reduce_scatter"""
        pass

    def generate_collective(self, size: int, layer_num: int, topology: LogicalTopology,
                            implementation_per_dimension: List[CollectiveImplementation],
                            dimensions_involved: List[bool], collective_type: ComType,
                            pref_scheduling: SchedulingPolicy,
                            event: EventType = EventType.NONE,
                            layer_ptr: Optional[Callable] = None) -> DataSet:
        """Generate collective - corresponds to Sys::generate_collective"""
        pass

    # Additional collective and stream methods
    def generate_collective_phase(self, collective_type: ComType, layer_num: int,
                                  topology: BasicLogicalTopology, data_size: int,
                                  queue_id: int, direction: Any, injection_policy: InjectionPolicy,
                                  collective_implementation: CollectiveImplementation,
                                  boost_mode: bool) -> CollectivePhase:
        """Generate collective phase - corresponds to Sys::generate_collective_phase"""
        pass

    def insert_stream(self, queue: List[BaseStream], baseStream: BaseStream) -> None:
        """Insert stream into queue - corresponds to Sys::insert_stream"""
        pass

    def proceed_to_next_vnet_baseline(self, stream: StreamBaseline) -> None:
        """Proceed to next vnet baseline - corresponds to Sys::proceed_to_next_vnet_baseline"""
        pass

    def determine_chunk_size(self, size: int, msg_type: ComType) -> int:
        """Determine chunk size - corresponds to Sys::determine_chunk_size"""
        pass

    def get_priority(self, pref_scheduling: SchedulingPolicy) -> int:
        """Get priority - corresponds to Sys::get_priority"""
        pass

    @staticmethod
    def handleEvent(arg: Any) -> None:
        """Handle event - corresponds to Sys::handleEvent"""
        pass

    def generate_time(self, cycles: int) -> timespec_t:
        """Generate time - corresponds to Sys::generate_time"""
        pass

    # Mock NCCL methods
    def generate_net_test_flow_model(self, data_size: int, nums: int) -> Dict[Tuple[int, int], SingleFlow]:
        """Generate network test flow model - corresponds to Sys::generate_net_test_flow_model"""
        pass

    def generate_nvl_test_flow_model(self, data_size: int, nums: int) -> Dict[Tuple[int, int], SingleFlow]:
        """Generate NVLink test flow model - corresponds to Sys::generate_nvl_test_flow_model"""
        pass

    def generate_flow_model(self, comm_ps: ParallelStrategy, data_size: int,
                            collective_type: ComType) -> Any:
        """Generate flow model - corresponds to Sys::generate_flow_model"""
        pass

    def get_nccl_Info(self, comm_ps: ParallelStrategy, data_size: int,
                      collective_type: ComType) -> ncclInfo:
        """Get NCCL info - corresponds to Sys::get_nccl_Info"""
        pass

    def mock_nccl_comms_init(self) -> bool:
        """Initialize mock NCCL comms - corresponds to Sys::mock_nccl_comms_init"""
        pass

    def mock_nccl_grobal_group_init(self) -> bool:
        """Initialize mock NCCL global group - corresponds to Sys::mock_nccl_grobal_group_init"""
        pass
