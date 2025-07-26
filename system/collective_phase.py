# CollectivePhase class - corresponds to CollectivePhase.cc/CollectivePhase.hh in SimAI

from typing import Optional
from .common import ComType

# Forward declarations
class Sys:
    pass

class Algorithm:
    pass

class BaseStream:
    pass

class CollectivePhase:
    """Collective phase class - corresponds to CollectivePhase.hh in SimAI"""

    def __init__(self, generator: Optional[Sys] = None, queue_id: int = 0, algorithm: Optional[Algorithm] = None):
        """Constructor - corresponds to CollectivePhase::CollectivePhase"""
        self.generator = generator
        self.queue_id = queue_id
        self.initial_data_size = 0
        self.final_data_size = 0
        self.enabled = True
        self.comm_type = ComType.None_
        self.algorithm = algorithm

        if algorithm is not None:
            self.initial_data_size = algorithm.data_size
            self.final_data_size = algorithm.final_data_size
            self.comm_type = algorithm.comType
            self.enabled = algorithm.enabled

    def init(self, stream: BaseStream) -> None:
        """Initialize phase - corresponds to CollectivePhase::init"""
        pass