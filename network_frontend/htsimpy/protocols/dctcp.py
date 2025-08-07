"""
DCTCP (Data Center TCP) Implementation

对应文件: dctcp.h/cpp
功能: 数据中心TCP协议实现，支持ECN标记的拥塞控制

DCTCP是专为数据中心网络设计的TCP变种，特点：
- 使用ECN(Explicit Congestion Notification)进行精细拥塞控制
- 维护α参数跟踪拥塞程度
- 基于标记比例调整拥塞窗口

主要类:
- DCTCPSrc: DCTCP源端，继承自TcpSrc

C++对应关系:
- DCTCPSrc::DCTCPSrc() -> DCTCPSrc.__init__()
- DCTCPSrc::deflate_window() -> DCTCPSrc.deflate_window()
- DCTCPSrc::receivePacket() -> DCTCPSrc.receivePacket()
- DCTCPSrc::rtx_timer_hook() -> DCTCPSrc.rtx_timer_hook()
"""

from typing import Optional
from .tcp import TcpSrc, TcpSink
from ..core.network import Packet
from ..core.eventlist import EventList
from ..core.logger.tcp import TcpLogger
from ..core.logger.traffic import TrafficLogger

# ECN标志位 - 对应C++ ecn.h
ECN_ECHO = 0x01  # ECN回显标志

def timeFromMs(ms: float) -> int:
    """毫秒转换为皮秒"""
    return int(ms * 1_000_000_000)

def timeAsMs(ps: int) -> float:
    """皮秒转换为毫秒"""
    return ps / 1_000_000_000


