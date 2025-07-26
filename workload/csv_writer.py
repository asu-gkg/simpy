# CSV writer class - corresponds to CSVWriter.cc/CSVWriter.hh in SimAI 

import os
import csv
from typing import List, Tuple, Any


class CSVWriter:
    """CSV写入器类 - 对应C++版本的CSVWriter类"""
    
    def __init__(self, path: str, name: str):
        """
        初始化CSV写入器
        
        Args:
            path: 文件路径
            name: 文件名
        """
        self.path = path
        self.name = name
        self.file_path = os.path.join(path, name)
        self.file = None
        self.writer = None
        self.initialized = False
        
        # 确保目录存在
        os.makedirs(path, exist_ok=True)
    
    def __del__(self):
        """析构函数"""
        if self.file and not self.file.closed:
            self.file.close()
    
    def initialize_csv(self, rows: int, cols: int):
        """
        初始化CSV文件
        
        Args:
            rows: 行数
            cols: 列数
        """
        try:
            self.file = open(self.file_path, 'w', newline='', encoding='utf-8')
            self.writer = csv.writer(self.file)
            self.initialized = True
            
            # 写入表头
            header = [f"Col_{i}" for i in range(cols)]
            self.writer.writerow(header)
            
        except Exception as e:
            print(f"初始化CSV文件时出错: {e}")
            self.initialized = False
    
    def write_cell(self, row: int, column: int, data: str):
        """
        写入单元格数据
        
        Args:
            row: 行号
            column: 列号
            data: 数据
        """
        if not self.initialized:
            print("CSV文件未初始化")
            return
        
        try:
            # 这里需要实现更复杂的逻辑来写入特定单元格
            # 由于CSV是顺序写入的，需要特殊处理
            # 暂时使用简单的实现
            self.writer.writerow([f"Row_{row}_Col_{column}: {data}"])
        except Exception as e:
            print(f"写入单元格时出错: {e}")
    
    def write_line(self, data: str):
        """
        写入一行数据
        
        Args:
            data: 行数据
        """
        if not self.initialized:
            print("CSV文件未初始化")
            return
        
        try:
            self.writer.writerow([data])
        except Exception as e:
            print(f"写入行时出错: {e}")
    
    def write_res(self, data: str):
        """
        写入结果数据
        
        Args:
            data: 结果数据
        """
        if not self.initialized:
            print("CSV文件未初始化")
            return
        
        try:
            self.writer.writerow([data])
        except Exception as e:
            print(f"写入结果时出错: {e}")
    
    def finalize_csv(self, dims: List[List[Tuple[int, float]]]):
        """
        完成CSV文件写入
        
        Args:
            dims: 维度数据列表
        """
        if not self.initialized:
            print("CSV文件未初始化")
            return
        
        try:
            # 写入维度数据
            for dim_list in dims:
                row_data = []
                for tick, value in dim_list:
                    row_data.append(f"{tick}:{value}")
                self.writer.writerow(row_data)
            
            # 关闭文件
            if self.file and not self.file.closed:
                self.file.close()
                self.initialized = False
                
        except Exception as e:
            print(f"完成CSV文件时出错: {e}")
    
    def exists_test(self, name: str) -> bool:
        """
        检查文件是否存在
        
        Args:
            name: 文件名
            
        Returns:
            文件是否存在
        """
        return os.path.exists(name) 