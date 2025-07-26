# *****************************************************************************
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.
# *****************************************************************************

# BasicEventHandlerData.py - corresponds to BasicEventHandlerData.hh/cc in SimAI

from typing import TYPE_CHECKING, Optional
from .callable import CallData
from .common import EventType

if TYPE_CHECKING:
    from .sys import Sys


class BasicEventHandlerData(CallData):
    """Basic event handler data class
    
    Corresponds to AstraSim::BasicEventHandlerData in SimAI
    """
    
    def __init__(self, *args, **kwargs):
        """Initialize BasicEventHandlerData
        
        Multiple constructor signatures:
        1. BasicEventHandlerData(node: Sys, event: EventType)
        2. BasicEventHandlerData(channel_id: int, flow_id: int)
        3. BasicEventHandlerData() - default constructor
        """
        super().__init__()
        
        # Initialize all member variables
        self.node: Optional['Sys'] = None
        self.event: EventType = EventType.NONE
        self.channel_id: int = -1
        self.flow_id: int = -1
        
        # Handle different constructor signatures
        if len(args) == 2:
            if hasattr(args[0], '__class__') and 'Sys' in str(type(args[0])):
                # Constructor: BasicEventHandlerData(Sys* node, EventType event)
                self.node = args[0]
                self.event = args[1]
                self.channel_id = -1
                self.flow_id = -1
            else:
                # Constructor: BasicEventHandlerData(int channel_id, int flow_id)
                self.channel_id = args[0]
                self.flow_id = args[1]
                self.node = None
                self.event = EventType.NONE
        elif len(args) == 0:
            # Default constructor
            self.node = None
            self.event = EventType.NONE
            self.channel_id = -1
            self.flow_id = -1
        else:
            raise ValueError(f"Invalid number of arguments: {len(args)}")
        
        # Handle keyword arguments
        if 'node' in kwargs:
            self.node = kwargs['node']
        if 'event' in kwargs:
            self.event = kwargs['event']
        if 'channel_id' in kwargs:
            self.channel_id = kwargs['channel_id']
        if 'flow_id' in kwargs:
            self.flow_id = kwargs['flow_id']
    
    def __str__(self) -> str:
        """String representation for debugging"""
        return (f"BasicEventHandlerData(node={self.node}, event={self.event}, "
                f"channel_id={self.channel_id}, flow_id={self.flow_id})")
    
    def __repr__(self) -> str:
        """Detailed string representation"""
        return self.__str__()
