#!/usr/bin/env python3
"""
深入调试为什么Python没有触发重传
即使在修复time_from_ms后仍然如此
"""

import sys
sys.path.append('/Users/nancy/PycharmProjects/simpy')

from network_frontend.htsimpy.core.eventlist import EventList
from network_frontend.htsimpy.protocols.tcp import TcpSrc, TcpSink, TcpRtxTimerScanner
from network_frontend.htsimpy.core.pipe import Pipe
from network_frontend.htsimpy.queues.base_queue import Queue
from network_frontend.htsimpy.core.route import Route
from network_frontend.htsimpy.packets.tcp_packet import TcpPacket, TcpAck

def time_from_ms(ms: int) -> int:
    """毫秒转换为皮秒"""
    return ms * 1_000_000_000

class RetransmissionMonitor:
    """监控重传事件"""
    def __init__(self, tcp_src, name):
        self.tcp_src = tcp_src
        self.name = name
        self.events = []
        
        # Hook into key methods
        self._original_retransmit = tcp_src.retransmit_packet
        self._original_do_next = tcp_src.do_next_event
        self._original_send_packets = tcp_src.send_packets
        self._original_rtx_timer_hook = tcp_src.rtx_timer_hook
        
        tcp_src.retransmit_packet = self._wrapped_retransmit
        tcp_src.do_next_event = self._wrapped_do_next
        tcp_src.send_packets = self._wrapped_send_packets
        tcp_src.rtx_timer_hook = self._wrapped_rtx_timer_hook
        
    def _wrapped_retransmit(self):
        time_ms = self.tcp_src._eventlist.now() // 1_000_000_000
        self.events.append(f"[{time_ms}ms] retransmit_packet called")
        print(f"\n*** RETRANSMISSION at {time_ms}ms for {self.name} ***")
        print(f"  RTO: {self.tcp_src._rto // 1_000_000_000}ms")
        print(f"  Highest sent: {self.tcp_src._highest_sent}")
        print(f"  Last acked: {self.tcp_src._last_acked}")
        return self._original_retransmit()
        
    def _wrapped_do_next(self):
        if self.tcp_src._rtx_timeout_pending:
            time_ms = self.tcp_src._eventlist.now() // 1_000_000_000
            self.events.append(f"[{time_ms}ms] do_next_event with rtx_timeout_pending=True")
        return self._original_do_next()
        
    def _wrapped_send_packets(self):
        time_ms = self.tcp_src._eventlist.now() // 1_000_000_000
        before_sent = self.tcp_src._highest_sent
        result = self._original_send_packets()
        after_sent = self.tcp_src._highest_sent
        if after_sent > before_sent:
            self.events.append(f"[{time_ms}ms] send_packets: sent {after_sent - before_sent} packets")
        return result
        
    def _wrapped_rtx_timer_hook(self, time, scanPeriod=None):
        time_ms = time // 1_000_000_000
        self.events.append(f"[{time_ms}ms] rtx_timer_hook called")
        print(f"\n[{time_ms}ms] RTX Timer Hook for {self.name}")
        print(f"  RFC2988_RTO_timeout: {self.tcp_src._RFC2988_RTO_timeout // 1_000_000_000}ms")
        print(f"  Current time: {time_ms}ms")
        print(f"  Should timeout: {time > self.tcp_src._RFC2988_RTO_timeout}")
        if scanPeriod is not None:
            return self._original_rtx_timer_hook(time, scanPeriod)
        else:
            return self._original_rtx_timer_hook(time)

def test_simple_retransmission():
    """Test a simple scenario that should trigger retransmission"""
    print("=== Testing Simple Retransmission Scenario ===")
    print("Setup: RTT=10s, initial RTO=3s (should trigger retransmission)")
    print()
    
    # Create event list
    eventlist = EventList()
    eventlist.set_endtime(time_from_ms(15000))  # 15 seconds
    
    # Create TCP scanner with 10ms period
    scanner = TcpRtxTimerScanner(time_from_ms(10), eventlist)
    
    # Create TCP source and sink
    tcp_src = TcpSrc(None, None, eventlist)
    tcp_src.setName("TestTCP")
    tcp_sink = TcpSink()
    
    # Register with scanner
    scanner.registerTcp(tcp_src)
    
    # Create high latency pipes (5s each way = 10s RTT)
    pipe_out = Pipe(time_from_ms(5000), eventlist)
    pipe_back = Pipe(time_from_ms(5000), eventlist)
    
    # Create routes
    route_out = Route()
    route_out.push_back(pipe_out)
    route_out.push_back(tcp_sink)
    
    route_back = Route()
    route_back.push_back(pipe_back)
    route_back.push_back(tcp_src)
    
    # Add monitoring
    monitor = RetransmissionMonitor(tcp_src, "TestTCP")
    
    # Connect with start time 0
    print(f"Initial state:")
    print(f"  RTO: {tcp_src._rto // 1_000_000_000}ms")
    print(f"  Established: {tcp_src._established}")
    
    tcp_src.connect(route_out, route_back, tcp_sink, 0)
    
    print(f"\nAfter connect:")
    print(f"  RTO: {tcp_src._rto // 1_000_000_000}ms")
    print(f"  RFC2988_RTO_timeout: {tcp_src._RFC2988_RTO_timeout // 1_000_000_000}ms")
    print(f"  Highest sent: {tcp_src._highest_sent}")
    
    # Run simulation
    print("\nRunning simulation...")
    print("-" * 60)
    
    events_count = 0
    last_report_time = -1
    
    while eventlist.do_next_event():
        events_count += 1
        current_time = eventlist.now()
        time_ms = current_time // 1_000_000_000
        
        # Report at key times
        if time_ms in [0, 10, 100, 1000, 3000, 3010, 3020, 3030, 6000, 9000, 10000] and time_ms != last_report_time:
            print(f"\n[{time_ms}ms] Status:")
            print(f"  Events processed: {events_count}")
            print(f"  Highest sent: {tcp_src._highest_sent}")
            print(f"  Last acked: {tcp_src._last_acked}")
            print(f"  RTO timeout at: {tcp_src._RFC2988_RTO_timeout // 1_000_000_000}ms")
            print(f"  RTX pending: {tcp_src._rtx_timeout_pending}")
            last_report_time = time_ms
    
    print(f"\nSimulation completed. Total events: {events_count}")
    
    # Check results
    print("\n=== Event Summary ===")
    for event in monitor.events:
        print(event)
    
    retransmissions = [e for e in monitor.events if "retransmit_packet" in e]
    if retransmissions:
        print(f"\n✓ Found {len(retransmissions)} retransmissions!")
    else:
        print("\n❌ No retransmissions detected!")
        
    # Additional diagnostics
    print("\n=== Diagnostics ===")
    print(f"Final state:")
    print(f"  Established: {tcp_src._established}")
    print(f"  Highest sent: {tcp_src._highest_sent}")
    print(f"  Last acked: {tcp_src._last_acked}")
    print(f"  CWND: {tcp_src._cwnd}")

if __name__ == "__main__":
    test_simple_retransmission()