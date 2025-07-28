"""
Drawable - 可绘制对象接口

对应文件: drawable.h
功能: 为拓扑中的可绘制对象提供基础类

主要类:
- Drawable: 可绘制对象基类

C++对应关系:
- Drawable::setPos() -> Drawable.set_pos()
- Drawable::_x -> Drawable._x
- Drawable::_y -> Drawable._y
"""


class Drawable:
    """
    可绘制对象基类 - 对应 drawable.h 中的 Drawable 类
    
    为拓扑中任何可绘制的对象提供基础功能
    """
    
    def __init__(self):
        """
        对应 C++ 构造函数 Drawable() : _x(0), _y(0) {}
        """
        self._x: int = 0
        self._y: int = 0
    
    def set_pos(self, x: int, y: int) -> None:
        """
        对应 C++ 中的 void setPos(int x, int y)
        设置对象在绘制坐标系中的位置
        
        Args:
            x: X坐标
            y: Y坐标
        """
        self._x = x
        self._y = y
    
    @property
    def x(self) -> int:
        """获取X坐标"""
        return self._x
    
    @property
    def y(self) -> int:
        """获取Y坐标"""
        return self._y
    
    def get_pos(self) -> tuple[int, int]:
        """
        获取位置坐标
        
        Returns:
            (x, y) 坐标元组
        """
        return (self._x, self._y)
    
    def __str__(self) -> str:
        """字符串表示"""
        return f"Drawable(x={self._x}, y={self._y})"
    
    def __repr__(self) -> str:
        """详细字符串表示"""
        return f"Drawable(x={self._x}, y={self._y})" 