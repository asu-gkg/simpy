"""
RouteTable - Routing Table Implementation

对应文件: routetable.h/cpp
功能: 路由表实现，管理网络中的路由信息

主要类:
- RouteTable: 路由表类

C++对应关系:
- RouteTable::addRoute() -> RouteTable.add_route()
- RouteTable::lookup() -> RouteTable.lookup()
- RouteTable::removeRoute() -> RouteTable.remove_route()
"""

from typing import Dict, Optional, List
from .route import Route


class RouteTable:
    """
    路由表类 - 对应 routetable.h/cpp 中的 RouteTable 类
    
    管理网络中的路由信息，提供路由查找和添加功能
    """
    
    def __init__(self):
        # 对应 C++ 中的路由表数据结构
        self._routes: Dict[int, Route] = {}  # 目标ID到路由的映射
        self._next_route_id = 0
    
    def add_route(self, destination: int, route: Route) -> int:
        """
        对应 C++ 中的 RouteTable::addRoute()
        添加路由到路由表
        
        Args:
            destination: 目标节点ID
            route: 路由路径
            
        Returns:
            路由ID
        """
        route_id = self._next_route_id
        self._next_route_id += 1
        
        # 存储路由信息
        self._routes[destination] = route
        
        return route_id
    
    def lookup(self, destination: int) -> Optional[Route]:
        """
        对应 C++ 中的 RouteTable::lookup()
        查找到指定目标的路由
        
        Args:
            destination: 目标节点ID
            
        Returns:
            找到的路由，如果不存在返回None
        """
        return self._routes.get(destination)
    
    def remove_route(self, destination: int) -> bool:
        """
        对应 C++ 中的 RouteTable::removeRoute()
        移除指定目标的路由
        
        Args:
            destination: 目标节点ID
            
        Returns:
            如果成功移除返回True，否则返回False
        """
        if destination in self._routes:
            del self._routes[destination]
            return True
        return False
    
    def has_route(self, destination: int) -> bool:
        """
        对应 C++ 中的 RouteTable::hasRoute()
        检查是否存在到指定目标的路由
        
        Args:
            destination: 目标节点ID
            
        Returns:
            如果存在路由返回True，否则返回False
        """
        return destination in self._routes
    
    def get_all_destinations(self) -> List[int]:
        """
        获取所有目标节点ID列表
        
        Returns:
            所有目标节点ID的列表
        """
        return list(self._routes.keys())
    
    def get_all_routes(self) -> Dict[int, Route]:
        """
        获取所有路由
        
        Returns:
            目标ID到路由的映射字典
        """
        return self._routes.copy()
    
    def clear(self) -> None:
        """
        清空路由表
        """
        self._routes.clear()
        self._next_route_id = 0
    
    def size(self) -> int:
        """
        获取路由表中的路由数量
        
        Returns:
            路由数量
        """
        return len(self._routes)
    
    def __str__(self) -> str:
        """字符串表示"""
        return f"RouteTable({len(self._routes)} routes)"
    
    def __repr__(self) -> str:
        """详细字符串表示"""
        return f"RouteTable(routes={self._routes}, next_id={self._next_route_id})"