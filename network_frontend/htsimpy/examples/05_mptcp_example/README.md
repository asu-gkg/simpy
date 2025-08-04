# MPTCP（多路径TCP）仿真示例详解

## 概述

本示例演示了**多路径TCP（MPTCP）**的仿真，这是一个允许TCP连接同时使用多条网络路径的协议扩展。程序模拟了一个典型场景：移动设备同时通过3G和WiFi网络传输数据。

## MPTCP是什么？

MPTCP（Multipath TCP）是TCP的扩展，允许：
- 一个TCP连接使用多条网络路径
- 提高吞吐量（聚合多条路径的带宽）
- 提高可靠性（一条路径失败时自动切换）
- 适用于移动设备（同时有WiFi和蜂窝网络）

## 程序架构

```
┌─────────────┐                              ┌──────────────┐
│  MPTCP源端  │                              │  MPTCP接收端 │
│             │                              │              │
│  ┌────────┐ │     路径1 (3G网络)          │  ┌────────┐  │
│  │子流1   ├─┼────────────────────────────┼──┤子流1   │  │
│  └────────┘ │  慢速: 1Mbps, RTT=150ms    │  └────────┘  │
│             │                              │              │
│  ┌────────┐ │     路径2 (WiFi网络)        │  ┌────────┐  │
│  │子流2   ├─┼────────────────────────────┼──┤子流2   │  │
│  └────────┘ │  快速: 可配置速率和延迟     │  └────────┘  │
└─────────────┘                              └──────────────┘
```

## 关键组件说明

### 1. 网络拓扑

程序创建了两条不同特性的网络路径：

**路径1 - 3G网络模拟**
- 带宽：166 pkt/s (约1Mbps)
- RTT：150ms
- 模拟较慢的蜂窝网络

**路径2 - WiFi网络模拟**
- 带宽：可配置（默认400 pkt/s，约5Mbps）
- RTT：可配置（默认10ms）
- 模拟较快的WiFi网络

### 2. 队列结构

每条路径都有复杂的队列结构：

```
源端 → [PQueue] → [RandomQueue] → [Pipe] → 接收端
         ↑              ↑           ↑
    预处理队列      主队列      传输延迟
```

- **PQueue**：预处理队列，2倍带宽，避免突发
- **RandomQueue**：主队列，实现随机早期丢弃（RED）
- **Pipe**：模拟传播延迟（RTT的一半）

### 3. MPTCP算法

程序支持5种MPTCP拥塞控制算法：

1. **UNCOUPLED**（默认）
   - 每个子流独立进行拥塞控制
   - 简单但可能不公平

2. **COUPLED_INC**
   - 增量耦合，子流之间部分协调
   - 平衡性能和公平性

3. **FULLY_COUPLED**
   - 完全耦合，所有子流共享拥塞窗口
   - 最公平但可能牺牲性能

4. **COUPLED_TCP**
   - 模拟标准TCP行为的耦合算法
   - 对其他TCP流友好

5. **COUPLED_EPSILON**
   - 带ε参数的耦合算法
   - 可调节耦合程度

## 程序流程

### 1. 初始化阶段
```python
# 解析命令行参数
args = parse_arguments()

# 创建仿真实例
sim = MptcpSimulation(args)

# 设置仿真参数（带宽、延迟、缓冲区等）
sim._setup_simulation_params()
```

### 2. 创建网络拓扑
```python
# 创建管道（Pipe）- 模拟传播延迟
pipes['pipe1'] = Pipe(rtt1 / 2)  # 3G路径
pipes['pipe2'] = Pipe(rtt2 / 2)  # WiFi路径

# 创建随机队列 - 带RED功能
queues['queue1'] = RandomQueue(bitrate=service1, maxsize=buffer1)
queues['queue2'] = RandomQueue(bitrate=service2, maxsize=buffer2)
```

### 3. 建立MPTCP连接
```python
# 创建MPTCP源端和接收端
mptcp_src = MultipathTcpSrc(algorithm, eventlist, logger, rwnd)
mptcp_sink = MultipathTcpSink(eventlist)

# 创建TCP子流
for i in range(num_subflows):
    tcp_src = TcpSrc(...)
    tcp_sink = TcpSink()
    
    # 加入MPTCP连接
    mptcp_src.addSubflow(tcp_src)
    mptcp_sink.addSubflow(tcp_sink)
```

### 4. 运行仿真
```python
# 事件驱动仿真
while eventlist.do_next_event():
    # 处理下一个事件（发送包、接收ACK、超时等）
    pass
```

## 关键参数说明

