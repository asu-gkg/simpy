# AstraMemoryAPI.py - corresponds to AstraMemoryAPI.hh in SimAI 

from abc import ABC, abstractmethod


class AstraMemoryAPI(ABC):
    """内存API抽象基类，对应C++中的AstraMemoryAPI"""
    
    @abstractmethod
    def mem_read(self, size: int) -> int:
        """
        内存读取
        
        Args:
            size: 读取的数据大小（字节，对应C++的uint64_t）
            
        Returns:
            读取延迟时间（对应C++的uint64_t）
        """
        pass
    
    @abstractmethod
    def mem_write(self, size: int) -> int:
        """
        内存写入
        
        Args:
            size: 写入的数据大小（字节，对应C++的uint64_t）
            
        Returns:
            写入延迟时间（对应C++的uint64_t）
        """
        pass
    
    @abstractmethod
    def npu_mem_read(self, size: int) -> int:
        """
        NPU内存读取
        
        Args:
            size: 读取的数据大小（字节，对应C++的uint64_t）
            
        Returns:
            读取延迟时间（对应C++的uint64_t）
        """
        pass
    
    @abstractmethod
    def npu_mem_write(self, size: int) -> int:
        """
        NPU内存写入
        
        Args:
            size: 写入的数据大小（字节，对应C++的uint64_t）
            
        Returns:
            写入延迟时间（对应C++的uint64_t）
        """
        pass
    
    @abstractmethod
    def nic_mem_read(self, size: int) -> int:
        """
        NIC内存读取
        
        Args:
            size: 读取的数据大小（字节，对应C++的uint64_t）
            
        Returns:
            读取延迟时间（对应C++的uint64_t）
        """
        pass
    
    @abstractmethod
    def nic_mem_write(self, size: int) -> int:
        """
        NIC内存写入
        
        Args:
            size: 写入的数据大小（字节，对应C++的uint64_t）
            
        Returns:
            写入延迟时间（对应C++的uint64_t）
        """
        pass