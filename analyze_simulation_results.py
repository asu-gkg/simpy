#!/usr/bin/env python3
"""
分析和对比C++和Python MPTCP仿真结果
"""

import subprocess
import os
import re
import time
import struct

def parse_cpp_output(output):
    """解析C++仿真输出"""
    results = {}
    
    # 查找重传信息
    retransmits = re.findall(r'At (\d+) RTO (\d+) MDEV (\d+) RTT (\d+) SEQ (\d+) HSENT (\d+) CWND (\d+)', output)
    results['retransmits'] = len(retransmits)
    
    # 查找完成时间标记（dots表示进度）
    dots = output.count('.')
    bars = output.count('|')
    results['progress_dots'] = dots
    results['progress_bars'] = bars
    
    return results

def parse_python_output(output):
    """解析Python仿真输出"""
    results = {}
    
    # 提取关键性能指标
    patterns = {
        '累积确认': r'累积确认: (\d+)',
        '数据确认': r'数据确认: (\d+)',
        '总事件数': r'总事件数: (\d+)',
        '执行时间': r'执行时间: ([\d.]+)秒'
    }
    
    for key, pattern in patterns.items():
        match = re.search(pattern, output)
        if match:
            results[key] = match.group(1)
    
    # 提取子流性能
    subflows = []
    subflow_sections = re.findall(r'子流(\d+)性能:.*?拥塞窗口: (\d+).*?发送包数: (\d+)', output, re.DOTALL)
    for idx, cwnd, packets in subflow_sections:
        subflows.append({
            'index': int(idx),
            'cwnd': int(cwnd),
            'packets_sent': int(packets)
        })
    results['subflows'] = subflows
    
    # 提取队列统计
    queues = {}
    queue_sections = re.findall(r'(\w+)统计:.*?队列大小: (\d+) bytes.*?最大容量: (\d+) bytes.*?丢包数: (\d+)', output, re.DOTALL)
    for name, size, capacity, drops in queue_sections:
        queues[name] = {
            'size': int(size),
            'capacity': int(capacity),
            'drops': int(drops)
        }
    results['queues'] = queues
    
    return results

def parse_cpp_logfile(filename):
    """解析C++日志文件"""
    if not os.path.exists(filename):
        return None
        
    results = {
        'components': {},
        'metadata': {},
        'records': 0
    }
    
    with open(filename, 'rb') as f:
        # 读取文本部分（组件映射和元数据）
        line_num = 0
        for line in f:
            line_num += 1
            try:
                line_str = line.decode('utf-8').strip()
                if line_str.startswith(':'):
                    # 组件映射 ": component_name=id"
                    parts = line_str[1:].split('=')
                    if len(parts) == 2:
                        results['components'][parts[0].strip()] = int(parts[1])
                elif line_str.startswith('#'):
                    # 元数据
                    if '=' in line_str:
                        key, value = line_str[1:].split('=', 1)
                        results['metadata'][key.strip()] = value.strip()
                elif line_str == '# TRACE':
                    # 开始二进制数据部分
                    break
            except:
                # 已到达二进制部分
                break
        
        # 统计二进制记录数（粗略估计）
        remaining = f.read()
        # 每条记录大约64字节
        results['records'] = len(remaining) // 64
    
    return results

def parse_python_logfile(filename):
    """解析Python日志文件"""
    if not os.path.exists(filename):
        return None
        
    results = {
        'components': [],
        'records': 0,
        'data_lines': []
    }
    
    with open(filename, 'r') as f:
        lines = f.readlines()
        
    # Python日志格式不同，直接解析数据行
    for line in lines:
        line = line.strip()
        if line:
            if ' ' in line:  # 数据行
                results['data_lines'].append(line)
                results['records'] += 1
            else:  # 组件名
                results['components'].append(line)
    
    return results

