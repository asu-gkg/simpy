# MyPacket class - corresponds to MyPacket.hh/cc in SimAI

from typing import Optional, TYPE_CHECKING
from .callable import Callable, CallData
from .common import EventType, Tick

if TYPE_CHECKING:
    pass


class MyPacket(Callable):
    """MyPacket class for network packet representation
    
    Corresponds to MyPacket.hh/cc in SimAI
    """
    
    def __init__(self, 
                 preferred_vnet: Optional[int] = None,
                 preferred_src: Optional[int] = None, 
                 preferred_dest: Optional[int] = None,
                 msg_size: Optional[int] = None,
                 channel_id: Optional[int] = None,
                 flow_id: Optional[int] = None):
        """Initialize MyPacket
        
        Args:
            preferred_vnet: Preferred virtual network
            preferred_src: Preferred source node
            preferred_dest: Preferred destination node  
            msg_size: Message size
            channel_id: Channel ID
            flow_id: Flow ID
        """
        super().__init__()
        
        # Basic packet properties
        self.cycles_needed: int = 0
        self.fm_id: int = 0
        self.stream_num: int = 0
        self.notifier: Optional[Callable] = None
        self.sender: Optional[Callable] = None
        
        # Network routing properties
        self.preferred_vnet: int = preferred_vnet if preferred_vnet is not None else 0
        self.preferred_dest: int = preferred_dest if preferred_dest is not None else 0
        self.preferred_src: int = preferred_src if preferred_src is not None else 0
        self.msg_size: int = msg_size if msg_size is not None else 0
        self.ready_time: Tick = 0
        
        # Flow model properties
        self.flow_id: int = flow_id if flow_id is not None else 0
        self.parent_flow_id: int = 0
        self.child_flow_id: int = 0
        self.channel_id: int = channel_id if channel_id is not None else 0
        self.chunk_id: int = 0
    
    @classmethod
    def create_basic(cls, preferred_vnet: int, preferred_src: int, preferred_dest: int) -> 'MyPacket':
        """Create basic packet - corresponds to MyPacket(int, int, int) constructor
        
        Args:
            preferred_vnet: Preferred virtual network
            preferred_src: Preferred source node
            preferred_dest: Preferred destination node
            
        Returns:
            MyPacket instance
        """
        return cls(preferred_vnet=preferred_vnet, 
                  preferred_src=preferred_src, 
                  preferred_dest=preferred_dest,
                  msg_size=0)
    
    @classmethod 
    def create_with_size(cls, msg_size: int, preferred_vnet: int, 
                        preferred_src: int, preferred_dest: int) -> 'MyPacket':
        """Create packet with message size - corresponds to MyPacket(uint64_t, int, int, int) constructor
        
        Args:
            msg_size: Message size
            preferred_vnet: Preferred virtual network
            preferred_src: Preferred source node
            preferred_dest: Preferred destination node
            
        Returns:
            MyPacket instance
        """
        return cls(preferred_vnet=preferred_vnet,
                  preferred_src=preferred_src,
                  preferred_dest=preferred_dest,
                  msg_size=msg_size)
    
    @classmethod
    def create_with_flow(cls, preferred_vnet: int, preferred_src: int, preferred_dest: int,
                        msg_size: int, channel_id: int, flow_id: int) -> 'MyPacket':
        """Create packet with flow info - corresponds to MyPacket(int, int, int, uint64_t, int, int) constructor
        
        Args:
            preferred_vnet: Preferred virtual network
            preferred_src: Preferred source node
            preferred_dest: Preferred destination node
            msg_size: Message size
            channel_id: Channel ID
            flow_id: Flow ID
            
        Returns:
            MyPacket instance
        """
        return cls(preferred_vnet=preferred_vnet,
                  preferred_src=preferred_src,
                  preferred_dest=preferred_dest,
                  msg_size=msg_size,
                  channel_id=channel_id,
                  flow_id=flow_id)
    
    def set_flow_id(self, flow_id: int) -> None:
        """Set flow ID
        
        Args:
            flow_id: Flow ID to set
        """
        self.flow_id = flow_id
    
    def set_notifier(self, notifier: Callable) -> None:
        """Set notifier callback
        
        Args:
            notifier: Callable object to notify
        """
        self.notifier = notifier
    
    def call(self, event_type: EventType, data: CallData) -> None:
        """Handle event call - from Callable interface
        
        Args:
            event_type: Type of event
            data: Associated call data
        """
        self.cycles_needed = 0
        if self.notifier is not None:
            self.notifier.call(EventType.General, None)
    
    def __str__(self) -> str:
        """String representation of the packet
        
        Returns:
            String description of the packet
        """
        return (f"MyPacket(vnet={self.preferred_vnet}, "
                f"src={self.preferred_src}, dest={self.preferred_dest}, "
                f"size={self.msg_size}, flow_id={self.flow_id}, "
                f"channel_id={self.channel_id})")
    
    def __repr__(self) -> str:
        """Detailed representation of the packet
        
        Returns:
            Detailed string representation
        """
        return self.__str__() 