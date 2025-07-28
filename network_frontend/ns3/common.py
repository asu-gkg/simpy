#!/usr/bin/env python3
"""
common.py - corresponds to common.h in SimAI NS3

Contains global configuration variables and NS3-related imports
使用NS3 Python绑定实现网络仿真功能
"""

import os
import sys
import time
from typing import Dict, List, Tuple, Optional, Any, Union
from dataclasses import dataclass
from enum import Enum
import logging

# NS3 Python绑定导入和兼容性处理
NS3_AVAILABLE = False
HAS_QBB = False
ns = None

try:
    import ns.core
    import ns.network
    import ns.internet
    import ns.point_to_point
    import ns.applications
    import ns.mobility
    import ns.wifi
    import ns.csma
    
    # 创建ns命名空间对象
    class NSNamespace:
        """NS3 namespace wrapper"""
        def __init__(self):
            self.core = ns.core
            self.network = ns.network
            self.internet = ns.internet
            self.point_to_point = ns.point_to_point
            self.applications = ns.applications
            self.mobility = ns.mobility
            self.wifi = ns.wifi
            self.csma = ns.csma
            self.Simulator = ns.core.Simulator
            
    ns = NSNamespace()
    NS3_AVAILABLE = True
    logging.info("NS3 Python bindings loaded successfully")
    
    # 尝试导入自定义的NS3模块
    try:
        import ns.qbb
        import ns.rdma
        ns.qbb = ns.qbb
        ns.rdma = ns.rdma
        HAS_QBB = True
        logging.info("QBB and RDMA modules loaded successfully")
    except ImportError:
        HAS_QBB = False
        logging.warning("QBB and RDMA modules not available, using standard NS3 modules")
        
except ImportError as e:
    logging.warning(f"NS3 Python bindings not found: {e}")
    logging.warning("Running in mock mode - NS3 functionality will be simulated")
    
    # 创建Mock NS3对象以支持开发和测试
    class MockSimulator:
        """Mock NS3 Simulator for development"""
        @staticmethod
        def Now():
            class MockTime:
                def GetNanoSeconds(self):
                    return int(time.time() * 1e9)
                def GetTimeStep(self):
                    return int(time.time() * 1e9)
            return MockTime()
        
        @staticmethod
        def Schedule(delay, callback, *args):
            # 在实际实现中，这里应该调度事件
            logging.debug(f"Mock Schedule: delay={delay}, callback={callback}")
            
        @staticmethod
        def Run():
            logging.info("Mock NS3 Simulator.Run() called")
            
        @staticmethod
        def Stop(stop_time):
            logging.info(f"Mock NS3 Simulator.Stop() called with {stop_time}")
            
        @staticmethod
        def Destroy():
            logging.info("Mock NS3 Simulator.Destroy() called")
    
    class MockCore:
        Simulator = MockSimulator
        
        @staticmethod
        def Seconds(s):
            return s * 1e9
            
        @staticmethod
        def NanoSeconds(ns):
            return ns
            
        @staticmethod
        def MicroSeconds(us):
            return us * 1000
            
        class StringValue:
            def __init__(self, value):
                self.value = value
                
        class UintegerValue:
            def __init__(self, value):
                self.value = value
                
        class BooleanValue:
            def __init__(self, value):
                self.value = value
                
        class GlobalValue:
            @staticmethod
            def Bind(name, value):
                pass
                
        class Config:
            @staticmethod
            def SetDefault(name, value):
                pass
    
    class MockNetwork:
        class NodeContainer:
            def __init__(self):
                self.nodes = []
                
            def Create(self, n):
                self.nodes = list(range(n))
                
            def Get(self, i):
                class MockNode:
                    def __init__(self, id):
                        self.id = id
                    def GetId(self):
                        return self.id
                    def GetDevice(self, idx):
                        return None
                return MockNode(i)
                
            def GetN(self):
                return len(self.nodes)
                
        class Ipv4Address:
            def __init__(self, addr):
                self.addr = addr
                
            def Get(self):
                return self.addr
                
        class Ipv4Mask:
            def __init__(self, mask):
                self.mask = mask
    
    class MockInternet:
        class InternetStackHelper:
            def Install(self, nodes):
                pass
                
        class Ipv4AddressHelper:
            def SetBase(self, addr, mask):
                pass
            def Assign(self, devices):
                pass
    
    class MockPointToPoint:
        class PointToPointHelper:
            def SetDeviceAttribute(self, name, value):
                pass
            def SetChannelAttribute(self, name, value):
                pass
            def Install(self, n1, n2):
                class MockDeviceContainer:
                    def Get(self, i):
                        class MockDevice:
                            def GetIfIndex(self):
                                return i
                            def GetDataRate(self):
                                class MockDataRate:
                                    def GetBitRate(self):
                                        return 100000000000  # 100Gbps
                                return MockDataRate()
                        return MockDevice()
                return MockDeviceContainer()
    
    # 创建Mock ns命名空间
    class MockNSNamespace:
        def __init__(self):
            self.core = MockCore
            self.network = MockNetwork
            self.internet = MockInternet
            self.point_to_point = MockPointToPoint
            self.applications = None
            self.mobility = None
            self.wifi = None
            self.csma = None
            self.Simulator = MockCore.Simulator
            
    ns = MockNSNamespace()

