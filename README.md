# SimPy NS3 网络后端

基于NS3的高性能网络仿真后端，精准复现C++版本的AstraSimNetwork功能，支持现代Python包管理器uv。

## 🚀 特性

- **精准复现**：完全基于C++版本的AstraSimNetwork.cc实现
- **NS3支持**：支持NS3 Python绑定（pip wheel和源码编译）
- **现代工具**：使用uv进行快速包管理
- **线程安全**：复现C++版本的多线程哈希映射操作
- **完整日志**：集成MockNcclLog日志系统

## 📋 系统要求

- **操作系统**：Linux (Ubuntu 20.04+, CentOS 8+)
- **Python**：3.8+ 
- **内存**：建议8GB+
- **uv**：现代Python包管理器

## 🔧 安装指南

### 步骤1：安装uv

```bash
# 方法1：使用curl安装（推荐）
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.bashrc

# 方法2：使用pip安装
pip install uv

# 验证安装
uv --version
```

### 步骤2：克隆项目

```bash
git clone <your-repository-url>
cd simpy
```

### 步骤3：创建虚拟环境

```bash
# 使用uv创建虚拟环境（比python -m venv快10-100倍）
uv venv --python 3.11
# 或指定特定Python版本
# uv venv --python 3.8

# 激活环境
source .venv/bin/activate
```

### 步骤4：安装依赖

#### 选项A：基础安装（无NS3）

```bash
# 安装核心依赖
uv pip install -e .
```

#### 选项B：完整安装（包含NS3 pip wheel）

```bash
# 安装包含NS3的完整版本
uv pip install -e ".[ns3]"
```

#### 选项C：开发环境安装

```bash
# 安装开发工具和测试框架
uv pip install -e ".[dev,ns3]"
```

#### 选项D：从源码编译NS3（高级用户）

```bash
# 1. 安装NS3编译依赖
sudo apt update
sudo apt install -y g++ python3-dev cmake ninja-build git \
    libxml2-dev libsqlite3-dev qtbase5-dev libgsl-dev

# 2. 下载并编译NS3
wget https://www.nsnam.org/releases/ns-allinone-3.44.tar.bz2
tar -xjf ns-allinone-3.44.tar.bz2
cd ns-allinone-3.44
./build.py --enable-examples --enable-tests

# 3. 编译Python绑定
cd ns-3.44
./ns3 configure --enable-python-bindings
./ns3 build

# 4. 设置环境变量
export PYTHONPATH="$PWD/build/bindings/python:$PYTHONPATH"
export LD_LIBRARY_PATH="$PWD/build/lib:$LD_LIBRARY_PATH"
```

## 🎯 快速开始

### 基础测试

```python
# test_basic.py
from network_frontend.ns3.AstraSimNetwork import ASTRASimNetwork
from network_frontend.ns3.common import NS3_AVAILABLE

# 检查NS3是否可用
print(f"NS3 Available: {NS3_AVAILABLE}")

# 创建网络实例
network = ASTRASimNetwork(rank=0, npu_offset=0)
print(f"Network backend: {network.get_backend_type()}")

# 测试时间获取
time_spec = network.sim_get_time()
print(f"Simulation time: {time_spec.time_val}")
```

运行测试：

```bash
# 使用uv运行
uv run python test_basic.py

# 或激活环境后运行
source .venv/bin/activate
python test_basic.py
```

### 完整仿真示例

```python
# simulation_example.py
import sys
from network_frontend.ns3.AstraSimNetwork import main

# 模拟命令行参数
sys.argv = [
    'simulation_example.py',
    '-w', 'examples/workload_analytical.txt',
    '-n', 'examples/busbw.yaml', 
    '-c', 'examples/network_config.conf'
]

# 运行主函数
if __name__ == "__main__":
    exit_code = main()
    print(f"Simulation completed with exit code: {exit_code}")
```

## 🔄 开发工作流

### 代码格式化

```bash
# 使用uv运行格式化工具
uv run black simpy/ system/ workload/ network_frontend/
uv run isort simpy/ system/ workload/ network_frontend/
```

### 类型检查

```bash
# 运行MyPy类型检查
uv run mypy simpy/ system/ workload/ network_frontend/
```

### 运行测试

