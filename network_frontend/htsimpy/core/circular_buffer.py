"""
CircularBuffer - 循环缓冲区实现

对应文件: circular_buffer.h
功能: 实现可调整大小的循环缓冲区，用作队列结构

主要类:
- CircularBuffer: 循环缓冲区，对应C++的CircularBuffer模板类

C++对应关系:
- CircularBuffer::push() -> CircularBuffer.push()
- CircularBuffer::pop() -> CircularBuffer.pop()
- CircularBuffer::pop_front() -> CircularBuffer.pop_front()
- CircularBuffer::back() -> CircularBuffer.back()
- CircularBuffer::empty() -> CircularBuffer.empty()
- CircularBuffer::size() -> CircularBuffer.size()
"""

from typing import TypeVar, Generic, List, Optional

T = TypeVar('T')


class CircularBuffer(Generic[T]):
    """
    循环缓冲区 - 对应 circular_buffer.h 中的 CircularBuffer 模板类
    
    一个可调整大小的循环缓冲区，用于替代List作为队列结构
    """
    
    def __init__(self, starting_size: int = 8):
        """
        对应 C++ 构造函数:
        CircularBuffer() 或 CircularBuffer(int starting_size)
        """
        self._count = 0
        self._next_push = 0
        self._next_pop = 0
        self._size = starting_size  # 初始大小，需要时会调整
        self._queue: List[Optional[T]] = [None] * self._size
    
    def push(self, item: T) -> None:
        """
        对应 C++ void push(T& item)
        在队尾添加元素
        """
        self._count += 1
        
        if self._count == self._size:
            # 需要扩容
            newsize = self._size * 2
            new_queue: List[Optional[T]] = [None] * newsize
            
            # 复制现有元素到新数组
            if self._next_push < self._next_pop:
                # 情况: 456789*123
                # NI *, NP 1
                # 复制 NP 到末尾的元素
                for i in range(self._next_pop, self._size):
                    new_queue[i - self._next_pop] = self._queue[i]
                # 复制开头到 NI 的元素
                for i in range(0, self._next_push):
                    new_queue[self._size - self._next_pop + i] = self._queue[i]
                self._next_pop = 0
                self._next_push = self._count - 1
            else:
                # 情况: 123456789*
                # 直接复制
                for i in range(self._next_pop, self._next_push):
                    new_queue[i] = self._queue[i]
            
            self._queue = new_queue
            self._size = newsize
        
        self._queue[self._next_push] = item
        self._next_push = (self._next_push + 1) % self._size
    
    def pop(self) -> T:
        """
        对应 C++ T& pop()
        从队首移除并返回元素
        """
        assert self._count > 0
        old_index = self._next_pop
        self._next_pop = (self._next_pop + 1) % self._size
        self._count -= 1
        return self._queue[old_index]  # type: ignore
    
    def pop_front(self) -> T:
        """
        对应 C++ T& pop_front()
        从队尾移除并返回元素
        """
        assert self._count > 0
        old_index = (self._next_push + self._size - 1) % self._size
        self._next_push = old_index
        self._count -= 1
        return self._queue[old_index]  # type: ignore
    
    def back(self) -> T:
        """
        对应 C++ T& back()
        返回下一个要被pop的元素（最老的元素）
        注意：C++中的注释说这个命名不好，更喜欢next_to_pop()
        """
        assert self._count > 0
        return self._queue[self._next_pop]  # type: ignore
    
    def next_to_pop(self) -> T:
        """
        对应 C++ T& next_to_pop()
        返回下一个要被pop的元素（最老的元素）
        """
        assert self._count > 0
        return self._queue[self._next_pop]  # type: ignore
    
    def empty(self) -> bool:
        """
        对应 C++ bool empty()
        检查缓冲区是否为空
        """
        return self._count == 0
    
    def size(self) -> int:
        """
        对应 C++ int size()
        返回缓冲区中的元素数量
        """
        return self._count
    
    def _validate(self) -> None:
        """
        对应 C++ void validate()
        验证内部状态的一致性（调试用）
        """
        assert self._count < self._size
        assert self._next_push < self._size
        assert self._next_pop < self._size
        
        if self._next_push > self._next_pop:
            assert self._next_push - self._next_pop == self._count
        elif self._next_push == self._next_pop:
            assert self._count == 0
        else:
            assert self._next_push + self._size - self._next_pop == self._count