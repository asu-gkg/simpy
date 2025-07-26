# Workload类 - 对应Workload.cc/Workload.hh in SimAI 
# 这个文件现在是一个简化的入口点，主要功能已经拆分到其他模块中

from .workload_base import Workload

# 为了向后兼容，直接导出Workload类
__all__ = ['Workload'] 
