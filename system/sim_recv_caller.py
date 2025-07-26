# SimRecvCaller.py - corresponds to SimRecvCaller.hh/cc in SimAI

from typing import Any, Optional, Callable as CallableType, TYPE_CHECKING
from .callable import Callable, CallData
from .common import EventType, SimRequest

if TYPE_CHECKING:
    from .sys import Sys


class SimRecvCaller(Callable):
    """Simulation receive caller - corresponds to SimRecvCaller class in SimAI
    
    This class handles simulation receive operations by calling the network interface
    and managing the message handling callback.
    """
    
    def __init__(self, generator: 'Sys', buffer: Any, count: int, type_: int,
                 src: int, tag: int, request: SimRequest, 
                 msg_handler: Optional[CallableType[[Any], None]], fun_arg: Any):
        """Initialize simulation receive caller - corresponds to SimRecvCaller constructor
        
        Args:
            generator: Reference to the Sys object (corresponds to Sys* generator)
            buffer: Data buffer to receive into (corresponds to void* buffer)
            count: Number of elements to receive (corresponds to uint64_t count)
            type_: Data type identifier (corresponds to int type)
            src: Source rank (corresponds to int src)
            tag: Message tag (corresponds to int tag)
            request: Simulation request object (corresponds to sim_request request)
            msg_handler: Message completion handler (corresponds to void (*msg_handler)(void* fun_arg))
            fun_arg: Argument for message handler (corresponds to void* fun_arg)
        """
        # Store all parameters as member variables - exact correspondence to C++
        self.generator = generator
        self.buffer = buffer
        self.count = count
        self.type = type_
        self.src = src
        self.tag = tag
        self.request = request
        self.msg_handler = msg_handler
        self.fun_arg = fun_arg
    
    def call(self, event_type: EventType, data: CallData) -> None:
        """Handle call event - corresponds to SimRecvCaller::call in SimAI
        
        This method calls the network interface sim_recv method with all stored
        parameters and then marks this object for cleanup.
        
        Args:
            event_type: Type of event (corresponds to EventType type)
            data: Call data (corresponds to CallData* data)
        """
        # Call the network interface sim_recv method - exact correspondence to C++
        self.generator.NI.sim_recv(
            self.buffer,
            self.count,
            self.type,
            self.src,
            self.tag,
            self.request,
            self.msg_handler,
            self.fun_arg
        )
        
        # In C++, the object deletes itself with "delete this"
        # In Python, we don't need explicit deletion, but we can clear references
        # to help with garbage collection
        self._cleanup()
    
    def _cleanup(self) -> None:
        """Clean up resources - corresponds to "delete this" in C++"""
        # Clear references to allow proper garbage collection
        self.generator = None
        self.buffer = None
        self.request = None
        self.msg_handler = None
        self.fun_arg = None 