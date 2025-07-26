# Simple memory model - corresponds to memory/SimpleMemory.hh/cc in SimAI

from typing import Dict, List, Optional, Any
from ..common import Tick


class MemoryRequest:
    """Memory request structure"""
    
    def __init__(self, request_id: int, address: int, size: int, 
                 is_read: bool = True, priority: int = 0):
        """Initialize memory request
        
        Args:
            request_id: Unique request identifier
            address: Memory address
            size: Size of the request in bytes
            is_read: True for read, False for write
            priority: Request priority
        """
        self.request_id = request_id
        self.address = address
        self.size = size
        self.is_read = is_read
        self.priority = priority
        self.arrival_time: Tick = 0
        self.start_time: Optional[Tick] = None
        self.completion_time: Optional[Tick] = None
        self.data: Optional[Any] = None


class MemoryBank:
    """Memory bank representation"""
    
    def __init__(self, bank_id: int, capacity: int, bandwidth: float):
        """Initialize memory bank
        
        Args:
            bank_id: Bank identifier
            capacity: Capacity in bytes
            bandwidth: Bandwidth in bytes per tick
        """
        self.bank_id = bank_id
        self.capacity = capacity
        self.bandwidth = bandwidth
        self.current_utilization = 0.0
        self.pending_requests: List[MemoryRequest] = []
        self.active_request: Optional[MemoryRequest] = None
        self.total_accesses = 0
        self.total_bytes_transferred = 0