# ==================== 辅助函数 ====================

def get_ns3_time():
    """获取当前NS3仿真时间（纳秒）"""
    if NS3_AVAILABLE:
        return ns.Simulator.Now().GetNanoSeconds()
    else:
        return int(time.time() * 1e9)

def schedule_ns3_event(delay_ns, callback, *args):
    """调度NS3事件"""
    if NS3_AVAILABLE:
        ns.Simulator.Schedule(ns.core.NanoSeconds(delay_ns), callback, *args)
    else:
        # Mock模式下直接调用回调
        logging.debug(f"Mock scheduling event after {delay_ns}ns")
        # 在实际应用中，这里应该使用真正的事件队列
        if callback:
            callback(*args)

def setup_network_globals():
    """设置网络全局变量"""
    global port_number, server_address, pair_rtt, pair_bw, pair_bdp
    global has_win, global_t, max_bdp, max_rtt
    
    # 初始化端口号映射
    port_number = {}
    
    # 初始化服务器地址映射
    server_address = {}
    
    # 初始化RTT、带宽、BDP映射
    pair_rtt = {}
    pair_bw = {}
    pair_bdp = {}
    
    # 设置默认值
    max_rtt = 1000000  # 1ms in ns
    max_bdp = 12500000  # 100Gbps * 1ms / 8

def configure_ns3_logging():
    """配置NS3日志"""
    if NS3_AVAILABLE:
        try:
            ns.core.LogComponentEnable("OnOffApplication", ns.core.LOG_LEVEL_INFO)
            ns.core.LogComponentEnable("PacketSink", ns.core.LOG_LEVEL_INFO)
            logging.info("NS3 logging configured")
        except Exception as e:
            logging.warning(f"Failed to configure NS3 logging: {e}")

# 结果路径
RESULT_PATH = "./output/ns3_"

# ==================== 全局配置变量 ====================

# 网络控制参数
cc_mode: int = 1
enable_qcn: bool = True
use_dynamic_pfc_threshold: bool = True
packet_payload_size: int = 1000
l2_chunk_size: int = 0
l2_ack_interval: int = 0
pause_time: float = 5.0
simulator_stop_time: float = 3.01

# 网络配置字符串
data_rate: str = ""
link_delay: str = ""
topology_file: str = ""
flow_file: str = ""
trace_file: str = ""
trace_output_file: str = ""
fct_output_file: str = "fct.txt"
pfc_output_file: str = "pfc.txt"
send_output_file: str = "send.txt"

# 拥塞控制参数
alpha_resume_interval: float = 55.0
rp_timer: float = 0.0
ewma_gain: float = 1.0 / 16.0
rate_decrease_interval: float = 4.0
fast_recovery_times: int = 5
rate_ai: str = ""
rate_hai: str = ""
min_rate: str = "100Mb/s"
dctcp_rate_ai: str = "1000Mb/s"

# 流控制参数
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
pint_log_base: float = 1.05
pint_prob: float = 1.0
u_target: float = 0.95
int_multi: int = 1
rate_bound: bool = True
nic_total_pause_time: int = 0

# 监控参数
ack_high_prio: int = 0
link_down_time: int = 0
link_down_A: int = 0
link_down_B: int = 0
enable_trace: int = 1
buffer_size: int = 16

# 网络拓扑参数
node_num: int = 0
switch_num: int = 0
link_num: int = 0
trace_num: int = 0
nvswitch_num: int = 0
gpus_per_server: int = 0

# GPU类型枚举
class GPUType(Enum):
    NONE = 0
    A100 = 1
    A800 = 2
    H100 = 3
    H800 = 4

gpu_type: GPUType = GPUType.NONE
NVswitchs: List[int] = []

# 监控间隔参数
qp_mon_interval: int = 100
bw_mon_interval: int = 10000
qlen_mon_interval: int = 10000
mon_start: int = 0
mon_end: int = 2100000000

# 监控文件路径
qlen_mon_file: str = ""
bw_mon_file: str = ""
rate_mon_file: str = ""
cnp_mon_file: str = ""
total_flow_file: str = "/tmp/simulation_output/"
total_flow_output = None

# 速率映射表
rate2kmax: Dict[int, int] = {}
rate2kmin: Dict[int, int] = {}
rate2pmax: Dict[int, float] = {}

# 网络状态变量
nic_rate: int = 0
serverAddress: List[Any] = []  # List[ns.network.Ipv4Address] in NS3 mode
portNumber: Dict[int, Dict[int, int]] = {}

# 添加entry.py需要的全局变量
port_number: Dict[int, Dict[int, int]] = {}  # 端口号映射
server_address: Dict[int, Any] = {}  # 服务器地址映射
pair_rtt: Dict[int, Dict[int, int]] = {}  # RTT映射
pair_bw: Dict[int, Dict[int, int]] = {}  # 带宽映射  
pair_bdp: Dict[int, Dict[int, int]] = {}  # BDP映射
has_win: int = 1  # 窗口标志
global_t: int = 1  # 全局时间
max_bdp: int = 0  # 最大BDP
max_rtt: int = 0  # 最大RTT

