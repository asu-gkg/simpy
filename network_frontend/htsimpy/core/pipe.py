"""
Pipe - Network Pipe Component

对应文件: pipe.h/cpp
功能: 网络管道，简单地延迟所有进入的数据包

主要类:
- Pipe: 网络管道类
- PktRecord: 数据包记录结构

C++对应关系:
- Pipe::receivePacket() -> Pipe.receive_packet()
- Pipe::doNextEvent() -> Pipe.do_next_event()
- Pipe::delay() -> Pipe.delay()
- Pipe::setNext() -> Pipe.set_next()
- Pipe::next() -> Pipe.next()
"""

from typing import Optional, List
from dataclasses import dataclass
from .network import PacketSink, Packet
from .eventlist import EventSource, EventList
from .drawable import Drawable
from .logger import TrafficLogger


@dataclass
class PktRecord:
    """
    对应 C++ 中的 pktrecord 结构体
    存储数据包和时间信息
    """
    time: int  # simtime_picosec
    pkt: Packet


class Pipe(EventSource, PacketSink, Drawable):
    """
    网络管道类 - 对应 pipe.h/cpp 中的 Pipe 类
    
    简单地延迟所有进入的数据包的设备
    继承自 EventSource, PacketSink, Drawable (对应C++完整定义)
    """
    
    def __init__(self, delay: int, eventlist: Optional[EventList] = None):
        """
        对应 C++ 中的 Pipe::Pipe(simtime_picosec delay, EventList& eventlist)
        
        Args:
            delay: 延迟时间（皮秒）
            eventlist: 事件列表
        """
        # 对应 C++ 构造函数：EventSource(eventlist,"pipe"), _delay(delay)
        if eventlist is None:
            eventlist = EventList.get_the_event_list()
        
        EventSource.__init__(self, eventlist, "pipe")
        PacketSink.__init__(self)
        Drawable.__init__(self)
        
        # 对应 C++ 私有成员
        self._delay: int = delay
        self._next_sink: Optional[PacketSink] = None
        
        # 环形缓冲区相关
        self._count: int = 0
        self._next_insert: int = 0
        self._next_pop: int = 0
        self._size: int = 16  # 初始大小，需要时会调整
        self._inflight_v: List[PktRecord] = [PktRecord(0, None) for _ in range(self._size)]
        
        # 对应 C++ 中的 stringstream 和 _nodename 设置
        # stringstream ss; ss << "pipe(" << delay/1000000 << "us)"; _nodename= ss.str();
        self._nodename = f"pipe({delay // 1000000}us)"
    
    def receivePacket(self, packet: Packet, virtual_queue=None) -> None:
        """
        对应 C++ 中的 void Pipe::receivePacket(Packet& pkt)
        接收数据包并安排其传输
        """
        # 对应 C++ 中被注释掉的: //pkt.flow().logTraffic(pkt,*this,TrafficLogger::PKT_ARRIVE);
        # if hasattr(packet, 'flow') and packet.flow() and packet.flow().log_me():
        #     packet.flow().log_traffic(packet, self, TrafficLogger.TrafficEvent.PKT_ARRIVE)
        
        if self._count == 0:
            # 没有数据包在途中；需要通知事件列表有待处理事件
            self._eventlist.source_is_pending_rel(self, self._delay)
        
        self._count += 1
        
        # 如果缓冲区满了，需要扩容
        if self._count == self._size:
            self._resize_buffer()
        
        # 添加数据包到环形缓冲区
        self._inflight_v[self._next_insert].time = self._eventlist.now() + self._delay
        self._inflight_v[self._next_insert].pkt = packet
        self._next_insert = (self._next_insert + 1) % self._size
    
    def do_next_event(self) -> None:
        """
        对应 C++ 中的 void Pipe::doNextEvent()
        处理下一个事件
        """
        if self._count == 0:
            return
        
        # 取出下一个要发送的数据包
        pkt = self._inflight_v[self._next_pop].pkt
        self._next_pop = (self._next_pop + 1) % self._size
        self._count -= 1
        
        # 对应 C++ 中的 pkt->flow().logTraffic(*pkt, *this,TrafficLogger::PKT_DEPART)
        pkt.flow().logTraffic(pkt, self, TrafficLogger.TrafficEvent.PKT_DEPART)
        
        # 调试信息
        if hasattr(pkt, '_nexthop') and hasattr(pkt, '_route') and pkt._route:
            if pkt._nexthop >= pkt._route.size():
                # 包已经到达目的地，不应该再发送
                # 这种情况可能发生在包被重用时
                return
        
        # 对应 C++ 中的 pkt->sendOn()
        pkt.sendOn()
        
        # 对应 C++ 中的条件检查和事件调度
        if self._count > 0:
            # 对应 C++ 中的 simtime_picosec nexteventtime = _inflight_v[_next_pop].time
            next_event_time = self._inflight_v[self._next_pop].time
            # 对应 C++ 中的 _eventlist.sourceIsPending(*this, nexteventtime)
            # 对应 C++ 中的 _eventlist.sourceIsPending(*this, nexteventtime)
            self._eventlist.source_is_pending(self, next_event_time)
    
    def _resize_buffer(self) -> None:
        """
        对应 C++ 中缓冲区扩容的逻辑
        当缓冲区满时扩容
        精确按照 C++ 实现：先扩容数组，然后重新排列数据
        """
        # 对应 C++ 中的 _inflight_v.resize(_size*2)
        old_size = self._size
        new_size = self._size * 2
        
        # 扩展现有数组
        self._inflight_v.extend([PktRecord(0, None) for _ in range(old_size)])
        
        # 对应 C++ 逻辑：如果 _next_insert < _next_pop，需要重新排列数据
        if self._next_insert < self._next_pop:
            # 对应 C++ 注释：//   456789*123 和 // NI *, NP 1
            # 将前半部分移动到新空间
            for i in range(self._next_insert):
                # 对应 C++ 中的 _inflight_v.at(_size+i) = _inflight_v.at(i)
                # 注释说明：move 4-9 into new space (实际是move 0到_next_insert-1)
                self._inflight_v[old_size + i] = self._inflight_v[i]
            # 对应 C++ 中的 _next_insert += _size
            self._next_insert += old_size
        else:
            # 对应 C++ 注释：// 123456789* -> // nothing to do
            pass
        
        # 对应 C++ 中的 _size += _size (等同于 _size *= 2)
        self._size = new_size
    
    def delay(self) -> int:
        """
        对应 C++ 中的 simtime_picosec delay()
        返回管道延迟
        """
        return self._delay
    
    def nodename(self) -> str:
        """
        对应 C++ 中的 const string& nodename()
        返回节点名称
        """
        return self._nodename
    
    def force_name(self, name: str) -> None:
        """
        对应 C++ 中的 void forceName(string name)
        强制设置节点名称
        """
        self._nodename = name
    
    def setName(self, name: str) -> None:
        """
        对应 C++ 中的 Logged::setName() - 通过EventSource继承
        设置对象名称
        """
        # 调用基类的setName方法
        EventSource.setName(self, name)
        # 可选：也更新nodename
        if not self._nodename:
            self._nodename = name
    
    def set_next(self, next_sink: PacketSink) -> None:
        """
        对应 C++ 中的 void setNext(PacketSink* next_sink)
        设置下一个接收器
        """
        self._next_sink = next_sink
    
    def next(self) -> Optional[PacketSink]:
        """
        对应 C++ 中的 PacketSink* next() const
        获取下一个接收器
        """
        return self._next_sink
    
    def __str__(self) -> str:
        """字符串表示"""
        return f"Pipe(delay={self._delay}ps, next={self._next_sink})"
    
    def __repr__(self) -> str:
        """详细字符串表示"""
        return f"Pipe(delay={self._delay}, count={self._count}, size={self._size})" 