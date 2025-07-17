# AkShare Redis 分布式缓存系统

## 概述

这是一个基于 Redis 的分布式缓存装饰器，专门为解决 Apache Airflow 等多任务环境中的缓存共享问题而设计。与标准的 `@lru_cache` 不同，这个缓存系统可以在不同的进程和任务之间共享缓存数据。

## 核心特性

- ✅ **分布式缓存**: 基于 Redis，支持多进程、多任务共享缓存
- ✅ **无缝替换**: 可以直接替换现有的 `@lru_cache` 装饰器
- ✅ **自动序列化**: 支持 pandas DataFrame、字典、列表等常见数据类型
- ✅ **灵活配置**: 支持环境变量配置，适应不同部署环境
- ✅ **缓存过期**: 支持设置缓存过期时间
- ✅ **集群支持**: 支持 Redis Cluster
- ✅ **向后兼容**: 当 Redis 不可用时自动降级到标准 lru_cache

## 安装依赖

```bash
pip install -r requirements-redis-cache.txt
```

或者单独安装：

```bash
pip install redis>=6.0.0
```

## 快速开始

### 1. 基本使用

```python
from akshare.utils.redis_cache import lru_cache

# 最简单的使用方式
@lru_cache()
def get_stock_data(symbol):
    # 耗时的数据获取操作
    return expensive_api_call(symbol)
```

### 2. 环境变量配置 (推荐)

```bash
# 设置环境变量
export REDIS_URL="redis://localhost:6379"
export AKSHARE_CACHE_PREFIX="akshare_prod"
```

```python
# 代码中直接使用，会自动读取环境变量
@lru_cache()
def get_market_data():
    return fetch_market_data()
```

### 3. 自定义配置

```python
@lru_cache(
    redis_url='redis://your-redis-server:6379',
    prefix='akshare',
    max_age=24 * 60 * 60,  # 24小时缓存
)
def get_historical_data(symbol, days):
    return fetch_historical_data(symbol, days)
```

## 详细配置选项

### 装饰器参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `redis_url` | str | 环境变量 REDIS_URL | Redis 连接字符串 |
| `prefix` | str | 环境变量 AKSHARE_CACHE_PREFIX 或 'akshare' | 缓存键前缀 |
| `max_age` | int | 86400 (24小时) | 缓存过期时间(秒) |
| `serialize_method` | str | 'pickle' | 序列化方法 ('pickle',) |
| `key_version` | str | 'v1' | 缓存键版本，用于缓存失效 |

### 环境变量

| 变量名 | 说明 | 示例 |
|--------|------|------|
| `REDIS_URL` | Redis 连接字符串 | `redis://localhost:6379` |
| `AKSHARE_CACHE_PREFIX` | 缓存键前缀 | `akshare_prod` |

## Redis 连接字符串格式

### 单机 Redis
```
redis://localhost:6379
redis://username:password@localhost:6379/0
redis://localhost:6379/0?ssl=true
```

### Redis Cluster
```
redis://node1:6379,node2:6379,node3:6379
```

## 使用场景和最佳实践

### 1. Airflow 任务场景

```python
from akshare.utils.redis_cache import lru_cache

# 配置生产环境缓存
@lru_cache(
    prefix='airflow_akshare',
    max_age=4 * 60 * 60  # 4小时缓存
)
def get_sector_mapping():
    """获取行业映射 - 在多个 Airflow 任务间共享缓存"""
    return fetch_sector_data()

# Task 1
def task_process_stocks():
    mapping = get_sector_mapping()  # 第一次调用，从API获取
    # 处理股票数据
    
# Task 2  
def task_generate_report():
    mapping = get_sector_mapping()  # 从缓存获取，不重复调用API
    # 生成报告
```

### 2. 不同环境的配置

