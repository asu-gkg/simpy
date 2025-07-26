# SendPacketEventHandlerData class - corresponds to SendPacketEventHandlerData.cc/SendPacketEventHandlerData.hh in SimAI

from .common import EventType

# Forward declarations
class Sys:
    pass

class BaseStream:
    pass

class BasicEventHandlerData:
    """Basic event handler data"""
    
    def __init__(self, node: Sys, event: EventType):
        self.node = node
        self.event = event

class MetaData:
    """Metadata base class"""
    pass

class ncclFlowTag:
    """NCCL flow tag"""
    pass

class SendPacketEventHandlerData(BasicEventHandlerData, MetaData):
    """Send packet event handler data - corresponds to SendPacketEventHandlerData.hh in SimAI"""
    
    def __init__(self, node: Sys, senderNodeId: int, receiverNodeId: int, tag: int, 
                 owner: BaseStream = None, event: EventType = EventType.PacketSent):
        """Constructor - corresponds to SendPacketEventHandlerData::SendPacketEventHandlerData"""
        super().__init__(node, event)
        self.owner = owner
        self.senderNodeId = senderNodeId
        self.receiverNodeId = receiverNodeId
        self.tag = tag
        # Flow model fields
        self.child_flow_id = -2
        self.channel_id = 0
        self.flowTag = ncclFlowTag()
