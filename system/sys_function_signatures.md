# Sys类函数签名

基于对Sys.cc/Sys.hh文件的分析，以下是Python版本中已实现的所有函数签名：

## 构造函数和析构函数
- `__init__(self, NI: AstraNetworkAPI, MEM: AstraMemoryAPI, id: int, npu_offset: int, num_passes: int, physical_dims: List[int], queues_per_dim: List[int], my_sys: str, my_workload: str, comm_scale: float, compute_scale: float, injection_scale: float, total_stat_rows: int, stat_row: int, path: str, run_name: str, seprate_log: bool, rendezvous_enabled: bool, gpu_type: GPUType, all_gpus: List[int], NVSwitchs: List[int], ngpus_per_node: int)` - 构造函数
- `__del__(self)` - 析构函数

## 事件处理方法
- `register_for_finished_stream(self, callable_obj: Callable) -> None` - 注册完成流
- `increase_finished_streams(self, amount: int) -> None` - 增加已完成流数量
- `zero_latecy_register_event(self, callable_obj: Callable, event: EventType, callData: CallData, cycles: int) -> None` - 零延迟注册事件
- `register_event(self, callable_obj: Callable, event: EventType, callData: CallData, cycles: int) -> None` - 注册事件
- `insert_into_ready_list(self, stream: BaseStream) -> None` - 插入到就绪列表
- `insert_into_running_list(self, stream: StreamBaseline) -> None` - 插入到运行列表
- `schedule(self, num: int) -> None` - 调度
- `register_phases(self, stream: BaseStream, phases_to_go: List[CollectivePhase]) -> None` - 注册阶段
- `call(self, event_type: EventType, data: CallData) -> None` - 调用
- `try_register_event(self, callable_obj: Callable, event: EventType, callData: CallData, cycles: Tick) -> None` - 尝试注册事件
- `call_events(self) -> None` - 调用事件
- `workload_finished(self) -> None` - 工作负载完成

## 静态方法
- `boostedTick() -> Tick` (静态) - 提升时钟周期
- `exiting() -> None` (静态) - 退出
- `sys_panic(msg: str) -> None` (静态) - 系统恐慌
- `get_layer_numbers(workload_input: str) -> int` (静态) - 获取层数
- `handleEvent(arg: Any) -> None` (静态) - 处理事件

## 工具方法
- `nextPowerOf2(self, n: int) -> int` - 下一个2的幂
- `exitSimLoop(self, msg: str) -> None` - 退出仿真循环
- `iterate(self) -> None` - 迭代
- `initialize_sys(self, name: str) -> bool` - 初始化系统
- `trim(self, string: str, whitespace: str) -> str` - 修剪字符串
- `parse_var(self, var: str, value: str) -> bool` - 解析变量
- `post_process_inputs(self) -> bool` - 后处理输入
- `generate_collective_implementation_from_input(self, input_str: str) -> List[CollectiveImplementation]` - 从输入生成集合实现
- `break_dimension(self, model_parallel_npu_group: int) -> int` - 分割维度
- `split_string(self, string: str, sep: str) -> List[str]` - 分割字符串
- `determine_chunk_size(self, size: int, msg_type: ComType) -> int` - 确定块大小
- `get_priority(self, pref_scheduling: SchedulingPolicy) -> int` - 获取优先级
- `generate_time(self, cycles: int) -> timespec_t` - 生成时间

## 通信方法
- `front_end_sim_send(self, delay: Tick, buffer: Any, count: int, msg_type: int, dst: int, tag: int, request: sim_request, msg_handler: CallableType, fun_arg: Any) -> int` - 前端仿真发送
- `front_end_sim_recv(self, delay: Tick, buffer: Any, count: int, msg_type: int, src: int, tag: int, request: sim_request, msg_handler: CallableType, fun_arg: Any) -> int` - 前端仿真接收
- `sim_send(self, delay: Tick, buffer: Any, count: int, msg_type: int, dst: int, tag: int, request: sim_request, msg_handler: CallableType, fun_arg: Any) -> int` - 仿真发送
- `sim_recv(self, delay: Tick, buffer: Any, count: int, msg_type: int, src: int, tag: int, request: sim_request, msg_handler: CallableType, fun_arg: Any) -> int` - 仿真接收
- `rendezvous_sim_send(self, delay: Tick, buffer: Any, count: int, msg_type: int, dst: int, tag: int, request: sim_request, msg_handler: CallableType, fun_arg: Any) -> int` - 集合点仿真发送
- `rendezvous_sim_recv(self, delay: Tick, buffer: Any, count: int, msg_type: int, src: int, tag: int, request: sim_request, msg_handler: CallableType, fun_arg: Any) -> int` - 集合点仿真接收