```bash
# 运行所有测试
uv run pytest

# 运行特定测试
uv run pytest tests/test_ns3_backend.py

# 运行不需要NS3的测试
uv run pytest -m "not ns3"

# 运行需要NS3的测试
uv run pytest -m "ns3"

# 生成覆盖率报告
uv run pytest --cov-report=html
```

## 📚 NS3集成说明

### 支持的NS3版本

- **NS3 3.37+**：推荐使用pip wheel安装
- **NS3 3.44**：最新版本，完整功能支持

### NS3 Python绑定配置

项目支持多种NS3配置方式：

1. **Pip Wheel安装**（推荐）：
   ```bash
   uv pip install ns3>=3.37
   ```

2. **源码编译**：
   ```bash
   # 在ns-3目录下
   ./ns3 configure --enable-python-bindings
   ./ns3 build
   ```

3. **Docker环境**：
   ```bash
   # 使用预配置的NS3 Docker镜像
   docker pull hamelik/ns3.26libdependencies:first
   ```

### 环境变量配置

```bash
# 添加到 ~/.bashrc 或 ~/.zshrc
export NS3_HOME="/path/to/ns-allinone-3.44/ns-3.44"
export PYTHONPATH="$NS3_HOME/build/bindings/python:$PYTHONPATH"
export LD_LIBRARY_PATH="$NS3_HOME/build/lib:$LD_LIBRARY_PATH"
```

## ⚡ uv优势

使用uv相比传统pip的优势：

- **速度**：安装速度提升10-100倍
- **缓存**：智能依赖缓存
- **兼容性**：完全兼容pip生态
- **虚拟环境**：内置虚拟环境管理
- **解析**：更快的依赖解析

### uv常用命令

```bash
# 环境管理
uv venv                    # 创建虚拟环境
uv venv --python 3.11     # 指定Python版本

# 包管理
uv pip install package    # 安装包
uv pip install -r req.txt # 从requirements安装
uv pip install -e .       # 开发模式安装
uv pip list               # 列出已安装包
uv pip freeze             # 冻结依赖

# 运行脚本
uv run python script.py   # 在虚拟环境中运行
uv run pytest            # 运行测试
```

## 🐛 故障排除

### NS3导入错误

```bash
# 错误：ImportError: No module named 'ns'
# 解决方案1：检查NS3安装
python -c "import ns; print('NS3 OK')"

# 解决方案2：使用pip wheel
uv pip install ns3

# 解决方案3：设置PYTHONPATH
export PYTHONPATH="/path/to/ns3/build/bindings/python:$PYTHONPATH"
```

### 编译错误

```bash
# 错误：找不到NS3头文件
# 解决方案：安装开发包
sudo apt install libns3-dev

# 错误：cppyy编译失败
# 解决方案：安装编译工具
sudo apt install build-essential cmake
```

### 性能优化

```bash
# 设置OpenBLAS线程数（避免cppyy多线程冲突）
export OPENBLAS_NUM_THREADS=1

# 设置NS3日志级别
export NS_LOG="*=level_error"
```

## 🔍 核心功能对比

| 功能 | C++版本 | Python版本 | 状态 |
|------|---------|-------------|------|
| sim_send | ✅ | ✅ | 完全复现 |
| sim_recv | ✅ | ✅ | 完全复现 |
| MockNcclLog | ✅ | ✅ | 完全复现 |
| 线程安全 | ✅ | ✅ | RLock实现 |
| NS3集成 | ✅ | ✅ | Cppyy绑定 |
| 哈希映射 | ✅ | ✅ | Dict实现 |

## 📄 许可证

Apache License 2.0 - 详见 [LICENSE](LICENSE) 文件

## 🤝 贡献

欢迎提交Issue和Pull Request！

### 开发环境设置

```bash
# 1. Fork和克隆项目
git clone <your-fork-url>
cd simpy

# 2. 安装开发环境
uv venv --python 3.11
source .venv/bin/activate
uv pip install -e ".[dev,ns3]"

# 3. 安装pre-commit hooks
uv run pre-commit install

# 4. 运行测试确保环境正常
uv run pytest
```

## 📞 支持

- **文档**：[在线文档](https://simpy-ns3.readthedocs.io)
- **Issues**：[GitHub Issues](https://github.com/your-org/simpy-ns3/issues)
- **讨论**：[GitHub Discussions](https://github.com/your-org/simpy-ns3/discussions)

---

⭐ 如果这个项目对你有帮助，请给个Star！ 