def run_simulation_comparison(algorithm="UNCOUPLED", rate2="400", rtt2="10000", rwnd="3000", run_paths="2"):
    """运行仿真并对比结果"""
    print(f"\n{'='*80}")
    print(f"对比仿真: {algorithm} rate={rate2} rtt={rtt2}ms rwnd={rwnd} paths={run_paths}")
    print(f"{'='*80}")
    
    args = [algorithm, rate2, rtt2, rwnd, run_paths]
    
    # 运行Python仿真
    print("\n1. 运行Python仿真...")
    py_cmd = ["uv", "run", "python", "network_frontend/htsimpy/examples/05_mptcp_example/main.py"] + args
    py_result = subprocess.run(py_cmd, capture_output=True, text=True, cwd="/Users/nancy/PycharmProjects/simpy")
    
    if py_result.returncode != 0:
        print(f"Python仿真失败: {py_result.stderr}")
        return
    
    py_output = py_result.stdout
    py_results = parse_python_output(py_output)
    
    # 等待文件写入
    time.sleep(0.5)
    
    # 运行C++仿真
    print("\n2. 运行C++仿真...")
    cpp_cmd = ["./main"] + args
    cpp_result = subprocess.run(cpp_cmd, capture_output=True, text=True, cwd="/Users/nancy/PycharmProjects/simpy/csg-htsim/sim/tests")
    
    if cpp_result.returncode != 0:
        print(f"C++仿真失败: {cpp_result.stderr}")
        return
    
    cpp_output = cpp_result.stdout
    cpp_results = parse_cpp_output(cpp_output)
    
    # 对比结果
    print("\n3. 仿真结果对比:")
    print("-" * 60)
    
    # Python结果
    print("\nPython仿真结果:")
    print(f"  总事件数: {py_results.get('总事件数', 'N/A')}")
    print(f"  执行时间: {py_results.get('执行时间', 'N/A')}秒")
    print(f"  累积确认: {py_results.get('累积确认', 'N/A')}")
    print(f"  数据确认: {py_results.get('数据确认', 'N/A')}")
    
    if 'subflows' in py_results:
        print(f"\n  子流统计:")
        for sf in py_results['subflows']:
            print(f"    子流{sf['index']}: CWND={sf['cwnd']}, 发送包数={sf['packets_sent']}")
    
    if 'queues' in py_results:
        print(f"\n  队列丢包统计:")
        total_drops = 0
        for name, stats in py_results['queues'].items():
            if stats['drops'] > 0:
                print(f"    {name}: {stats['drops']}个包")
                total_drops += stats['drops']
        print(f"    总丢包数: {total_drops}")
    
    # C++结果
    print(f"\nC++仿真结果:")
    print(f"  重传次数: {cpp_results.get('retransmits', 0)}")
    print(f"  进度标记: {cpp_results.get('progress_dots', 0)}个点, {cpp_results.get('progress_bars', 0)}个竖线")
    
    # 分析日志文件
    print("\n4. 日志文件分析:")
    print("-" * 60)
    
    logfile = f"logout.{rate2}pktps.{int(rtt2)}ms.{rwnd}rwnd"
    py_logfile = f"/Users/nancy/PycharmProjects/simpy/data/{logfile}"
    cpp_logfile = f"/Users/nancy/PycharmProjects/simpy/csg-htsim/sim/data/{logfile}"
    
    py_log = parse_python_logfile(py_logfile)
    cpp_log = parse_cpp_logfile(cpp_logfile)
    
    if py_log:
        print(f"\nPython日志文件:")
        print(f"  文件大小: {os.path.getsize(py_logfile)} bytes")
        print(f"  组件数: {len(py_log['components'])}")
        print(f"  记录数: {py_log['records']}")
    
    if cpp_log:
        print(f"\nC++日志文件:")
        print(f"  文件大小: {os.path.getsize(cpp_logfile)} bytes")
        print(f"  组件数: {len(cpp_log['components'])}")
        print(f"  记录数: {cpp_log['records']}")
        print(f"  元数据:")
        for key, value in cpp_log['metadata'].items():
            print(f"    {key}: {value}")
    
    # 行为分析
    print("\n5. 行为一致性分析:")
    print("-" * 60)
    
    issues = []
    
    # 检查Python仿真的子流行为
    if 'subflows' in py_results:
        active_subflows = [sf for sf in py_results['subflows'] if sf['packets_sent'] > 0]
        if len(active_subflows) == 0:
            issues.append("Python仿真中没有活跃的子流（所有子流发送包数为0）")
        elif run_paths == "2" and len(active_subflows) < 2:
            issues.append(f"期望2个活跃子流，但只有{len(active_subflows)}个")
    
    # 检查C++重传
    if cpp_results.get('retransmits', 0) > 0:
        issues.append(f"C++仿真检测到{cpp_results['retransmits']}次重传")
    
    # 检查日志文件差异
    if py_log and cpp_log:
        record_diff = abs(py_log['records'] - cpp_log['records'])
        if record_diff > cpp_log['records'] * 0.1:  # 超过10%的差异
            issues.append(f"日志记录数差异较大: Python={py_log['records']}, C++={cpp_log['records']}")
    
    if issues:
        print("发现的问题:")
        for i, issue in enumerate(issues, 1):
            print(f"  {i}. {issue}")
    else:
        print("✓ 未发现明显的行为差异")
    
    return py_results, cpp_results

def main():
    """主函数"""
    print("MPTCP仿真结果对比分析工具")
    print("=" * 80)
    
    # 测试不同的算法和参数
    test_cases = [
        # (algorithm, rate2, rtt2, rwnd, run_paths)
        ("UNCOUPLED", "400", "10000", "3000", "2"),
        ("COUPLED_INC", "400", "10000", "3000", "2"),
        ("FULLY_COUPLED", "400", "10000", "3000", "2"),
        # 测试单路径
        ("UNCOUPLED", "400", "10000", "3000", "1"),
        # 测试不同RTT
        ("UNCOUPLED", "400", "100", "3000", "2"),
    ]
    
    all_results = []
    
    for test_case in test_cases[:1]:  # 先只运行第一个测试
        py_res, cpp_res = run_simulation_comparison(*test_case)
        all_results.append((test_case, py_res, cpp_res))
        time.sleep(1)  # 避免文件冲突
    
    # 总结
    print("\n" + "="*80)
    print("总结")
    print("="*80)
    
    print("\n测试用例数:", len(all_results))
    for test_case, py_res, cpp_res in all_results:
        print(f"\n{test_case[0]} rate={test_case[1]} rtt={test_case[2]}ms:")
        if py_res and 'subflows' in py_res:
            total_packets = sum(sf['packets_sent'] for sf in py_res['subflows'])
            print(f"  Python: 总发送包数={total_packets}")
        if cpp_res:
            print(f"  C++: 重传次数={cpp_res.get('retransmits', 0)}")

if __name__ == "__main__":
    main()