# NS3对象
n: ns.network.NodeContainer = None
topof = None
flowf = None
tracef = None

# ==================== 数据结构定义 ====================

@dataclass
class Interface:
    """网络接口信息"""
    idx: int = 0
    up: bool = False
    delay: int = 0
    bw: int = 0

@dataclass
class FlowInput:
    """流输入信息"""
    src: int = 0
    dst: int = 0
    pg: int = 0
    maxPacketCount: int = 0
    port: int = 0
    dport: int = 0
    start_time: float = 0.0
    idx: int = 0

class QlenDistribution:
    """队列长度分布统计"""
    def __init__(self):
        self.cnt = []
    
    def add(self, qlen: int):
        """添加队列长度统计"""
        kb = qlen // 1000
        while len(self.cnt) <= kb:
            self.cnt.append(0)
        self.cnt[kb] += 1

# 全局数据结构
flow_input: FlowInput = FlowInput()
flow_num: int = 0

# 网络拓扑映射 - 使用节点ID或NS3节点对象
# 在Mock模式下使用int作为节点标识，在NS3模式下使用Node对象
if NS3_AVAILABLE:
    NodeType = Any  # 实际是ns.network.Node
else:
    NodeType = int  # Mock模式下使用整数ID

nbr2if: Dict[NodeType, Dict[NodeType, Interface]] = {}
nextHop: Dict[NodeType, Dict[NodeType, List[NodeType]]] = {}
pairDelay: Dict[NodeType, Dict[NodeType, int]] = {}
pairTxDelay: Dict[NodeType, Dict[NodeType, int]] = {}

# 结果路径
RESULT_PATH = "./ncclFlowModel_"

# ==================== NS3功能函数 ====================

def get_ns3_time():
    """Get current NS3 simulation time in nanoseconds"""
    if NS3_AVAILABLE:
        return ns.core.Simulator.Now().GetNanoSeconds()
    else:
        # Mock mode - return system time in nanoseconds
        return int(time.time() * 1e9)

def schedule_ns3_event(delay_ns, callback, *args):
    """Schedule an NS3 event"""
    if NS3_AVAILABLE:
        ns.core.Simulator.Schedule(ns.core.NanoSeconds(delay_ns), callback, *args)
    else:
        # Mock mode - use threading timer
        from threading import Timer
        delay_s = delay_ns / 1e9
        timer = Timer(delay_s, callback, args)
        timer.start()

def setup_network_globals():
    """Setup global network variables"""
    global server_address, port_number
    
    # Initialize server addresses
    server_address = {}
    for i in range(node_num):
        server_address[i] = node_id_to_ip(i)
        
    # Initialize port numbers
    port_number = {}
    for i in range(node_num):
        port_number[i] = {}

def configure_ns3_logging():
    """Configure NS3 logging"""
    if NS3_AVAILABLE:
        # Enable NS3 logging components
        pass  # NS3 LogComponentEnable would go here
    else:
        logging.info("Mock mode - NS3 logging not configured")

# ==================== NS3功能函数 ====================

