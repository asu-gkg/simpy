"""
Route - Routing Information

对应文件: route.h/cpp
功能: 路由信息管理，定义数据包的路由路径

主要类:
- Route: 路由路径类

C++对应关系:
- Route::push_back() -> Route.append()
- Route::at() -> Route.get()
- Route::size() -> Route.size()
"""

from typing import List, Optional
from .network import PacketSink


class Route:
    """
    路由路径类 - 对应 route.h/cpp 中的 Route 类
    
    表示数据包从源到目的地的完整路径
    """
    
    def __init__(self):
        self._path: List[PacketSink] = []
        self._reverse_path: Optional['Route'] = None
    
    def append(self, sink: PacketSink) -> None:
        """
        对应 C++ 中的 Route::push_back()
        向路由路径添加一个节点
        """
        self._path.append(sink)
    
    def get(self, index: int) -> PacketSink:
        """
        对应 C++ 中的 Route::at()
        获取指定索引的节点
        """
        if 0 <= index < len(self._path):
            return self._path[index]
        raise IndexError(f"Route index {index} out of range")
    
    def __getitem__(self, index: int) -> PacketSink:
        """支持索引访问"""
        return self.get(index)
    
    def __len__(self) -> int:
        """对应 C++ 中的 Route::size()"""
        return len(self._path)
    
    @property
    def size(self) -> int:
        """对应 C++ 中的 Route::size()"""
        return len(self._path)
    
    def set_reverse(self, reverse_route: 'Route') -> None:
        """
        对应 C++ 中的 Route::set_reverse()
        设置反向路由
        """
        self._reverse_path = reverse_route
    
    @property
    def reverse(self) -> Optional['Route']:
        """
        对应 C++ 中的 Route::reverse()
        获取反向路由
        """
        return self._reverse_path
    
    def clear(self) -> None:
        """
        对应 C++ 中的 Route::clear()
        清空路由路径
        """
        self._path.clear()
    
    def is_empty(self) -> bool:
        """
        对应 C++ 中的 Route::empty()
        检查路由是否为空
        """
        return len(self._path) == 0
    
    def front(self) -> Optional[PacketSink]:
        """
        对应 C++ 中的 Route::front()
        获取路径的第一个节点
        """
        return self._path[0] if self._path else None
    
    def back(self) -> Optional[PacketSink]:
        """
        对应 C++ 中的 Route::back()
        获取路径的最后一个节点
        """
        return self._path[-1] if self._path else None
    
    def __str__(self) -> str:
        """字符串表示"""
        if not self._path:
            return "Route(empty)"
        
        path_str = " -> ".join([str(sink) for sink in self._path])
        return f"Route({path_str})"
    
    def __repr__(self) -> str:
        """详细字符串表示"""
        return f"Route(path={self._path}, reverse={self._reverse_path is not None})"


def print_route(route: Route) -> None:
    """
    对应 C++ 中的 print_route() 函数
    打印路由信息
    """
    print(f"Route with {len(route)} hops:")
    for i, sink in enumerate(route._path):
        print(f"  {i}: {sink}")
    if route.reverse:
        print("  Has reverse route")