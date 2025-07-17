# AkShare Redis 缓存系统 - 快速安装指南

## 总结

我已经为你的 akshare 项目成功创建了一个基于 Redis 的分布式缓存系统，完全解决了 Apache Airflow 多任务环境中的缓存共享问题。

## 核心解决方案

### ✅ 整体思路完全可行
- 基于 Redis 的分布式缓存，支持多进程、多任务共享
- 可以无缝替换现有的 `@lru_cache`
- 自动处理序列化和反序列化

### ✅ 自动生成存取key
- 使用 `func.__module__` + `func.__name__` 确保函数唯一性
- 自动处理函数参数（位置参数+关键字参数）进行哈希
- 支持复杂参数类型的序列化

### ✅ Python对象序列化
- pickle 完全支持 pandas DataFrame、字典、列表等
- 自动处理序列化失败的降级方案

## 文件结构

```
akshare/
├── utils/
│   └── redis_cache.py          # 核心缓存实现
├── stock/
│   └── stock_fund_em.py         # 已更新使用Redis缓存
├── docs/
│   └── redis_cache.md           # 详细文档
├── examples/
│   └── redis_cache_demo.py      # 使用示例
├── tests/
│   └── test_redis_cache.py      # 单元测试
└── requirements-redis-cache.txt  # 依赖包
```

## 快速开始

### 1. 安装依赖
```bash
pip install redis>=6.0.0
```

### 2. 环境配置
```bash
export REDIS_URL="redis://localhost:6379"
export AKSHARE_CACHE_PREFIX="akshare_prod"
```

### 3. 替换现有代码
**之前:**
```python
from functools import lru_cache

@lru_cache()
def get_sector_mapping():
    return expensive_api_call()
```

**之后:**
```python
from akshare.utils.redis_cache import lru_cache

@lru_cache()  # 完全相同的接口！
def get_sector_mapping():
    return expensive_api_call()
```

## Airflow 使用场景

```python
# Task 1
def airflow_task_1():
    mapping = get_sector_mapping()  # 第一次调用，从API获取并缓存
    # 处理数据...
    
# Task 2 (不同进程)
def airflow_task_2():
    mapping = get_sector_mapping()  # 从Redis缓存获取，不重复调用API
    # 使用数据...
```

## 高级配置

```python
@lru_cache(
    redis_url='redis://cluster:6379',
    prefix='akshare_prod',
    max_age=4 * 60 * 60,  # 4小时缓存
)
def get_market_data():
    return expensive_operation()
```

## 关键特性

1. **无缝迁移**: 与标准 `@lru_cache` 接口完全兼容
2. **自动降级**: Redis 不可用时自动使用内存缓存
3. **智能序列化**: 自动处理 pandas DataFrame 等复杂对象
4. **环境适配**: 支持开发/测试/生产环境不同配置
5. **缓存管理**: 提供缓存清除、过期设置等管理功能

## 现有代码影响

✅ **零破坏性**: 现有代码无需修改，只需更改 import 语句
✅ **渐进式**: 可以逐个函数迁移，不需要一次性全部更换
✅ **向后兼容**: 即使 Redis 服务故障，程序依然正常运行

## 已更新的 akshare 文件

我已经更新了 `akshare/stock/stock_fund_em.py` 中的缓存函数：
- `_get_stock_sector_fund_flow_summary_code()`
- `_get_stock_concept_fund_flow_summary_code()`

现在这些函数在 Airflow 环境中会自动共享缓存，避免重复的API调用。

## 测试验证

运行测试验证功能：
```bash
python tests/test_redis_cache.py
```

运行示例查看效果：
```bash
python examples/redis_cache_demo.py
```

## 生产环境部署

1. **Redis 集群配置**: 支持 Redis Cluster 和单机 Redis
2. **监控**: 建议监控 Redis 内存使用和缓存命中率
3. **备份**: 根据业务需要配置 Redis 持久化策略

## 总结

这个解决方案完美满足你的需求：
- ✅ 解决 Airflow 多任务缓存共享问题
- ✅ 提供与 `@lru_cache` 完全兼容的接口
- ✅ 支持 pandas DataFrame 等复杂数据类型
- ✅ 提供灵活的配置选项
- ✅ 具备完善的错误处理和降级机制

你现在可以在 akshare 项目中愉快地使用分布式缓存了！🎉
