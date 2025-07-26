# Offline greedy scheduler - corresponds to scheduling/OfflineGreedy.hh/cc in SimAI

from typing import List, Dict, Tuple, Optional, Any
from ..common import Tick, SchedulingPolicy
from ..callable import Callable


class StreamInfo:
    """Information about a stream for scheduling"""
    def __init__(self, stream_id: int, arrival_time: Tick, size: int, 
                 priority: int = 0, dependencies: List[int] = None):
        self.stream_id = stream_id
        self.arrival_time = arrival_time
        self.size = size
        self.priority = priority
        self.dependencies = dependencies or []
        self.scheduled_time: Optional[Tick] = None
        self.completion_time: Optional[Tick] = None
        self.resource_allocation: Dict[str, Any] = {}


class ResourceInfo:
    """Information about available resources"""
    def __init__(self, resource_id: str, capacity: float, availability_time: Tick = 0):
        self.resource_id = resource_id
        self.capacity = capacity
        self.availability_time = availability_time
        self.current_utilization = 0.0
        self.scheduled_tasks: List[Tuple[Tick, Tick, int]] = []  # (start, end, stream_id)


class OfflineGreedy:
    """Offline greedy scheduling algorithm
    
    Corresponds to scheduling/OfflineGreedy.hh/cc in SimAI
    """
    
    def __init__(self, num_resources: int = 1):
        """Initialize offline greedy scheduler
        
        Args:
            num_resources: Number of available resources
        """
        self.num_resources = num_resources
        self.resources: Dict[str, ResourceInfo] = {}
        self.streams: Dict[int, StreamInfo] = {}
        self.scheduling_queue: List[StreamInfo] = []
        self.completed_streams: List[StreamInfo] = []
        
        # Scheduling parameters
        self.time_horizon = 1000  # Maximum time to consider
        self.scheduling_policy = SchedulingPolicy.FIFO
        self.allow_preemption = False
        
        # Statistics
        self.total_scheduling_time = 0
        self.average_completion_time = 0.0
        self.resource_utilization: Dict[str, float] = {}
        
        # Initialize default resources
        for i in range(num_resources):
            resource_id = f"resource_{i}"
            self.resources[resource_id] = ResourceInfo(resource_id, 1.0)
    
    def add_resource(self, resource_id: str, capacity: float, 
                    availability_time: Tick = 0) -> None:
        """Add a resource to the scheduler
        
        Args:
            resource_id: Unique identifier for the resource
            capacity: Processing capacity of the resource
            availability_time: Time when resource becomes available
        """
        self.resources[resource_id] = ResourceInfo(resource_id, capacity, availability_time)
    
    def add_stream(self, stream_id: int, arrival_time: Tick, size: int,
                  priority: int = 0, dependencies: List[int] = None) -> None:
        """Add a stream to be scheduled
        
        Args:
            stream_id: Unique identifier for the stream
            arrival_time: Time when stream arrives
            size: Size/duration of the stream
            priority: Priority of the stream (higher is more important)
            dependencies: List of stream IDs that must complete first
        """
        stream_info = StreamInfo(stream_id, arrival_time, size, priority, dependencies)
        self.streams[stream_id] = stream_info
        self.scheduling_queue.append(stream_info)
    
    def schedule_all_streams(self) -> Dict[int, Tuple[Tick, str]]:
        """Schedule all streams using offline greedy algorithm
        
        Returns:
            Dictionary mapping stream_id to (scheduled_time, resource_id)
        """
        # Sort streams by arrival time and priority
        self._sort_scheduling_queue()
        
        schedule = {}
        
        for stream in self.scheduling_queue:
            # Check if dependencies are satisfied
            if not self._dependencies_satisfied(stream):
                continue
            
            # Find best resource for this stream
            best_resource, start_time = self._find_best_resource(stream)
            
            if best_resource:
                # Schedule the stream
                stream.scheduled_time = start_time
                stream.completion_time = start_time + stream.size
                stream.resource_allocation['resource_id'] = best_resource.resource_id
                
                # Update resource availability
                best_resource.scheduled_tasks.append(
                    (start_time, stream.completion_time, stream.stream_id)
                )
                best_resource.availability_time = max(
                    best_resource.availability_time, 
                    stream.completion_time
                )
                
                schedule[stream.stream_id] = (start_time, best_resource.resource_id)
                self.completed_streams.append(stream)
        
        # Calculate statistics
        self._calculate_statistics()
        
        return schedule
    
    def _sort_scheduling_queue(self) -> None:
        """Sort the scheduling queue based on scheduling policy"""
        if self.scheduling_policy == SchedulingPolicy.FIFO:
            self.scheduling_queue.sort(key=lambda s: s.arrival_time)
        elif self.scheduling_policy == SchedulingPolicy.SJF:
            self.scheduling_queue.sort(key=lambda s: (s.arrival_time, s.size))
        elif self.scheduling_policy == SchedulingPolicy.LJF:
            self.scheduling_queue.sort(key=lambda s: (s.arrival_time, -s.size))
        else:  # Priority-based
            self.scheduling_queue.sort(
                key=lambda s: (s.arrival_time, -s.priority, s.size)
            )
    
    def _dependencies_satisfied(self, stream: StreamInfo) -> bool:
        """Check if all dependencies for a stream are satisfied
        
        Args:
            stream: Stream to check dependencies for
            
        Returns:
            True if all dependencies are completed
        """
        for dep_id in stream.dependencies:
            if dep_id in self.streams:
                dep_stream = self.streams[dep_id]
                if dep_stream.completion_time is None:
                    return False
        return True
    
    def _find_best_resource(self, stream: StreamInfo) -> Tuple[Optional[ResourceInfo], Tick]:
        """Find the best resource for scheduling a stream
        
        Args:
            stream: Stream to schedule
            
        Returns:
            Tuple of (best_resource, earliest_start_time)
        """
        best_resource = None
        earliest_start_time = float('inf')
        
        for resource in self.resources.values():
            # Find earliest time this resource can start the stream
            start_time = max(stream.arrival_time, resource.availability_time)
            
            # Check for dependency constraints
            for dep_id in stream.dependencies:
                if dep_id in self.streams:
                    dep_stream = self.streams[dep_id]
                    if dep_stream.completion_time:
                        start_time = max(start_time, dep_stream.completion_time)
            
            # Find a gap in the resource's schedule
            actual_start_time = self._find_schedule_gap(resource, start_time, stream.size)
            
            if actual_start_time < earliest_start_time:
                earliest_start_time = actual_start_time
                best_resource = resource
        
        return best_resource, earliest_start_time
    
    def _find_schedule_gap(self, resource: ResourceInfo, earliest_start: Tick, 
                          duration: int) -> Tick:
        """Find a gap in the resource schedule for the given duration
        
        Args:
            resource: Resource to check
            earliest_start: Earliest possible start time
            duration: Required duration
            
        Returns:
            Start time for the gap
        """
        # Sort scheduled tasks by start time
        tasks = sorted(resource.scheduled_tasks, key=lambda x: x[0])
        
        # Check if we can start at earliest_start
        current_time = earliest_start
        
        for start, end, _ in tasks:
            # Check if there's a gap before this task
            if current_time + duration <= start:
                return current_time
            
            # Move to after this task
            current_time = max(current_time, end)
        
        # No conflicts, can start at current_time
        return current_time
    
    def _calculate_statistics(self) -> None:
        """Calculate scheduling statistics"""
        if not self.completed_streams:
            return
        
        # Calculate average completion time
        total_completion_time = sum(
            stream.completion_time - stream.arrival_time 
            for stream in self.completed_streams 
            if stream.completion_time
        )
        self.average_completion_time = total_completion_time / len(self.completed_streams)
        
        # Calculate resource utilization
        max_time = max(
            stream.completion_time for stream in self.completed_streams 
            if stream.completion_time
        ) if self.completed_streams else 0
        
        for resource_id, resource in self.resources.items():
            total_busy_time = sum(
                end - start for start, end, _ in resource.scheduled_tasks
            )
            utilization = total_busy_time / max_time if max_time > 0 else 0
            self.resource_utilization[resource_id] = utilization
    
    def get_schedule_info(self) -> Dict[str, Any]:
        """Get scheduling information and statistics
        
        Returns:
            Dictionary containing scheduling statistics
        """
        return {
            'num_streams': len(self.streams),
            'num_completed': len(self.completed_streams),
            'average_completion_time': self.average_completion_time,
            'resource_utilization': self.resource_utilization.copy(),
            'scheduling_policy': self.scheduling_policy.name if hasattr(self.scheduling_policy, 'name') else str(self.scheduling_policy)
        }
    
    def reset(self) -> None:
        """Reset the scheduler state"""
        self.streams.clear()
        self.scheduling_queue.clear()
        self.completed_streams.clear()
        
        # Reset resource states
        for resource in self.resources.values():
            resource.availability_time = 0
            resource.current_utilization = 0.0
            resource.scheduled_tasks.clear()
        
        # Reset statistics
        self.total_scheduling_time = 0
        self.average_completion_time = 0.0
        self.resource_utilization.clear() 