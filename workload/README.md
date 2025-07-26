# Workload模块拆分说明

## 概述

原始的 `workload.py` 文件过于庞大（1400行），包含了太多不同的职责。为了更好的代码组织和维护性，我们将其拆分为以下几个模块：

## 文件结构

### 1. `workload_base.py` - 基础工作负载类
**对应C++函数签名：**
- `Workload::Workload(std::string run_name, Sys* generator, std::string name, int TOTAL_PASS, int total_rows, int stat_row, std::string path, bool seprate_log)` - 构造函数
- `Workload::~Workload()` - 析构函数
- `void Workload::call(EventType event, CallData* data)` - 事件处理
- `void Workload::fire()` - 触发执行
- `void Workload::check_for_sim_end()` - 检查仿真结束
- `static int Workload::get_layer_numbers(std::string workload_input)` - 获取层数

**功能：**
- 包含 `Workload` 类的基本结构
- 构造函数和析构函数
- 核心事件处理方法
- 仿真结束检查逻辑

### 2. `workload_parser.py` - 工作负载解析器
**对应C++函数签名：**
- `bool Workload::initialize_workload(std::string name)` - 初始化工作负载
- `ParallelismPolicy Workload::decode_parallelsim(std::string parallelism)` - 解码并行策略
- `std::map<std::string, std::vector<bool>> Workload::decode_involved_dimensions(ParallelismPolicy policy, int model_parallel_npu_group)` - 解码涉及维度

**功能：**
- 解析工作负载文件
- 解码并行策略字符串
- 解析通信类型和组类型
- 创建和初始化层对象

### 3. `workload_iterators.py` - 工作负载迭代器
**对应C++函数签名：**
- `void Workload::iterate_micro_benchmark()` - 微基准测试迭代
- `void Workload::iterate_data_parallel()` - 数据并行迭代
- `void Workload::iterate_hybrid_parallel_Transformer()` - Transformer混合并行迭代
- `void Workload::iterate_hybrid_parallel_Transformer_fwd_in_bckwd()` - Transformer前向反向混合并行迭代
- `void Workload::iterate_hybrid_parallel_DLRM()` - DLRM混合并行迭代
- `void Workload::iterate_model_parallel()` - 模型并行迭代
- `void Workload::iterate_hybrid_parallel_data_model()` - 数据模型混合并行迭代
- `void Workload::iterate_hybrid_parallel_model_data()` - 模型数据混合并行迭代
- `void Workload::iterate_distributed_inference()` - 分布式推理迭代
- `void Workload::iterate_hybrid_parallel_customized()` - 自定义混合并行迭代

**功能：**
- 实现各种并行策略的迭代逻辑
- 处理前向传播、权重梯度、输入梯度等不同阶段
- 管理层的执行顺序和状态转换

### 4. `workload_reporting.py` - 工作负载报告器
**对应C++函数签名：**
- `void Workload::report()` - 生成报告

**功能：**
- 生成工作负载执行报告
- 收集统计信息
- 处理维度利用率报告
- 调用网络接口的报告方法

### 5. `workload.py` - 简化入口点
**功能：**
- 为了向后兼容，提供简化的入口点
- 直接导出 `Workload` 类

### 6. `__init__.py` - 模块初始化
**功能：**
- 定义模块的公共接口
- 导出所有相关的类

## 使用方式

### 原有代码兼容性
```python
# 原有的导入方式仍然有效
from workload.workload import Workload

# 创建Workload实例
workload = Workload(run_name, generator, name, total_pass, total_rows, stat_row, path, separate_log)
```

### 新的模块化导入
```python
# 可以直接导入具体的组件
from workload.workload_base import Workload
from workload.workload_parser import WorkloadParser
from workload.workload_iterators import WorkloadIterators
from workload.workload_reporting import WorkloadReporting
```

## 优势

1. **代码组织更清晰**：每个文件都有明确的职责
2. **维护性更好**：修改特定功能时只需要关注对应的文件
3. **可读性更强**：文件大小合理，更容易理解
4. **可扩展性更好**：新增功能时可以轻松添加新的模块
5. **向后兼容**：原有代码无需修改即可使用

## 注意事项

- 所有功能保持与原始C++版本的一致性
- 每个函数都标注了对应的C++函数签名
- 模块间的依赖关系清晰明确
- 保持了原有的接口和功能 