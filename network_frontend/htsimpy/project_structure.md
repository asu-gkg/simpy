 # HTSimPy Project Structure

HTSimPy - Python implementation of htsim network simulator for SimAI integration

## 项目目录结构

```
network_frontend/htsimpy/
├── __init__.py                    # 主要导出接口
├── project_structure.md          # 本文档
├── README.md                     # 项目说明
│
├── core/                         # 核心组件 (对应htsim/sim/核心文件)
│   ├── __init__.py
│   ├── eventlist.py              # ← eventlist.h/cpp (事件调度系统)
│   ├── network.py                # ← network.h/cpp (网络基础抽象)
│   ├── packet.py                 # ← 各种packet.h文件的基类
│   ├── route.py                  # ← route.h/cpp (路由信息)
│   ├── routetable.py             # ← routetable.h/cpp (路由表)
│   ├── config.py                 # ← config.h (配置定义)
│   └── logger.py                 # ← loggers.h/cpp (日志系统)
│
├── packets/                      # 数据包类型 (对应各种packet文件)
│   ├── __init__.py
│   ├── base_packet.py            # 基础数据包类
│   ├── tcp_packet.py             # ← tcppacket.h/cpp
│   ├── ndp_packet.py             # ← ndppacket.h/cpp
│   ├── swift_packet.py           # ← swiftpacket.h/cpp
│   ├── roce_packet.py            # ← rocepacket.h/cpp
│   ├── hpcc_packet.py            # ← hpccpacket.h/cpp
│   └── strack_packet.py          # ← strackpacket.h/cpp
│
├── queues/                       # 队列系统 (对应各种queue文件)
│   ├── __init__.py
│   ├── base_queue.py             # ← queue.h/cpp (基础队列)
│   ├── fifo_queue.py             # FIFO队列实现
│   ├── priority_queue.py         # ← prioqueue.h/cpp
│   ├── random_queue.py           # ← randomqueue.h/cpp
│   ├── lossless_queue.py         # ← queue_lossless.h/cpp
│   ├── fair_queue.py             # ← fairpullqueue.h/cpp
│   └── composite_queue.py        # ← faircompositequeue.h/cpp
│
├── protocols/                    # 协议实现 (对应各种协议文件)
│   ├── __init__.py
│   ├── base_protocol.py          # 协议基类
│   ├── tcp.py                    # ← tcp.h/cpp
│   ├── ndp.py                    # ← ndp.h/cpp
│   ├── swift.py                  # ← swift.h/cpp
│   ├── roce.py                   # ← roce.h/cpp
│   ├── hpcc.py                   # ← hpcc.h/cpp
│   ├── strack.py                 # ← strack.h/cpp
│   └── dctcp.py                  # DCTCP实现 (基于tcp扩展)
│
├── topology/                     # 网络拓扑 (对应htsim中的拓扑构建)
│   ├── __init__.py
│   ├── base_topology.py          # 拓扑基类
│   ├── fat_tree.py               # Fat-tree拓扑
│   ├── leaf_spine.py             # Leaf-spine拓扑
│   ├── mesh.py                   # Mesh拓扑
│   └── topology_builder.py       # 拓扑构建器
│
├── switches/                     # 交换机模型 (对应switch相关文件)
│   ├── __init__.py
│   ├── base_switch.py            # ← switch.h/cpp
│   ├── cut_through_switch.py     # Cut-through交换机
│   └── store_forward_switch.py   # Store-and-forward交换机
│
├── utils/                        # 工具类
│   ├── __init__.py
│   ├── rng.py                    # ← rng.cpp (随机数生成)
│   ├── meter.py                  # ← meter.h/cpp (性能计量)
│   ├── timer.py                  # ← rtx_timer.h/cpp (定时器)
│   └── stats.py                  # 统计工具
│
├── api/                          # SimAI集成接口
│   ├── __init__.py
│   ├── htsimpy_network.py        # 主要NetworkAPI实现
│   ├── config_parser.py          # 配置解析器
│   └── flow_generator.py         # 流量生成器
│
├── examples/                     # 示例和测试
│   ├── __init__.py
│   ├── simple_network.py         # 简单网络示例
│   ├── fat_tree_test.py          # Fat-tree测试
│   └── protocol_comparison.py    # 协议对比测试
│
└── tests/                        # 单元测试
    ├── __init__.py
    ├── test_core.py
    ├── test_protocols.py
    ├── test_queues.py
    └── test_topology.py
```

