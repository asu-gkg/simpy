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
            # 对应 C++: Route(const Route& orig, PacketSink& dst) : _sinklist(orig.size()+1)
            # 预分配空间并逐个赋值，精确对应C++实现
            self._path_id = orig_route.path_id()
            self._reverse = orig_route._reverse
            self._hop_count = orig_route.hop_count()  # 先设置为原始值
            self._no_of_paths = orig_route.no_of_paths()
            
            # C++中的实现方式：预分配空间后逐个赋值
            self._sinklist = [None] * (orig_route.size() + 1)
            for i in range(orig_route.size()):
                self._sinklist[i] = orig_route.at(i)
            self._sinklist[orig_route.size()] = dst
            # 对应 C++: _hop_count++; (直接增加，不调用update_hopcount)
            self._hop_count += 1
        elif size is not None:
            # 对应 C++: Route(int size) : _hop_count(0), _reverse(NULL) { _sinklist.reserve(size); }
            # Python中预分配空间的等价实现
            self._sinklist = []  # Python列表会自动管理内存
        # else: 默认构造函数，所有成员变量已在上面初始化
    
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
        # 对应 C++ 中被注释掉的代码: //_sinklist.push_back(dst);
        # self._sinklist.append(dst)  # 这行在C++中被注释掉了
        
        # 对应 C++: if (_reverse) { _reverse->push_back(src); }
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
        # 对应 C++: Route *copy = new Route(_hop_count);
        # 注意：这里C++传的是_hop_count作为size参数，不是作为hop_count值
        copy = Route(self._hop_count)
        copy.set_path_id(self._path_id, self._no_of_paths)
        
        # 对应 C++: copy->_reverse = _reverse; (浅拷贝反向路由)
        # 注释说明不克隆反向路径: /* don't clone the reverse path */
        copy._reverse = self._reverse
        
        # 对应 C++: copy->_sinklist.resize(_sinklist.size());
        # 然后逐个赋值: copy->_sinklist[i] = _sinklist[i];
        copy._sinklist = [None] * len(self._sinklist)
        for i in range(len(self._sinklist)):
            copy._sinklist[i] = self._sinklist[i]
        
        # C++中没有显式设置_hop_count，是通过直接赋值保持的
        # 但在Python中我们需要显式设置
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
# C++: typedef Route route_t;
route_t = Route
# C++: typedef vector<route_t*> routes_t; (Route对象指针的vector)
# Python: List[route_t] (Route对象的List，Python中对象本身就是引用)
routes_t = List[route_t]


def check_non_null(rt: Route) -> None:
    """
    对应 C++ 中的 void check_non_null(Route* rt) 函数
    检查路由中是否有空节点
    """
    # 对应 C++: int fail = 0;
    fail = 0
    
    # 对应 C++: for (size_t i=1;i<rt->size()-1;i++)
    #           if (rt->at(i)==NULL){ fail = 1; break; }
    for i in range(1, rt.size() - 1):
        if rt.at(i) is None:
            fail = 1
            break
    
    if fail:
        # 对应 C++被注释掉的: //cout <<"Null queue in route"<<endl;
        # print("Null queue in route")
        
        # 对应 C++: for (size_t i=1;i<rt->size()-1;i++) printf("%p ",rt->at(i));
        for i in range(1, rt.size() - 1):
            print(f"{id(rt.at(i)):p} ", end="")  # 使用id()模拟指针地址
        
        # 对应 C++: cout<<endl; assert(0);
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