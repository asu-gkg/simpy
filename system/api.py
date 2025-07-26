# API definitions - unified import interface
# This file serves as a unified import point for all API definitions
# Corresponds to AstraComputeAPI.hh, AstraMemoryAPI.hh, AstraNetworkAPI.hh, AstraSimDataAPI.hh in SimAI 

# Import all API classes and types from the separate files
from .AstraComputeAPI import (
    ComputeAPI
)

from .AstraMemoryAPI import (
    AstraMemoryAPI
)

from .AstraNetworkAPI import (
    TimeType,
    BackendType,
    TimeSpec,
    SimRequest,
    NcclFlowTag,
    SimComm,
    AstraNetworkAPI
)

from .AstraSimDataAPI import (
    LayerData,
    AstraSimDataAPI
)

# Re-export all for backward compatibility
__all__ = [
    # Compute API
    'ComputeAPI',
    
    # Memory API
    'AstraMemoryAPI',
    
    # Network API
    'TimeType',
    'BackendType',
    'TimeSpec',
    'SimRequest',
    'NcclFlowTag',
    'SimComm',
    'AstraNetworkAPI',
    
    # Data API
    'LayerData',
    'AstraSimDataAPI'
]