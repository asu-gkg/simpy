# TCP协议示例

这个示例测试HTSimPy中TCP协议的基本实现和功能。

## 测试内容

### 1. **TCP数据包创建和配置**
- 测试`TCPPacket`类的基本功能（对应htsim的`tcppacket.h/cpp`）
- 验证TCP数据包的属性设置：序列号、确认号、窗口大小、标志位
- 测试SYN、ACK、PSH、FIN等TCP标志位的设置

### 2. **TCP连接生命周期模拟**
当前示例创建了以下TCP数据包类型：
- **SYN包**: 连接建立请求（序列号1000，大小64字节）
- **数据包**: 实际数据传输（序列号1001，大小1460字节，MSS标准大小）

### 3. **htsim对应关系验证**
测试以下组件是否正确对应htsim C++实现：

| 测试组件 | Python类 | C++文件 | 测试功能 |
|---------|----------|---------|----------|
| 事件调度 | `EventList` | `eventlist.h/cpp` | 事件系统初始化 |
| 数据包流 | `PacketFlow` | `network.h/cpp` | 流管理和ID设置 |
| TCP数据包 | `TCPPacket` | `tcppacket.h/cpp` | TCP包创建和属性 |
| FIFO队列 | `FIFOQueue` | `queue.h/cpp` | 基础队列功能 |

### 4. **TCP协议特性测试**
- **序列号管理**: 验证TCP序列号的正确设置和递增
- **标志位处理**: 测试SYN、ACK、PSH、FIN标志位
- **数据包大小**: 测试不同大小数据包（SYN: 64字节，数据: 1460字节）
- **窗口控制**: 验证TCP窗口大小设置（默认65536）

## 运行方法

```bash
cd network_frontend/htsimpy/examples/04_tcp_example
uv run main.py
```

## 预期输出

```
=== HTSimPy TCP协议示例 ===
创建TCP数据包...
SYN包: 序列号=1000
数据包: 序列号=1001
=== TCP示例完成 ===
```

## 测试验证点

### ✅ 成功验证的功能
1. **导入系统**: 所有TCP相关模块正确导入，无循环依赖
2. **对象创建**: EventList、PacketFlow、TCPPacket成功创建
3. **属性设置**: TCP数据包属性（序列号、窗口大小、标志位）正确设置
4. **标志位管理**: SYN和ACK标志位设置功能正常

### 🔄 待完善的功能
1. **完整连接流程**: 目前只测试了包创建，未测试完整的TCP三次握手
2. **队列传输**: 数据包创建后未实际通过队列传输
3. **接收确认**: 未测试TCP确认机制
4. **拥塞控制**: 未测试TCP拥塞控制算法

## 代码结构

```python
# 核心组件导入（所有组件对应htsim C++文件）
from network_frontend.htsimpy.core.eventlist import EventList      # eventlist.h/cpp
from network_frontend.htsimpy.core.network import PacketFlow       # network.h/cpp
from network_frontend.htsimpy.queues.fifo_queue import FIFOQueue   # queue.h/cpp
from network_frontend.htsimpy.packets.tcp_packet import TCPPacket  # tcppacket.h/cpp

def main():
    # 1. 创建事件调度器
    eventlist = EventList()
    
    # 2. 创建TCP接收器（简单版本）
    receiver = TCPReceiver("TCP接收器")
    
    # 3. 创建FIFO队列
    queue = FIFOQueue(eventlist, "TCP链路队列", capacity=20, link_speed=10_000_000_000)
    
    # 4. 创建数据包流
    flow = PacketFlow(logger=None)
    flow.set_flow_id(100)
    
    # 5. 创建和配置TCP数据包
    syn_packet = TCPPacket()
    syn_packet.set(flow, 64, 1, 1000, 0, 65536, 0x02)  # SYN包
    
    data_packet = TCPPacket()
    data_packet.set(flow, 1460, 2, 1001, 0, 65536, 0x18)  # 数据包
```

## 学习要点

1. **严格对应**: 只使用对应htsim C++文件的组件，保持一致性
2. **模块化设计**: TCP功能独立实现，便于扩展和维护
3. **协议准确性**: TCP数据包格式和标志位与RFC标准一致
4. **简单明了**: 专注核心TCP功能测试，避免复杂特性

## 下一步扩展

1. **完整TCP流程**: 实现三次握手和四次挥手
2. **数据传输**: 实现完整的TCP数据传输流程
3. **错误处理**: 添加丢包重传和超时处理
4. **性能测试**: 添加吞吐量和延迟测试 