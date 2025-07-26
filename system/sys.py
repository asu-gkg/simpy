# System class - corresponds to Sys.cc/Sys.hh in SimAI
# This is the main system simulation class that manages the entire simulation

from typing import List, Dict, Tuple, Optional, Any, Callable as CallableType
from abc import ABC, abstractmethod
import time
from enum import Enum
import threading
import math
import random
from .callable import Callable, CallData
from .common import (
    EventType, ComType, CollectiveImplementationType, CollectiveOptimization,
    SchedulingPolicy, IntraDimensionScheduling, InterDimensionScheduling,
    InjectionPolicy, StreamState, Tick, GPUType, ParallelStrategy, CLOCK_PERIOD
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
from .common import CollectiveImplementation
from .mock_nccl_comm import MockNcclComm, SingleFlow, ncclInfo
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
            self.latency_per_dimension: List[Tick] = [0] * len(queues)
            self.total_chunks_per_dimension: List[float] = [0.0] * len(queues)
            self.total_active_chunks_per_dimension: List[int] = [0] * len(queues)
            self.queue_id_to_dimension: Dict[int, int] = {}
            self.usage: List[UsageTracker] = [UsageTracker() for _ in queues]

            # 建立队列ID到维度的映射
            queue_id = 0
            for dim, queue_count in enumerate(queues):
                for _ in range(queue_count):
                    self.queue_id_to_dimension[queue_id] = dim
                    queue_id += 1

        def notify_stream_removed(self, vnet: int, running_time: Tick) -> None:
            """Notify that a stream has been removed"""
            if vnet in self.running_streams:
                del self.running_streams[vnet]
            
            # 更新统计信息
            if vnet in self.queue_id_to_dimension:
                dim = self.queue_id_to_dimension[vnet]
                if dim < len(self.latency_per_dimension):
                    self.latency_per_dimension[dim] += running_time
                    if dim < len(self.total_chunks_per_dimension):
                        self.total_chunks_per_dimension[dim] += 1.0

        def notify_stream_added(self, vnet: int) -> None:
            """Notify that a stream has been added"""
            if vnet not in self.running_streams:
                self.running_streams[vnet] = 1
            else:
                self.running_streams[vnet] += 1

        def notify_stream_added_into_ready_list(self) -> None:
            """Notify that a stream has been added to ready list"""
            # 可以在这里添加调度相关的逻辑
            pass

        def get_average_latency_per_dimension(self) -> List[float]:
            """Get average latency per dimension"""
            result = []
            for i, (latency, chunks) in enumerate(zip(self.latency_per_dimension, self.total_chunks_per_dimension)):
                if chunks > 0:
                    result.append(latency / chunks)
                else:
                    result.append(0.0)
            return result

    class sysCriticalSection:
        """Critical section class for thread safety - corresponds to Sys::sysCriticalSection in SimAI"""

        def __init__(self):
            # Simulate atomic exchange operation
            self.lock = threading.Lock()
            self.lock.acquire()

        def ExitSection(self) -> None:
            """Exit critical section"""
            try:
                self.lock.release()
            except:
                pass

        def __del__(self):
            """Destructor"""
            self.ExitSection()

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
        self.num_gpus = len(all_gpus) if all_gpus else 0
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
        self.max_running = 100000000
        self.concurrent_streams = 1
        self.active_first_phase = 100000000
        self.dim_to_break = -1
        self.logical_broken_dims: List[int] = []

        # Scheduling and execution
        self.priority_counter = 0
        self.boost_mode = False
        self.rendezvous_enabled = rendezvous_enabled
        self.initialized = False

        # Latencies and delays
        self.processing_latency = 10
        self.communication_delay = 10
        self.preferred_dataset_splits = 1
        self.num_channels = 1
        self.compute_scale = compute_scale
        self.comm_scale = comm_scale
        self.injection_scale = injection_scale
        self.local_reduction_delay = 1
        self.pending_events = 0
        self.method = "baseline"

        # Core components
        self.workload: Optional[Workload] = None
        self.memBus: Optional[MemBus] = None
        self.all_queues = sum(queues_per_dim)
        self.ready_list: List[BaseStream] = []
        self.running_list: List[StreamBaseline] = []  # PHY_MTP
        self.scheduling_policy: SchedulingPolicy = SchedulingPolicy.FIFO
        self.first_phase_streams = 0
        self.total_running_streams = 0
        self.active_Streams: Dict[int, List[BaseStream]] = {}
        self.stream_priorities: Dict[int, List[int]] = {}

        # Initialize active_Streams for each queue
        element = 0
        self.total_nodes = 1
        for current_dim in range(len(queues_per_dim)):
            if len(physical_dims) > current_dim and physical_dims[current_dim] >= 1:
                self.total_nodes *= physical_dims[current_dim]
            for j in range(queues_per_dim[current_dim]):
                self.active_Streams[element] = []
                self.stream_priorities[element] = []
                element += 1

        # Data for analysis
        self.nic_ratio_data: List[List[str]] = []
        self.nvlink_ratio_data: List[List[str]] = []
        self.ata_ratio_data: List[List[str]] = []

        # Topology and levels
        self.vLevels: Optional[QueueLevels] = None
        self.logical_topologies: Dict[str, LogicalTopology] = {}
        self.event_queue: Dict[Tick, List[Tuple[Callable, EventType, CallData]]] = {}

        # Stream tracking
        self.streams_injected = 0
        self.streams_finished = 0
        self.stream_counter = 0
        self.enabled = True

        # Configuration strings and parameters
        self.inp_scheduling_policy = "LIFO"
        self.inp_all_reduce_implementation = "NcclFlowModel"
        self.inp_reduce_scatter_implementation = "NcclFlowModel"
        self.inp_all_gather_implementation = "NcclFlowModel"
        self.inp_all_to_all_implementation = "NcclFlowModel"
        self.inp_collective_optimization = "baseline"

        # LogGP parameters
        self.inp_L = 0.0
        self.inp_o = 0.0
        self.inp_g = 0.0
        self.inp_G = 0.0
        self.inp_model_shared_bus = 0
        self.active_chunks_per_dimension = 1
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

        # 设置默认参数
        self.communication_delay = 10 * injection_scale
        self.preferred_dataset_splits = 1

        # Post process inputs
        self._post_process_inputs()

        # 扩展 all_generators
        if (id + npu_offset + 1) > len(Sys.all_generators):
            Sys.all_generators.extend([None] * ((id + npu_offset + 1) - len(Sys.all_generators)))
        Sys.all_generators[id + npu_offset] = self

        # 计算 concurrent_streams
        if len(queues_per_dim) > 0:
            self.concurrent_streams = math.ceil(self.active_chunks_per_dimension / queues_per_dim[0])

        # 初始化调度器单元
        self.scheduler_unit = self.SchedulerUnit(
            self, queues_per_dim, self.max_running,
            self.active_first_phase, self.concurrent_streams
        )

        # 初始化队列级别
        self.vLevels = QueueLevels(queues_per_dim, 0, self.NI.get_backend_type() if self.NI else "analytical")

        # 初始化网络接口
        if self.NI:
            self.NI.sim_init(self.MEM)

        # 初始化内存总线
        self.memBus = MemBus(
            "NPU", "MA", self, self.inp_L, self.inp_o, self.inp_g, self.inp_G,
            self.model_shared_bus, self.communication_delay, True
        )

        # 初始化工作负载
        self.workload = Workload(
            run_name, self, my_workload, num_passes, total_stat_rows,
            stat_row, path, self.seprate_log
        )

        if not self.workload.initialized:
            self.sys_panic("Unable to initialize the workload layer")

        # 初始化离线贪婪调度器（如果需要）
        if (self.inter_dimension_scheduling == InterDimensionScheduling.OfflineGreedy or
            self.inter_dimension_scheduling == InterDimensionScheduling.OfflineGreedyFlex):
            self.offline_greedy = OfflineGreedy(self)

        self.initialized = True

    def _post_process_inputs(self) -> bool:
        """Post process inputs - corresponds to Sys::post_process_inputs"""
        # 设置调度策略
        if self.inp_scheduling_policy == "LIFO":
            self.scheduling_policy = SchedulingPolicy.LIFO
        elif self.inp_scheduling_policy == "FIFO":
            self.scheduling_policy = SchedulingPolicy.FIFO
        else:
            self.scheduling_policy = SchedulingPolicy.FIFO

        # 设置集合优化
        if self.inp_collective_optimization == "baseline":
            self.collectiveOptimization = CollectiveOptimization.Baseline
        elif self.inp_collective_optimization == "localBWAware":
            self.collectiveOptimization = CollectiveOptimization.LocalBWAware

        # 设置模型共享总线
        self.model_shared_bus = (self.inp_model_shared_bus == 1)

        # 设置提升模式
        self.boost_mode = (self.inp_boost_mode == 1)

        # 生成集合实现
        self.all_reduce_implementation_per_dimension = self._generate_collective_implementation_from_input(
            self.inp_all_reduce_implementation
        )
        self.reduce_scatter_implementation_per_dimension = self._generate_collective_implementation_from_input(
            self.inp_reduce_scatter_implementation
        )
        self.all_gather_implementation_per_dimension = self._generate_collective_implementation_from_input(
            self.inp_all_gather_implementation
        )
        self.all_to_all_implementation_per_dimension = self._generate_collective_implementation_from_input(
            self.inp_all_to_all_implementation
        )

        return True

    def _generate_collective_implementation_from_input(self, input_str: str) -> List[CollectiveImplementation]:
        """Generate collective implementation from input string"""
        inputs_per_dimension = input_str.split("_")
        result = []

        for dimension_input in inputs_per_dimension:
            if dimension_input == "ring":
                result.append(CollectiveImplementation(CollectiveImplementationType.Ring))
            elif dimension_input == "oneRing":
                result.append(CollectiveImplementation(CollectiveImplementationType.OneRing))
            elif dimension_input == "doubleBinaryTree":
                result.append(CollectiveImplementation(CollectiveImplementationType.DoubleBinaryTree))
            elif dimension_input.startswith("direct"):
                window = -1
                if dimension_input != "direct" and len(dimension_input) > 6:
                    try:
                        window = int(dimension_input[6:])
                    except ValueError:
                        window = -1
                result.append(CollectiveImplementation(CollectiveImplementationType.Direct, window))
            elif dimension_input.startswith("oneDirect"):
                window = -1
                if dimension_input != "oneDirect" and len(dimension_input) > 9:
                    try:
                        window = int(dimension_input[9:])
                    except ValueError:
                        window = -1
                result.append(CollectiveImplementation(CollectiveImplementationType.OneDirect, window))
            elif dimension_input == "halvingDoubling":
                result.append(CollectiveImplementation(CollectiveImplementationType.HalvingDoubling))
            elif dimension_input == "oneHalvingDoubling":
                result.append(CollectiveImplementation(CollectiveImplementationType.OneHalvingDoubling))
            elif dimension_input == "NcclFlowModel":
                result.append(CollectiveImplementation(CollectiveImplementationType.NcclFlowModel))
            elif dimension_input == "ncclRingTreeModel":
                result.append(CollectiveImplementation(CollectiveImplementationType.NcclTreeFlowModel))
            else:
                self.sys_panic(f"Cannot interpret collective implementation: {dimension_input}")

        return result

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
            print(f"Total simulation duration: {duration_minutes:.2f} minutes")
            print(f"Total streams injected: {self.streams_injected}")
            print(f"Total streams finished: {self.streams_finished}")
            if self.streams_injected > 0:
                print(f"Percentage of finished streams: {(self.streams_finished / self.streams_injected) * 100:.2f}%")
            print("*****")

    # Event handling methods
    def register_for_finished_stream(self, callable_obj: Callable) -> None:
        """Register for finished stream event - corresponds to Sys::register_for_finished_stream"""
        self.registered_for_finished_stream_event.append(callable_obj)

    def increase_finished_streams(self, amount: int) -> None:
        """Increase finished streams count - corresponds to Sys::increase_finished_streams"""
        self.streams_finished += amount
        for c in self.registered_for_finished_stream_event:
            c.call(EventType.StreamsFinishedIncrease, None)

    def zero_latecy_register_event(self, callable_obj: Callable, event: EventType,
                                   callData: CallData, cycles: int) -> None:
        """Register zero latency event - corresponds to Sys::zero_latecy_register_event"""
        mycycles = 0
        should_schedule = False
        
        current_tick = self.boostedTick() + mycycles
        if current_tick not in self.event_queue:
            self.event_queue[current_tick] = []
            should_schedule = True
            
        self.event_queue[current_tick].append((callable_obj, event, callData))
        self.pending_events += 1
        
        if should_schedule:
            # 立即处理零延迟事件
            self._handle_event_immediate(event)

    def register_event(self, callable_obj: Callable, event: EventType,
                       callData: CallData, cycles: int) -> None:
        """Register event - corresponds to Sys::register_event"""
        mycycles = Tick(cycles)
        self.try_register_event(callable_obj, event, callData, mycycles)

    def try_register_event(self, callable_obj: Callable, event: EventType,
                           callData: CallData, cycles: Tick) -> None:
        """Try to register event - corresponds to Sys::try_register_event"""
        should_schedule = False
        
        current_tick = self.boostedTick() + cycles
        if current_tick not in self.event_queue:
            self.event_queue[current_tick] = []
            should_schedule = True
            
        self.event_queue[current_tick].append((callable_obj, event, callData))
        self.pending_events += 1
        
        if should_schedule and self.NI:
            tmp = self.generate_time(int(cycles))
            # 这里应该调用网络接口的调度方法
            # self.NI.sim_schedule(tmp, self.handleEvent, data)

    def _handle_event_immediate(self, event: EventType) -> None:
        """Handle immediate event"""
        if event == EventType.CallEvents:
            self.iterate()

    def call_events(self) -> None:
        """Call events - corresponds to Sys::call_events"""
        current_tick = self.boostedTick()
        
        if current_tick not in self.event_queue:
            return
            
        # 处理当前时刻的所有事件
        for callable_obj, event, call_data in self.event_queue[current_tick]:
            try:
                self.pending_events -= 1
                callable_obj.call(event, call_data)
            except Exception as e:
                print(f"Warning! a callable is removed before call: {e}")
                
        # 清理已处理的事件
        if current_tick in self.event_queue:
            del self.event_queue[current_tick]
            
        # 检查是否应该退出
        if (self.finished_workloads == 1 and 
            len(self.event_queue) == 0 and 
            len(self.pending_sends) == 0) or not self.initialized:
            # 应该退出模拟
            pass

    def workload_finished(self) -> None:
        """Mark workload as finished - corresponds to Sys::workload_finished"""
        self.finished_workloads += 1

    # Static methods
    @staticmethod
    def boostedTick() -> Tick:
        """Get boosted tick - corresponds to Sys::boostedTick"""
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
        if ts.NI:
            tmp = ts.NI.sim_get_time()
            tick = tmp.time_val // CLOCK_PERIOD
            return tick + Sys.offset
        else:
            return Sys.offset

    def get_tick(self) -> Tick:
        """Get current tick - corresponds to Sys::get_tick"""
        return self.boostedTick()

    @staticmethod
    def exiting() -> None:
        """Handle exiting - corresponds to Sys::exiting"""
        pass

    def nextPowerOf2(self, n: int) -> int:
        """Get next power of 2 - corresponds to Sys::nextPowerOf2"""
        if n <= 1:
            return 1
        count = 0
        while n > 1:
            n >>= 1
            count += 1
        return 1 << count

    @staticmethod
    def sys_panic(msg: str) -> None:
        """System panic - corresponds to Sys::sys_panic"""
        print(f"SYS PANIC: {msg}")
        exit(1)

    def exitSimLoop(self, msg: str) -> None:
        """Exit simulation loop - corresponds to Sys::exitSimLoop"""
        if self.id == 0:
            print(msg)
        if self.NI:
            self.NI.sim_finish()

    # Main simulation methods
    def iterate(self) -> None:
        """Main iteration method - corresponds to Sys::iterate"""
        self.call_events()

    def initialize_sys(self, name: str) -> bool:
        """Initialize system from file - corresponds to Sys::initialize_sys"""
        # 这里可以添加从配置文件读取系统参数的逻辑
        return True

    def trim(self, string: str, whitespace: str = " \t") -> str:
        """Trim string - corresponds to Sys::trim"""
        return string.strip(whitespace)

    def parse_var(self, var: str, value: str) -> bool:
        """Parse variable - corresponds to Sys::parse_var"""
        var = self.trim(var)
        value = self.trim(value)
        
        if self.id == 0:
            print(f"Var is: {var}, val is: {value}")
            
        if var == "scheduling-policy:":
            self.inp_scheduling_policy = value
        elif var == "all-reduce-implementation:":
            self.inp_all_reduce_implementation = value
        elif var == "reduce-scatter-implementation:":
            self.inp_reduce_scatter_implementation = value
        elif var == "all-gather-implementation:":
            self.inp_all_gather_implementation = value
        elif var == "all-to-all-implementation:":
            self.inp_all_to_all_implementation = value
        elif var == "collective-optimization:":
            self.inp_collective_optimization = value
        elif var == "endpoint-delay:":
            self.communication_delay = int(float(value)) * self.injection_scale
        elif var == "local-reduction-delay:":
            self.local_reduction_delay = int(float(value))
        elif var == "active-chunks-per-dimension:":
            self.active_chunks_per_dimension = int(float(value))
        elif var == "L:":
            self.inp_L = float(value)
        elif var == "o:":
            self.inp_o = float(value)
        elif var == "g:":
            self.inp_g = float(value)
        elif var == "G:":
            self.inp_G = float(value)
        elif var == "model-shared-bus:":
            self.inp_model_shared_bus = int(float(value))
        elif var == "preferred-dataset-splits:":
            self.preferred_dataset_splits = int(float(value))
        elif var == "boost-mode:":
            self.inp_boost_mode = int(float(value))
        elif var == "intra-dimension-scheduling:":
            if value == "FIFO":
                self.intra_dimension_scheduling = IntraDimensionScheduling.FIFO
            elif value == "RG":
                self.intra_dimension_scheduling = IntraDimensionScheduling.RG
            elif value == "smallestFirst":
                self.intra_dimension_scheduling = IntraDimensionScheduling.SmallestFirst
            elif value == "lessRemainingPhaseFirst":
                self.intra_dimension_scheduling = IntraDimensionScheduling.LessRemainingPhaseFirst
            else:
                self.sys_panic(f"unknown value for intra-dimension-scheduling: {value}")
        elif var == "inter-dimension-scheduling:":
            if value == "ascending":
                self.inter_dimension_scheduling = InterDimensionScheduling.Ascending
            elif value == "offlineGreedy":
                self.inter_dimension_scheduling = InterDimensionScheduling.OfflineGreedy
            elif value == "offlineGreedyFlex":
                self.inter_dimension_scheduling = InterDimensionScheduling.OfflineGreedyFlex
            elif value == "roundRobin":
                self.inter_dimension_scheduling = InterDimensionScheduling.RoundRobin
            else:
                self.sys_panic(f"unknown value for inter-dimension-scheduling: {value}")
        elif var == "seprate-log:":
            self.seprate_log = (int(float(value)) != 0)
        else:
            print(f"Unknown variable: {var}")
            return False
            
        return True

    def insert_into_ready_list(self, stream: BaseStream) -> None:
        """Insert stream into ready list - corresponds to Sys::insert_into_ready_list"""
        self.insert_stream(self.ready_list, stream)
        self.scheduler_unit.notify_stream_added_into_ready_list()

    def insert_into_running_list(self, stream: StreamBaseline) -> None:
        """Insert stream into running list - corresponds to Sys::insert_into_running_list (PHY_MTP)"""
        self.running_list.append(stream)

    def insert_stream(self, queue: List[BaseStream], baseStream: BaseStream) -> None:
        """Insert stream into queue - corresponds to Sys::insert_stream"""
        # 根据调度策略确定插入位置
        insert_pos = len(queue)
        
        if self.intra_dimension_scheduling == IntraDimensionScheduling.FIFO:
            # FIFO: 插入到末尾
            insert_pos = len(queue)
        elif self.intra_dimension_scheduling == IntraDimensionScheduling.SmallestFirst:
            # 最小优先：根据数据大小排序
            for i, stream in enumerate(queue):
                if not stream.initialized and hasattr(stream, 'my_current_phase'):
                    if (hasattr(baseStream, 'my_current_phase') and 
                        stream.my_current_phase.init_data_size > baseStream.my_current_phase.init_data_size):
                        insert_pos = i
                        break
        elif self.intra_dimension_scheduling == IntraDimensionScheduling.LessRemainingPhaseFirst:
            # 剩余阶段少的优先
            for i, stream in enumerate(queue):
                if not stream.initialized:
                    if len(stream.phases_to_go) < len(baseStream.phases_to_go):
                        continue
                    else:
                        insert_pos = i
                        break
        
        queue.insert(insert_pos, baseStream)

    def schedule(self, num: int) -> None:
        """Schedule streams - corresponds to Sys::schedule"""
        ready_list_size = len(self.ready_list)
        counter = min(num, ready_list_size)
        
        while counter > 0 and len(self.ready_list) > 0:
            stream = self.ready_list[0]
            if hasattr(stream, 'phases_to_go') and len(stream.phases_to_go) > 0:
                top_vn = stream.phases_to_go[0].queue_id
                
            self.proceed_to_next_vnet_baseline(stream)
            
            if hasattr(stream, 'current_queue_id') and stream.current_queue_id == -1:
                self.sys_panic("should not happen!")
                
            self.ready_list.pop(0)
            self.first_phase_streams += 1
            self.total_running_streams += 1
            counter -= 1

    def proceed_to_next_vnet_baseline(self, stream: BaseStream) -> None:
        """Proceed to next vnet baseline - corresponds to Sys::proceed_to_next_vnet_baseline"""
        # 这里应该实现流到下一个虚拟网络的转换逻辑
        if hasattr(stream, 'phases_to_go') and len(stream.phases_to_go) > 0:
            current_phase = stream.phases_to_go[0]
            # 模拟处理当前阶段
            stream.current_queue_id = current_phase.queue_id
            # 移除已处理的阶段
            if len(stream.phases_to_go) > 1:
                stream.phases_to_go = stream.phases_to_go[1:]
            else:
                stream.phases_to_go = []

    def register_phases(self, stream: BaseStream, phases_to_go: List[CollectivePhase]) -> None:
        """Register phases for stream - corresponds to Sys::register_phases"""
        for phase in phases_to_go:
            if phase.queue_id in self.stream_priorities:
                self.stream_priorities[phase.queue_id].append(stream.stream_num)

    def call(self, event_type: EventType, data: CallData) -> None:
        """Handle events - implementation of Callable interface - corresponds to Sys::call"""
        if self.id == 0 and event_type == EventType.General:
            self.increase_finished_streams(1)

    # Communication methods
    def front_end_sim_send(self, delay: Tick, buffer: Any, count: int, msg_type: int,
                           dst: int, tag: int, request: sim_request,
                           msg_handler: CallableType, fun_arg: Any) -> int:
        """Frontend simulation send - corresponds to Sys::front_end_sim_send"""
        if self.rendezvous_enabled:
            return self.rendezvous_sim_send(delay, buffer, count, msg_type, dst, tag, request, msg_handler, fun_arg)
        else:
            return self.sim_send(delay, buffer, count, msg_type, dst, tag, request, msg_handler, fun_arg)

    def front_end_sim_recv(self, delay: Tick, buffer: Any, count: int, msg_type: int,
                           src: int, tag: int, request: sim_request,
                           msg_handler: CallableType, fun_arg: Any) -> int:
        """Frontend simulation receive - corresponds to Sys::front_end_sim_recv"""
        if self.rendezvous_enabled:
            return self.rendezvous_sim_recv(delay, buffer, count, msg_type, src, tag, request, msg_handler, fun_arg)
        else:
            return self.sim_recv(delay, buffer, count, msg_type, src, tag, request, msg_handler, fun_arg)

    def sim_send(self, delay: Tick, buffer: Any, count: int, msg_type: int,
                 dst: int, tag: int, request: sim_request,
                 msg_handler: CallableType, fun_arg: Any) -> int:
        """Simulation send - corresponds to Sys::sim_send"""
        if delay == 0 and fun_arg is None:
            # 处理立即发送
            fun_arg_tmp = SendPacketEventHandlerData(self, self.id + self.npu_offset, dst, tag)
            fun_arg = fun_arg_tmp
            
            send_key = (dst, tag)
            if send_key not in self.is_there_pending_sends or not self.is_there_pending_sends[send_key]:
                self.is_there_pending_sends[send_key] = True
            else:
                # 有待处理的发送，加入队列
                if send_key not in self.pending_sends:
                    self.pending_sends[send_key] = []
                self.pending_sends[send_key].append(
                    SimSendCaller(self, buffer, count, msg_type, dst, tag, request, msg_handler, fun_arg)
                )
                return 1

        if delay == 0:
            # 立即发送
            if self.NI:
                self.NI.sim_send(buffer, count, msg_type, dst, tag, request, msg_handler, fun_arg)
        else:
            # 延迟发送
            sender = SimSendCaller(self, buffer, count, msg_type, dst, tag, request, msg_handler, fun_arg)
            self.try_register_event(sender, EventType.General, None, delay)
            
        return 1

    def sim_recv(self, delay: Tick, buffer: Any, count: int, msg_type: int,
                 src: int, tag: int, request: sim_request,
                 msg_handler: CallableType, fun_arg: Any) -> int:
        """Simulation receive - corresponds to Sys::sim_recv"""
        if delay == 0:
            # 立即接收
            if self.NI:
                self.NI.sim_recv(buffer, count, msg_type, src, tag, request, msg_handler, fun_arg)
        else:
            # 延迟接收
            receiver = SimRecvCaller(self, buffer, count, msg_type, src, tag, request, msg_handler, fun_arg)
            self.try_register_event(receiver, EventType.General, None, delay)
            
        return 1

    def rendezvous_sim_send(self, delay: Tick, buffer: Any, count: int, msg_type: int,
                            dst: int, tag: int, request: sim_request,
                            msg_handler: CallableType, fun_arg: Any) -> int:
        """Rendezvous simulation send - corresponds to Sys::rendezvous_sim_send"""
        # 实现会合发送协议
        # 这里应该先发送一个小的控制消息，然后等待确认
        rendevouz_size = 8192
        new_request = request.__class__(
            srcRank=request.dstRank,
            dstRank=request.srcRank,
            reqCount=rendevouz_size,
            tag=tag + 500000000
        )
        
        # 先接收确认消息
        self.sim_recv(delay, buffer, rendevouz_size, msg_type, dst, 
                      tag + 500000000, new_request, self.handleEvent, None)
        return 1

    def rendezvous_sim_recv(self, delay: Tick, buffer: Any, count: int, msg_type: int,
                            src: int, tag: int, request: sim_request,
                            msg_handler: CallableType, fun_arg: Any) -> int:
        """Rendezvous simulation receive - corresponds to Sys::rendezvous_sim_recv"""
        # 实现会合接收协议
        rendevouz_size = 8192
        new_request = request.__class__(
            srcRank=request.dstRank,
            dstRank=request.srcRank,
            reqCount=rendevouz_size,
            tag=tag + 500000000
        )
        
        # 先发送确认消息
        self.sim_send(delay, buffer, rendevouz_size, msg_type, src,
                      tag + 500000000, new_request, self.handleEvent, None)
        return 1

    # Memory operations
    def mem_read(self, bytes_count: int) -> Tick:
        """Memory read operation - corresponds to Sys::mem_read"""
        if self.MEM is None:
            return 10
        delay_ns = self.MEM.npu_mem_read(bytes_count)
        delay_cycles = delay_ns // CLOCK_PERIOD
        return delay_cycles

    def mem_write(self, bytes_count: int) -> Tick:
        """Memory write operation - corresponds to Sys::mem_write"""
        if self.MEM is None:
            return 10
        delay_ns = self.MEM.npu_mem_write(bytes_count)
        delay_cycles = delay_ns // CLOCK_PERIOD
        return delay_cycles

    # Utility methods
    @staticmethod
    def get_layer_numbers(workload_input: str) -> int:
        """Get layer numbers from workload - corresponds to Sys::get_layer_numbers"""
        # 这里应该解析工作负载文件获取层数
        # 暂时返回默认值
        return 1

    def split_string(self, string: str, sep: str) -> List[str]:
        """Split string - corresponds to Sys::split_string"""
        return string.split(sep)

    def determine_chunk_size(self, size: int, msg_type: ComType) -> int:
        """Determine chunk size - corresponds to Sys::determine_chunk_size"""
        chunk_size = size // self.preferred_dataset_splits
        return max(chunk_size, 1)  # 确保至少为1

    def get_priority(self, pref_scheduling: SchedulingPolicy) -> int:
        """Get priority - corresponds to Sys::get_priority"""
        if pref_scheduling == SchedulingPolicy.NONE:
            if self.scheduling_policy == SchedulingPolicy.LIFO:
                self.priority_counter += 1
                return self.priority_counter
            else:
                self.priority_counter -= 1
                return self.priority_counter
        elif pref_scheduling == SchedulingPolicy.HIGHEST:
            return 100000000
        else:
            if self.scheduling_policy == SchedulingPolicy.LIFO:
                self.priority_counter += 1
                return self.priority_counter
            else:
                self.priority_counter -= 1
                return self.priority_counter

    @staticmethod
    def handleEvent(arg: Any) -> None:
        """Handle event - corresponds to Sys::handleEvent"""
        if arg is None:
            return
        # 这里应该根据事件类型处理不同的事件
        # 具体实现依赖于 BasicEventHandlerData 的结构

    def generate_time(self, cycles: int) -> timespec_t:
        """Generate time - corresponds to Sys::generate_time"""
        # 生成时间规格
        time_val = cycles * CLOCK_PERIOD
        return timespec_t(time_val=time_val)

    # Collective generation methods
    def generate_all_reduce(self, size: int, involved_dimensions: List[bool],
                            pref_scheduling: SchedulingPolicy, layer: int,
                            event: EventType = EventType.NONE,
                            layer_ptr: Optional[Callable] = None) -> DataSet:
        """Generate all-reduce collective - corresponds to Sys::generate_all_reduce"""
        return self.generate_collective(
            size, layer, self.logical_topologies.get("AllReduce"),
            self.all_reduce_implementation_per_dimension, involved_dimensions,
            ComType.All_Reduce, pref_scheduling, event, layer_ptr
        )

    def generate_all_to_all(self, size: int, involved_dimensions: List[bool],
                            pref_scheduling: SchedulingPolicy, layer: int,
                            event: EventType = EventType.NONE,
                            layer_ptr: Optional[Callable] = None) -> DataSet:
        """Generate all-to-all collective - corresponds to Sys::generate_all_to_all"""
        return self.generate_collective(
            size, layer, self.logical_topologies.get("AllToAll"),
            self.all_to_all_implementation_per_dimension, involved_dimensions,
            ComType.All_to_All, pref_scheduling, event, layer_ptr
        )

    def generate_all_gather(self, size: int, involved_dimensions: List[bool],
                            pref_scheduling: SchedulingPolicy, layer: int,
                            event: EventType = EventType.NONE,
                            layer_ptr: Optional[Callable] = None) -> DataSet:
        """Generate all-gather collective - corresponds to Sys::generate_all_gather"""
        return self.generate_collective(
            size, layer, self.logical_topologies.get("AllGather"),
            self.all_gather_implementation_per_dimension, involved_dimensions,
            ComType.All_Gather, pref_scheduling, event, layer_ptr
        )

    def generate_reduce_scatter(self, size: int, involved_dimensions: List[bool],
                                pref_scheduling: SchedulingPolicy, layer: int,
                                event: EventType = EventType.NONE,
                                layer_ptr: Optional[Callable] = None) -> DataSet:
        """Generate reduce-scatter collective - corresponds to Sys::generate_reduce_scatter"""
        return self.generate_collective(
            size, layer, self.logical_topologies.get("ReduceScatter"),
            self.reduce_scatter_implementation_per_dimension, involved_dimensions,
            ComType.Reduce_Scatter, pref_scheduling, event, layer_ptr
        )

    def generate_collective(self, size: int, layer_num: int, topology: LogicalTopology,
                            implementation_per_dimension: List[CollectiveImplementation],
                            dimensions_involved: List[bool], collective_type: ComType,
                            pref_scheduling: SchedulingPolicy,
                            event: EventType = EventType.NONE,
                            layer_ptr: Optional[Callable] = None) -> DataSet:
        """Generate collective - corresponds to Sys::generate_collective"""
        if topology is None:
            self.sys_panic("Topology is None in generate_collective")
            
        chunk_size = self.determine_chunk_size(size, collective_type)
        if self.id == 0:
            print(f"chunk size is: {chunk_size}, size is: {size}, layer_num is: {layer_num}, node: {self.id}")
            
        recommended_chunk_size = chunk_size
        streams = math.ceil(size / chunk_size)
        dataset = DataSet(streams)
        
        # 设置通知器（如果需要）
        if event != EventType.NONE and layer_ptr is not None:
            dataset.set_notifier(layer_ptr, event)
            
        pri = self.get_priority(pref_scheduling)
        count = 0
        
        # 处理离线贪婪调度
        if (self.id == 0 and 
            (self.inter_dimension_scheduling == InterDimensionScheduling.OfflineGreedy or
             self.inter_dimension_scheduling == InterDimensionScheduling.OfflineGreedyFlex)):
            if self.last_scheduled_collective != self.boostedTick():
                if self.offline_greedy:
                    self.offline_greedy.reset_loads()
                self.last_scheduled_collective = self.boostedTick()
        
        while size > 0:
            count += 1
            chunk_size = min(chunk_size, size)
            
            # 创建维度映射器
            dim_mapper = list(range(topology.get_num_of_dimensions()))
            
            # 根据集合类型调整维度顺序
            if collective_type == ComType.All_Gather:
                dim_mapper.reverse()
                
            # 根据维度间调度策略调整顺序
            if self.inter_dimension_scheduling == InterDimensionScheduling.RoundRobin:
                # 轮询调度
                if self.round_robin_inter_dimension_scheduler < len(dim_mapper):
                    dim_mapper = (dim_mapper[self.round_robin_inter_dimension_scheduler:] +
                                  dim_mapper[:self.round_robin_inter_dimension_scheduler])
                self.round_robin_inter_dimension_scheduler += 1
                if self.round_robin_inter_dimension_scheduler >= topology.get_num_of_dimensions():
                    self.round_robin_inter_dimension_scheduler = 0
            elif (collective_type != ComType.All_to_All and
                  (self.inter_dimension_scheduling == InterDimensionScheduling.OfflineGreedy or
                   self.inter_dimension_scheduling == InterDimensionScheduling.OfflineGreedyFlex)):
                # 离线贪婪调度
                if self.offline_greedy:
                    prev_size = size
                    dim_mapper = self.offline_greedy.get_chunk_scheduling(
                        self.stream_counter, size, recommended_chunk_size,
                        dimensions_involved, self.inter_dimension_scheduling, collective_type
                    )
                    chunk_size = prev_size - size
            
            # 减少剩余大小
            if (collective_type == ComType.All_to_All or
                (self.inter_dimension_scheduling != InterDimensionScheduling.OfflineGreedy and
                 self.inter_dimension_scheduling != InterDimensionScheduling.OfflineGreedyFlex)):
                size -= chunk_size
                
            tmp = chunk_size
            phases = []
            
            # 生成集合阶段
            if (collective_type != ComType.All_Reduce or
                self.collectiveOptimization == CollectiveOptimization.Baseline):
                # 基线实现
                for dim in range(topology.get_num_of_dimensions()):
                    mapped_dim = dim_mapper[dim]
                    if (topology.get_num_of_nodes_in_dimension(mapped_dim) == 1 or
                        not dimensions_involved[mapped_dim]):
                        continue
                        
                    # 获取队列
                    queue_info = self.vLevels.get_next_queue_at_level(mapped_dim)
                    queue_id = queue_info[0] if isinstance(queue_info, tuple) else queue_info
                    direction = queue_info[1] if isinstance(queue_info, tuple) and len(queue_info) > 1 else 0
                    
                    # 生成集合阶段
                    phase = self.generate_collective_phase(
                        collective_type, layer_num,
                        topology.get_basic_topology_at_dimension(mapped_dim, collective_type),
                        tmp, queue_id, direction, InjectionPolicy.Normal,
                        implementation_per_dimension[mapped_dim], self.boost_mode
                    )
                    phases.append(phase)
                    tmp = phase.final_data_size
            else:
                # 优化的 All-Reduce 实现（Reduce-Scatter + All-Gather）
                # Reduce-Scatter 阶段
                for dim in range(topology.get_num_of_dimensions()):
                    mapped_dim = dim_mapper[dim]
                    if (topology.get_num_of_nodes_in_dimension(mapped_dim) == 1 or
                        not dimensions_involved[mapped_dim]):
                        continue
                        
                    queue_info = self.vLevels.get_next_queue_at_level(mapped_dim)
                    queue_id = queue_info[0] if isinstance(queue_info, tuple) else queue_info
                    direction = queue_info[1] if isinstance(queue_info, tuple) and len(queue_info) > 1 else 0
                    
                    phase = self.generate_collective_phase(
                        ComType.Reduce_Scatter, layer_num,
                        topology.get_basic_topology_at_dimension(mapped_dim, ComType.Reduce_Scatter),
                        tmp, queue_id, direction, InjectionPolicy.Normal,
                        implementation_per_dimension[mapped_dim], self.boost_mode
                    )
                    phases.append(phase)
                    tmp = phase.final_data_size
                    
                # All-Gather 阶段（反向）
                for dim in range(topology.get_num_of_dimensions() - 1, -1, -1):
                    mapped_dim = dim_mapper[dim]
                    if (topology.get_num_of_nodes_in_dimension(mapped_dim) == 1 or
                        not dimensions_involved[mapped_dim]):
                        continue
                        
                    queue_info = self.vLevels.get_next_queue_at_level(mapped_dim)
                    queue_id = queue_info[0] if isinstance(queue_info, tuple) else queue_info
                    direction = queue_info[1] if isinstance(queue_info, tuple) and len(queue_info) > 1 else 0
                    
                    phase = self.generate_collective_phase(
                        ComType.All_Gather, layer_num,
                        topology.get_basic_topology_at_dimension(mapped_dim, ComType.All_Gather),
                        tmp, queue_id, direction, InjectionPolicy.Normal,
                        implementation_per_dimension[mapped_dim], self.boost_mode
                    )
                    phases.append(phase)
                    tmp = phase.final_data_size
            
            # 创建流并添加到数据集
            if len(phases) > 0:
                stream = BaseStream(
                    self.stream_counter, self, phases, pri,
                    self.get_tick() + self.communication_delay
                )
                self.streams_injected += 1
                self.stream_counter += 1
                dataset.add_stream(stream)
                
        return dataset

    def generate_collective_phase(self, collective_type: ComType, layer_num: int,
                                  topology: BasicLogicalTopology, data_size: int,
                                  queue_id: int, direction: Any, injection_policy: InjectionPolicy,
                                  collective_implementation: CollectiveImplementation,
                                  boost_mode: bool) -> CollectivePhase:
        """Generate collective phase - corresponds to Sys::generate_collective_phase"""
        # 根据集合实现类型创建相应的集合阶段
        if collective_implementation.type == CollectiveImplementationType.Ring:
            from .collective.ring import Ring
            collective_impl = Ring(
                collective_type, self.id, layer_num, topology,
                data_size, direction, injection_policy, boost_mode
            )
        elif collective_implementation.type == CollectiveImplementationType.OneRing:
            from .collective.ring import Ring
            collective_impl = Ring(
                collective_type, self.id, layer_num, topology,
                data_size, direction, injection_policy, boost_mode
            )
        elif collective_implementation.type == CollectiveImplementationType.DoubleBinaryTree:
            from .collective.double_binary_tree_allreduce import DoubleBinaryTreeAllReduce
            collective_impl = DoubleBinaryTreeAllReduce(
                self.id, layer_num, topology, data_size, boost_mode
            )
        elif collective_implementation.type == CollectiveImplementationType.HalvingDoubling:
            from .collective.halving_doubling import HalvingDoubling
            collective_impl = HalvingDoubling(
                collective_type, self.id, layer_num, topology,
                data_size, boost_mode
            )
        elif collective_implementation.type == CollectiveImplementationType.OneHalvingDoubling:
            from .collective.halving_doubling import HalvingDoubling
            collective_impl = HalvingDoubling(
                collective_type, self.id, layer_num, topology,
                data_size, boost_mode
            )
        elif collective_implementation.type == CollectiveImplementationType.Direct:
            from .collective.all_to_all import AllToAll
            window = getattr(collective_implementation, 'direct_collective_window', -1)
            collective_impl = AllToAll(
                collective_type, window, self.id, layer_num, topology,
                data_size, direction, InjectionPolicy.Normal, boost_mode
            )
        elif collective_implementation.type == CollectiveImplementationType.OneDirect:
            from .collective.all_to_all import AllToAll
            window = getattr(collective_implementation, 'direct_collective_window', -1)
            collective_impl = AllToAll(
                collective_type, window, self.id, layer_num, topology,
                data_size, direction, InjectionPolicy.Normal, boost_mode
            )
        elif collective_implementation.type == CollectiveImplementationType.NcclFlowModel:
            from .collective.nccl_tree_flow_model import NcclTreeFlowModel
            
            # 获取并行策略
            comm_ps = ParallelStrategy.NONE
            if self.workload and hasattr(self.workload, 'current_state'):
                if hasattr(self.workload, 'index') and hasattr(self.workload, 'layers'):
                    if (self.workload.index < len(self.workload.layers) and 
                        self.workload.layers[self.workload.index]):
                        layer = self.workload.layers[self.workload.index]
                        if self.workload.current_state == "Forward_Pass":
                            comm_ps = getattr(layer, 'fwd_pass_group_type', ParallelStrategy.NONE)
                        elif self.workload.current_state == "Input_Gradient":
                            comm_ps = getattr(layer, 'input_grad_group_type', ParallelStrategy.NONE)
                        elif self.workload.current_state == "Weight_Gradient":
                            comm_ps = getattr(layer, 'weight_grad_group_type', ParallelStrategy.NONE)
            
            # 生成流模型
            nccl_info = self.get_nccl_Info(comm_ps, data_size, collective_type)
            flow_models = self.generate_flow_model(comm_ps, data_size, collective_type)
            
            collective_impl = NcclTreeFlowModel(
                collective_type, self.id, layer_num, topology,
                data_size, direction, injection_policy, boost_mode,
                flow_models, 1  # channel count
            )
        else:
            self.sys_panic(f"Unknown collective implementation type: {collective_implementation.type}")
            
        return CollectivePhase(self, queue_id, collective_impl)

    # Mock NCCL methods
    def generate_net_test_flow_model(self, data_size: int, nums: int) -> Dict[Tuple[int, int], SingleFlow]:
        """Generate network test flow model - corresponds to Sys::generate_net_test_flow_model"""
        result = {}
        for i in range(nums):
            flow = SingleFlow(
                flow_id=i, src=0, dest=1, flow_size=data_size,
                parent_flow_id=[], child_flow_id=[], channel_id=0
            )
            result[(0, i)] = flow
        return result

    def generate_nvl_test_flow_model(self, data_size: int, nums: int) -> Dict[Tuple[int, int], SingleFlow]:
        """Generate NVLink test flow model - corresponds to Sys::generate_nvl_test_flow_model"""
        result = {}
        for i in range(nums):
            flow = SingleFlow(
                flow_id=i, src=0, dest=1, flow_size=data_size,
                parent_flow_id=[], child_flow_id=[], channel_id=0
            )
            result[(0, i)] = flow
        return result

    def generate_flow_model(self, comm_ps: ParallelStrategy, data_size: int,
                            collective_type: ComType) -> Any:
        """Generate flow model - corresponds to Sys::generate_flow_model"""
        if comm_ps in self.mock_nccl_comms:
            # 转换工作负载状态
            current_state = "Forward_Pass"
            if self.workload and hasattr(self.workload, 'current_state'):
                current_state = self.workload.current_state
                
            return self.mock_nccl_comms[comm_ps].get_flow_model(
                data_size, collective_type, 
                self.workload.index if self.workload else 0,
                current_state
            )
        return None

    def get_nccl_Info(self, comm_ps: ParallelStrategy, data_size: int,
                      collective_type: ComType) -> ncclInfo:
        """Get NCCL info - corresponds to Sys::get_nccl_Info"""
        if comm_ps in self.mock_nccl_comms:
            return self.mock_nccl_comms[comm_ps].get_algo_proto_info(data_size, collective_type)
        # 返回默认的 NCCL 信息
        return ncclInfo()

    def mock_nccl_comms_init(self) -> bool:
        """Initialize mock NCCL comms - corresponds to Sys::mock_nccl_comms_init"""
        if not self.workload:
            return False
            
        TP_size = (self.workload.model_parallel_npu_group 
                   if self.workload.model_parallel_npu_group > 0 
                   else self.total_nodes)
        PP_size = 1
        DP_size = self.total_nodes // (TP_size * PP_size)
        EP_size = getattr(self.workload, 'expert_parallel_npu_group', 1)
        DP_EP_size = DP_size // EP_size if EP_size > 0 else DP_size
        
        # 创建各种并行策略的通信器
        if TP_size > 1:
            self.mock_nccl_comms[ParallelStrategy.TP] = MockNcclComm(
                self.id, "TP", None  # 这里应该传入 global group
            )
        if DP_size > 1:
            self.mock_nccl_comms[ParallelStrategy.DP] = MockNcclComm(
                self.id, "DP", None
            )
        if EP_size > 1:
            self.mock_nccl_comms[ParallelStrategy.EP] = MockNcclComm(
                self.id, "EP", None
            )
        if DP_EP_size > 1:
            self.mock_nccl_comms[ParallelStrategy.DP_EP] = MockNcclComm(
                self.id, "DP_EP", None
            )
            
        return True

    def mock_nccl_grobal_group_init(self) -> bool:
        """Initialize mock NCCL global group - corresponds to Sys::mock_nccl_grobal_group_init"""
        # 这里应该初始化全局NCCL组
        # 暂时返回True，表示初始化成功
        return True

    def break_dimension(self, model_parallel_npu_group: int) -> int:
        """Break dimension - corresponds to Sys::break_dimension"""
        if model_parallel_npu_group == 1:
            return -1
            
        dimension_to_break = 0
        all_npus = 1
        
        for dimension_to_break in range(len(self.physical_dims)):
            if all_npus * self.physical_dims[dimension_to_break] < model_parallel_npu_group:
                all_npus *= self.physical_dims[dimension_to_break]
            elif all_npus * self.physical_dims[dimension_to_break] > model_parallel_npu_group:
                # 需要拆分这个维度
                first_subdim = model_parallel_npu_group // all_npus
                second_subdim = self.physical_dims[dimension_to_break] // first_subdim
                
                # 重新构建逻辑维度
                logical_dims = []
                for dim in range(len(self.physical_dims)):
                    if dim != dimension_to_break:
                        logical_dims.append(self.physical_dims[dim])
                    else:
                        logical_dims.extend([first_subdim, second_subdim])
                        
                self.logical_broken_dims = logical_dims
                self.dim_to_break = dimension_to_break
                
                # 这里需要重新初始化相关组件
                # 包括 scheduler_unit, vLevels, logical_topologies 等
                
                return dimension_to_break
            elif all_npus * self.physical_dims[dimension_to_break] == model_parallel_npu_group:
                return dimension_to_break
                
        return -1