class SimpleMemory:
    """Simple memory model implementation
    
    Corresponds to memory/SimpleMemory.hh/cc in SimAI
    """
    
    def __init__(self, total_capacity: int = 1024*1024*1024, 
                 num_banks: int = 4, bandwidth_per_bank: float = 1000.0):
        """Initialize simple memory model
        
        Args:
            total_capacity: Total memory capacity in bytes
            num_banks: Number of memory banks
            bandwidth_per_bank: Bandwidth per bank in bytes per tick
        """
        self.total_capacity = total_capacity
        self.num_banks = num_banks
        self.bandwidth_per_bank = bandwidth_per_bank
        
        # Memory banks
        self.banks: List[MemoryBank] = []
        bank_capacity = total_capacity // num_banks
        for i in range(num_banks):
            self.banks.append(MemoryBank(i, bank_capacity, bandwidth_per_bank))
        
        # Memory management
        self.memory_map: Dict[int, int] = {}  # address -> bank_id
        self.next_request_id = 0
        self.current_time: Tick = 0
        
        # Performance parameters
        self.latency_per_access = 10  # Base latency in ticks
        self.row_buffer_hit_latency = 5  # Latency for row buffer hits
        self.row_buffer_miss_latency = 15  # Latency for row buffer misses
        
        # Statistics
        self.total_requests = 0
        self.total_read_requests = 0
        self.total_write_requests = 0
        self.total_bytes_read = 0
        self.total_bytes_written = 0
        self.average_latency: float = 0.0
        
        # Queue management
        self.request_queue: List[MemoryRequest] = []
        self.completed_requests: List[MemoryRequest] = []
    
    def read(self, address: int, size: int, priority: int = 0) -> int:
        """Initiate a memory read operation
        
        Args:
            address: Memory address to read from
            size: Number of bytes to read
            priority: Request priority
            
        Returns:
            Request ID for tracking
        """
        request_id = self._generate_request_id()
        request = MemoryRequest(request_id, address, size, True, priority)
        request.arrival_time = self.current_time
        
        self._schedule_request(request)
        self.total_requests += 1
        self.total_read_requests += 1
        
        return request_id
    
    def write(self, address: int, size: int, data: Any = None, priority: int = 0) -> int:
        """Initiate a memory write operation
        
        Args:
            address: Memory address to write to
            size: Number of bytes to write
            data: Data to write (optional)
            priority: Request priority
            
        Returns:
            Request ID for tracking
        """
        request_id = self._generate_request_id()
        request = MemoryRequest(request_id, address, size, False, priority)
        request.arrival_time = self.current_time
        request.data = data
        
        self._schedule_request(request)
        self.total_requests += 1
        self.total_write_requests += 1
        
        return request_id
    
    def _generate_request_id(self) -> int:
        """Generate a unique request ID
        
        Returns:
            Unique request ID
        """
        self.next_request_id += 1
        return self.next_request_id
    
    def _schedule_request(self, request: MemoryRequest) -> None:
        """Schedule a memory request
        
        Args:
            request: Memory request to schedule
        """
        # Determine which bank to use based on address
        bank_id = self._get_bank_for_address(request.address)
        bank = self.banks[bank_id]
        
        # Add to bank's pending requests
        bank.pending_requests.append(request)
        
        # Sort by priority and arrival time
        bank.pending_requests.sort(
            key=lambda r: (-r.priority, r.arrival_time)
        )
        
        # Process requests if bank is idle
        self._process_bank_requests(bank)
    
    def _get_bank_for_address(self, address: int) -> int:
        """Get the bank ID for a memory address
        
        Args:
            address: Memory address
            
        Returns:
            Bank ID
        """
        # Simple interleaving: use address modulo number of banks
        return address % self.num_banks
    
    def _process_bank_requests(self, bank: MemoryBank) -> None:
        """Process pending requests for a bank
        
        Args:
            bank: Memory bank to process
        """
        # If bank is busy, return
        if bank.active_request is not None:
            return
        
        # If no pending requests, return
        if not bank.pending_requests:
            return
        
        # Get next request
        request = bank.pending_requests.pop(0)
        bank.active_request = request
        
        # Calculate completion time
        request.start_time = self.current_time
        access_latency = self._calculate_access_latency(request, bank)
        transfer_time = self._calculate_transfer_time(request.size, bank.bandwidth)
        
        request.completion_time = request.start_time + access_latency + transfer_time
        
        # Schedule completion
        self._schedule_completion(request, bank)
    
    def _calculate_access_latency(self, request: MemoryRequest, bank: MemoryBank) -> Tick:
        """Calculate access latency for a request
        
        Args:
            request: Memory request
            bank: Memory bank
            
        Returns:
            Access latency in ticks
        """
        # Simple model: base latency + row buffer effects
        base_latency = self.latency_per_access
        
        # For simplicity, assume 50% row buffer hit rate
        if (request.address // 1024) % 2 == 0:  # Simple heuristic
            return base_latency + self.row_buffer_hit_latency
        else:
            return base_latency + self.row_buffer_miss_latency
    
    def _calculate_transfer_time(self, size: int, bandwidth: float) -> Tick:
        """Calculate data transfer time
        
        Args:
            size: Transfer size in bytes
            bandwidth: Available bandwidth in bytes per tick
            
        Returns:
            Transfer time in ticks
        """
        return int(size / bandwidth) if bandwidth > 0 else 0
    
    def _schedule_completion(self, request: MemoryRequest, bank: MemoryBank) -> None:
        """Schedule request completion
        
        Args:
            request: Memory request
            bank: Memory bank
        """
        # In a real simulation, this would schedule an event
        # For now, we'll mark it as ready to complete
        pass
    
    def advance_time(self, new_time: Tick) -> None:
        """Advance simulation time and process completions
        
        Args:
            new_time: New simulation time
        """
        self.current_time = new_time
        
        # Check for completed requests
        for bank in self.banks:
            if (bank.active_request and 
                bank.active_request.completion_time and
                bank.active_request.completion_time <= self.current_time):
                
                # Complete the request
                self._complete_request(bank.active_request, bank)
                bank.active_request = None
                
                # Process next request
                self._process_bank_requests(bank)
    
    def _complete_request(self, request: MemoryRequest, bank: MemoryBank) -> None:
        """Complete a memory request
        
        Args:
            request: Completed request
            bank: Memory bank
        """
        # Update statistics
        bank.total_accesses += 1
        bank.total_bytes_transferred += request.size
        
        if request.is_read:
            self.total_bytes_read += request.size
        else:
            self.total_bytes_written += request.size
        
        # Calculate latency
        if request.start_time is not None:
            latency = self.current_time - request.arrival_time
            self._update_average_latency(latency)
        
        # Add to completed requests
        self.completed_requests.append(request)
    
    def _update_average_latency(self, latency: Tick) -> None:
        """Update average latency statistics
        
        Args:
            latency: New latency measurement
        """
        # Simple moving average
        if self.average_latency == 0:
            self.average_latency = float(latency)
        else:
            alpha = 0.1  # Smoothing factor
            self.average_latency = (1 - alpha) * self.average_latency + alpha * latency
    
    def is_request_complete(self, request_id: int) -> bool:
        """Check if a request is complete
        
        Args:
            request_id: Request ID to check
            
        Returns:
            True if request is complete
        """
        return any(req.request_id == request_id for req in self.completed_requests)
    
    def get_request_latency(self, request_id: int) -> Optional[Tick]:
        """Get latency for a completed request
        
        Args:
            request_id: Request ID
            
        Returns:
            Request latency, or None if not found or not complete
        """
        for request in self.completed_requests:
            if request.request_id == request_id and request.completion_time:
                return request.completion_time - request.arrival_time
        return None
    
    def get_memory_utilization(self) -> float:
        """Get overall memory utilization
        
        Returns:
            Memory utilization as a percentage
        """
        if self.current_time == 0:
            return 0.0
        
        total_busy_time = sum(
            bank.total_bytes_transferred / bank.bandwidth 
            for bank in self.banks
        )
        total_available_time = self.current_time * len(self.banks)
        
        return (total_busy_time / total_available_time) * 100.0 if total_available_time > 0 else 0.0
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get memory system statistics
        
        Returns:
            Dictionary containing memory statistics
        """
        return {
            'total_capacity': self.total_capacity,
            'num_banks': self.num_banks,
            'total_requests': self.total_requests,
            'total_read_requests': self.total_read_requests,
            'total_write_requests': self.total_write_requests,
            'total_bytes_read': self.total_bytes_read,
            'total_bytes_written': self.total_bytes_written,
            'average_latency': self.average_latency,
            'memory_utilization': self.get_memory_utilization(),
            'pending_requests': sum(len(bank.pending_requests) for bank in self.banks),
            'completed_requests': len(self.completed_requests)
        }
    
    def reset(self) -> None:
        """Reset the memory system"""
        # Reset banks
        for bank in self.banks:
            bank.pending_requests.clear()
            bank.active_request = None
            bank.total_accesses = 0
            bank.total_bytes_transferred = 0
            bank.current_utilization = 0.0
        
        # Reset statistics
        self.total_requests = 0
        self.total_read_requests = 0
        self.total_write_requests = 0
        self.total_bytes_read = 0
        self.total_bytes_written = 0
        self.average_latency = 0.0
        
        # Reset queues
        self.request_queue.clear()
        self.completed_requests.clear()
        self.memory_map.clear()
        
        # Reset time
        self.current_time = 0
        self.next_request_id = 0 