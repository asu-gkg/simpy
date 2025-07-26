# CollectivePhase class - corresponds to CollectivePhase.cc/CollectivePhase.hh in SimAI

from typing import Optional, TYPE_CHECKING
from .common import ComType

from .collective.algorithm import Algorithm
from .base_stream import BaseStream

if TYPE_CHECKING:
    from .sys import Sys

class CollectivePhase:
    """Collective phase class - corresponds to CollectivePhase.hh in SimAI"""

    def __init__(self, generator: Optional['Sys'] = None, queue_id: int = None, algorithm: Optional[Algorithm] = None):
        """Constructor - corresponds to CollectivePhase::CollectivePhase"""
        if generator is not None and queue_id is not None and algorithm is not None:
            # Parameterized constructor
            self.generator = generator
            self.queue_id = queue_id
            self.algorithm = algorithm
            self.enabled = True
            self.initial_data_size = algorithm.data_size
            self.final_data_size = algorithm.final_data_size
            self.comm_type = algorithm.comType
            self.enabled = algorithm.enabled
        else:
            # Default constructor - corresponds to CollectivePhase::CollectivePhase()
            self.queue_id = -1
            self.generator = None
            self.algorithm = None
            self.initial_data_size = 0
            self.final_data_size = 0
            self.enabled = True
            self.comm_type = ComType.None_

    def init(self, stream: BaseStream) -> None:
        """Initialize phase - corresponds to CollectivePhase::init"""
        if self.algorithm is not None:
            self.algorithm.init(stream)