"""
Core Logger Classes - 核心日志类

对应文件: loggertypes.h (LoggedManager和Logged类)
功能: 提供日志系统的核心基础设施

主要类:
- LoggedManager: 日志管理器，跟踪所有已记录项目
- Logged: 日志基类，为对象提供唯一ID和名称
"""

from typing import List, TYPE_CHECKING

if TYPE_CHECKING:
    pass


class LoggedManager:
    """
    日志管理器 - 对应 loggertypes.h 中的 LoggedManager 类
    
    跟踪所有已记录的项目，以便稍后进行 ID->名称映射
    """
    
    def __init__(self):
        """对应 C++ 构造函数 LoggedManager()"""
        self._idmap: List['Logged'] = []
    
    def add_logged(self, logged: 'Logged') -> None:
        """对应 C++ 中的 LoggedManager::add_logged()"""
        self._idmap.append(logged)
    
    def dump_idmap(self) -> None:
        """对应 C++ 中的 LoggedManager::dump_idmap() - 写入idmap.txt文件"""
        try:
            with open("idmap.txt", "w") as fout:
                for logged in self._idmap:
                    fout.write(f"{logged.get_id()} {logged._name}\n")
        except IOError as e:
            print(f"Warning: Failed to write idmap.txt: {e}")


class Logged:
    """
    日志基类 - 对应 loggertypes.h 中的 Logged 类
    
    为对象提供唯一ID和名称，所有需要记录的对象都应继承此类
    这是C++版本的精准复现
    """
    
    # 对应 C++ 静态成员变量 (注意在C++中是uint32_t)
    LASTIDNUM: int = 0
    _logged_manager: LoggedManager = LoggedManager()
    
    # 对应 C++ 中的 id_t 类型 (typedef uint32_t id_t)
    IdType = int
    
    def __init__(self, name: str):
        """对应 C++ 构造函数 Logged(const string& name)"""
        self._name = name
        self._log_id = Logged.LASTIDNUM
        Logged.LASTIDNUM += 1
        Logged._logged_manager.add_logged(self)
    
    def __del__(self):
        """对应 C++ 虚析构函数"""
        pass
    
    def setName(self, name: str) -> None:
        """对应 C++ 中的 Logged::setName() - 注意C++使用驼峰命名"""
        self._name = name
    
    def str(self) -> str:
        """对应 C++ 中的 Logged::str()"""
        return self._name
    
    def get_id(self) -> IdType:
        """对应 C++ 中的 Logged::get_id()"""
        return self._log_id
    
    def set_id(self, id_val: IdType) -> None:
        """对应 C++ 中的 Logged::set_id()"""
        assert id_val < Logged.LASTIDNUM, "ID must be less than LASTIDNUM"
        self._log_id = id_val
    
    @classmethod
    def dump_idmap(cls) -> None:
        """对应 C++ 中的 Logged::dump_idmap() - 静态方法"""
        cls._logged_manager.dump_idmap()