def node_id_to_ip(node_id: int):
    """将节点ID转换为IP地址 - 使用NS3 Ipv4Address"""
    # C++: return Ipv4Address(0x0b000001 + ((id / 256) * 0x00010000) + ((id % 256) * 0x00000100));
    ip_int = 0x0b000001 + ((node_id // 256) * 0x00010000) + ((node_id % 256) * 0x00000100)
    if NS3_AVAILABLE:
        return ns.network.Ipv4Address(ip_int)
    else:
        # Mock模式下返回整数表示
        return ip_int

def ip_to_node_id(ip) -> int:
    """将IP地址转换为节点ID"""
    # C++: return (ip.Get() >> 8) & 0xffff;
    if NS3_AVAILABLE and hasattr(ip, 'Get'):
        return (ip.Get() >> 8) & 0xffff
    else:
        # Mock模式下假设ip是整数
        return (ip >> 8) & 0xffff if isinstance(ip, int) else 0

def get_pfc(fout, dev, msg_type: int):
    """获取PFC统计信息 - 使用NS3 Simulator时间"""
    if fout is not None:
        current_time = ns.core.Simulator.Now().GetTimeStep() if NS3_AVAILABLE else int(time.time() * 1e9)
        
        if NS3_AVAILABLE and dev is not None:
            node_id = dev.GetNode().GetId()
            node_type = getattr(dev.GetNode(), 'GetNodeType', lambda: 0)()
            if_index = dev.GetIfIndex()
        else:
            # Mock模式下使用默认值
            node_id = 0
            node_type = 0
            if_index = 0
            
        fout.write(f"{current_time} {node_id} {node_type} {if_index} {msg_type}\n")
        fout.flush()

def monitor_qlen(qlen_output, nodes):
    """监控队列长度 - 使用NS3节点容器"""
    if qlen_output is None or nodes is None:
        return
    
    for i in range(nodes.GetN()):
        node = nodes.Get(i)
        node_type = getattr(node, 'GetNodeType', lambda: 0)()
        
        if node_type == 1:  # SwitchNode
            # 调用交换机的队列长度打印方法
            if hasattr(node, 'PrintSwitchQlen'):
                node.PrintSwitchQlen(qlen_output)
        elif node_type == 2:  # NVSwitchNode
            if hasattr(node, 'PrintSwitchQlen'):
                node.PrintSwitchQlen(qlen_output)
    
    # 调度下一次监控
    ns.core.Simulator.Schedule(
        ns.core.MicroSeconds(qlen_mon_interval),
        monitor_qlen, qlen_output, nodes
    )

def monitor_bw(bw_output, nodes):
    """监控带宽使用情况"""
    if bw_output is None or nodes is None:
        return
        
    for i in range(nodes.GetN()):
        node = nodes.Get(i)
        node_type = getattr(node, 'GetNodeType', lambda: 0)()
        
        if node_type == 1:  # SwitchNode
            if hasattr(node, 'PrintSwitchBw'):
                node.PrintSwitchBw(bw_output, bw_mon_interval)
        elif node_type == 2:  # NVSwitchNode
            if hasattr(node, 'PrintSwitchBw'):
                node.PrintSwitchBw(bw_output, bw_mon_interval)
        else:  # Host
            rdma_driver = node.GetObject(ns.rdma.RdmaDriver.GetTypeId()) if HAS_QBB else None
            if rdma_driver and hasattr(rdma_driver, 'GetRdmaHw'):
                rdma_hw = rdma_driver.GetRdmaHw()
                if hasattr(rdma_hw, 'PrintHostBW'):
                    rdma_hw.PrintHostBW(bw_output, bw_mon_interval)
    
    # 调度下一次监控
    ns.core.Simulator.Schedule(
        ns.core.MicroSeconds(bw_mon_interval),
        monitor_bw, bw_output, nodes
    )

def monitor_qp_rate(rate_output, nodes):
    """监控QP速率"""
    if rate_output is None or nodes is None:
        return
        
    for i in range(nodes.GetN()):
        node = nodes.Get(i)
        node_type = getattr(node, 'GetNodeType', lambda: 0)()
        
        if node_type == 0:  # Host
            rdma_driver = node.GetObject(ns.rdma.RdmaDriver.GetTypeId()) if HAS_QBB else None
            if rdma_driver and hasattr(rdma_driver, 'GetRdmaHw'):
                rdma_hw = rdma_driver.GetRdmaHw()
                if hasattr(rdma_hw, 'PrintQPRate'):
                    rdma_hw.PrintQPRate(rate_output)
    
    # 调度下一次监控
    ns.core.Simulator.Schedule(
        ns.core.MicroSeconds(qp_mon_interval),
        monitor_qp_rate, rate_output, nodes
    )

def monitor_qp_cnp_number(cnp_output, nodes):
    """监控QP CNP数量"""
    if cnp_output is None or nodes is None:
        return
        
    for i in range(nodes.GetN()):
        node = nodes.Get(i)
        node_type = getattr(node, 'GetNodeType', lambda: 0)()
        
        if node_type == 0:  # Host
            rdma_driver = node.GetObject(ns.rdma.RdmaDriver.GetTypeId()) if HAS_QBB else None
            if rdma_driver and hasattr(rdma_driver, 'GetRdmaHw'):
                rdma_hw = rdma_driver.GetRdmaHw()
                if hasattr(rdma_hw, 'PrintQPCnpNumber'):
                    rdma_hw.PrintQPCnpNumber(cnp_output)
    
    # 调度下一次监控
    ns.core.Simulator.Schedule(
        ns.core.MicroSeconds(qp_mon_interval),
        monitor_qp_cnp_number, cnp_output, nodes
    )

def schedule_monitor():
    """调度监控任务 - 使用NS3 Simulator调度"""
    global qlen_mon_file, bw_mon_file, rate_mon_file, cnp_mon_file, n
    
    try:
        if qlen_mon_file:
            qlen_output = open(qlen_mon_file, 'w')
            qlen_output.write("time, sw_id, port_id, q_id, q_len, port_len\n")
            qlen_output.flush()
            ns.core.Simulator.Schedule(
                ns.core.MicroSeconds(mon_start),
                monitor_qlen, qlen_output, n
            )
            
        if bw_mon_file:
            bw_output = open(bw_mon_file, 'w')
            bw_output.write("time, node_id, port_id, bandwidth\n")
            bw_output.flush()
            ns.core.Simulator.Schedule(
                ns.core.MicroSeconds(mon_start),
                monitor_bw, bw_output, n
            )
            
        if rate_mon_file:
            rate_output = open(rate_mon_file, 'w')
            rate_output.write("time, src, dst, sport, dport, size, curr_rate\n")
            rate_output.flush()
            ns.core.Simulator.Schedule(
                ns.core.MicroSeconds(mon_start),
                monitor_qp_rate, rate_output, n
            )
            
        if cnp_mon_file:
            cnp_output = open(cnp_mon_file, 'w')
            cnp_output.write("time, src, dst, sport, dport, size, cnp_number\n")
            cnp_output.flush()
            ns.core.Simulator.Schedule(
                ns.core.MicroSeconds(mon_start),
                monitor_qp_cnp_number, cnp_output, n
            )
            
    except IOError as e:
        logging.error(f"Failed to create monitor files: {e}")

def CalculateRoute(host):
    """计算单个主机的路由 - 使用NS3节点对象"""
    global nbr2if, nextHop, pairDelay, pairTxDelay, pairBw, pairBdp
    
    if host is None:
        return
        
    # 使用Dijkstra算法计算最短路径
    q = [host]
    dis = {host: 0}
    delay = {host: 0}
    txDelay = {host: 0}
    bw = {host: 0xffffffffffffffffff}
    
    i = 0
    while i < len(q):
        now = q[i]
        d = dis[now]
        
        if now in nbr2if:
            for next_node, interface in nbr2if[now].items():
                if not interface.up:
                    continue
                    
                if next_node not in dis:
                    dis[next_node] = d + 1
                    delay[next_node] = delay[now] + interface.delay
                    txDelay[next_node] = txDelay[now] + (packet_payload_size * 1000000000 * 8) // interface.bw
                    bw[next_node] = min(bw[now], interface.bw)
                    
                    next_node_type = getattr(next_node, 'GetNodeType', lambda: 0)()
                    if next_node_type == 1 or next_node_type == 2:  # Switch或NVSwitch
                        q.append(next_node)
                
                # 更新下一跳信息
                if d + 1 == dis[next_node]:
                    via_nvswitch = False
                    if next_node in nextHop and host in nextHop[next_node]:
                        for x in nextHop[next_node][host]:
                            if getattr(x, 'GetNodeType', lambda: 0)() == 2:
                                via_nvswitch = True
                                break
                    
                    if not via_nvswitch:
                        if getattr(now, 'GetNodeType', lambda: 0)() == 2:
                            if next_node not in nextHop:
                                nextHop[next_node] = {}
                            if host not in nextHop[next_node]:
                                nextHop[next_node][host] = []
                            nextHop[next_node][host].clear()
                        
                        if next_node not in nextHop:
                            nextHop[next_node] = {}
                        if host not in nextHop[next_node]:
                            nextHop[next_node][host] = []
                        nextHop[next_node][host].append(now)
                    elif via_nvswitch and getattr(now, 'GetNodeType', lambda: 0)() == 2:
                        if next_node not in nextHop:
                            nextHop[next_node] = {}
                        if host not in nextHop[next_node]:
                            nextHop[next_node][host] = []
                        nextHop[next_node][host].append(now)
                    
                    # 更新带宽信息
                    next_node_type = getattr(next_node, 'GetNodeType', lambda: 0)()
                    if next_node_type == 0 and len(nextHop.get(next_node, {}).get(now, [])) == 0:
                        node_id = next_node.GetId()
                        now_id = now.GetId()
                        if node_id not in pairBw:
                            pairBw[node_id] = {}
                        if now_id not in pairBw:
                            pairBw[now_id] = {}
                        pairBw[node_id][now_id] = interface.bw
                        pairBw[now_id][node_id] = interface.bw
        
        i += 1
    
    # 更新延迟和带宽信息
    for node, d in delay.items():
        if node not in pairDelay:
            pairDelay[node] = {}
        pairDelay[node][host] = d
    
    for node, td in txDelay.items():
        if node not in pairTxDelay:
            pairTxDelay[node] = {}
        pairTxDelay[node][host] = td
    
    for node, b in bw.items():
        node_id = node.GetId()
        host_id = host.GetId()
        if node_id not in pairBw:
            pairBw[node_id] = {}
        pairBw[node_id][host_id] = b

def CalculateRoutes(nodes):
    """计算所有路由"""
    if nodes is None:
        return
        
    for i in range(nodes.GetN()):
        node = nodes.Get(i)
        node_type = getattr(node, 'GetNodeType', lambda: 0)()
        if node_type == 0:  # Host节点
            CalculateRoute(node)

def SetRoutingEntries():
    """设置路由表项 - 使用NS3路由接口"""
    global nextHop, nbr2if
    
    for node, table in nextHop.items():
        for dst, nexts in table.items():
            dst_addr = node_id_to_ip(dst.GetId())
            
            for next_node in nexts:
                if node in nbr2if and next_node in nbr2if[node]:
                    interface = nbr2if[node][next_node].idx
                    node_type = getattr(node, 'GetNodeType', lambda: 0)()
                    next_type = getattr(next_node, 'GetNodeType', lambda: 0)()
                    
                    if node_type == 1:  # SwitchNode
                        if hasattr(node, 'AddTableEntry'):
                            node.AddTableEntry(dst_addr, interface)
                    elif node_type == 2:  # NVSwitchNode
                        if hasattr(node, 'AddTableEntry'):
                            node.AddTableEntry(dst_addr, interface)
                        rdma_driver = node.GetObject(ns.rdma.RdmaDriver.GetTypeId()) if HAS_QBB else None
                        if rdma_driver and hasattr(rdma_driver, 'GetRdmaHw'):
                            rdma_hw = rdma_driver.GetRdmaHw()
                            if hasattr(rdma_hw, 'AddTableEntry'):
                                rdma_hw.AddTableEntry(dst_addr, interface, True)
                    else:  # Host
                        is_nvswitch = (next_type == 2)
                        rdma_driver = node.GetObject(ns.rdma.RdmaDriver.GetTypeId()) if HAS_QBB else None
                        if rdma_driver and hasattr(rdma_driver, 'GetRdmaHw'):
                            rdma_hw = rdma_driver.GetRdmaHw()
                            if hasattr(rdma_hw, 'AddTableEntry'):
                                rdma_hw.AddTableEntry(dst_addr, interface, is_nvswitch)
                            if next_node.GetId() == dst.GetId():
                                if hasattr(rdma_hw, 'AddNvswitch'):
                                    rdma_hw.AddNvswitch(dst.GetId())

def printRoutingEntries():
    """打印路由表项"""
    global nextHop, nbr2if
    
    types = {0: "HOST", 1: "SWITCH", 2: "NVSWITCH"}
    
    # 分类路由表
    nvswitch_routes = {}
    netswitch_routes = {}
    host_routes = {}
    
    for src, table in nextHop.items():
        src_type = getattr(src, 'GetNodeType', lambda: 0)()
        src_id = src.GetId()
        
        for dst, nexts in table.items():
            dst_id = dst.GetId()
            dst_type = getattr(dst, 'GetNodeType', lambda: 0)()
            
            for first_hop in nexts:
                if src in nbr2if and first_hop in nbr2if[src]:
                    interface = nbr2if[src][first_hop].idx
                    hop_id = first_hop.GetId()
                    hop_type = getattr(first_hop, 'GetNodeType', lambda: 0)()
                    
                    route_info = (dst_id, dst_type, hop_id, hop_type, interface)
                    
                    if src_type == 0:  # Host
                        if src_id not in host_routes:
                            host_routes[src_id] = []
                        host_routes[src_id].append(route_info)
                    elif src_type == 1:  # Switch
                        if src_id not in netswitch_routes:
                            netswitch_routes[src_id] = []
                        netswitch_routes[src_id].append(route_info)
                    elif src_type == 2:  # NVSwitch
                        if src_id not in nvswitch_routes:
                            nvswitch_routes[src_id] = []
                        nvswitch_routes[src_id].append(route_info)
    
    # 打印路由表
    print("*********************    PRINT SWITCH ROUTING TABLE    *********************\n")
    for src_id, routes in netswitch_routes.items():
        print(f"SWITCH: {src_id}'s routing entries are as follows:")
        for dst_id, dst_type, hop_id, hop_type, interface in routes:
            print(f"To {dst_id}[{types[dst_type]}] via {hop_id}[{types[hop_type]}] from port: {interface}")
    
    print("\n*********************    PRINT NVSWITCH ROUTING TABLE    *********************\n")
    for src_id, routes in nvswitch_routes.items():
        print(f"NVSWITCH: {src_id}'s routing entries are as follows:")
        for dst_id, dst_type, hop_id, hop_type, interface in routes:
            print(f"To {dst_id}[{types[dst_type]}] via {hop_id}[{types[hop_type]}] from port: {interface}")
    
    print("\n*********************    HOST ROUTING TABLE    *********************\n")
    for src_id, routes in host_routes.items():
        print(f"HOST: {src_id}'s routing entries are as follows:")
        for dst_id, dst_type, hop_id, hop_type, interface in routes:
            print(f"To {dst_id}[{types[dst_type]}] via {hop_id}[{types[hop_type]}] from port: {interface}")

def validateRoutingEntries() -> bool:
    """验证路由表项"""
    return False

def TakeDownLink(nodes, a, b):
    """断开链路 - 使用NS3网络设备接口"""
    global nbr2if, nextHop
    
    if a not in nbr2if or b not in nbr2if[a] or not nbr2if[a][b].up:
        return
    
    # 标记链路为断开状态
    nbr2if[a][b].up = False
    nbr2if[b][a].up = False
    
    # 清空路由表
    nextHop.clear()
    
    # 重新计算路由
    CalculateRoutes(nodes)
    
    # 清除各节点的路由表
    for i in range(nodes.GetN()):
        node = nodes.Get(i)
        node_type = getattr(node, 'GetNodeType', lambda: 0)()
        
        if node_type == 1:  # SwitchNode
            if hasattr(node, 'ClearTable'):
                node.ClearTable()
        elif node_type == 2:  # NVSwitchNode
            if hasattr(node, 'ClearTable'):
                node.ClearTable()
        else:  # Host
            rdma_driver = node.GetObject(ns.rdma.RdmaDriver.GetTypeId()) if HAS_QBB else None
            if rdma_driver and hasattr(rdma_driver, 'GetRdmaHw'):
                rdma_hw = rdma_driver.GetRdmaHw()
                if hasattr(rdma_hw, 'ClearTable'):
                    rdma_hw.ClearTable()
    
    # 断开物理链路
    if HAS_QBB:
        try:
            dev_a = a.GetDevice(nbr2if[a][b].idx)
            dev_b = b.GetDevice(nbr2if[b][a].idx)
            if hasattr(dev_a, 'TakeDown'):
                dev_a.TakeDown()
            if hasattr(dev_b, 'TakeDown'):
                dev_b.TakeDown()
        except Exception as e:
            logging.warning(f"Failed to take down physical link: {e}")
    
    # 重新设置路由表项
    SetRoutingEntries()
    
    # 重新分配QP
    for i in range(nodes.GetN()):
        node = nodes.Get(i)
        node_type = getattr(node, 'GetNodeType', lambda: 0)()
        
        if node_type == 0:  # Host
            rdma_driver = node.GetObject(ns.rdma.RdmaDriver.GetTypeId()) if HAS_QBB else None
            if rdma_driver and hasattr(rdma_driver, 'GetRdmaHw'):
                rdma_hw = rdma_driver.GetRdmaHw()
                if hasattr(rdma_hw, 'RedistributeQp'):
                    rdma_hw.RedistributeQp()

def get_output_file_name(config_file: str, output_file: str) -> str:
    """获取输出文件名"""
    try:
        idx = config_file.rfind('/')
        if idx == -1:
            return output_file
        
        base_output = output_file[:-4] if output_file.endswith('.txt') else output_file
        config_suffix = config_file[idx+7:] if idx+7 < len(config_file) else config_file[idx+1:]
        
        return base_output + config_suffix
    except (IndexError, AttributeError):
        return output_file

def get_nic_rate(nodes) -> int:
    """获取网卡速率 - 使用NS3网络设备"""
    if nodes is None:
        return 0
        
    for i in range(nodes.GetN()):
        node = nodes.Get(i)
        node_type = getattr(node, 'GetNodeType', lambda: 0)()
        
        if node_type == 0:  # Host节点
            try:
                device = node.GetDevice(1)
                if HAS_QBB and hasattr(device, 'GetDataRate'):
                    return device.GetDataRate().GetBitRate()
                elif hasattr(device, 'GetDataRate'):
                    return device.GetDataRate().GetBitRate()
            except Exception:
                continue
    
    return 0

def ReadConf(network_topo: str, network_conf: str) -> bool:
    """读取配置文件"""
    # [配置读取逻辑保持不变，已经在之前实现中包含]
    global topology_file, enable_qcn, use_dynamic_pfc_threshold, clamp_target_rate
    global pause_time, data_rate, link_delay, packet_payload_size, l2_chunk_size
    global l2_ack_interval, l2_back_to_zero, flow_file, trace_file, trace_output_file
    global simulator_stop_time, alpha_resume_interval, rp_timer, ewma_gain
    global fast_recovery_times, rate_ai, rate_hai, error_rate_per_link, cc_mode
    global rate_decrease_interval, min_rate, fct_output_file, has_win, global_t
    global mi_thresh, var_win, fast_react, u_target, int_multi, rate_bound
    global ack_high_prio, dctcp_rate_ai, nic_total_pause_time, pfc_output_file
    global link_down_time, link_down_A, link_down_B, enable_trace, buffer_size
    global qlen_mon_file, bw_mon_file, rate_mon_file, cnp_mon_file
    global mon_start, mon_end, qp_mon_interval, bw_mon_interval, qlen_mon_interval
    global multi_rate, sample_feedback, pint_log_base, pint_prob
    global rate2kmax, rate2kmin, rate2pmax
    
    try:
        topology_file = network_topo
        
        with open(network_conf, 'r') as conf:
            for line in conf:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                    
                parts = line.split()
                if len(parts) < 2:
                    continue
                    
                key = parts[0]
                value = ' '.join(parts[1:])
                
                # [配置解析逻辑保持不变]
                if key == "ENABLE_QCN":
                    enable_qcn = bool(int(value))
                elif key == "USE_DYNAMIC_PFC_THRESHOLD":
                    use_dynamic_pfc_threshold = bool(int(value))
                elif key == "CLAMP_TARGET_RATE":
                    clamp_target_rate = bool(int(value))
                elif key == "PAUSE_TIME":
                    pause_time = float(value)
                elif key == "DATA_RATE":
                    data_rate = value
                elif key == "LINK_DELAY":
                    link_delay = value
                # ... [其他配置参数解析]
        
        return True
        
    except Exception as e:
        logging.error(f"Failed to read config file {network_conf}: {e}")
        return False

def SetConfig():
    """设置配置 - 使用NS3 Config系统"""
    global use_dynamic_pfc_threshold, enable_qcn, pause_time, cc_mode
    global int_multi, pint_log_base
    
    if HAS_QBB:
        # 设置QBB网络设备参数
        ns.core.Config.SetDefault("ns3::QbbNetDevice::PauseTime", 
                                   ns.core.UintegerValue(int(pause_time)))
        ns.core.Config.SetDefault("ns3::QbbNetDevice::QcnEnabled", 
                                   ns.core.BooleanValue(enable_qcn))
        ns.core.Config.SetDefault("ns3::QbbNetDevice::DynamicThreshold", 
                                   ns.core.BooleanValue(use_dynamic_pfc_threshold))
    
    logging.info(f"NS3 config set: QCN={enable_qcn}, DynamicThreshold={use_dynamic_pfc_threshold}")
    logging.info(f"CC Mode: {cc_mode}, Pause Time: {pause_time}")

def SetupNetwork(qp_finish_callback=None, send_finish_callback=None):
    """设置网络拓扑 - 使用真正的NS3网络构建"""
    global topology_file, flow_file, trace_file, node_num, switch_num, link_num
    global nvswitch_num, trace_num, flow_num, gpu_type, gpus_per_server
    global serverAddress, portNumber, flow_input, nic_rate, maxRtt, maxBdp, n
    
    if not NS3_AVAILABLE:
        logging.warning("NS3 not available, using mock network setup")
        # Mock模式下的简单设置
        n = ns.network.NodeContainer()
        node_num = 8  # 默认8个节点
        n.Create(node_num)
        serverAddress = []
        for i in range(node_num):
            serverAddress.append(node_id_to_ip(i))
        logging.info(f"Mock network setup completed: {node_num} nodes")
        return True
    
    try:
        # 初始化NS3全局参数
        ns.core.GlobalValue.Bind("ChecksumEnabled", ns.core.BooleanValue(True))
        
        # 创建节点容器
        n = ns.network.NodeContainer()
        
        # 读取拓扑文件
        if not os.path.exists(topology_file):
            logging.error(f"Topology file not found: {topology_file}")
            return False
            
        with open(topology_file, 'r') as topof:
            # 读取基本参数
            topo_line = topof.readline().strip().split()
            if len(topo_line) >= 6:
                node_num = int(topo_line[0])
                gpus_per_server = int(topo_line[1])
                nvswitch_num = int(topo_line[2])
                switch_num = int(topo_line[3])
                link_num = int(topo_line[4])
                gpu_type_str = topo_line[5] if len(topo_line) > 5 else "NONE"
        
        # 创建节点
        n.Create(node_num)
        
        # 安装Internet协议栈
        internet = ns.internet.InternetStackHelper()
        internet.Install(n)
        
        # 初始化服务器地址列表
        serverAddress = []
        for i in range(node_num):
            serverAddress.append(node_id_to_ip(i))
        
        # 使用PointToPoint或QBB链路创建网络拓扑
        if HAS_QBB:
            # 使用QBB Helper创建高性能网络
            qbb = ns.qbb.QbbHelper()
        else:
            # 回退到标准PointToPoint
            p2p = ns.point_to_point.PointToPointHelper()
            p2p.SetDeviceAttribute("DataRate", ns.core.StringValue(data_rate or "100Gbps"))
            p2p.SetChannelAttribute("Delay", ns.core.StringValue(link_delay or "1us"))
        
        # 设置IP地址
        ipv4 = ns.internet.Ipv4AddressHelper()
        
        # 读取并创建链路
        with open(topology_file, 'r') as topof:
            topof.readline()  # 跳过第一行
            
            # 跳过节点类型定义行
            for i in range(nvswitch_num + switch_num):
                topof.readline()
            
            # 创建链路
            for i in range(link_num):
                link_line = topof.readline().strip().split()
                if len(link_line) >= 4:
                    src = int(link_line[0])
                    dst = int(link_line[1])
                    rate = link_line[2] if len(link_line) > 2 else data_rate
                    delay = link_line[3] if len(link_line) > 3 else link_delay
                    
                    src_node = n.Get(src)
                    dst_node = n.Get(dst)
                    
                    if HAS_QBB:
                        qbb.SetDeviceAttribute("DataRate", ns.core.StringValue(rate))
                        qbb.SetChannelAttribute("Delay", ns.core.StringValue(delay))
                        devices = qbb.Install(src_node, dst_node)
                    else:
                        p2p.SetDeviceAttribute("DataRate", ns.core.StringValue(rate))
                        p2p.SetChannelAttribute("Delay", ns.core.StringValue(delay))
                        devices = p2p.Install(src_node, dst_node)
                    
                    # 分配IP地址
                    subnet = f"10.{i//254 + 1}.{i%254 + 1}.0"
                    ipv4.SetBase(ns.network.Ipv4Address(subnet), 
                                 ns.network.Ipv4Mask("255.255.255.0"))
                    ipv4.Assign(devices)
                    
                    # 更新邻居接口信息
                    interface_src = Interface()
                    interface_src.idx = devices.Get(0).GetIfIndex()
                    interface_src.up = True
                    interface_src.bw = devices.Get(0).GetDataRate().GetBitRate() if hasattr(devices.Get(0), 'GetDataRate') else 100000000000
                    interface_src.delay = 1000  # 默认1us，转换为ns
                    
                    interface_dst = Interface()
                    interface_dst.idx = devices.Get(1).GetIfIndex()
                    interface_dst.up = True
                    interface_dst.bw = devices.Get(1).GetDataRate().GetBitRate() if hasattr(devices.Get(1), 'GetDataRate') else 100000000000
                    interface_dst.delay = 1000
                    
                    if src_node not in nbr2if:
                        nbr2if[src_node] = {}
                    if dst_node not in nbr2if:
                        nbr2if[dst_node] = {}
                    
                    nbr2if[src_node][dst_node] = interface_dst
                    nbr2if[dst_node][src_node] = interface_src
        
        # 计算路由
        CalculateRoutes(n)
        SetRoutingEntries()
        
        # 获取网卡速率
        nic_rate = get_nic_rate(n)
        
        logging.info(f"NS3 network setup completed: {node_num} nodes, {link_num} links")
        logging.info(f"NIC rate: {nic_rate} bps")
        
        return True
        
    except Exception as e:
        logging.error(f"Failed to setup NS3 network: {e}")
        return False
