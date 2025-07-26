# Queue levels management - corresponds to QueueLevels.hh/cc in SimAI

from typing import List, Dict, Any, Optional
from .common import Tick


class QueueLevels:
    """Manages queue levels and virtual networks
    
    Corresponds to QueueLevels.hh/cc in SimAI
    """
    
    def __init__(self, num_levels: int = 1):
        """Initialize queue levels
        
        Args:
            num_levels: Number of queue levels to manage
        """
        self.num_levels = num_levels
        self.levels: List[List[Any]] = [[] for _ in range(num_levels)]
        self.level_occupancy: List[int] = [0] * num_levels
        self.max_level_size: List[int] = [100] * num_levels  # Default max size
        
        # Virtual network mappings
        self.vnet_to_level: Dict[int, int] = {}
        self.level_to_vnets: Dict[int, List[int]] = {}
        
        # Statistics
        self.total_packets_processed = 0
        self.packets_per_level: List[int] = [0] * num_levels
        
    def add_to_level(self, level: int, item: Any) -> bool:
        """Add an item to a specific queue level
        
        Args:
            level: Queue level to add to
            item: Item to add to the queue
            
        Returns:
            True if successfully added, False if level is full
        """
        if level < 0 or level >= self.num_levels:
            return False
            
        if self.level_occupancy[level] >= self.max_level_size[level]:
            return False
            
        self.levels[level].append(item)
        self.level_occupancy[level] += 1
        return True
    
    def remove_from_level(self, level: int) -> Optional[Any]:
        """Remove an item from a specific queue level
        
        Args:
            level: Queue level to remove from
            
        Returns:
            The removed item, or None if level is empty
        """
        if level < 0 or level >= self.num_levels:
            return None
            
        if self.level_occupancy[level] == 0:
            return None
            
        item = self.levels[level].pop(0)
        self.level_occupancy[level] -= 1
        self.packets_per_level[level] += 1
        self.total_packets_processed += 1
        return item
    
    def get_level_occupancy(self, level: int) -> int:
        """Get the current occupancy of a queue level
        
        Args:
            level: Queue level to check
            
        Returns:
            Number of items in the specified level
        """
        if level < 0 or level >= self.num_levels:
            return 0
        return self.level_occupancy[level]
    
    def is_level_full(self, level: int) -> bool:
        """Check if a queue level is full
        
        Args:
            level: Queue level to check
            
        Returns:
            True if the level is at maximum capacity
        """
        if level < 0 or level >= self.num_levels:
            return True
        return self.level_occupancy[level] >= self.max_level_size[level]
    
    def is_level_empty(self, level: int) -> bool:
        """Check if a queue level is empty
        
        Args:
            level: Queue level to check
            
        Returns:
            True if the level has no items
        """
        if level < 0 or level >= self.num_levels:
            return True
        return self.level_occupancy[level] == 0
    
    def map_vnet_to_level(self, vnet_id: int, level: int) -> None:
        """Map a virtual network to a queue level
        
        Args:
            vnet_id: Virtual network identifier
            level: Queue level to map to
        """
        self.vnet_to_level[vnet_id] = level
        if level not in self.level_to_vnets:
            self.level_to_vnets[level] = []
        if vnet_id not in self.level_to_vnets[level]:
            self.level_to_vnets[level].append(vnet_id)
    
    def get_level_for_vnet(self, vnet_id: int) -> int:
        """Get the queue level for a virtual network
        
        Args:
            vnet_id: Virtual network identifier
            
        Returns:
            Queue level for the virtual network, or 0 if not mapped
        """
        return self.vnet_to_level.get(vnet_id, 0)
    
    def get_total_occupancy(self) -> int:
        """Get total occupancy across all levels
        
        Returns:
            Total number of items across all queue levels
        """
        return sum(self.level_occupancy)
    
    def set_level_capacity(self, level: int, capacity: int) -> None:
        """Set the maximum capacity for a queue level
        
        Args:
            level: Queue level to configure
            capacity: Maximum number of items for this level
        """
        if 0 <= level < self.num_levels:
            self.max_level_size[level] = capacity 