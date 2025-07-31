#!/usr/bin/env python3
"""
验证RTO修复后的行为
"""

import sys
sys.path.append('/Users/nancy/PycharmProjects/simpy')

from network_frontend.htsimpy.examples.mptcp_example_05.main import MptcpSimulation

class DebugMptcpSimulation(MptcpSimulation):
    """带调试功能的MPTCP仿真"""
    
    def __init__(self, args):
        super().__init__(args)
        self.retransmit_events = []
        self.timeout_events = []
        
    def _create_subflows(self):
        """覆盖父类方法，添加调试钩子"""
        super()._create_subflows()
        
        # 为每个TCP源添加调试钩子
        for i, tcp_src in enumerate(self.tcp_sources):
            original_retransmit = tcp_src.retransmit_packet
            original_do_next = tcp_src.do_next_event
            
            def debug_retransmit(src=tcp_src, idx=i):
                time_ms = self.eventlist.now() // 1_000_000
                self.retransmit_events.append({
                    'time_ms': time_ms,
                    'subflow': idx + 1,
                    'highest_sent': src._highest_sent,
                    'last_acked': src._last_acked,
                    'rto': src._rto // 1_000_000
                })
                print(f"\n*** 重传触发 ***")
                print(f"时间: {time_ms}ms")
                print(f"子流: Subflow{idx + 1}")
                print(f"最高发送: {src._highest_sent}")
                print(f"最后确认: {src._last_acked}")
                print(f"当前RTO: {src._rto // 1_000_000}ms")
                return original_retransmit()
            
            def debug_do_next(src=tcp_src, idx=i):
                if src._rtx_timeout_pending:
                    time_ms = self.eventlist.now() // 1_000_000
                    self.timeout_events.append({
                        'time_ms': time_ms,
                        'subflow': idx + 1
                    })
                    print(f"\n*** 超时处理 ***")
                    print(f"时间: {time_ms}ms")
                    print(f"子流: Subflow{idx + 1}")
                return original_do_next()
            
            tcp_src.retransmit_packet = debug_retransmit
            tcp_src.do_next_event = debug_do_next
            
            # 打印初始RTO
            print(f"\n子流{i+1}初始状态:")
            print(f"  初始RTO: {tcp_src._rto // 1_000_000}ms")
            print(f"  初始CWND: {tcp_src._cwnd}")
            print(f"  初始ssthresh: {tcp_src._ssthresh}")

def main():
    """主函数"""
    print("验证RTO修复后的行为")
    print("=" * 80)
    
    # 创建参数
    class Args:
        pass
    
    args = Args()
    args.algorithm = "UNCOUPLED"
    args.epsilon = 1.0
    args.rate2 = 400
    args.rtt2 = 10000  # 10秒RTT
    args.rwnd = 3000
    args.run_paths = 2
    args.duration = 60
    args.algo_value = 1  # UNCOUPLED
    
    # 运行仿真
    sim = DebugMptcpSimulation(args)
    sim.setup()
    
    print("\n开始仿真...")
    print("-" * 60)
    
    sim.run_simulation()
    
    print("\n仿真结果分析:")
    print("=" * 60)
    
    if sim.retransmit_events:
        print(f"\n✓ 检测到 {len(sim.retransmit_events)} 次重传!")
        for event in sim.retransmit_events:
            print(f"  - 时间 {event['time_ms']}ms: 子流{event['subflow']} 重传")
    else:
        print("\n❌ 没有检测到重传!")
        
    if sim.timeout_events:
        print(f"\n✓ 检测到 {len(sim.timeout_events)} 次超时事件!")
        for event in sim.timeout_events:
            print(f"  - 时间 {event['time_ms']}ms: 子流{event['subflow']} 超时")
    else:
        print("\n❌ 没有检测到超时事件!")
    
    # 检查TCP源的最终状态
    print("\n最终状态:")
    for i, tcp_src in enumerate(sim.tcp_sources):
        print(f"\n子流{i+1}:")
        print(f"  最高发送: {tcp_src._highest_sent}")
        print(f"  最后确认: {tcp_src._last_acked}")
        print(f"  CWND: {tcp_src._cwnd}")
        print(f"  RTO: {tcp_src._rto // 1_000_000}ms")
        print(f"  已建立: {tcp_src._established}")

if __name__ == "__main__":
    main()