```python
import os

def get_cache_config():
    env = os.getenv('ENV', 'dev')
    
    configs = {
        'prod': {
            'redis_url': 'redis://prod-cluster:6379',
            'prefix': 'akshare_prod',
            'max_age': 4 * 60 * 60,  # 4小时
        },
        'staging': {
            'redis_url': 'redis://staging:6379', 
            'prefix': 'akshare_staging',
            'max_age': 2 * 60 * 60,  # 2小时
        },
        'dev': {
            'redis_url': 'redis://localhost:6379',
            'prefix': 'akshare_dev', 
            'max_age': 30 * 60,  # 30分钟
        }
    }
    
    return configs.get(env, configs['dev'])

# 使用环境相关配置
@lru_cache(**get_cache_config())
def get_data():
    return expensive_operation()
```

### 3. 改造现有函数

```python
from akshare.utils.redis_cache import cached_function

# 原有函数
def original_function(param1, param2):
    return expensive_operation(param1, param2)

# 添加缓存
cached_function_with_cache = cached_function(
    original_function,
    max_age=60 * 60  # 1小时缓存
)
```

## 缓存管理

### 查看缓存信息
```python
@lru_cache()
def my_function():
    return data

# 查看缓存配置
print(my_function.cache_info())
```

### 清除缓存
```python
# 清除特定函数的所有缓存
my_function.cache_clear()

# 清除所有缓存
from akshare.utils.redis_cache import clear_all_cache
clear_all_cache()

# 清除特定前缀的缓存
clear_all_cache(prefix='my_app')
```

## 性能优化建议

### 1. 合理设置缓存时间
- **静态数据** (如行业分类): 24小时或更长
- **准实时数据** (如股票价格): 1-5分钟  
- **历史数据**: 4-12小时
- **配置数据**: 1-24小时

### 2. 使用有意义的前缀
```python
# 好的做法
@lru_cache(prefix='stock_basic_info')
def get_stock_info(): ...

@lru_cache(prefix='market_data')  
def get_market_data(): ...

# 避免
@lru_cache(prefix='data')  # 太通用
```

### 3. 监控缓存使用
- 定期检查 Redis 内存使用
- 监控缓存命中率
- 设置合理的 Redis 内存淘汰策略

## 故障处理

### 1. Redis 不可用时的降级
当 Redis 服务不可用时，装饰器会自动降级到标准的 `lru_cache`，确保程序正常运行。

### 2. 序列化错误处理
如果某些对象无法序列化，会记录警告并跳过缓存，直接执行函数。

### 3. 网络超时处理
Redis 操作设置了合理的超时时间，避免影响主程序性能。

## 与现有代码的集成

### 替换标准 lru_cache

**之前:**
```python
from functools import lru_cache

@lru_cache()
def get_data():
    return expensive_operation()
```

**之后:**
```python
from akshare.utils.redis_cache import lru_cache

@lru_cache()  # 完全相同的接口
def get_data():
    return expensive_operation()
```

### 渐进式迁移

你可以逐步迁移现有函数：

```python
# 1. 先导入新的缓存
from akshare.utils.redis_cache import lru_cache as redis_lru_cache

# 2. 测试特定函数
@redis_lru_cache(max_age=60*60)
def test_function():
    return data

# 3. 确认无问题后，全面替换
from akshare.utils.redis_cache import lru_cache
```

## 故障排除

### 常见问题

1. **Redis 连接失败**
   - 检查 Redis 服务是否运行
   - 验证连接字符串格式
   - 检查网络连通性和防火墙设置

2. **序列化错误**
   - 某些自定义对象可能无法序列化
   - 或者修改函数返回更简单的数据结构

3. **内存使用过高**
   - 调整 `max_age` 减少缓存时间
   - 设置 Redis 内存淘汰策略
   - 监控并清理不必要的缓存

### 调试模式

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# 这会输出详细的缓存操作日志
@lru_cache()
def debug_function():
    return data
```

## 示例代码

完整的使用示例请参考 `examples/redis_cache_demo.py`。

## 注意事项

1. **数据一致性**: 缓存可能导致数据延迟，请根据业务需求设置合理的过期时间
2. **内存管理**: 监控 Redis 内存使用，避免内存溢出
3. **网络依赖**: 确保 Redis 服务的高可用性
4. **版本兼容**: 当数据格式变化时，记得更新 `key_version` 参数
