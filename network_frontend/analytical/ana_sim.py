# Analytical simulation class - corresponds to AnaSim.cc/AnaSim.h in SimAI 
"""
Analytical simulation class - corresponds to AnaSim.cc/AnaSim.h in SimAI

This module provides an event-driven simulation framework for analytical network simulation.
It includes task scheduling, time management, and event execution capabilities.
"""

import heapq
from typing import Callable, Any, Optional
from dataclasses import dataclass
import time


@dataclass
class CallTask:
    """
    Represents a scheduled task in the simulation.
    Corresponds to the CallTask struct in AnaSim.h
    """
    time: int
    fun_ptr: Callable[[Any], None]
    fun_arg: Any
    
    def __lt__(self, other):
        """For heapq comparison - tasks with earlier time have higher priority"""
        return self.time < other.time


class AnaSim:
    """
    Analytical simulation class - corresponds to AnaSim.cc/AnaSim.h in SimAI
    
    This class provides a discrete event simulation framework with:
    - Task scheduling with delays
    - Time management
    - Event execution
    - Simulation control (run, stop, destroy)
    """
    
    # Static variables corresponding to C++ static members
    _call_list: list = []  # Using list as priority queue with heapq
    _tick: int = 0
    _running: bool = False
    
    @classmethod
    def Now(cls) -> float:
        """
        Get current simulation time.
        Corresponds to double AnaSim::Now() in C++
        
        Returns:
            float: Current simulation time (tick)
        """
        return float(cls._tick)
    
    @classmethod
    def Run(cls) -> None:
        """
        Run the simulation until all tasks are completed.
        Corresponds to void AnaSim::Run() in C++
        
        The simulation processes all scheduled tasks in chronological order.
        """
        cls._running = True
        
        while cls._call_list and cls._running:
            # Get the next task (earliest time)
            calltask = heapq.heappop(cls._call_list)
            
            # Advance time to task execution time
            while cls._tick < calltask.time:
                cls._tick += 1
            
            # Execute the task
            try:
                calltask.fun_ptr(calltask.fun_arg)
            except Exception as e:
                print(f"Error executing task at time {cls._tick}: {e}")
        
        cls._running = False
    
    @classmethod
    def Schedule(cls, delay: int, fun_ptr: Callable[[Any], None], fun_arg: Any) -> None:
        """
        Schedule a task to be executed after a specified delay.
        Corresponds to void AnaSim::Schedule() in C++
        
        Args:
            delay: Time delay before task execution
            fun_ptr: Function to be called
            fun_arg: Argument to pass to the function
        """
        execution_time = cls._tick + delay
        calltask = CallTask(execution_time, fun_ptr, fun_arg)
        
        # Add to priority queue
        heapq.heappush(cls._call_list, calltask)
    
    @classmethod
    def Stop(cls) -> None:
        """
        Stop the simulation.
        Corresponds to void AnaSim::Stop() in C++
        """
        cls._running = False
    
    @classmethod
    def Destroy(cls) -> None:
        """
        Clean up simulation resources.
        Corresponds to void AnaSim::Destroy() in C++
        """
        cls._call_list.clear()
        cls._tick = 0
        cls._running = False
    
    @classmethod
    def get_queue_size(cls) -> int:
        """
        Get the number of pending tasks.
        
        Returns:
            int: Number of tasks in the queue
        """
        return len(cls._call_list)
    
    @classmethod
    def is_running(cls) -> bool:
        """
        Check if simulation is currently running.
        
        Returns:
            bool: True if simulation is running, False otherwise
        """
        return cls._running
    
    @classmethod
    def reset(cls) -> None:
        """
        Reset the simulation to initial state.
        """
        cls.Destroy()