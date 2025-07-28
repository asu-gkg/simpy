# HTSimPy Examples

这个文件夹包含了HTSimPy网络模拟器的各种示例程序，从简单的点对点通信到复杂的网络拓扑仿真。

## 示例列表

### 基础示例
- `01_simple_p2p/` - 最简单的点对点通信示例（使用NDP协议）
- `02_queue_demo/` - 队列系统演示
- `03_protocol_basic/` - 基础协议演示

### 协议示例  
- `04_tcp_example/` - TCP协议实现示例（对应tcp.h/cpp）
- `05_ndp_example/` - NDP协议实现示例（对应ndp.h/cpp）
- `06_protocol_comparison/` - 多协议性能对比

### 拓扑示例
- `07_dumbbell_topology/` - 哑铃拓扑示例
- `08_fat_tree_topology/` - Fat-tree拓扑示例

## htsim对应关系

所有示例都严格对应htsim的C++实现：

| 示例类别 | Python组件 | C++文件 |
|---------|-----------|---------|
| 事件系统 | EventList | eventlist.h/cpp |
| 网络基础 | Packet, PacketFlow | network.h/cpp |
| 队列系统 | FIFOQueue | queue.h/cpp |
| TCP协议 | TCPPacket | tcppacket.h/cpp |
| NDP协议 | NDPPacket | ndppacket.h/cpp |
| Swift协议 | SwiftPacket | swiftpacket.h/cpp |

## 运行示例

每个示例文件夹都包含：
- `main.py` - 主程序文件
- `README.md` - 详细说明
- 必要的配置文件

运行示例的基本命令：
```bash
cd network_frontend/htsimpy/examples/01_simple_p2p
uv run main.py
```

## 设计原则

1. **严格对应**: 只使用对应htsim C++文件的组件
2. **模块化**: 代码逻辑分离到模块中，符合用户偏好
3. **简单明了**: 避免复杂功能，专注核心概念演示
4. **中文注释**: 详细的中文说明和注释 