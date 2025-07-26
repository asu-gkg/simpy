# Queue levels management - corresponds to QueueLevels.hh/cc in SimAI

from typing import List, Dict, Any, Optional, Tuple
from enum import Enum
from .common import Tick


class Direction(Enum):
    """Ring topology direction - corresponds to RingTopology::Direction"""
    Clockwise = "Clockwise"
    Anticlockwise = "Anticlockwise"


class BackendType(Enum):
    """Network backend type - corresponds to AstraNetworkAPI::BackendType"""
    NotSpecified = "NotSpecified"
    Garnet = "Garnet"
    NS3 = "NS3"
    Analytical = "Analytical"


class QueueLevelHandler:
    """Handler for a single queue level - corresponds to QueueLevelHandler.hh/cc"""
    
    def __init__(self, level: int, start: int, end: int, backend: BackendType):
        """Initialize queue level handler
        
        Args:
            level: Level identifier
            start: Start queue ID (inclusive)
            end: End queue ID (inclusive)
            backend: Backend type
        """
        self.queues: List[int] = []
        for i in range(start, end + 1):
            self.queues.append(i)  # queues means that it has [start, end] queues
        
        self.allocator = 0
        self.first_allocator = 0
        self.last_allocator = len(self.queues) // 2
        self.level = level
        self.backend = backend
    
    def get_next_queue_id(self) -> Tuple[int, Direction]:
        """Get next queue ID with direction
        
        Returns:
            Tuple of (queue_id, direction)
        """
        if (self.backend != BackendType.Garnet or self.level > 0) and \
           len(self.queues) > 1 and self.allocator >= (len(self.queues) // 2):
            direction = Direction.Anticlockwise
        else:
            direction = Direction.Clockwise
        
        if len(self.queues) == 0:
            return (-1, direction)
        
        tmp = self.queues[self.allocator]
        self.allocator += 1
        if self.allocator == len(self.queues):
            self.allocator = 0
        
        return (tmp, direction)
    
    def get_next_queue_id_first(self) -> Tuple[int, Direction]:
        """Get next queue ID from first half
        
        Returns:
            Tuple of (queue_id, direction)
        """
        direction = Direction.Clockwise
        
        if len(self.queues) == 0:
            return (-1, direction)
        
        tmp = self.queues[self.first_allocator]
        self.first_allocator += 1
        if self.first_allocator == len(self.queues) // 2:
            self.first_allocator = 0
        
        return (tmp, direction)
    
    def get_next_queue_id_last(self) -> Tuple[int, Direction]:
        """Get next queue ID from last half
        
        Returns:
            Tuple of (queue_id, direction)
        """
        direction = Direction.Anticlockwise
        
        if len(self.queues) == 0:
            return (-1, direction)
        
        tmp = self.queues[self.last_allocator]
        self.last_allocator += 1
        if self.last_allocator == len(self.queues):
            self.last_allocator = len(self.queues) // 2
        
        return (tmp, direction)


class QueueLevels:
    """Manages queue levels and handlers - corresponds to QueueLevels.hh/cc"""
    
    def __init__(self, levels_or_vector, queues_per_level_or_offset=None, offset_or_backend=None, backend=None):
        """Initialize queue levels
        
        Args:
            For constructor 1 (levels, queues_per_level, offset, backend):
                levels_or_vector (int): Number of levels
                queues_per_level_or_offset (int): Queues per level
                offset_or_backend (int): Starting offset
                backend (BackendType): Backend type
            
            For constructor 2 (vector<int>, offset, backend):
                levels_or_vector (List[int]): Number of queues for each level
                queues_per_level_or_offset (int): Starting offset
                offset_or_backend (BackendType): Backend type
                backend (None): Not used in this case
        """
        self.levels: List[QueueLevelHandler] = []
        
        if isinstance(levels_or_vector, int):
            # Constructor 1: QueueLevels(int levels, int queues_per_level, int offset, BackendType backend)
            total_levels = levels_or_vector
            queues_per_level = queues_per_level_or_offset
            offset = offset_or_backend
            backend_type = backend
            
            start = offset
            for i in range(total_levels):
                tmp = QueueLevelHandler(i, start, start + queues_per_level - 1, backend_type)
                self.levels.append(tmp)
                start += queues_per_level
        
        elif isinstance(levels_or_vector, list):
            # Constructor 2: QueueLevels(vector<int> lv, int offset, BackendType backend)
            lv = levels_or_vector
            offset = queues_per_level_or_offset
            backend_type = offset_or_backend
            
            start = offset
            l = 0
            for i in lv:
                tmp = QueueLevelHandler(l, start, start + i - 1, backend_type)
                self.levels.append(tmp)
                l += 1
                start += i
    
    def get_next_queue_at_level(self, level: int) -> Tuple[int, Direction]:
        """Get next queue at specific level
        
        Args:
            level: Level to get queue from
            
        Returns:
            Tuple of (queue_id, direction)
        """
        return self.levels[level].get_next_queue_id()
    
    def get_next_queue_at_level_first(self, level: int) -> Tuple[int, Direction]:
        """Get next queue from first half at specific level
        
        Args:
            level: Level to get queue from
            
        Returns:
            Tuple of (queue_id, direction)
        """
        return self.levels[level].get_next_queue_id_first()
    
    def get_next_queue_at_level_last(self, level: int) -> Tuple[int, Direction]:
        """Get next queue from last half at specific level
        
        Args:
            level: Level to get queue from
            
        Returns:
            Tuple of (queue_id, direction)
        """
        return self.levels[level].get_next_queue_id_last() 