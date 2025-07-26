# SendPacketEventHandlerData class - corresponds to SendPacketEventHandlerData.cc/SendPacketEventHandlerData.hh in SimAI

from typing import TYPE_CHECKING
from .common import EventType
from .base_stream import BaseStream
from .basic_event_handler_data import BasicEventHandlerData
from .AstraNetworkAPI import MetaData, NcclFlowTag

if TYPE_CHECKING:
    from .sys import Sys


class SendPacketEventHandlerData(BasicEventHandlerData, MetaData):
    """Send packet event handler data - corresponds to SendPacketEventHandlerData.hh in SimAI"""
    
    def __init__(self, *args, **kwargs):
        """Constructor - supports both C++ constructor signatures"""
        if len(args) == 4 and not isinstance(args[0], BaseStream):
            # First constructor: SendPacketEventHandlerData(Sys *node, int senderNodeId, int receiverNodeId, int tag)
            node, senderNodeId, receiverNodeId, tag = args
            super().__init__(node, EventType.PacketSent)
            self.owner = None  # Not set in first constructor
            self.senderNodeId = senderNodeId
            self.receiverNodeId = receiverNodeId
            self.tag = tag
            self.child_flow_id = -2  # Set to -2 in first constructor
            self.channel_id = 0  # Default value (not set in C++ first constructor)
            self.flowTag = NcclFlowTag()
            
        elif len(args) >= 4 and isinstance(args[0], BaseStream):
            # Second constructor: SendPacketEventHandlerData(BaseStream* owner, int senderNodeId, int receiverNodeId, int tag, EventType event)
            owner, senderNodeId, receiverNodeId, tag = args[:4]
            event = args[4] if len(args) > 4 else kwargs.get('event', EventType.PacketSent)
            
            super().__init__(owner.owner, event)  # owner.owner is the Sys node
            self.owner = owner
            self.senderNodeId = senderNodeId
            self.receiverNodeId = receiverNodeId
            self.tag = tag
            self.channel_id = -1  # Set to -1 in second constructor
            self.child_flow_id = -1  # Set to -1 in second constructor
            self.flowTag = NcclFlowTag()
            
        else:
            raise ValueError("Invalid arguments for SendPacketEventHandlerData constructor")
