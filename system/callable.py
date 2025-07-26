# Callable.py - corresponds to Callable.hh and CallData.hh in SimAI
# This file contains the base Callable interface and CallData class for event handling

from abc import ABC, abstractmethod
from typing import Any, Optional
from .common import EventType

class CallData:
    """Base class for call data - corresponds to CallData.hh in SimAI"""
    
    def __init__(self):
        """Initialize call data"""
        pass
    
    def __del__(self):
        """Destructor"""
        pass

class Callable(ABC):
    """Base interface for callable objects - corresponds to Callable.hh in SimAI"""
    
    def __init__(self):
        """Initialize callable object"""
        pass
    
    def __del__(self):
        """Destructor"""
        pass
    
    @abstractmethod
    def call(self, event_type: EventType, data: CallData) -> None:
        """
        Handle an event - to be implemented by subclasses
        
        Args:
            event_type: Type of event to handle
            data: Associated data for the event
        """
        pass