### 命令行参数
```bash
python main.py [算法] [rate2] [rtt2] [rwnd] [run_paths]
```

- **算法**：MPTCP算法类型
- **rate2**：路径2速率（pkt/s）
- **rtt2**：路径2往返时延（ms）
- **rwnd**：接收窗口大小（包数）
- **run_paths**：运行路径选择
  - 0：仅路径1
  - 1：仅路径2
  - 2：双路径（默认）

### 缓冲区计算

缓冲区大小基于带宽延迟积（BDP）计算：

```python
# 路径1缓冲区 = 随机缓冲 + RTT * 带宽 * 12
buffer1 = RANDOM_BUFFER + RTT1 * 带宽1 * 12

# 路径2缓冲区 = 随机缓冲 + max(RTT * 带宽 * 4, 10)
buffer2 = RANDOM_BUFFER + max(RTT2 * 带宽2 * 4, 10)
```

## 输出解释

### 仿真参数输出
```
路径1: 1Mbps, RTT=150ms, 缓冲区=451500字节
路径2: 5Mbps, RTT=10ms, 缓冲区=34500字节
MPTCP算法: UNCOUPLED
接收窗口: 10
```

### 性能统计
```
MPTCP总体性能:
  累积确认: 12345678
  数据确认: 12345678

子流1性能:
  拥塞窗口: 50
  发送包数: 10000

队列统计:
  队列大小: 15000 bytes
  丢包数: 5
```

### 日志文件
程序生成详细日志文件：
```
data/logout.[rate2]pktps.[rtt2]ms.[rwnd]rwnd
```

## 典型使用场景

### 1. 基础测试
```bash
# 使用默认参数
uv run python main.py

# 相当于
python main.py UNCOUPLED 400 10
```

### 2. 测试不同算法
```bash
# 完全耦合算法
python main.py FULLY_COUPLED 400 10

# 带参数的耦合算法
python main.py COUPLED_EPSILON 0.5 400 10
```

### 3. 模拟不同网络条件
```bash
# 高延迟WiFi（卫星网络）
python main.py UNCOUPLED 1000 500

# 低带宽蜂窝网络
python main.py UNCOUPLED 50 200

# 极端不平衡路径
python main.py UNCOUPLED 1 1000
```

### 4. 单路径测试
```bash
# 仅使用3G路径
python main.py UNCOUPLED 400 10 10 0

# 仅使用WiFi路径
python main.py UNCOUPLED 400 10 10 1
```

## 代码结构

```
05_mptcp_example/
├── main.py          # 主程序
├── README.md        # 本文档
└── __init__.py      # Python包标识

依赖的核心模块：
├── protocols/
│   ├── tcp.py              # TCP协议实现
│   └── multipath_tcp.py    # MPTCP扩展
├── queues/
│   ├── base_queue.py       # 基础队列
│   └── random_queue.py     # RED队列
└── core/
    ├── eventlist.py        # 事件调度器
    ├── network.py          # 网络基础类
    └── pipe.py             # 传输管道
```

## 与C++版本的对应关系

本Python实现精确复现了C++版本（csg-htsim/sim/tests/main.cpp）的功能：

1. **相同的网络拓扑**：双路径结构，相同的队列配置
2. **相同的参数计算**：缓冲区大小、接收窗口等
3. **相同的MPTCP算法**：5种算法的实现逻辑
4. **相同的事件处理**：基于离散事件仿真

主要差异仅在语言特性：
- Python使用对象引用代替C++指针
- Python自动内存管理代替C++手动管理
- Python使用SimPy框架的协程机制

## 扩展和修改

### 添加新的MPTCP算法
1. 在`multipath_tcp.py`中定义新算法常量
2. 实现新的窗口管理逻辑
3. 在`main.py`中添加命令行支持

### 修改网络拓扑
1. 调整`_setup_simulation_params()`中的参数
2. 在`_create_network_topology()`中添加新组件
3. 更新路由配置

### 添加新的测量指标
1. 在日志记录器中添加新指标
2. 在`print_results()`中输出
3. 可选：写入日志文件

## 故障排除

### 常见问题

1. **没有数据传输**
   - 检查MODEL_RECEIVE_WINDOW配置
   - 确认MPTCP连接正确建立

2. **大量重传**
   - 可能是队列太小
   - 检查RTT和带宽设置是否合理

3. **仿真运行缓慢**
   - 减少仿真时长
   - 使用更大的事件粒度

## 参考资料

- [RFC 6824](https://tools.ietf.org/html/rfc6824) - TCP Extensions for Multipath Operation
- [MPTCP Linux实现](https://www.multipath-tcp.org/)
- HTSim论文和文档