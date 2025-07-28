# 简单点对点通信示例

这是HTSimPy最基础的示例，演示了如何使用HTSimPy进行简单的点对点网络通信仿真。

## 功能特性

- 基于htsim对应实现：使用真实对应C++文件的组件
- 事件驱动仿真：使用EventList进行事件调度
- NDP协议：使用NDPPacket（对应ndppacket.h/cpp）
- FIFO队列：使用基础队列模型（对应queue.h/cpp）
- 简单输出：展示数据包传输过程

## htsim对应关系

| Python组件 | C++文件 | 功能说明 |
|-----------|---------|----------|
| `EventList` | `eventlist.h/cpp` | 事件调度器 |
| `NDPPacket` | `ndppacket.h/cpp` | NDP协议数据包 |
| `FIFOQueue` | `queue.h/cpp` | 基础FIFO队列 |
| `PacketFlow` | `network.h/cpp` | 数据包流管理 |

## 运行方法

```bash
cd examples/01_simple_p2p
uv run main.py
```

## 预期输出

```
=== HTSimPy 简单点对点通信示例 ===

1. 创建事件调度器...
2. 创建接收器...
3. 创建FIFO队列...
4. 创建数据包流...
5. 设置路由...
6. 创建并发送NDP数据包...
   发送数据包 1: NDPPacket(...)
   发送数据包 2: NDPPacket(...)
   发送数据包 3: NDPPacket(...)

7. 运行仿真...
   执行仿真步骤 1
   执行仿真步骤 2
   执行仿真步骤 3

8. 仿真结果:
   队列状态: FIFOQueue(...)
   接收器收到 3 个数据包
```

## 学习要点

1. **模块化设计**: 每个组件独立，符合用户偏好
2. **事件驱动**: 理解HTSimPy的事件调度机制
3. **协议对应**: 使用真实对应htsim的NDP协议
4. **简单明了**: 避免复杂功能，专注核心概念

## 下一步

运行成功后，可以继续学习：
- `02_queue_demo/` - 队列系统演示
- `04_tcp_example/` - TCP协议示例 