## 内存操作
- `mem_read(self, bytes_count: int) -> Tick` - 内存读取
- `mem_write(self, bytes_count: int) -> Tick` - 内存写入

## 集合生成方法
- `generate_all_reduce(self, size: int, involved_dimensions: List[bool], pref_scheduling: SchedulingPolicy, layer: int, event: EventType = EventType.NONE, layer_ptr: Optional[Callable] = None) -> DataSet` - 生成全归约
- `generate_all_to_all(self, size: int, involved_dimensions: List[bool], pref_scheduling: SchedulingPolicy, layer: int, event: EventType = EventType.NONE, layer_ptr: Optional[Callable] = None) -> DataSet` - 生成全到全
- `generate_all_gather(self, size: int, involved_dimensions: List[bool], pref_scheduling: SchedulingPolicy, layer: int, event: EventType = EventType.NONE, layer_ptr: Optional[Callable] = None) -> DataSet` - 生成全收集
- `generate_reduce_scatter(self, size: int, involved_dimensions: List[bool], pref_scheduling: SchedulingPolicy, layer: int, event: EventType = EventType.NONE, layer_ptr: Optional[Callable] = None) -> DataSet` - 生成归约分散
- `generate_collective(self, size: int, layer_num: int, topology: LogicalTopology, implementation_per_dimension: List[CollectiveImplementation], dimensions_involved: List[bool], collective_type: ComType, pref_scheduling: SchedulingPolicy, event: EventType = EventType.NONE, layer_ptr: Optional[Callable] = None) -> DataSet` - 生成集合通信
- `generate_collective_phase(self, collective_type: ComType, layer_num: int, topology: BasicLogicalTopology, data_size: int, queue_id: int, direction: Any, injection_policy: InjectionPolicy, collective_implementation: CollectiveImplementation, boost_mode: bool) -> CollectivePhase` - 生成集合阶段

## 流管理方法
- `insert_stream(self, queue: List[BaseStream], baseStream: BaseStream) -> None` - 插入流
- `proceed_to_next_vnet_baseline(self, stream: StreamBaseline) -> None` - 推进到下一个虚拟网络基线

## Mock NCCL方法
- `generate_net_test_flow_model(self, data_size: int, nums: int) -> Dict[Tuple[int, int], SingleFlow]` - 生成网络测试流模型
- `generate_nvl_test_flow_model(self, data_size: int, nums: int) -> Dict[Tuple[int, int], SingleFlow]` - 生成NVL测试流模型
- `generate_flow_model(self, comm_ps: ParallelStrategy, data_size: int, collective_type: ComType) -> Any` - 生成流模型
- `get_nccl_Info(self, comm_ps: ParallelStrategy, data_size: int, collective_type: ComType) -> ncclInfo` - 获取NCCL信息
- `mock_nccl_comms_init(self) -> bool` - Mock NCCL通信初始化
- `mock_nccl_grobal_group_init(self) -> bool` - Mock NCCL全局组初始化

## 内部类
### SchedulerUnit（调度器单元）
- `__init__(self, sys: 'Sys', queues: List[int], max_running_streams: int, ready_list_threshold: int, queue_threshold: int)` - 构造函数
- `notify_stream_removed(self, vnet: int, running_time: Tick) -> None` - 通知流移除
- `notify_stream_added(self, vnet: int) -> None` - 通知流添加
- `notify_stream_added_into_ready_list(self) -> None` - 通知流添加到就绪列表
- `get_average_latency_per_dimension(self) -> List[float]` - 获取每维度平均延迟

### sysCriticalSection（系统临界区）
- `__init__(self)` - 构造函数
- `ExitSection(self) -> None` - 退出区域
- `__del__(self)` - 析构函数

## 静态变量
- `g_sys_inCriticalSection: bool` - 全局系统临界区标志
- `offset: Tick` - 偏移量
- `dummy_data: bytes` - 虚拟数据
- `all_generators: List['Sys']` - 所有生成器

所有函数目前都以`pass`作为实现，准备根据原始C++代码进行实际实现。