## 核心文件对应关系

### 核心组件映射
| Python文件 | 对应C++文件 | 功能描述 |
|-----------|------------|----------|
| `core/eventlist.py` | `eventlist.h/cpp` | 离散事件调度系统 |
| `core/network.py` | `network.h/cpp` | 网络基础抽象类 |
| `core/packet.py` | 各`*packet.h` | 数据包基类定义 |
| `core/route.py` | `route.h/cpp` | 路由信息管理 |
| `core/routetable.py` | `routetable.h/cpp` | 路由表实现 |
| `core/logger.py` | `loggers.h/cpp` | 日志和统计系统 |

### 数据包映射
| Python文件 | 对应C++文件 | 协议类型 |
|-----------|------------|----------|
| `packets/tcp_packet.py` | `tcppacket.h/cpp` | TCP数据包 |
| `packets/ndp_packet.py` | `ndppacket.h/cpp` | NDP数据包 |
| `packets/swift_packet.py` | `swiftpacket.h/cpp` | Swift数据包 |
| `packets/roce_packet.py` | `rocepacket.h/cpp` | RoCE数据包 |
| `packets/hpcc_packet.py` | `hpccpacket.h/cpp` | HPCC数据包 |

### 协议映射
| Python文件 | 对应C++文件 | 协议描述 |
|-----------|------------|----------|
| `protocols/tcp.py` | `tcp.h/cpp` | TCP协议实现 |
| `protocols/ndp.py` | `ndp.h/cpp` | NDP协议实现 |
| `protocols/swift.py` | `swift.h/cpp` | Swift协议实现 |
| `protocols/roce.py` | `roce.h/cpp` | RoCE协议实现 |
| `protocols/hpcc.py` | `hpcc.h/cpp` | HPCC协议实现 |
| `protocols/strack.py` | `strack.h/cpp` | STrack协议实现 |

### 队列映射
| Python文件 | 对应C++文件 | 队列类型 |
|-----------|------------|----------|
| `queues/base_queue.py` | `queue.h/cpp` | 基础队列抽象 |
| `queues/priority_queue.py` | `prioqueue.h/cpp` | 优先级队列 |
| `queues/random_queue.py` | `randomqueue.h/cpp` | 随机队列 |
| `queues/lossless_queue.py` | `queue_lossless.h/cpp` | 无损队列 |
| `queues/fair_queue.py` | `fairpullqueue.h/cpp` | 公平队列 |

## SimAI集成接口

### 主要API类
```python
# api/htsimpy_network.py
class HTSimPyNetwork(AstraNetworkAPI):
    """
    HTSimPy网络后端 - 继承AstraNetworkAPI
    提供与SimAI系统的标准接口
    """
    
    def get_backend_type(self) -> BackendType:
        return BackendType.HTSimPy
    
    # 实现所有AstraNetworkAPI要求的方法
    def sim_send(self, ...): pass
    def sim_recv(self, ...): pass
    def sim_schedule(self, ...): pass
    # ... 其他方法
```

### 配置接口
```python
# api/config_parser.py  
class HTSimPyConfig:
    """HTSimPy配置解析器"""
    protocol: str = "ndp"           # 协议选择
    topology: str = "fat_tree"      # 拓扑类型
    link_speed: str = "100Gb/s"     # 链路速度
    queue_size: int = 64            # 队列大小
    buffer_size: int = 1024         # 缓冲区大小
```

## 设计原则

1. **模块化**: 每个组件独立，便于测试和维护
2. **可扩展**: 易于添加新协议和新功能
3. **高性能**: 基于AnaSim事件系统，保证仿真性能
4. **标准接口**: 完全兼容AstraNetworkAPI
5. **文档化**: 清晰的cpp文件对应关系

## 下一步实现计划

1. 实现核心组件(eventlist, network, packet)
2. 实现基础队列系统
3. 实现NDP协议作为第一个协议示例
4. 实现Fat-tree拓扑作为基础拓扑
5. 集成SimAI接口
6. 添加测试和示例