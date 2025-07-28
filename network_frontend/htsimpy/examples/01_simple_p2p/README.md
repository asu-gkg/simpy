# 简单点对点通信示例

这是HTSimPy最基础的示例，演示了如何使用HTSimPy进行简单的点对点网络通信仿真。

## 功能特性

- **严格对应htsim**: 只使用对应C++文件的组件
- **事件驱动仿真**: 使用EventList进行事件调度
- **NDP协议**: 使用NDPPacket（对应ndppacket.h/cpp）
- **FIFO队列**: 使用基础队列模型（对应queue.h/cpp）
- **模块化设计**: 代码逻辑分离，符合用户偏好

## htsim对应关系

| Python组件 | C++文件 | 功能说明 |
|-----------|---------|----------|
| `EventList` | `eventlist.h/cpp` | 事件调度器 |
| `NDPPacket` | `ndppacket.h/cpp` | NDP协议数据包 |
| `FIFOQueue` | `queue.h/cpp` | 基础FIFO队列 |
| `PacketFlow` | `network.h/cpp` | 数据包流管理 |

## 运行方法

```bash
cd network_frontend/htsimpy/examples/01_simple_p2p
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
   注意：目前仅演示数据结构创建，完整的事件仿真需要更多组件实现

8. 仿真结果:
   队列状态: FIFOQueue(...)
   事件调度器状态: EventList(...)
   接收器状态: 准备接收数据包

=== 示例完成 ===
这个示例展示了HTSimPy的基本组件创建和配置过程
```

## 学习要点

1. **模块化设计**: 每个组件独立，避免复杂功能
2. **事件驱动**: 理解HTSimPy的事件调度机制  
3. **协议对应**: 使用真实对应htsim的NDP协议
4. **简单明了**: 专注核心概念，避免低级错误

## 代码结构

```python
# 导入HTSimPy组件（所有组件都对应htsim C++文件）
from core.eventlist import EventList      # eventlist.h/cpp
from core.network import PacketFlow       # network.h/cpp
from queues.fifo_queue import FIFOQueue   # queue.h/cpp
from packets.ndp_packet import NDPPacket  # ndppacket.h/cpp

# 创建简单接收器（仅用于演示）
class SimpleReceiver:
    def receive_packet(self, packet): pass

# 主要流程
def main():
    # 1. 创建事件调度器
    # 2. 创建FIFO队列
    # 3. 创建NDP数据包
    # 4. 设置路由和发送
```

## 下一步

运行成功后，可以继续学习：
- `04_tcp_example/` - TCP协议示例（对应tcp.h/cpp）
- `02_queue_demo/` - 队列系统演示 