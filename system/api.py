# API definitions - unified import interface
# This file serves as a unified import point for all API definitions
# Corresponds to AstraComputeAPI.hh, AstraMemoryAPI.hh, AstraNetworkAPI.hh in SimAI 

# Import all API classes and types from the three separate files
from .AstraComputeAPI import (
    ReqType,
    SimRequest,
    AstraComputeAPI
)

from .AstraMemoryAPI import (
    MemoryType,
    MemoryAccessType,
    MemoryRequest,
    AstraMemoryAPI
)

from .AstraNetworkAPI import (
    TimeType,
    BackendType,
    TimeSpec,
    NcclFlowTag,
    SimComm,
    AstraNetworkAPI
)

# Re-export all for backward compatibility
__all__ = [
    # Compute API
    'ReqType',
    'SimRequest', 
    'AstraComputeAPI',
    
    # Memory API
    'MemoryType',
    'MemoryAccessType',
    'MemoryRequest',
    'AstraMemoryAPI',
    
    # Network API
    'TimeType',
    'BackendType',
    'TimeSpec',
    'NcclFlowTag',
    'SimComm',
    'AstraNetworkAPI'
]