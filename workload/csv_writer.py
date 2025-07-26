# CSV writer class - corresponds to CSVWriter.cc/CSVWriter.hh in SimAI 

import os
import pandas as pd
from typing import List, Tuple, Any


class CSVWriter:
    """严格复现C++ CSVWriter，支持精确单元格写入、首行插入、表头和多维数据对齐写入。"""
    def __init__(self, path: str, name: str):
        self.path = path
        self.name = name
        self.file_path = os.path.join(path, name)
        os.makedirs(path, exist_ok=True)
        self.df = None  # 用于缓存DataFrame
        self.initialized = False

    def __del__(self):
        self._save_and_close()

    def _save_and_close(self):
        if self.df is not None:
            self.df.to_csv(self.file_path, index=False)
            self.df = None
            self.initialized = False

    def initialize_csv(self, rows: int, cols: int):
        """
        初始化CSV文件（只清空文件，不写表头，行为与C++一致）
        """
        # 只清空文件
        open(self.file_path, 'w').close()
        self.df = pd.DataFrame(index=range(rows), columns=range(cols))
        self.initialized = True

    def write_cell(self, row: int, column: int, data: str):
        """
        精确写入某个单元格
        """
        if not self.initialized or self.df is None:
            # 尝试加载
            if os.path.exists(self.file_path):
                self.df = pd.read_csv(self.file_path, header=0)
                self.df.index = range(len(self.df))
                self.initialized = True
            else:
                print("CSV文件未初始化")
                return
        try:
            self.df.iat[row, column] = data
            self.df.to_csv(self.file_path, index=False)
        except Exception as e:
            print(f"写入单元格时出错: {e}")

    def write_line(self, data: str):
        """
        以追加方式写入一整行字符串（与C++一致）
        """
        with open(self.file_path, 'a', encoding='utf-8') as f:
            f.write(data + '\n')

    def write_res(self, data: str):
        """
        首行插入数据，后面跟原内容（与C++一致）
        """
        if not os.path.exists(self.file_path):
            with open(self.file_path, 'w', encoding='utf-8') as f:
                f.write(data + '\n')
            return
        with open(self.file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        with open(self.file_path, 'w', encoding='utf-8') as f:
            f.write(data + '\n')
            f.write(content)

    def finalize_csv(self, dims: List[List[Tuple[int, float]]]):
        """
        写入表头（时间、各维度util），并对齐多维数据（与C++一致）
        """
        # 生成表头
        dim_num = 1
        header = ["time (us)"] + [f"dim{dim_num+i} util" for i in range(len(dims))]
        # 对齐多维数据
        rows = []
        # 先找出每个维度的迭代器
        iters = [iter(dim) for dim in dims]
        finished = [False] * len(dims)
        while not all(finished):
            row = []
            time_val = None
            for i, it in enumerate(iters):
                try:
                    tick, value = next(it)
                    if i == 0:
                        time_val = tick
                        row.append(tick)
                    else:
                        # 检查tick一致性
                        if tick != time_val:
                            raise ValueError("tick不一致")
                except StopIteration:
                    finished[i] = True
                    if i == 0:
                        row.append('')
                    else:
                        row.append('')
                    continue
                if i == 0:
                    continue  # time已加
                row.append(value)
            if any(not f for f in finished):
                rows.append(row)
        df = pd.DataFrame(rows, columns=header)
        df.to_csv(self.file_path, index=False)
        self.df = df
        self.initialized = False

    def exists_test(self, name: str) -> bool:
        return os.path.exists(name) 