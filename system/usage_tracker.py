# UsageTracker class - corresponds to UsageTracker.cc/UsageTracker.hh in SimAI

from typing import List, Tuple
from .common import Tick
import sys

class Usage:
    """Usage class for tracking usage periods - corresponds to Usage.hh"""
    
    def __init__(self, level: int, start: Tick, end: Tick):
        """Constructor - corresponds to Usage::Usage"""
        self.level = level
        self.start = start
        self.end = end

class CSVWriter:
    """CSV Writer placeholder"""
    pass

class UsageTracker:
    """Usage tracker class - corresponds to UsageTracker.hh in SimAI"""
    
    def __init__(self, levels: int):
        """Constructor - corresponds to UsageTracker::UsageTracker"""
        self.levels = levels
        self.current_level = 0
        self.last_tick = 0
        self.usage: List[Usage] = []
    
    def increase_usage(self) -> None:
        """Increase usage - corresponds to UsageTracker::increase_usage"""
        if self.current_level < self.levels - 1:
            # Import here to avoid circular import
            from .sys import Sys
            current_tick = Sys.boostedTick()
            u = Usage(self.current_level, self.last_tick, current_tick)
            self.usage.append(u)
            self.current_level += 1
            self.last_tick = current_tick
    
    def decrease_usage(self) -> None:
        """Decrease usage - corresponds to UsageTracker::decrease_usage"""
        if self.current_level > 0:
            # Import here to avoid circular import
            from .sys import Sys
            current_tick = Sys.boostedTick()
            u = Usage(self.current_level, self.last_tick, current_tick)
            self.usage.append(u)
            self.current_level -= 1
            self.last_tick = current_tick
    
    def set_usage(self, level: int) -> None:
        """Set usage level - corresponds to UsageTracker::set_usage"""
        if self.current_level != level:
            # Import here to avoid circular import
            from .sys import Sys
            current_tick = Sys.boostedTick()
            u = Usage(self.current_level, self.last_tick, current_tick)
            self.usage.append(u)
            self.current_level = level
            self.last_tick = current_tick
    
    def report(self, writer, offset: int) -> None:
        """Report usage - corresponds to UsageTracker::report"""
        col = offset * 3
        row = 1
        for a in self.usage:
            writer.write_cell(row, col, str(a.start))
            writer.write_cell(row, col + 1, str(a.level))
            row += 1
        return
    
    def report_percentage(self, cycles: int) -> List[Tuple[int, float]]:
        """Report percentage - corresponds to UsageTracker::report_percentage"""
        self.decrease_usage()
        self.increase_usage()
        
        total_activity_possible = (self.levels - 1) * cycles
        usage_pointer = 0
        current_activity = 0
        period_start = 0
        period_end = cycles
        result: List[Tuple[int, float]] = []
        
        while usage_pointer < len(self.usage):
            current_usage = self.usage[usage_pointer]
            begin = max(period_start, current_usage.start)
            end = min(period_end, current_usage.end)
            
            assert begin <= end
            
            current_activity += ((end - begin) * current_usage.level)
            
            if current_usage.end >= period_end:
                percentage = (float(current_activity) / total_activity_possible) * 100
                result.append((period_end, percentage))
                period_start += cycles
                period_end += cycles
                current_activity = 0
            else:
                usage_pointer += 1
        
        return result
