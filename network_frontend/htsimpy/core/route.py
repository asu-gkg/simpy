"""
Route - Routing Information

对应文件: route.h/cpp
功能: 路由信息管理，定义数据包的路由路径

主要类:
- Route: 路由路径类

C++对应关系:
- Route::push_back() -> Route.push_back()
- Route::at() -> Route.at()
- Route::size() -> Route.size()
- Route::clone() -> Route.clone()
- Route::push_at() -> Route.push_at()
- Route::push_front() -> Route.push_front()
- Route::add_endpoints() -> Route.add_endpoints()
- Route::set_path_id() -> Route.set_path_id()
- Route::path_id() -> Route.path_id()
- Route::no_of_paths() -> Route.no_of_paths()
- Route::hop_count() -> Route.hop_count()
- Route::reverse() -> Route.reverse()
- Route::set_reverse() -> Route.set_reverse()
"""

from typing import List, Optional, Iterator
from .network import PacketSink


class Route:
    """
    路由路径类 - 对应 route.h/cpp 中的 Route 类
    
    表示数据包从源到目的地的完整路径
    """
    
    def __init__(self, size: Optional[int] = None, orig_route: Optional['Route'] = None, dst: Optional[PacketSink] = None):
        """
        对应 C++ 中的三个构造函数:
        1. Route() - 默认构造
        2. Route(int size) - 带预分配大小的构造
        3. Route(const Route& orig, PacketSink& dst) - 拷贝构造加目标
        """
        self._sinklist: List[PacketSink] = []
        self._hop_count: int = 0
        self._reverse: Optional['Route'] = None
        self._path_id: int = 0
        self._no_of_paths: int = 0
        
        if orig_route is not None and dst is not None:
            # 拷贝构造函数实现
            self._path_id = orig_route.path_id()
            self._reverse = orig_route._reverse
            self._hop_count = orig_route.hop_count()
            self._no_of_paths = orig_route.no_of_paths()
            
            # 复制原路由的所有节点
            for i in range(orig_route.size()):
                self._sinklist.append(orig_route.at(i))
            
            # 添加目标节点
            self._sinklist.append(dst)
            self._hop_count += 1
        elif size is not None:
            # 预分配空间（Python 中通过预分配列表实现）
            pass  # Python 列表会自动管理内存
    
    def at(self, n: int) -> PacketSink:
        """
        对应 C++ 中的 PacketSink* at(size_t n) const
        获取指定索引的节点
        """
        if 0 <= n < len(self._sinklist):
            return self._sinklist[n]
        raise IndexError(f"Route index {n} out of range")
    
    def push_back(self, sink: PacketSink) -> None:
        """
        对应 C++ 中的 void push_back(PacketSink* sink)
        向路由路径末尾添加一个节点
        """
        assert sink is not None, "PacketSink cannot be None"
        self._sinklist.append(sink)
        self._update_hopcount(sink)
    
    def push_at(self, sink: PacketSink, id: int) -> None:
        """
        对应 C++ 中的 void push_at(PacketSink* sink, int id)
        在指定位置插入节点
        """
        self._sinklist.insert(id, sink)
        self._update_hopcount(sink)
    
    def push_front(self, sink: PacketSink) -> None:
        """
        对应 C++ 中的 void push_front(PacketSink* sink)
        在路由路径开头添加一个节点
        """
        self._sinklist.insert(0, sink)
        self._update_hopcount(sink)
    
    def add_endpoints(self, src: PacketSink, dst: PacketSink) -> None:
        """
        对应 C++ 中的 void add_endpoints(PacketSink *src, PacketSink* dst)
        添加端点
        """
        if self._reverse:
            self._reverse.push_back(src)
    
    def size(self) -> int:
        """
        对应 C++ 中的 size_t size() const
        返回路由路径的大小
        """
        return len(self._sinklist)
    
    def clone(self) -> 'Route':
        """
        对应 C++ 中的 Route* clone() const
        创建路由的深拷贝
        """
        copy = Route(self._hop_count)
        copy.set_path_id(self._path_id, self._no_of_paths)
        copy._reverse = self._reverse  # 浅拷贝反向路由
        
        # 复制所有节点
        copy._sinklist = self._sinklist.copy()
        copy._hop_count = self._hop_count
        
        return copy
    
    def set_reverse(self, reverse: 'Route') -> None:
        """
        对应 C++ 中的 void set_reverse(Route* reverse)
        设置反向路由
        """
        self._reverse = reverse
    
    def reverse(self) -> Optional['Route']:
        """
        对应 C++ 中的 const Route* reverse() const
        获取反向路由
        """
        return self._reverse
    
    def set_path_id(self, path_id: int, no_of_paths: int) -> None:
        """
        对应 C++ 中的 void set_path_id(int path_id, int no_of_paths)
        设置路径ID和总路径数
        """
        self._path_id = path_id
        self._no_of_paths = no_of_paths
    
    def path_id(self) -> int:
        """
        对应 C++ 中的 int path_id() const
        获取路径ID
        """
        return self._path_id
    
    def no_of_paths(self) -> int:
        """
        对应 C++ 中的 int no_of_paths() const
        获取总路径数
        """
        return self._no_of_paths
    
    def hop_count(self) -> int:
        """
        对应 C++ 中的 uint32_t hop_count() const
        获取跳数
        """
        return self._hop_count
    
    def _update_hopcount(self, sink: PacketSink) -> None:
        """
        对应 C++ 中的 void update_hopcount(PacketSink* sink)
        更新跳数（如果sink是Pipe类型）
        """
        # 检查是否是 Pipe 类型来更新跳数
        # 对应 C++ 中的 dynamic_cast<Pipe*>(sink) != NULL
        from .pipe import Pipe
        if isinstance(sink, Pipe):
            self._hop_count += 1
    
    # 迭代器支持 - 对应 C++ 中的 const_iterator
    def __iter__(self) -> Iterator[PacketSink]:
        """支持迭代"""
        return iter(self._sinklist)
    
    def begin(self) -> Iterator[PacketSink]:
        """对应 C++ 中的 const_iterator begin() const"""
        return iter(self._sinklist)
    
    def end(self) -> Iterator[PacketSink]:
        """对应 C++ 中的 const_iterator end() const"""
        # Python 中没有直接的 end() 概念，这里返回一个空迭代器
        return iter([])
    
    # 兼容性方法（保持与旧版本的兼容）
    def append(self, sink: PacketSink) -> None:
        """别名方法，调用 push_back"""
        self.push_back(sink)
    
    def get(self, index: int) -> PacketSink:
        """别名方法，调用 at"""
        return self.at(index)
    
    def __getitem__(self, index: int) -> PacketSink:
        """支持索引访问"""
        return self.at(index)
    
    def __len__(self) -> int:
        """支持 len() 函数"""
        return self.size()
    
    def clear(self) -> None:
        """清空路由路径"""
        self._sinklist.clear()
        self._hop_count = 0
    
    def is_empty(self) -> bool:
        """检查路由是否为空"""
        return len(self._sinklist) == 0
    
    def front(self) -> Optional[PacketSink]:
        """获取路径的第一个节点"""
        return self._sinklist[0] if self._sinklist else None
    
    def back(self) -> Optional[PacketSink]:
        """获取路径的最后一个节点"""
        return self._sinklist[-1] if self._sinklist else None
    
    def __str__(self) -> str:
        """字符串表示"""
        if not self._sinklist:
            return "Route(empty)"
        
        path_str = " -> ".join([str(sink) for sink in self._sinklist])
        return f"Route({path_str})"
    
    def __repr__(self) -> str:
        """详细字符串表示"""
        return f"Route(path={self._sinklist}, hops={self._hop_count}, path_id={self._path_id}, reverse={self._reverse is not None})"


# 类型别名 - 对应 C++ 中的 typedef
route_t = Route
routes_t = List[route_t]


def check_non_null(rt: Route) -> None:
    """
    对应 C++ 中的 void check_non_null(Route* rt) 函数
    检查路由中是否有空节点
    """
    fail = False
    for i in range(1, rt.size() - 1):
        if rt.at(i) is None:
            fail = True
            break
    
    if fail:
        print("Null sink in route")
        for i in range(1, rt.size() - 1):
            print(f"{rt.at(i)} ", end="")
        print()
        assert False, "Route contains null sinks"


def print_route(route: Route) -> None:
    """
    打印路由信息的辅助函数
    """
    print(f"Route with {len(route)} hops:")
    for i, sink in enumerate(route._sinklist):
        print(f"  {i}: {sink}")
    if route.reverse():
        print("  Has reverse route")