class DCTCPSrc(TcpSrc):
    """
    DCTCP源端实现 - 精确对应 dctcp.h/cpp 中的 DCTCPSrc 类
    
    class DCTCPSrc : public TcpSrc {
    public:
        DCTCPSrc(TcpLogger* logger, TrafficLogger* pktlogger, EventList &eventlist);
        ~DCTCPSrc(){}
        
        // Mechanism
        virtual void deflate_window();
        virtual void receivePacket(Packet& pkt);
        virtual void rtx_timer_hook(simtime_picosec now,simtime_picosec period);
        
    private:
        uint32_t _past_cwnd;
        double _alfa;
        uint32_t _pkts_seen, _pkts_marked;
    };
    """
    
    def __init__(self, 
                 logger: Optional[TcpLogger] = None,
                 traffic_logger: Optional[TrafficLogger] = None,
                 eventlist: Optional[EventList] = None):
        """
        初始化DCTCP源端 - 对应 C++ DCTCPSrc::DCTCPSrc()
        
        DCTCPSrc::DCTCPSrc(TcpLogger* logger, TrafficLogger* pktlogger, 
                           EventList &eventlist) : TcpSrc(logger,pktlogger,eventlist)
        {
            _pkts_seen = 0;
            _pkts_marked = 0;
            _alfa = 0;
            _past_cwnd = 2*Packet::data_packet_size();
            _rto = timeFromMs(10);    
        }
        
        Args:
            logger: TCP日志记录器
            traffic_logger: 流量日志记录器
            eventlist: 事件列表
        """
        # 调用父类TcpSrc的构造函数
        super().__init__(logger, traffic_logger, eventlist)
        
        # DCTCP特有成员变量 - 对应C++私有成员
        self._pkts_seen = 0      # uint32_t _pkts_seen - 看到的包数
        self._pkts_marked = 0    # uint32_t _pkts_marked - 被标记的包数
        self._alfa = 0.0         # double _alfa - DCTCP的α参数
        self._past_cwnd = 2 * Packet.data_packet_size()  # uint32_t _past_cwnd
        
        # 设置RTO为10ms - 对应 _rto = timeFromMs(10)
        self._rto = timeFromMs(10)
        
        # 设置节点名称
        self._nodename = "dctcpsrc"
    
    def deflate_window(self) -> None:
        """
        收缩拥塞窗口 - 对应 C++ DCTCPSrc::deflate_window()
        
        void DCTCPSrc::deflate_window(){
            _pkts_seen = 0;
            _pkts_marked = 0;
            if (_mSrc==NULL){
                _ssthresh = max(_cwnd/2, (uint32_t)(2 * _mss));
            }
            else
                _ssthresh = _mSrc->deflate_window(_cwnd,_mss);
            
            _past_cwnd = _cwnd;
        }
        """
        # 重置计数器
        self._pkts_seen = 0
        self._pkts_marked = 0
        
        # 根据是否有MPTCP连接调整ssthresh
        if self._mSrc is None:
            # 独立DCTCP连接
            self._ssthresh = max(self._cwnd // 2, 2 * self._mss)
        else:
            # MPTCP子流 - 调用MPTCP的deflate_window
            self._ssthresh = self._mSrc.deflate_window(self._cwnd, self._mss)
        
        # 记录当前窗口大小
        self._past_cwnd = self._cwnd
    
    def receivePacket(self, pkt: Packet) -> None:
        """
        接收数据包处理 - 对应 C++ DCTCPSrc::receivePacket()
        
        完整实现DCTCP的ECN处理逻辑：
        1. 统计ECN标记的包
        2. 每RTT更新一次α参数
        3. 基于α调整拥塞窗口
        
        void DCTCPSrc::receivePacket(Packet& pkt) 
        {
            _pkts_seen++;
            
            if (pkt.flags() & ECN_ECHO){
                _pkts_marked += 1;
                
                //exit slow start since we're causing congestion
                if (_ssthresh>_cwnd)
                    _ssthresh = _cwnd;
            }
            
            if (_pkts_seen * _mss >= _past_cwnd){
                //update window, once per RTT
                
                double f = (double)_pkts_marked/_pkts_seen;
                
                _alfa = 15.0/16.0 * _alfa + 1.0/16.0 * f;
                _pkts_seen = 0;
                _pkts_marked = 0;
                
                if (_alfa>0){
                    _cwnd = _cwnd * (1-_alfa/2);
                    
                    if (_cwnd<_mss)
                        _cwnd = _mss;
                    
                    _ssthresh = _cwnd;
                }
                _past_cwnd = _cwnd;
            }
            
            TcpSrc::receivePacket(pkt);
        }
        """
        # 增加看到的包计数
        self._pkts_seen += 1
        
        # 检查ECN标记 - 对应 if (pkt.flags() & ECN_ECHO)
        if hasattr(pkt, 'flags') and (pkt.flags() & ECN_ECHO):
            self._pkts_marked += 1
            
            # 退出慢启动，因为我们正在造成拥塞
            if self._ssthresh > self._cwnd:
                self._ssthresh = self._cwnd
        
        # 每RTT更新一次窗口 - 对应 if (_pkts_seen * _mss >= _past_cwnd)
        if self._pkts_seen * self._mss >= self._past_cwnd:
            # 计算标记比例
            if self._pkts_seen > 0:
                f = self._pkts_marked / self._pkts_seen
            else:
                f = 0.0
            
            # 更新α参数 - EWMA with g=1/16
            # _alfa = 15.0/16.0 * _alfa + 1.0/16.0 * f
            self._alfa = (15.0 / 16.0) * self._alfa + (1.0 / 16.0) * f
            
            # 重置计数器
            self._pkts_seen = 0
            self._pkts_marked = 0
            
            # 基于α调整拥塞窗口
            if self._alfa > 0:
                # DCTCP公式: cwnd = cwnd * (1 - α/2)
                self._cwnd = int(self._cwnd * (1 - self._alfa / 2))
                
                # 确保窗口不小于MSS
                if self._cwnd < self._mss:
                    self._cwnd = self._mss
                
                # 更新慢启动阈值
                self._ssthresh = self._cwnd
            
            # 记录当前窗口大小
            self._past_cwnd = self._cwnd
            
            # 调试输出（可选）
            # print(f"DCTCP UPDATE: time={timeAsMs(self._eventlist.now()):.3f}ms "
            #       f"cwnd={self._cwnd} alfa={self._alfa:.4f} marked_ratio={f:.4f}")
        
        # 调用父类的receivePacket处理其他逻辑
        super().receivePacket(pkt)
    
    def rtx_timer_hook(self, now: int, period: int) -> None:
        """
        重传定时器钩子 - 对应 C++ DCTCPSrc::rtx_timer_hook()
        
        void DCTCPSrc::rtx_timer_hook(simtime_picosec now,simtime_picosec period){
            TcpSrc::rtx_timer_hook(now,period);
        };
        
        Args:
            now: 当前时间（皮秒）
            period: 定时器周期（皮秒）
        """
        # 直接调用父类的rtx_timer_hook
        super().rtx_timer_hook(now, period)
    
    def get_alfa(self) -> float:
        """
        获取当前的α参数值
        
        Returns:
            当前的α值（0到1之间）
        """
        return self._alfa
    
    def get_marking_stats(self) -> tuple[int, int]:
        """
        获取标记统计信息
        
        Returns:
            (pkts_seen, pkts_marked) - 看到的包数和被标记的包数
        """
        return (self._pkts_seen, self._pkts_marked)
    
    def __str__(self) -> str:
        """返回字符串表示"""
        return f"DCTCPSrc[id={self.get_id()}, cwnd={self._cwnd}, alfa={self._alfa:.4f}]"


class DCTCPSink(TcpSink):
    """
    DCTCP接收端实现
    
    注意：在C++版本中，DCTCP使用标准的TcpSink，
    因为ECN标记是在队列中完成的，接收端只需要回显ECN标记。
    这里提供一个包装类以便将来扩展。
    """
    
    def __init__(self):
        """初始化DCTCP接收端"""
        super().__init__()
        self._nodename = "dctcpsink"
    
    def connect(self, src: DCTCPSrc, route) -> None:
        """
        连接到DCTCP源端
        
        Args:
            src: DCTCP源端
            route: 返回路由
        """
        super().connect(src, route)


# 导出接口
__all__ = [
    'DCTCPSrc',
    'DCTCPSink',
    'ECN_ECHO',
]